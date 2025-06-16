from fastapi import HTTPException, UploadFile
from PIL import Image
import rasterio
import magic
import hashlib
import os
from typing import List, Dict, Any
import logging
import io
import tempfile

logger = logging.getLogger(__name__)

class FileValidator:
    def __init__(self):
        self.allowed_extensions = {
            'image': ['.jpg', '.jpeg', '.png'],
            'multispectral': ['.tif', '.tiff']
        }
        
        self.allowed_mime_types = {
            'image/jpeg': 'image',
            'image/png': 'image',
            'image/tiff': 'multispectral',
            'image/tif': 'multispectral'
        }
        
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.min_image_size = (512, 512)  # Minimum çözünürlük
        self.max_image_size = (10000, 10000)  # Maximum çözünürlük
    
    async def validate_file(self, file: UploadFile) -> Dict[str, Any]:
        """Comprehensive file validation"""
        validation_result = {
            'valid': False,
            'file_type': None,
            'errors': [],
            'warnings': [],
            'metadata': {}
        }
        
        try:
            # Dosya adı kontrolü
            if not file.filename:
                validation_result['errors'].append("Dosya adı boş")
                return validation_result
            
            # Uzantı kontrolü
            file_ext = os.path.splitext(file.filename)[1].lower()
            file_type = self._get_file_type_by_extension(file_ext)
            
            if not file_type:
                validation_result['errors'].append(f"Desteklenmeyen dosya uzantısı: {file_ext}")
                return validation_result
            
            validation_result['file_type'] = file_type
            
            # Dosya içeriğini oku
            content = await file.read()
            await file.seek(0)  # Dosya pointer'ını başa al
            
            # Boyut kontrolü
            file_size = len(content)
            if file_size > self.max_file_size:
                validation_result['errors'].append(f"Dosya çok büyük: {file_size} bytes (max: {self.max_file_size})")
                return validation_result
            
            if file_size == 0:
                validation_result['errors'].append("Dosya boş")
                return validation_result
            
            validation_result['metadata']['file_size'] = file_size
            
            # MIME type kontrolü
            try:
                mime_type = magic.from_buffer(content, mime=True)
                if mime_type not in self.allowed_mime_types:
                    validation_result['errors'].append(f"Desteklenmeyen MIME type: {mime_type}")
                    return validation_result
                
                validation_result['metadata']['mime_type'] = mime_type
            except Exception as e:
                validation_result['errors'].append(f"MIME type kontrolü hatası: {str(e)}")
                return validation_result
            
            # Dosya hash'i
            file_hash = hashlib.md5(content).hexdigest()
            validation_result['metadata']['file_hash'] = file_hash
            
            # Dosya türüne göre özel validasyon
            if file_type == 'image':
                await self._validate_image(content, validation_result)
            elif file_type == 'multispectral':
                await self._validate_multispectral(content, validation_result)
            
            # Hata yoksa geçerli
            if not validation_result['errors']:
                validation_result['valid'] = True
            
        except Exception as e:
            logger.error(f"Dosya validasyon hatası: {e}")
            validation_result['errors'].append(f"Dosya validasyon hatası: {str(e)}")
        
        return validation_result
    
    def _get_file_type_by_extension(self, extension: str) -> str:
        """Uzantıya göre dosya türünü belirle"""
        for file_type, extensions in self.allowed_extensions.items():
            if extension in extensions:
                return file_type
        return None
    
    async def _validate_image(self, content: bytes, result: Dict):
        """RGB görsel validasyonu"""
        try:
            # PIL ile görsel aç
            with Image.open(io.BytesIO(content)) as img:
                width, height = img.size
                mode = img.mode
                format_name = img.format
                
                result['metadata'].update({
                    'width': width,
                    'height': height,
                    'mode': mode,
                    'format': format_name
                })
                
                # Çözünürlük kontrolü
                if width < self.min_image_size[0] or height < self.min_image_size[1]:
                    result['errors'].append(
                        f"Görsel çözünürlüğü çok düşük: {width}x{height} "
                        f"(minimum: {self.min_image_size[0]}x{self.min_image_size[1]})"
                    )
                
                if width > self.max_image_size[0] or height > self.max_image_size[1]:
                    result['warnings'].append(
                        f"Görsel çözünürlüğü çok yüksek: {width}x{height} "
                        f"(maksimum: {self.max_image_size[0]}x{self.max_image_size[1]})"
                    )
                
                # Renk modu kontrolü
                if mode not in ['RGB', 'RGBA', 'L']:
                    result['warnings'].append(f"Beklenmeyen renk modu: {mode}")
                
                # EXIF verilerini kontrol et
                if hasattr(img, '_getexif') and img._getexif():
                    exif_data = img._getexif()
                    if exif_data:
                        # GPS bilgisi var mı?
                        gps_info = exif_data.get(34853)  # GPS IFD
                        if gps_info:
                            result['metadata']['has_gps'] = True
                        else:
                            result['warnings'].append("GPS bilgisi bulunamadı")
                
        except Exception as e:
            result['errors'].append(f"Görsel validasyon hatası: {str(e)}")
    
    async def _validate_multispectral(self, content: bytes, result: Dict):
        """Multispektral dosya validasyonu"""
        temp_path = None
        try:
            # Geçici dosya oluştur
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tif') as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            # Rasterio ile aç
            with rasterio.open(temp_path) as src:
                width = src.width
                height = src.height
                count = src.count
                dtype = src.dtypes[0]
                crs = src.crs
                bounds = src.bounds
                
                result['metadata'].update({
                    'width': width,
                    'height': height,
                    'band_count': count,
                    'data_type': str(dtype),
                    'crs': str(crs) if crs else None,
                    'bounds': bounds
                })
                
                # Band sayısı kontrolü
                if count < 3:
                    result['warnings'].append(f"Az band sayısı: {count} (minimum 3 önerilir)")
                elif count >= 4:
                    result['metadata']['has_nir'] = True  # NIR band var
                
                # Koordinat sistemi kontrolü
                if not crs:
                    result['warnings'].append("Koordinat sistemi bilgisi bulunamadı")
                
                # Çözünürlük kontrolü
                if width < self.min_image_size[0] or height < self.min_image_size[1]:
                    result['errors'].append(
                        f"Multispektral görsel çözünürlüğü çok düşük: {width}x{height}"
                    )
                
                # Veri tipi kontrolü
                if dtype not in ['uint8', 'uint16', 'float32']:
                    result['warnings'].append(f"Beklenmeyen veri tipi: {dtype}")
                    
        except Exception as e:
            result['errors'].append(f"Multispektral validasyon hatası: {str(e)}")
        finally:
            # Geçici dosyayı sil
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"Geçici dosya silinemedi: {e}")
    
    async def validate_multiple_files(self, files: List[UploadFile]) -> Dict[str, Any]:
        """Çoklu dosya validasyonu"""
        validation_results = {
            'valid': True,
            'files': [],
            'summary': {
                'total_files': len(files),
                'valid_files': 0,
                'invalid_files': 0,
                'total_size': 0,
                'file_types': {}
            },
            'errors': [],
            'warnings': []
        }
        
        file_hashes = set()
        
        for file in files:
            file_result = await self.validate_file(file)
            validation_results['files'].append({
                'filename': file.filename,
                'result': file_result
            })
            
            if file_result['valid']:
                validation_results['summary']['valid_files'] += 1
                
                # Dosya boyutunu ekle
                file_size = file_result['metadata'].get('file_size', 0)
                validation_results['summary']['total_size'] += file_size
                
                # Dosya türü sayısını güncelle
                file_type = file_result['file_type']
                validation_results['summary']['file_types'][file_type] = \
                    validation_results['summary']['file_types'].get(file_type, 0) + 1
                
                # Duplicate kontrolü
                file_hash = file_result['metadata'].get('file_hash')
                if file_hash in file_hashes:
                    validation_results['warnings'].append(f"Duplicate dosya: {file.filename}")
                else:
                    file_hashes.add(file_hash)
                    
            else:
                validation_results['summary']['invalid_files'] += 1
                validation_results['valid'] = False
        
        # Genel kontroller
        if validation_results['summary']['valid_files'] == 0:
            validation_results['errors'].append("Hiç geçerli dosya bulunamadı")
        
        # Dosya türü uyarıları
        file_types = validation_results['summary']['file_types']
        if 'image' not in file_types:
            validation_results['warnings'].append("RGB görsel bulunamadı")
        
        if 'multispectral' not in file_types:
            validation_results['warnings'].append("Multispektral dosya bulunamadı")
        
        return validation_results

# Global validator instance
file_validator = FileValidator()