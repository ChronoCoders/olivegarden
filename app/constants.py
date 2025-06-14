"""
Zeytin Ağacı Analiz Sistemi - Sabitler
Tüm magic number'lar ve sabit değerler burada tanımlanır
"""

# Zeytin Analizi Sabitleri
DEFAULT_OLIVE_WEIGHT = 0.004  # kg - Ortalama zeytin ağırlığı
DEFAULT_OLIVES_PER_DETECTION = 10  # Her tespit için tahmini zeytin sayısı
OLIVE_DIAMETER_COEFFICIENT = 0.1  # Bounding box genişliğinden çap hesaplama katsayısı

# Dosya Sabitleri
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MIN_IMAGE_SIZE = (512, 512)  # Minimum görsel boyutu
MAX_IMAGE_SIZE = (10000, 10000)  # Maximum görsel boyutu

# YOLO Model Sabitleri
YOLO_CONFIDENCE_THRESHOLD = 0.5
YOLO_TREE_CLASS = 0  # Ağaç sınıfı
YOLO_OLIVE_CLASS = 1  # Zeytin sınıfı

# NDVI Sağlık Sınıflandırması
NDVI_VERY_HEALTHY = 0.7
NDVI_HEALTHY = 0.5
NDVI_MODERATE_STRESS = 0.3
NDVI_STRESSED = 0.1

# Sağlık Durumu Mesajları
HEALTH_STATUS = {
    "very_healthy": "Çok Sağlıklı",
    "healthy": "Sağlıklı", 
    "moderate_stress": "Orta Düzeyde Stresli",
    "stressed": "Stresli",
    "very_stressed": "Çok Stresli/Hasta"
}

# Rate Limiting Sabitleri
DEFAULT_RATE_LIMIT = 100  # İstek/saat
UPLOAD_RATE_LIMIT = 5  # Yükleme/5dk
ANALYSIS_RATE_LIMIT = 10  # Analiz/10dk
AUTH_RATE_LIMIT = 5  # Giriş/5dk

# Database Sabitleri
DB_POOL_SIZE = 10
DB_TIMEOUT = 30
DB_RETRY_COUNT = 3

# GPU Sabitleri
GPU_MEMORY_THRESHOLD = 0.9  # %90 bellek kullanımında uyarı
GPU_CLEANUP_INTERVAL = 300  # 5 dakikada bir temizlik

# Monitoring Sabitleri
HEALTH_CHECK_TIMEOUT = 5  # saniye
METRICS_UPDATE_INTERVAL = 60  # saniye
DISK_SPACE_WARNING_THRESHOLD = 0.85  # %85 disk kullanımında uyarı

# Backup Sabitleri
BACKUP_RETENTION_DAYS = 30
BACKUP_COMPRESSION_LEVEL = 6

# Error Messages
ERROR_MESSAGES = {
    "file_too_large": "Dosya boyutu çok büyük",
    "invalid_format": "Desteklenmeyen dosya formatı",
    "analysis_failed": "Analiz işlemi başarısız",
    "gpu_not_available": "GPU mevcut değil",
    "insufficient_permissions": "Yetersiz yetki",
    "rate_limit_exceeded": "İstek limiti aşıldı",
    "internal_error": "Sistem hatası oluştu"
}

# Success Messages
SUCCESS_MESSAGES = {
    "file_uploaded": "Dosya başarıyla yüklendi",
    "analysis_completed": "Analiz başarıyla tamamlandı",
    "report_generated": "Rapor oluşturuldu",
    "backup_created": "Yedek oluşturuldu",
    "user_created": "Kullanıcı oluşturuldu"
}

# API Response Codes
API_RESPONSES = {
    "success": {"code": 200, "message": "İşlem başarılı"},
    "created": {"code": 201, "message": "Kaynak oluşturuldu"},
    "bad_request": {"code": 400, "message": "Geçersiz istek"},
    "unauthorized": {"code": 401, "message": "Kimlik doğrulama gerekli"},
    "forbidden": {"code": 403, "message": "Erişim reddedildi"},
    "not_found": {"code": 404, "message": "Kaynak bulunamadı"},
    "rate_limited": {"code": 429, "message": "İstek limiti aşıldı"},
    "internal_error": {"code": 500, "message": "Sunucu hatası"}
}

# File Extensions
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png']
ALLOWED_MULTISPECTRAL_EXTENSIONS = ['.tif', '.tiff']
ALL_ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS + ALLOWED_MULTISPECTRAL_EXTENSIONS

# MIME Types
ALLOWED_MIME_TYPES = {
    'image/jpeg': 'image',
    'image/png': 'image',
    'image/tiff': 'multispectral',
    'image/tif': 'multispectral'
}

# Default Coordinates (for demo purposes)
DEFAULT_COORDINATES = {
    "latitude": 39.0,
    "longitude": 35.0,
    "coordinate_increment": 0.001
}

# Analysis Modes
ANALYSIS_MODES = {
    "cpu": {
        "name": "CPU Modu",
        "description": "Standart işlemci ile analiz",
        "speed": "Orta",
        "requirements": "Yok"
    },
    "gpu": {
        "name": "GPU Modu", 
        "description": "Grafik kartı ile hızlandırılmış analiz",
        "speed": "Yüksek",
        "requirements": "NVIDIA GPU + CUDA"
    }
}

# Log Formats
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
ACCESS_LOG_FORMAT = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Cache Settings
CACHE_TTL = 3600  # 1 saat
CACHE_MAX_SIZE = 1000  # Maximum cache entries

# Validation Rules
VALIDATION_RULES = {
    "username": {
        "min_length": 3,
        "max_length": 50,
        "pattern": r"^[a-zA-Z0-9_]+$"
    },
    "password": {
        "min_length": 8,
        "max_length": 128,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_digit": True
    },
    "email": {
        "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    }
}