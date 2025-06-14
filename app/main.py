from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from typing import List, Optional
from pydantic import BaseModel
import os
import uuid
import shutil
from datetime import datetime
import logging
import json
import time
import psutil

from .ai_analysis import ZeytinAnalizci
from .gpu_detector import gpu_detector
from .auth import auth_manager, get_current_user, get_admin_user, get_current_user_optional
from .rate_limiter import check_rate_limit
from .middleware import LoggingMiddleware, SecurityHeadersMiddleware
from .backup import backup_manager
from .validation import file_validator
from .database import init_db, get_db_connection
from .config import settings
from .constants import ERROR_MESSAGES, SUCCESS_MESSAGES, API_RESPONSES

# Logging yapılandırması
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="AI destekli zeytin bahçesi analizi ve raporlama sistemi"
)

# Middleware ekle
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Static dosyalar
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Veri dizinlerini oluştur
os.makedirs(os.path.join(settings.DATA_PATH, "analizler"), exist_ok=True)

# Veritabanını başlat
init_db()

# AI analizcisini başlat
analizci = ZeytinAnalizci()

# Security
security = HTTPBearer()

# Metrics için global değişkenler
metrics_data = {
    "requests_total": 0,
    "requests_by_endpoint": {},
    "analysis_count": 0,
    "gpu_usage_count": 0,
    "cpu_usage_count": 0,
    "errors_total": 0,
    "upload_size_total": 0
}

class AnalysisRequest(BaseModel):
    analiz_id: str
    analiz_modu: Optional[str] = "cpu"

class LoginRequest(BaseModel):
    kullanici_adi: str
    sifre: str

class UserCreateRequest(BaseModel):
    kullanici_adi: str
    email: str
    sifre: str
    rol: Optional[str] = "standart"

def update_metrics(endpoint: str, error: bool = False):
    """Metrics güncelle"""
    global metrics_data
    metrics_data["requests_total"] += 1
    metrics_data["requests_by_endpoint"][endpoint] = metrics_data["requests_by_endpoint"].get(endpoint, 0) + 1
    if error:
        metrics_data["errors_total"] += 1

def safe_error_response(status_code: int, detail: str, log_detail: str = None):
    """Güvenli hata yanıtı - client'a generic mesaj, loglara detay"""
    if log_detail:
        logger.error(f"API Hatası: {log_detail}")
    else:
        logger.error(f"API Hatası: {detail}")
    
    # Production'da generic mesajlar
    if settings.is_production:
        generic_messages = {
            400: ERROR_MESSAGES["invalid_format"],
            401: ERROR_MESSAGES["insufficient_permissions"],
            403: ERROR_MESSAGES["insufficient_permissions"],
            404: "Kaynak bulunamadı",
            429: ERROR_MESSAGES["rate_limit_exceeded"],
            500: ERROR_MESSAGES["internal_error"]
        }
        detail = generic_messages.get(status_code, ERROR_MESSAGES["internal_error"])
    
    raise HTTPException(status_code=status_code, detail=detail)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Ana sayfa"""
    return templates.TemplateResponse("index.html", {"request": request})

# Metrics endpoint
@app.get("/metrics")
async def get_metrics():
    """Prometheus uyumlu metrics"""
    if not settings.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics devre dışı")
    
    try:
        # Sistem metrikleri
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # GPU metrikleri
        gpu_status = gpu_detector.get_gpu_status()
        
        metrics_text = f"""# HELP zeytin_requests_total Toplam API istekleri
# TYPE zeytin_requests_total counter
zeytin_requests_total {metrics_data["requests_total"]}

# HELP zeytin_analysis_total Toplam analiz sayısı
# TYPE zeytin_analysis_total counter
zeytin_analysis_total {metrics_data["analysis_count"]}

# HELP zeytin_gpu_usage_total GPU kullanım sayısı
# TYPE zeytin_gpu_usage_total counter
zeytin_gpu_usage_total {metrics_data["gpu_usage_count"]}

# HELP zeytin_cpu_usage_total CPU kullanım sayısı
# TYPE zeytin_cpu_usage_total counter
zeytin_cpu_usage_total {metrics_data["cpu_usage_count"]}

