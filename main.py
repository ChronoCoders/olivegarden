from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Depends, Header
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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

from app.ai_analysis import ZeytinAnalizci
from app.gpu_detector import gpu_detector
from app.auth import auth_manager, get_current_user, get_admin_user, get_current_user_optional
from app.rate_limiter import check_rate_limit
from app.middleware import LoggingMiddleware, SecurityHeadersMiddleware
from app.backup import backup_manager
from app.validation import file_validator
from app.database import init_db, get_db_connection, create_analysis, get_analysis, update_analysis, add_file_upload
from app.config import settings
from app.constants import ERROR_MESSAGES, SUCCESS_MESSAGES, API_RESPONSES
from app.models import model_manager, model_trainer

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
security = HTTPBearer(auto_error=False)

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

class ModelTrainingRequest(BaseModel):
    images_dir: str
    annotations_dir: str
    model_name: Optional[str] = "custom_olive"
    epochs: Optional[int] = 100

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

def get_current_user_from_header(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Get current user from Authorization header"""
    if not credentials:
        return None
    
    try:
        return get_current_user(credentials.credentials)
    except HTTPException:
        return None

def get_admin_user_from_header(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get admin user from Authorization header"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    return get_admin_user(credentials.credentials)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Ana sayfa"""
    return templates.TemplateResponse("index.html", {"request": request})

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
            best_model = model_manager.get_best_model()
            checks["model_available"] = best_model is not None
            if best_model:
                model_size = os.path.getsize(best_model)
                checks["model_size_mb"] = round(model_size / (1024**2), 2)
                checks["model_path"] = best_model
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
            data={"user_id": user["kullanici_id"], "username": user["kullanici_adi"], "role": user["rol"]}
        )
        refresh_token = auth_manager.create_refresh_token(user["kullanici_id"])
        
        # Update last login
        auth_manager.update_last_login(user["kullanici_id"])
        
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
                     current_user: dict = Depends(get_current_user_from_header)):
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
                
                # Dosya hash'i
                import hashlib
                dosya_hash = hashlib.md5(dosya_icerik).hexdigest()
                
                # Database'e kaydet
                add_file_upload(analiz_id, dosya.filename, dosya_boyutu, dosya_tipi, dosya_hash, dosya_yolu)
                
                yuklenen_dosyalar.append({
                    "dosya_adi": dosya.filename,
                    "dosya_boyutu": dosya_boyutu,
                    "dosya_tipi": dosya_tipi
                })
                
                logger.info(f"Dosya yüklendi: {dosya.filename} ({dosya_boyutu} bytes)")
        
        # Metrics güncelle
        metrics_data["upload_size_total"] += toplam_boyut
        
        # Analiz kaydı oluştur
        kullanici_id = current_user["kullanici_id"] if current_user else None
        create_analysis(analiz_id, len(yuklenen_dosyalar), kullanici_id)
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)