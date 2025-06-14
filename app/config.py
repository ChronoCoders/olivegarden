import os
import secrets
from pathlib import Path
from typing import Optional

class Settings:
    """Uygulama ayarları - Environment variable'lardan yüklenir"""
    
    # Temel ayarlar
    APP_NAME: str = os.getenv("APP_NAME", "Zeytin Ağacı Analiz Sistemi")
    VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Sunucu ayarları
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Güvenlik ayarları - PRODUCTION'DA MUTLAKA DEĞİŞTİRİLMELİ
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        if ENVIRONMENT == "production":
            raise ValueError("SECRET_KEY environment variable must be set in production")
        SECRET_KEY = secrets.token_urlsafe(32)
    
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # Veri klasörü
    DATA_PATH: str = os.getenv("DATA_PATH", "data")
    
    # Veritabanı
    DATABASE_URL: str = os.getenv("DATABASE_URL", os.path.join(DATA_PATH, "analiz.db"))
    DATABASE_POOL_SIZE: int = int(os.getenv("DATABASE_POOL_SIZE", "10"))
    DATABASE_TIMEOUT: int = int(os.getenv("DATABASE_TIMEOUT", "30"))
    
    # AI modeli ayarları
    YOLO_MODEL_PATH: str = os.getenv("YOLO_MODEL_PATH", "models/yolov8n.pt")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    DEFAULT_ANALYSIS_MODE: str = os.getenv("DEFAULT_ANALYSIS_MODE", "cpu")
    
    # Dosya limitleri
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "104857600"))  # 100MB
    ALLOWED_EXTENSIONS: list = os.getenv("ALLOWED_EXTENSIONS", "jpg,jpeg,png,tif,tiff").split(",")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp")
    CLEANUP_AFTER_DAYS: int = int(os.getenv("CLEANUP_AFTER_DAYS", "30"))
    
    # Rate limiting ayarları
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))  # 1 hour
    UPLOAD_RATE_LIMIT: int = int(os.getenv("UPLOAD_RATE_LIMIT", "5"))
    UPLOAD_RATE_WINDOW: int = int(os.getenv("UPLOAD_RATE_WINDOW", "300"))  # 5 minutes
    
    # Monitoring ayarları
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    METRICS_ENABLED: bool = os.getenv("METRICS_ENABLED", "True").lower() == "true"
    HEALTH_CHECK_TIMEOUT: int = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))
    
    # Backup ayarları
    BACKUP_DIR: str = os.getenv("BACKUP_DIR", "/backups")
    BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
    BACKUP_COMPRESSION: bool = os.getenv("BACKUP_COMPRESSION", "True").lower() == "true"
    
    # Email ayarları (opsiyonel)
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "False").lower() == "true"
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASS: Optional[str] = os.getenv("SMTP_PASS")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM")
    EMAIL_TO: Optional[str] = os.getenv("EMAIL_TO")
    
    # Uzak yedekleme ayarları (opsiyonel)
    REMOTE_BACKUP_ENABLED: bool = os.getenv("REMOTE_BACKUP_ENABLED", "False").lower() == "true"
    REMOTE_TYPE: str = os.getenv("REMOTE_TYPE", "sftp")  # sftp veya s3
    REMOTE_HOST: Optional[str] = os.getenv("REMOTE_HOST")
    REMOTE_USER: Optional[str] = os.getenv("REMOTE_USER")
    REMOTE_PATH: Optional[str] = os.getenv("REMOTE_PATH")
    S3_BUCKET: Optional[str] = os.getenv("S3_BUCKET")
    S3_PREFIX: str = os.getenv("S3_PREFIX", "zeytin-backups")
    
    # GPU ayarları
    CUDA_VISIBLE_DEVICES: str = os.getenv("CUDA_VISIBLE_DEVICES", "0")
    GPU_MEMORY_FRACTION: float = float(os.getenv("GPU_MEMORY_FRACTION", "0.8"))
    
    def __init__(self):
        """Gerekli klasörleri oluştur"""
        self._create_directories()
        self._validate_settings()
    
    def _create_directories(self):
        """Gerekli klasörleri oluştur"""
        directories = [
            self.DATA_PATH,
            os.path.join(self.DATA_PATH, "analizler"),
            "models",
            self.BACKUP_DIR,
            self.TEMP_DIR
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def _validate_settings(self):
        """Ayarları doğrula"""
        if self.ENVIRONMENT == "production":
            # Production kontrolları
            if self.SECRET_KEY == "your-secret-key-change-in-production":
                raise ValueError("Production ortamında SECRET_KEY değiştirilmelidir!")
            
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY en az 32 karakter olmalıdır!")
            
            if self.DEBUG:
                raise ValueError("Production ortamında DEBUG=False olmalıdır!")
        
        # Dosya yolu kontrolları
        if not os.path.exists(self.DATA_PATH):
            raise ValueError(f"DATA_PATH bulunamadı: {self.DATA_PATH}")
        
        # Model dosyası kontrolü
        if not os.path.exists(self.YOLO_MODEL_PATH):
            import logging
            logging.warning(f"YOLO model dosyası bulunamadı: {self.YOLO_MODEL_PATH}")
    
    @property
    def is_production(self) -> bool:
        """Production ortamında mı?"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """Development ortamında mı?"""
        return self.ENVIRONMENT == "development"
    
    def get_database_url(self) -> str:
        """Tam veritabanı URL'ini döndür"""
        if os.path.isabs(self.DATABASE_URL):
            return self.DATABASE_URL
        return os.path.join(os.getcwd(), self.DATABASE_URL)

# Global settings instance
settings = Settings()