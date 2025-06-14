import cv2
import numpy as np
import rasterio
from ultralytics import YOLO
import os
import json
from typing import Dict, List, Tuple, Optional
import logging
import torch
from datetime import datetime
import gc
import psutil

from .gpu_detector import gpu_detector
from .constants import *
from .config import settings

logger = logging.getLogger(__name__)

class ZeytinAnalizci:
    def __init__(self):
        self.yolo_model = None
        self.current_device = "cpu"
        self.analysis_mode = "cpu"
        self.analysis_start_time = None
        
    def set_analysis_mode(self, mode: str = "cpu"):
        """Analiz modunu ayarla"""
        self.analysis_mode = mode.lower()
        self.current_device = gpu_detector.get_optimal_device(self.analysis_mode)
        logger.info(f"Analiz modu ayarlandı: {self.analysis_mode}, cihaz: {self.current_device}")
    
    def load_yolo_model(self, model_path: str = None):
        """YOLOv8 modelini yükle"""
        if model_path is None:
            model_path = settings.YOLO_MODEL_PATH
        
        try:
            # Önceki modeli temizle
            if self.yolo_model is not None:
                del self.yolo_model
                if self.current_device == "cuda":
                    gpu_detector.clear_gpu_cache()
                gc.collect()
            
            # Model dosyası kontrolü
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Model dosyası bulunamadı: {model_path}")
            
            # Modeli yükle
            self.yolo_model = YOLO(model_path)
            
            # Cihaza taşı
            if self.current_device == "cuda" and gpu_detector.gpu_available:
                self.yolo_model.to('cuda')
                logger.info(f"YOLOv8 modeli GPU'ya yüklendi: {gpu_detector.gpu_info.get('device_name', 'Bilinmeyen')}")
            else:
                self.yolo_model.to('cpu')
                logger.info("YOLOv8 modeli CPU'ya yüklendi")
                
        except Exception as e:
            logger.error(f"YOLOv8 model yükleme hatası: {e}")
            # CPU'ya fallback
            if self.current_device == "cuda":
                logger.warning("GPU'dan CPU'ya geçiliyor")
                self.current_device = "cpu"
                self.analysis_mode = "cpu"
                try:
                    self.yolo_model = YOLO(model_path)
                    self.yolo_model.to('cpu')
                    logger.info("YOLOv8 modeli CPU'ya yüklendi (fallback)")
                except Exception as e2:
                    logger.error(f"CPU fallback da başarısız: {e2}")
                    self.yolo_model = None
                    raise e2
    
    async def analiz_yap(self, yukleme_klasoru: str, analiz_klasoru: str, log_yolu: str, 
                        analiz_modu: str = "cpu") -> Dict:
        """Ana analiz fonksiyonu"""
        
        self.analysis_start_time = datetime.now()
        
        # Analiz modunu ayarla
        self.set_analysis_mode(analiz_modu)
        
        # Modeli yükle
        self.load_yolo_model()
        
        sonuclar = {
            'toplam_agac': 0,
            'toplam_zeytin': 0,
            'tahmini_zeytin_miktari': 0.0,
            'ndvi_ortalama': 0.0,
            'gndvi_ortalama': 0.0,
            'ndre_ortalama': 0.0,
            'saglik_durumu': '',
            'agac_cap_ortalama': 0.0,
            'detaylar': [],
            'analiz_modu': self.analysis_mode,
            'kullanilan_cihaz': self.current_device,
            'gpu_durumu': gpu_detector.get_gpu_status(),
            'sistem_durumu': self._get_system_status()
        }
        
        try:
            # Analiz başlangıcını logla
            self._log_yazdir(log_yolu, f"Analiz başlatıldı - Mod: {self.analysis_mode}, Cihaz: {self.current_device}")
            
            # Dosyaları listele
            dosyalar = os.listdir(yukleme_klasoru)
            rgb_dosyalar = [f for f in dosyalar if f.lower().endswith(tuple(ALLOWED_IMAGE_EXTENSIONS))]
            multispektral_dosyalar = [f for f in dosyalar if f.lower().endswith(tuple(ALLOWED_MULTISPECTRAL_EXTENSIONS))]
            
            self._log_yazdir(log_yolu, f"RGB dosya sayısı: {len(rgb_dosyalar)}")
            self._log_yazdir(log_yolu, f"Multispektral dosya sayısı: {len(multispektral_dosyalar)}")
            
            # RGB analizi
            if rgb_dosyalar and self.yolo_model:
                rgb_sonuclari = await self._rgb_analiz(yukleme_klasoru, rgb_dosyalar, analiz_klasoru, log_yolu)
                sonuclar.update(rgb_sonuclari)
            
            # Multispektral analizi
            if multispektral_dosyalar:
                multispektral_sonuclari = await self._multispektral_analiz(yukleme_klasoru, multispektral_dosyalar, analiz_klasoru, log_yolu)
                sonuclar.update(multispektral_sonuclari)
            
            # Sağlık değerlendirmesi
            sonuclar['saglik_durumu'] = self._saglik_degerlendirmesi(sonuclar)
            
            # GeoJSON oluştur
            await self._geojson_olustur(sonuclar, analiz_klasoru)
            
            # Analiz süresini hesapla
            analiz_suresi = self._get_analysis_time()
            sonuclar['analiz_suresi'] = analiz_suresi
            
            self._log_yazdir(log_yolu, f"Analiz tamamlandı - Süre: {analiz_suresi:.2f} saniye")
            
        except Exception as e:
            self._log_yazdir(log_yolu, f"Analiz hatası: {str(e)}")
            # GPU belleğini temizle
            if self.current_device == "cuda":
                gpu_detector.clear_gpu_cache()
            # CPU belleğini temizle
            self._cleanup_memory()
            raise e
        finally:
            # Temizlik
            if self.current_device == "cuda":
                gpu_detector.clear_gpu_cache()
            self._cleanup_memory()
        
        return sonuclar
    
    async def _rgb_analiz(self, yukleme_klasoru: str, rgb_dosyalar: List[str], 
                         analiz_klasoru: str, log_yolu: str) -> Dict:
        """RGB analizi"""
        toplam_agac = 0
        toplam_zeytin = 0
        toplam_cap = 0.0
        detaylar = []
        
        self._log_yazdir(log_yolu, f"RGB analizi başlatılıyor - Cihaz: {self.current_device}")
        
        for dosya_adi in rgb_dosyalar:
            try:
                dosya_yolu = os.path.join(yukleme_klasoru, dosya_adi)
                gorsel = cv2.imread(dosya_yolu)
                
                if gorsel is None:
                    self._log_yazdir(log_yolu, f"Görsel okunamadı: {dosya_adi}")
                    continue
                
                # YOLOv8 tespiti
                start_time = datetime.now()
                
                if self.current_device == "cuda":
                    sonuclar = self.yolo_model(gorsel, device='cuda', conf=settings.CONFIDENCE_THRESHOLD)
                else:
                    sonuclar = self.yolo_model(gorsel, device='cpu', conf=settings.CONFIDENCE_THRESHOLD)
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                # Sonuçları işle
                agac_sayisi = 0
                zeytin_sayisi = 0
                cap_toplam = 0.0
                
                for result in sonuclar:
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            cls = int(box.cls[0])
                            conf = float(box.conf[0])
                            
                            if conf > settings.CONFIDENCE_THRESHOLD:
                                if cls == YOLO_TREE_CLASS:
                                    agac_sayisi += 1
                                    # Çap hesaplama
                                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                                    genislik = x2 - x1
                                    tahmini_cap = genislik * OLIVE_DIAMETER_COEFFICIENT
                                    cap_toplam += tahmini_cap
                                
                                elif cls == YOLO_OLIVE_CLASS:
                                    zeytin_sayisi += DEFAULT_OLIVES_PER_DETECTION
                
                # Görseli işaretle ve kaydet
                annotated_img = self._gorseli_isaretle(gorsel, sonuclar)
                cikti_yolu = os.path.join(analiz_klasoru, f"isretli_{dosya_adi}")
                cv2.imwrite(cikti_yolu, annotated_img)
                
                toplam_agac += agac_sayisi
                toplam_zeytin += zeytin_sayisi
                toplam_cap += cap_toplam
                
                detaylar.append({
                    'dosya': dosya_adi,
                    'agac_sayisi': agac_sayisi,
                    'zeytin_sayisi': zeytin_sayisi,
                    'ortalama_cap': cap_toplam / max(agac_sayisi, 1),
                    'isleme_suresi': processing_time,
                    'cihaz': self.current_device
                })
                
                self._log_yazdir(log_yolu, f"{dosya_adi}: {agac_sayisi} ağaç, {zeytin_sayisi} zeytin ({processing_time:.2f}s - {self.current_device.upper()})")
                
                # Bellek temizliği (her dosyadan sonra)
                if self.current_device == "cuda":
                    torch.cuda.empty_cache()
                
            except Exception as e:
                self._log_yazdir(log_yolu, f"{dosya_adi} analiz hatası: {str(e)}")
                continue
        
        # Tahmini zeytin miktarı
        tahmini_miktar = toplam_zeytin * DEFAULT_OLIVE_WEIGHT
        
        return {
            'toplam_agac': toplam_agac,
            'toplam_zeytin': toplam_zeytin,
            'tahmini_zeytin_miktari': tahmini_miktar,
            'agac_cap_ortalama': toplam_cap / max(toplam_agac, 1),
            'detaylar': detaylar
        }
    
    async def _multispektral_analiz(self, yukleme_klasoru: str, multispektral_dosyalar: List[str], 
                                   analiz_klasoru: str, log_yolu: str) -> Dict:
        """Multispektral analizi"""
        ndvi_toplam = 0.0
        gndvi_toplam = 0.0
        ndre_toplam = 0.0
        dosya_sayisi = 0
        
        self._log_yazdir(log_yolu, "Multispektral analizi başlatılıyor (CPU)")
        
        for dosya_adi in multispektral_dosyalar:
            try:
                dosya_yolu = os.path.join(yukleme_klasoru, dosya_adi)
                
                with rasterio.open(dosya_yolu) as src:
                    if src.count >= 4:
                        red = src.read(1).astype(float)
                        green = src.read(2).astype(float)
                        blue = src.read(3).astype(float)
                        nir = src.read(4).astype(float)
                        
                        # NDVI hesaplama
                        ndvi = np.where((nir + red) != 0, (nir - red) / (nir + red), 0)
                        
                        # GNDVI hesaplama
                        gndvi = np.where((nir + green) != 0, (nir - green) / (nir + green), 0)
                        
                        # NDRE hesaplama
                        if src.count >= 5:
                            red_edge = src.read(5).astype(float)
                            ndre = np.where((nir + red_edge) != 0, (nir - red_edge) / (nir + red_edge), 0)
                        else:
                            ndre = ndvi
                        
                        # Ortalama değerler
                        ndvi_ort = np.nanmean(ndvi)
                        gndvi_ort = np.nanmean(gndvi)
                        ndre_ort = np.nanmean(ndre)
                        
                        ndvi_toplam += ndvi_ort
                        gndvi_toplam += gndvi_ort
                        ndre_toplam += ndre_ort
                        dosya_sayisi += 1
                        
                        # NDVI görselini kaydet
                        ndvi_cikti = os.path.join(analiz_klasoru, f"ndvi_{dosya_adi}")
                        self._ndvi_gorseli_kaydet(ndvi, ndvi_cikti, src.profile)
                        
                        self._log_yazdir(log_yolu, f"{dosya_adi}: NDVI={ndvi_ort:.3f}, GNDVI={gndvi_ort:.3f}, NDRE={ndre_ort:.3f}")
                    
            except Exception as e:
                self._log_yazdir(log_yolu, f"{dosya_adi} multispektral analiz hatası: {str(e)}")
                continue
        
        if dosya_sayisi > 0:
            return {
                'ndvi_ortalama': ndvi_toplam / dosya_sayisi,
                'gndvi_ortalama': gndvi_toplam / dosya_sayisi,
                'ndre_ortalama': ndre_toplam / dosya_sayisi
            }
        else:
            return {
                'ndvi_ortalama': 0.0,
                'gndvi_ortalama': 0.0,
                'ndre_ortalama': 0.0
            }
    
    def _gorseli_isaretle(self, gorsel: np.ndarray, sonuclar) -> np.ndarray:
        """YOLO sonuçlarını görsele çiz"""
        annotated_img = gorsel.copy()
        
        for result in sonuclar:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].int().tolist()
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    
                    if conf > settings.CONFIDENCE_THRESHOLD:
                        # Sınıfa göre renk seç
                        color = (0, 255, 0) if cls == YOLO_TREE_CLASS else (0, 0, 255)
                        
                        # Dikdörtgen çiz
                        cv2.rectangle(annotated_img, (x1, y1), (x2, y2), color, 2)
                        
                        # Etiket ekle
                        label = f"Ağaç: {conf:.2f}" if cls == YOLO_TREE_CLASS else f"Zeytin: {conf:.2f}"
                        cv2.putText(annotated_img, label, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        
        return annotated_img
    
    def _ndvi_gorseli_kaydet(self, ndvi: np.ndarray, cikti_yolu: str, profile: dict):
        """NDVI görselini kaydet"""
        # NDVI'yi 0-255 aralığına normalize et
        ndvi_normalized = np.clip((ndvi + 1) * 127.5, 0, 255).astype(np.uint8)
        
        # Profili güncelle
        profile.update(dtype=rasterio.uint8, count=1)
        
        with rasterio.open(cikti_yolu, 'w', **profile) as dst:
            dst.write(ndvi_normalized, 1)
    
    def _saglik_degerlendirmesi(self, sonuclar: Dict) -> str:
        """NDVI değerine göre sağlık durumu"""
        ndvi = sonuclar.get('ndvi_ortalama', 0.0)
        
        if ndvi > NDVI_VERY_HEALTHY:
            return HEALTH_STATUS["very_healthy"]
        elif ndvi > NDVI_HEALTHY:
            return HEALTH_STATUS["healthy"]
        elif ndvi > NDVI_MODERATE_STRESS:
            return HEALTH_STATUS["moderate_stress"]
        elif ndvi > NDVI_STRESSED:
            return HEALTH_STATUS["stressed"]
        else:
            return HEALTH_STATUS["very_stressed"]
    
    async def _geojson_olustur(self, sonuclar: Dict, analiz_klasoru: str):
        """GeoJSON harita verisi oluştur"""
        geojson = {
            "type": "FeatureCollection",
            "features": []
        }
        
        # Örnek koordinatlar (gerçek projede GPS koordinatları kullanılacak)
        for i, detay in enumerate(sonuclar.get('detaylar', [])):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        DEFAULT_COORDINATES["longitude"] + i * DEFAULT_COORDINATES["coordinate_increment"],
                        DEFAULT_COORDINATES["latitude"] + i * DEFAULT_COORDINATES["coordinate_increment"]
                    ]
                },
                "properties": {
                    "dosya": detay['dosya'],
                    "agac_sayisi": detay['agac_sayisi'],
                    "zeytin_sayisi": detay['zeytin_sayisi'],
                    "ortalama_cap": detay['ortalama_cap'],
                    "ndvi": sonuclar.get('ndvi_ortalama', 0.0),
                    "saglik_durumu": sonuclar.get('saglik_durumu', ''),
                    "isleme_suresi": detay.get('isleme_suresi', 0),
                    "cihaz": detay.get('cihaz', 'cpu')
                }
            }
            geojson["features"].append(feature)
        
        # GeoJSON dosyasını kaydet
        geojson_yolu = os.path.join(analiz_klasoru, "geojson.json")
        with open(geojson_yolu, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        
        sonuclar['geojson_path'] = geojson_yolu
    
    def _log_yazdir(self, log_yolu: str, mesaj: str):
        """Log dosyasına mesaj yaz"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_yolu, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {mesaj}\n")
    
    def _get_analysis_time(self) -> float:
        """Analiz süresini hesapla"""
        if self.analysis_start_time:
            return (datetime.now() - self.analysis_start_time).total_seconds()
        return 0.0
    
    def _get_system_status(self) -> Dict:
        """Sistem durumu bilgisi"""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': memory.percent,
                'memory_available': memory.available,
                'disk_percent': (disk.used / disk.total) * 100,
                'disk_free': disk.free
            }
        except Exception as e:
            logger.warning(f"Sistem durumu alınamadı: {e}")
            return {}
    
    def _cleanup_memory(self):
        """Bellek temizliği"""
        try:
            # Python garbage collection
            gc.collect()
            
            # CPU bellek kullanımını kontrol et
            memory = psutil.virtual_memory()
            if memory.percent > 85:  # %85'in üzerindeyse uyar
                logger.warning(f"Yüksek bellek kullanımı: %{memory.percent}")
            
        except Exception as e:
            logger.warning(f"Bellek temizliği hatası: {e}")
    
    def get_device_info(self) -> Dict:
        """Mevcut cihaz bilgisi"""
        return {
            'analysis_mode': self.analysis_mode,
            'current_device': self.current_device,
            'gpu_status': gpu_detector.get_gpu_status(),
            'system_status': self._get_system_status()
        }