# HELP zeytin_errors_total Toplam hata sayısı
# TYPE zeytin_errors_total counter
zeytin_errors_total {metrics_data["errors_total"]}

# HELP zeytin_upload_size_bytes Toplam yüklenen dosya boyutu
# TYPE zeytin_upload_size_bytes counter
zeytin_upload_size_bytes {metrics_data["upload_size_total"]}

# HELP system_cpu_percent CPU kullanım yüzdesi
# TYPE system_cpu_percent gauge
system_cpu_percent {cpu_percent}

# HELP system_memory_percent Bellek kullanım yüzdesi
# TYPE system_memory_percent gauge
system_memory_percent {memory.percent}

# HELP system_disk_percent Disk kullanım yüzdesi
# TYPE system_disk_percent gauge
system_disk_percent {(disk.used / disk.total) * 100}

# HELP gpu_available GPU mevcut mu
# TYPE gpu_available gauge
gpu_available {1 if gpu_status.get('gpu_available', False) else 0}
"""
        
        # Endpoint bazlı metrikler
        for endpoint, count in metrics_data["requests_by_endpoint"].items():
            safe_endpoint = endpoint.replace("/", "_").replace("-", "_")
            metrics_text += f"""
# HELP zeytin_requests_by_endpoint_{safe_endpoint} {endpoint} endpoint istekleri
# TYPE zeytin_requests_by_endpoint_{safe_endpoint} counter
zeytin_requests_by_endpoint_{safe_endpoint} {count}
"""
        
        return Response(content=metrics_text, media_type="text/plain")
        
    except Exception as e:
        logger.error(f"Metrics hatası: {str(e)}")
        safe_error_response(500, "Metrics alınamadı", str(e))

# Enhanced Health Check
@app.get("/health")
async def health_check():
    """Gelişmiş sağlık kontrolü"""
    start_time = time.time()
    
    try:
        checks = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT
        }
        
        # Database kontrolü
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            checks["database"] = "healthy"
        except Exception as e:
            checks["database"] = "unhealthy"
            checks["database_error"] = str(e)
            logger.error(f"Database health check failed: {e}")
        
        # Disk alanı kontrolü
        try:
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            checks["disk_usage_percent"] = round(disk_percent, 2)
            checks["disk_free_gb"] = round(disk.free / (1024**3), 2)
            
            if disk_percent > 90:
                checks["disk"] = "critical"
            elif disk_percent > 80:
                checks["disk"] = "warning"
            else:
                checks["disk"] = "healthy"
        except Exception as e:
            checks["disk"] = "unknown"
            logger.error(f"Disk check failed: {e}")
        
        # GPU durumu
        try:
            gpu_status = gpu_detector.get_gpu_status()
            checks["gpu_available"] = gpu_status.get('gpu_available', False)
            checks["cuda_available"] = gpu_status.get('cuda_available', False)
            if gpu_status.get('gpu_available'):
                checks["gpu_device"] = gpu_status.get('gpu_info', {}).get('device_name', 'Unknown')
        except Exception as e:
            checks["gpu_available"] = False
            logger.error(f"GPU check failed: {e}")
        
        # Model dosyası kontrolü
        try:
            model_exists = os.path.exists(settings.YOLO_MODEL_PATH)
            checks["model_available"] = model_exists
            if model_exists:
                model_size = os.path.getsize(settings.YOLO_MODEL_PATH)
                checks["model_size_mb"] = round(model_size / (1024**2), 2)
        except Exception as e:
            checks["model_available"] = False
            logger.error(f"Model check failed: {e}")
        
        # Bellek kontrolü
        try:
            memory = psutil.virtual_memory()
            checks["memory_usage_percent"] = round(memory.percent, 2)
            checks["memory_available_gb"] = round(memory.available / (1024**3), 2)
            
            if memory.percent > 90:
                checks["memory"] = "critical"
            elif memory.percent > 80:
                checks["memory"] = "warning"
            else:
                checks["memory"] = "healthy"
        except Exception as e:
            checks["memory"] = "unknown"
            logger.error(f"Memory check failed: {e}")
        
        # Genel durum
        unhealthy_components = [k for k, v in checks.items() 
                              if isinstance(v, str) and v in ["unhealthy", "critical"]]
        
        if unhealthy_components:
            checks["status"] = "unhealthy"
            checks["unhealthy_components"] = unhealthy_components
        
        # Response süresi
        checks["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        status_code = 200 if checks["status"] == "healthy" else 503
        return JSONResponse(content=checks, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": "Health check failed",
                "timestamp": datetime.now().isoformat()
            },
            status_code=503
        )

# Authentication endpoints
@app.post("/auth/giris")
async def giris(request: Request, login_data: LoginRequest):
    """Kullanıcı girişi"""
    await check_rate_limit(request, "/auth/giris")
    update_metrics("/auth/giris")
    
    try:
        user = auth_manager.authenticate_user(login_data.kullanici_adi, login_data.sifre)
        if not user:
            safe_error_response(401, "Geçersiz kimlik bilgileri")
        
        access_token = auth_manager.create_access_token(
            data={"user_id": user["kullanici_id"], "username": user["kullanici_adi"]}
        )
        refresh_token = auth_manager.create_refresh_token(user["kullanici_id"])
        
        logger.info(f"Başarılı giriş: {user['kullanici_adi']}")
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "kullanici_id": user["kullanici_id"],
                "kullanici_adi": user["kullanici_adi"],
                "email": user["email"],
                "rol": user["rol"]
            }
        }
    except HTTPException:
        update_metrics("/auth/giris", error=True)
        raise
    except Exception as e:
        update_metrics("/auth/giris", error=True)
        safe_error_response(500, "Giriş hatası", str(e))

@app.post("/auth/yenile")
async def token_yenile(request: Request, refresh_token: str):
    """Token yenileme"""
    await check_rate_limit(request, "/auth/yenile")
    update_metrics("/auth/yenile")
    
    try:
        new_access_token = auth_manager.refresh_access_token(refresh_token)
        if not new_access_token:
            safe_error_response(401, "Geçersiz refresh token")
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
    except HTTPException:
        update_metrics("/auth/yenile", error=True)
        raise
    except Exception as e:
        update_metrics("/auth/yenile", error=True)
        safe_error_response(500, "Token yenileme hatası", str(e))

@app.post("/auth/cikis")
async def cikis(request: Request, current_user: dict = Depends(get_current_user)):
    """Kullanıcı çıkışı"""
    update_metrics("/auth/cikis")
    
    try:
        # Token'ı blacklist'e ekle
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            auth_manager.revoke_token(token)
        
        logger.info(f"Kullanıcı çıkışı: {current_user['kullanici_adi']}")
        return {"message": SUCCESS_MESSAGES["user_created"]}
    except Exception as e:
        update_metrics("/auth/cikis", error=True)
        safe_error_response(500, "Çıkış hatası", str(e))

@app.post("/auth/kullanici-olustur")
async def kullanici_olustur(request: Request, user_data: UserCreateRequest, 
                           admin_user: dict = Depends(get_admin_user)):
    """Yeni kullanıcı oluştur (sadece admin)"""
    await check_rate_limit(request)
    update_metrics("/auth/kullanici-olustur")
    
    try:
        success = auth_manager.create_user(
            username=user_data.kullanici_adi,
            email=user_data.email,
            password=user_data.sifre,
            role=user_data.rol
        )
        
        if not success:
            safe_error_response(400, "Kullanıcı oluşturulamadı")
        
        logger.info(f"Yeni kullanıcı oluşturuldu: {user_data.kullanici_adi} (Admin: {admin_user['kullanici_adi']})")
        return {"message": SUCCESS_MESSAGES["user_created"]}
    except HTTPException:
        update_metrics("/auth/kullanici-olustur", error=True)
        raise
    except Exception as e:
        update_metrics("/auth/kullanici-olustur", error=True)
        safe_error_response(500, "Kullanıcı oluşturma hatası", str(e))

@app.get("/gpu-durum")
async def gpu_durum():
    """GPU durumu endpoint'i"""
    update_metrics("/gpu-durum")
    
    try:
        gpu_status = gpu_detector.get_gpu_status()
        device_info = analizci.get_device_info()
        
        return JSONResponse({
            "success": True,
            "gpu_status": gpu_status,
            "device_info": device_info,
            "available_modes": ["cpu", "gpu"] if gpu_status['gpu_available'] else ["cpu"]
        })
    except Exception as e:
        update_metrics("/gpu-durum", error=True)
        safe_error_response(500, "GPU durum hatası", str(e))

@app.post("/analiz/yukle")
async def dosya_yukle(request: Request, dosyalar: List[UploadFile] = File(...),
                     current_user: dict = Depends(get_current_user_optional)):
    """Dosya yükleme endpoint'i"""
    await check_rate_limit(request, "/analiz/yukle")
    update_metrics("/analiz/yukle")
    
    try:
        # Dosya validasyonu
        validation_result = await file_validator.validate_multiple_files(dosyalar)
        
        if not validation_result['valid']:
            safe_error_response(400, "Dosya validasyon hatası", f"Validation: {validation_result}")
        
        analiz_id = str(uuid.uuid4())
        analiz_klasoru = os.path.join(settings.DATA_PATH, "analizler", analiz_id)
        yuklenen_klasor = os.path.join(analiz_klasoru, "yuklenen_dosyalar")
        
        # Klasörleri oluştur
        os.makedirs(yuklenen_klasor, exist_ok=True)
        
        yuklenen_dosyalar = []
        toplam_boyut = 0
        
        # Dosya kontrolü ve yükleme
        for dosya in dosyalar:
            if dosya.filename:
                dosya_icerik = await dosya.read()
                dosya_boyutu = len(dosya_icerik)
                toplam_boyut += dosya_boyutu
                
                # Dosyayı kaydet
                dosya_yolu = os.path.join(yuklenen_klasor, dosya.filename)
                with open(dosya_yolu, "wb") as buffer:
                    buffer.write(dosya_icerik)
                
                # Dosya türünü belirle
                dosya_uzantisi = dosya.filename.split('.')[-1].lower()
                dosya_tipi = "RGB" if dosya_uzantisi in ['jpg', 'jpeg', 'png'] else "Multispektral"
                
                yuklenen_dosyalar.append({
                    "dosya_adi": dosya.filename,
                    "dosya_boyutu": dosya_boyutu,
                    "dosya_tipi": dosya_tipi
                })
                
                logger.info(f"Dosya yüklendi: {dosya.filename} ({dosya_boyutu} bytes)")
        
        # Metrics güncelle
        metrics_data["upload_size_total"] += toplam_boyut
        
        # Log dosyası oluştur
        log_yolu = os.path.join(analiz_klasoru, "log.txt")
        with open(log_yolu, "w", encoding="utf-8") as log_file:
            log_file.write(f"Analiz ID: {analiz_id}\n")
            log_file.write(f"Yükleme Tarihi: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if current_user:
                log_file.write(f"Kullanıcı: {current_user['kullanici_adi']} (ID: {current_user['kullanici_id']})\n")
            log_file.write(f"Toplam Dosya Sayısı: {len(yuklenen_dosyalar)}\n")
            log_file.write(f"Toplam Boyut: {toplam_boyut} bytes\n")
            log_file.write(f"GPU Durumu: {gpu_detector.get_gpu_status()}\n\n")
            
            for dosya in yuklenen_dosyalar:
                log_file.write(f"Dosya: {dosya['dosya_adi']} - Boyut: {dosya['dosya_boyutu']} bytes - Tip: {dosya['dosya_tipi']}\n")
        
        return JSONResponse({
            "success": True,
            "analiz_id": analiz_id,
            "yuklenen_dosyalar": yuklenen_dosyalar,
            "toplam_dosya": len(yuklenen_dosyalar),
            "toplam_boyut": toplam_boyut,
            "gpu_mevcut": gpu_detector.gpu_available,
            "validation_warnings": validation_result.get('warnings', []),
            "mesaj": SUCCESS_MESSAGES["file_uploaded"]
        })
        
    except HTTPException:
        update_metrics("/analiz/yukle", error=True)
        raise
    except Exception as e:
        update_metrics("/analiz/yukle", error=True)
        safe_error_response(500, "Dosya yükleme hatası", str(e))

@app.post("/analiz/baslat")
async def analiz_baslat(
    request: Request,
    analiz_id: str = Form(...),
    analiz_modu: str = Form(default="cpu"),
    admin_user: dict = Depends(get_admin_user)
):
    """Analiz başlatma endpoint'i"""
    await check_rate_limit(request, "/analiz/baslat")
    update_metrics("/analiz/baslat")
    
    try:
        analiz_klasoru = os.path.join(settings.DATA_PATH, "analizler", analiz_id)
        yuklenen_klasor = os.path.join(analiz_klasoru, "yuklenen_dosyalar")
        log_yolu = os.path.join(analiz_klasoru, "log.txt")
        
        if not os.path.exists(analiz_klasoru):
            safe_error_response(404, "Analiz bulunamadı")
        
        # Analiz modunu kontrol et
        if analiz_modu.lower() not in ["cpu", "gpu"]:
            analiz_modu = "cpu"
        
        # GPU istendi ama mevcut değilse uyar
        if analiz_modu.lower() == "gpu" and not gpu_detector.gpu_available:
            logger.warning("GPU istendi ama mevcut değil, CPU moduna geçiliyor")
            analiz_modu = "cpu"
        
        # Metrics güncelle
        metrics_data["analysis_count"] += 1
        if analiz_modu == "gpu":
            metrics_data["gpu_usage_count"] += 1
        else:
            metrics_data["cpu_usage_count"] += 1
        
        # Log dosyasına analiz başlangıcını yaz
        with open(log_yolu, "a", encoding="utf-8") as log_file:
            log_file.write(f"\n--- Analiz Başlatıldı: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log_file.write(f"Başlatan Kullanıcı: {admin_user['kullanici_adi']} (ID: {admin_user['kullanici_id']})\n")
            log_file.write(f"İstenen Analiz Modu: {analiz_modu.upper()}\n")
            log_file.write(f"GPU Durumu: {gpu_detector.get_gpu_status()}\n")
        
        # AI analizi başlat
        start_time = datetime.now()
        analiz_sonuclari = await analizci.analiz_yap(
            yuklenen_klasor, 
            analiz_klasoru, 
            log_yolu,
            analiz_modu
        )
        end_time = datetime.now()
        
        # Analiz süresini hesapla
        analiz_suresi = (end_time - start_time).total_seconds()
        analiz_sonuclari['analiz_suresi'] = analiz_suresi
        
        # Log dosyasını güncelle
        with open(log_yolu, "a", encoding="utf-8") as log_file:
            log_file.write(f"--- Analiz Tamamlandı: {end_time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            log_file.write(f"Toplam Süre: {analiz_suresi:.2f} saniye\n")
            log_file.write(f"Kullanılan Cihaz: {analiz_sonuclari.get('kullanilan_cihaz', 'cpu').upper()}\n")
            log_file.write(f"Toplam Ağaç: {analiz_sonuclari['toplam_agac']}\n")
            log_file.write(f"Toplam Zeytin: {analiz_sonuclari['toplam_zeytin']}\n")
            log_file.write(f"Tahmini Zeytin Miktarı: {analiz_sonuclari['tahmini_zeytin_miktari']} kg\n")
            log_file.write(f"NDVI Ortalama: {analiz_sonuclari['ndvi_ortalama']:.3f}\n")
            log_file.write(f"Sağlık Durumu: {analiz_sonuclari['saglik_durumu']}\n")
        
        logger.info(f"Analiz tamamlandı: {analiz_id} - {analiz_suresi:.2f}s - {analiz_sonuclari.get('kullanilan_cihaz', 'cpu').upper()}")
        
        return JSONResponse({
            "success": True,
            "sonuc": analiz_sonuclari,
            "mesaj": SUCCESS_MESSAGES["analysis_completed"]
        })
        
    except HTTPException:
        update_metrics("/analiz/baslat", error=True)
        raise
    except Exception as e:
        update_metrics("/analiz/baslat", error=True)
        safe_error_response(500, "Analiz hatası", str(e))

@app.post("/analiz/baslat-json")
async def analiz_baslat_json(request: Request, analysis_request: AnalysisRequest,
                            admin_user: dict = Depends(get_admin_user)):
    """JSON body ile analiz başlatma endpoint'i"""
    try:
        return await analiz_baslat(
            request=request,
            analiz_id=analysis_request.analiz_id,
            analiz_modu=analysis_request.analiz_modu,
            admin_user=admin_user
        )
    except Exception as e:
        update_metrics("/analiz/baslat-json", error=True)
        safe_error_response(500, "JSON analiz hatası", str(e))

@app.get("/analiz/durum/{analiz_id}")
async def analiz_durum(request: Request, analiz_id: str,
                      current_user: dict = Depends(get_current_user_optional)):
    """Analiz durumu sorgulama"""
    await check_rate_limit(request)
    update_metrics("/analiz/durum")
    
    try:
        analiz_klasoru = os.path.join(settings.DATA_PATH, "analizler", analiz_id)
        log_yolu = os.path.join(analiz_klasoru, "log.txt")
        
        if not os.path.exists(analiz_klasoru):
            safe_error_response(404, "Analiz bulunamadı")
        
        # Log dosyasını oku
        log_icerik = ""
        if os.path.exists(log_yolu):
            with open(log_yolu, "r", encoding="utf-8") as f:
                log_icerik = f.read()
        
        # Sonuç dosyasını kontrol et
        sonuc_dosyasi = os.path.join(analiz_klasoru, "sonuc.json")
        sonuc = None
        if os.path.exists(sonuc_dosyasi):
            with open(sonuc_dosyasi, "r", encoding="utf-8") as f:
                sonuc = json.load(f)
        
        return JSONResponse({
            "analiz_id": analiz_id,
            "durum": "tamamlandi" if sonuc else "devam_ediyor",
            "log": log_icerik,
            "sonuc": sonuc,
            "gpu_durumu": gpu_detector.get_gpu_status()
        })
        
    except HTTPException:
        update_metrics("/analiz/durum", error=True)
        raise
    except Exception as e:
        update_metrics("/analiz/durum", error=True)
        safe_error_response(500, "Durum sorgulama hatası", str(e))

@app.get("/analiz/rapor/{analiz_id}")
async def rapor_indir(request: Request, analiz_id: str, format: str = "pdf",
                     admin_user: dict = Depends(get_admin_user)):
    """Rapor indirme endpoint'i"""
    await check_rate_limit(request)
    update_metrics("/analiz/rapor")
    
    try:
        analiz_klasoru = os.path.join(settings.DATA_PATH, "analizler", analiz_id)
        
        if not os.path.exists(analiz_klasoru):
            safe_error_response(404, "Analiz bulunamadı")
        
        if format.lower() == "pdf":
            dosya_yolu = os.path.join(analiz_klasoru, "rapor.pdf")
            media_type = "application/pdf"
            dosya_adi = f"zeytin_analiz_raporu_{analiz_id}.pdf"
        elif format.lower() == "excel":
            dosya_yolu = os.path.join(analiz_klasoru, "rapor.xlsx")
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            dosya_adi = f"zeytin_analiz_raporu_{analiz_id}.xlsx"
        else:
            safe_error_response(400, "Desteklenmeyen format")
        
        if not os.path.exists(dosya_yolu):
            # Basit bir rapor oluştur
            with open(dosya_yolu, "w", encoding="utf-8") as f:
                f.write(f"Zeytin Analiz Raporu - {analiz_id}\n")
                f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"İndiren: {admin_user['kullanici_adi']}\n")
        
        logger.info(f"Rapor indirildi: {analiz_id} - {format} - {admin_user['kullanici_adi']}")
        
        return FileResponse(
            path=dosya_yolu,
            media_type=media_type,
            filename=dosya_adi
        )
        
    except HTTPException:
        update_metrics("/analiz/rapor", error=True)
        raise
    except Exception as e:
        update_metrics("/analiz/rapor", error=True)
        safe_error_response(500, "Rapor indirme hatası", str(e))

@app.get("/analiz/harita/{analiz_id}")
async def harita_verisi(request: Request, analiz_id: str,
                       current_user: dict = Depends(get_current_user_optional)):
    """GeoJSON formatında harita verisi"""
    await check_rate_limit(request)
    update_metrics("/analiz/harita")
    
    try:
        analiz_klasoru = os.path.join(settings.DATA_PATH, "analizler", analiz_id)
        geojson_yolu = os.path.join(analiz_klasoru, "geojson.json")
        
        if not os.path.exists(geojson_yolu):
            # Basit bir GeoJSON oluştur
            geojson_data = {
                "type": "FeatureCollection",
                "features": []
            }
        else:
            with open(geojson_yolu, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)
        
        return JSONResponse(geojson_data)
        
    except Exception as e:
        update_metrics("/analiz/harita", error=True)
        safe_error_response(500, "Harita verisi hatası", str(e))

# Admin endpoints
@app.post("/admin/yedek-olustur")
async def yedek_olustur(request: Request, admin_user: dict = Depends(get_admin_user)):
    """Sistem yedeği oluştur"""
    await check_rate_limit(request)
    update_metrics("/admin/yedek-olustur")
    
    try:
        backup_path = backup_manager.create_backup("manual")
        logger.info(f"Manuel yedek oluşturuldu: {backup_path} - {admin_user['kullanici_adi']}")
        return {
            "success": True,
            "backup_path": backup_path,
            "message": SUCCESS_MESSAGES["backup_created"]
        }
    except Exception as e:
        update_metrics("/admin/yedek-olustur", error=True)
        safe_error_response(500, "Yedek oluşturma hatası", str(e))

@app.get("/admin/yedekler")
async def yedekleri_listele(request: Request, admin_user: dict = Depends(get_admin_user)):
    """Mevcut yedekleri listele"""
    await check_rate_limit(request)
    update_metrics("/admin/yedekler")
    
    try:
        backups = backup_manager.list_backups()
        return {
            "success": True,
            "backups": backups
        }
    except Exception as e:
        update_metrics("/admin/yedekler", error=True)
        safe_error_response(500, "Yedek listeleme hatası", str(e))

@app.post("/admin/yedek-temizle")
async def yedek_temizle(request: Request, admin_user: dict = Depends(get_admin_user)):
    """Eski yedekleri temizle"""
    await check_rate_limit(request)
    update_metrics("/admin/yedek-temizle")
    
    try:
        backup_manager.cleanup_old_backups()
        logger.info(f"Yedek temizleme yapıldı - {admin_user['kullanici_adi']}")
        return {
            "success": True,
            "message": "Eski yedekler temizlendi"
        }
    except Exception as e:
        update_metrics("/admin/yedek-temizle", error=True)
        safe_error_response(500, "Yedek temizleme hatası", str(e))

@app.get("/admin/sistem-durumu")
async def sistem_durumu(request: Request, admin_user: dict = Depends(get_admin_user)):
    """Sistem durumu bilgileri"""
    await check_rate_limit(request)
    update_metrics("/admin/sistem-durumu")
    
    try:
        # Sistem bilgileri
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # GPU bilgileri
        gpu_status = gpu_detector.get_gpu_status()
        
        # Analiz istatistikleri
        from .database import get_all_analyses
        analyses = get_all_analyses()
        
        return {
            "success": True,
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available": memory.available,
                "disk_percent": (disk.used / disk.total) * 100,
                "disk_free": disk.free
            },
            "gpu": gpu_status,
            "analyses": {
                "total": len(analyses),
                "completed": len([a for a in analyses if a['durum'] == 'tamamlandi']),
                "recent": analyses[:5]  # Son 5 analiz
            },
            "metrics": metrics_data
        }
    except Exception as e:
        update_metrics("/admin/sistem-durumu", error=True)
        safe_error_response(500, "Sistem durumu hatası", str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)