# 🔗 Zeytin Ağacı Analiz Sistemi - API Dokümantasyonu

Bu dokümantasyon, Zeytin Ağacı Analiz Sistemi'nin tüm API endpoint'lerini ve kullanım örneklerini içerir.

## 📋 İçindekiler

1. [Kimlik Doğrulama](#kimlik-doğrulama)
2. [Dosya İşlemleri](#dosya-işlemleri)
3. [Analiz İşlemleri](#analiz-işlemleri)
4. [Rapor İşlemleri](#rapor-işlemleri)
5. [Admin İşlemleri](#admin-işlemleri)
6. [Sistem İşlemleri](#sistem-işlemleri)
7. [Hata Kodları](#hata-kodları)
8. [Rate Limiting](#rate-limiting)

## 🔐 Kimlik Doğrulama

### POST /auth/giris
Kullanıcı girişi yapar ve JWT token alır.

**Request Body:**
```json
{
  "kullanici_adi": "admin",
  "sifre": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "kullanici_id": 1,
    "kullanici_adi": "admin",
    "email": "admin@zeytinanaliz.com",
    "rol": "admin"
  }
}
```

**cURL Örneği:**
```bash
curl -X POST http://localhost:8000/auth/giris \
  -H "Content-Type: application/json" \
  -d '{"kullanici_adi": "admin", "sifre": "admin123"}'
```

### POST /auth/yenile
Access token'ı yeniler.

**Request Body:**
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

### POST /auth/cikis
Kullanıcı çıkışı yapar ve token'ı geçersiz kılar.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "message": "Başarıyla çıkış yapıldı"
}
```

### POST /auth/kullanici-olustur
Yeni kullanıcı oluşturur (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
```

**Request Body:**
```json
{
  "kullanici_adi": "yenikullanici",
  "email": "yeni@example.com",
  "sifre": "guvenliSifre123",
  "rol": "standart"
}
```

**Response:**
```json
{
  "message": "Kullanıcı başarıyla oluşturuldu"
}
```

## 📁 Dosya İşlemleri

### POST /analiz/yukle
Analiz için dosya yükler.

**Content-Type:** `multipart/form-data`

**Form Data:**
- `dosyalar`: Dosya(lar) (RGB: .jpg, .png | Multispektral: .tif, .tiff)

**Headers (Opsiyonel):**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "success": true,
  "analiz_id": "550e8400-e29b-41d4-a716-446655440000",
  "yuklenen_dosyalar": [
    {
      "dosya_adi": "ornek.jpg",
      "dosya_boyutu": 2048576,
      "dosya_tipi": "RGB"
    },
    {
      "dosya_adi": "multispektral.tif",
      "dosya_boyutu": 10485760,
      "dosya_tipi": "Multispektral"
    }
  ],
  "toplam_dosya": 2,
  "toplam_boyut": 12534336,
  "gpu_mevcut": true,
  "validation_warnings": [],
  "mesaj": "2 dosya başarıyla yüklendi"
}
```

**cURL Örneği:**
```bash
curl -X POST http://localhost:8000/analiz/yukle \
  -F "dosyalar=@ornek.jpg" \
  -F "dosyalar=@multispektral.tif"
```

## 🔬 Analiz İşlemleri

### GET /gpu-durum
GPU durumunu ve mevcut analiz modlarını sorgular.

**Response:**
```json
{
  "success": true,
  "gpu_status": {
    "gpu_available": true,
    "cuda_available": true,
    "gpu_info": {
      "device_name": "NVIDIA GeForce RTX 3080",
      "memory_total": 10737418240,
      "memory_usage": {
        "allocated": 1073741824,
        "cached": 2147483648,
        "free": 7516192768
      }
    }
  },
  "device_info": {
    "analysis_mode": "cpu",
    "current_device": "cpu"
  },
  "available_modes": ["cpu", "gpu"]
}
```

### POST /analiz/baslat
Analizi başlatır (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
```

**Content-Type:** `application/x-www-form-urlencoded`

**Form Data:**
- `analiz_id`: Analiz ID'si
- `analiz_modu`: "cpu" veya "gpu"

**Response:**
```json
{
  "success": true,
  "sonuc": {
    "toplam_agac": 25,
    "toplam_zeytin": 1250,
    "tahmini_zeytin_miktari": 5.0,
    "ndvi_ortalama": 0.752,
    "gndvi_ortalama": 0.698,
    "ndre_ortalama": 0.721,
    "saglik_durumu": "Sağlıklı",
    "agac_cap_ortalama": 45.2,
    "analiz_modu": "gpu",
    "kullanilan_cihaz": "cuda",
    "analiz_suresi": 15.3,
    "gpu_durumu": {
      "gpu_available": true,
      "memory_usage": {...}
    },
    "detaylar": [
      {
        "dosya": "ornek.jpg",
        "agac_sayisi": 12,
        "zeytin_sayisi": 600,
        "ortalama_cap": 42.1,
        "isleme_suresi": 8.2,
        "cihaz": "cuda"
      }
    ]
  },
  "mesaj": "Analiz başarıyla tamamlandı (15.3 saniye)"
}
```

**cURL Örneği:**
```bash
curl -X POST http://localhost:8000/analiz/baslat \
  -H "Authorization: Bearer <admin_token>" \
  -d "analiz_id=550e8400-e29b-41d4-a716-446655440000&analiz_modu=gpu"
```

### POST /analiz/baslat-json
JSON formatında analiz başlatır (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "analiz_id": "550e8400-e29b-41d4-a716-446655440000",
  "analiz_modu": "gpu"
}
```

**Response:** `/analiz/baslat` ile aynı

### GET /analiz/durum/{analiz_id}
Analiz durumunu sorgular.

**Headers (Opsiyonel):**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "analiz_id": "550e8400-e29b-41d4-a716-446655440000",
  "durum": "tamamlandi",
  "log": "[2024-01-15 10:30:00] Analiz başlatıldı...\n[2024-01-15 10:30:15] Analiz tamamlandı",
  "sonuc": {
    "toplam_agac": 25,
    "toplam_zeytin": 1250,
    ...
  },
  "gpu_durumu": {
    "gpu_available": true,
    ...
  }
}
```

## 📊 Rapor İşlemleri

### GET /analiz/rapor/{analiz_id}
Analiz raporunu indirir (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
```

**Query Parameters:**
- `format`: "pdf" veya "excel"

**Response:** Dosya indirme

**cURL Örneği:**
```bash
# PDF raporu
curl -X GET "http://localhost:8000/analiz/rapor/550e8400-e29b-41d4-a716-446655440000?format=pdf" \
  -H "Authorization: Bearer <admin_token>" \
  -o rapor.pdf

# Excel raporu
curl -X GET "http://localhost:8000/analiz/rapor/550e8400-e29b-41d4-a716-446655440000?format=excel" \
  -H "Authorization: Bearer <admin_token>" \
  -o rapor.xlsx
```

### GET /analiz/harita/{analiz_id}
GeoJSON formatında harita verisi alır.

**Headers (Opsiyonel):**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [35.001, 39.001]
      },
      "properties": {
        "dosya": "ornek.jpg",
        "agac_sayisi": 12,
        "zeytin_sayisi": 600,
        "ortalama_cap": 42.1,
        "ndvi": 0.752,
        "saglik_durumu": "Sağlıklı",
        "isleme_suresi": 8.2,
        "cihaz": "cuda"
      }
    }
  ]
}
```

## 👨‍💼 Admin İşlemleri

### POST /admin/yedek-olustur
Sistem yedeği oluşturur (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
```

**Response:**
```json
{
  "success": true,
  "backup_path": "/backups/zeytin_analiz_manual_20240115_103000.tar.gz",
  "message": "Yedek başarıyla oluşturuldu"
}
```

### GET /admin/yedekler
Mevcut yedekleri listeler (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
```

**Response:**
```json
{
  "success": true,
  "backups": [
    {
      "filename": "zeytin_analiz_auto_20240115_020000.tar.gz",
      "path": "/backups/zeytin_analiz_auto_20240115_020000.tar.gz",
      "size": 104857600,
      "created": "2024-01-15T02:00:00",
      "modified": "2024-01-15T02:05:30"
    }
  ]
}
```

### POST /admin/yedek-temizle
Eski yedekleri temizler (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
```

**Response:**
```json
{
  "success": true,
  "message": "Eski yedekler temizlendi"
}
```

### GET /admin/sistem-durumu
Sistem durumu bilgilerini alır (sadece admin).

**Headers:**
```
Authorization: Bearer <admin_access_token>
```

**Response:**
```json
{
  "success": true,
  "system": {
    "cpu_percent": 25.3,
    "memory_percent": 68.2,
    "memory_available": 4294967296,
    "disk_percent": 45.7,
    "disk_free": 53687091200
  },
  "gpu": {
    "gpu_available": true,
    "cuda_available": true,
    "gpu_info": {
      "device_name": "NVIDIA GeForce RTX 3080",
      "memory_total": 10737418240
    }
  },
  "analyses": {
    "total": 150,
    "completed": 142,
    "recent": [
      {
        "analiz_id": "550e8400-e29b-41d4-a716-446655440000",
        "tarih_saat": "2024-01-15T10:30:00",
        "durum": "tamamlandi",
        "toplam_agac": 25,
        "analiz_modu": "gpu"
      }
    ]
  }
}
```

## 🔧 Sistem İşlemleri

### GET /health
Sistem sağlık kontrolü.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.123456",
  "gpu_available": true,
  "cuda_available": true
}
```

### GET /
Ana sayfa (HTML).

**Response:** HTML sayfası

## ❌ Hata Kodları

### HTTP Status Kodları

| Kod | Açıklama | Örnek Durum |
|-----|----------|-------------|
| 200 | Başarılı | İstek başarıyla tamamlandı |
| 400 | Kötü İstek | Geçersiz dosya formatı |
| 401 | Yetkisiz | Geçersiz token |
| 403 | Yasak | Admin yetkisi gerekli |
| 404 | Bulunamadı | Analiz bulunamadı |
| 429 | Çok Fazla İstek | Rate limit aşıldı |
| 500 | Sunucu Hatası | İç sunucu hatası |

### Hata Yanıt Formatı

```json
{
  "detail": "Hata açıklaması",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

### Yaygın Hatalar

**401 - Geçersiz Token:**
```json
{
  "detail": "Geçersiz kimlik bilgileri"
}
```

**403 - Yetkisiz Erişim:**
```json
{
  "detail": "Bu işlem için admin yetkisi gerekli"
}
```

**400 - Dosya Validasyon Hatası:**
```json
{
  "detail": {
    "error": "Dosya validasyon hatası",
    "validation_result": {
      "valid": false,
      "files": [...],
      "errors": ["Desteklenmeyen dosya formatı: test.bmp"]
    }
  }
}
```

**429 - Rate Limit:**
```json
{
  "detail": {
    "error": "Çok fazla istek",
    "limit": 10,
    "window": 600,
    "retry_after": 300
  }
}
```

## ⏱️ Rate Limiting

### Endpoint Limitleri

| Endpoint | Limit | Zaman Penceresi |
|----------|-------|-----------------|
| `/analiz/yukle` | 5 istek | 5 dakika |
| `/analiz/baslat` | 10 istek | 10 dakika |
| `/auth/giris` | 5 istek | 5 dakika |
| Diğer | 100 istek | 1 saat |

### Rate Limit Headers

Her yanıtta aşağıdaki header'lar eklenir:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1642248600
```

### Rate Limit Aşımı

Rate limit aşıldığında:

1. HTTP 429 status kodu döner
2. IP geçici olarak bloklanır (5 dakika)
3. `retry_after` değeri saniye cinsinden bekleme süresini belirtir

## 🔍 Örnek Kullanım Senaryoları

### Senaryo 1: Tam Analiz İş Akışı

```bash
# 1. Giriş yap
TOKEN=$(curl -s -X POST http://localhost:8000/auth/giris \
  -H "Content-Type: application/json" \
  -d '{"kullanici_adi": "admin", "sifre": "admin123"}' | \
  jq -r '.access_token')

# 2. GPU durumunu kontrol et
curl -s http://localhost:8000/gpu-durum | jq

# 3. Dosya yükle
ANALIZ_ID=$(curl -s -X POST http://localhost:8000/analiz/yukle \
  -F "dosyalar=@ornek.jpg" \
  -F "dosyalar=@multispektral.tif" | \
  jq -r '.analiz_id')

# 4. Analizi başlat (GPU modu)
curl -s -X POST http://localhost:8000/analiz/baslat \
  -H "Authorization: Bearer $TOKEN" \
  -d "analiz_id=$ANALIZ_ID&analiz_modu=gpu" | jq

# 5. Analiz durumunu kontrol et
curl -s "http://localhost:8000/analiz/durum/$ANALIZ_ID" | jq

# 6. PDF raporu indir
curl -X GET "http://localhost:8000/analiz/rapor/$ANALIZ_ID?format=pdf" \
  -H "Authorization: Bearer $TOKEN" \
  -o rapor.pdf

# 7. Harita verisini al
curl -s "http://localhost:8000/analiz/harita/$ANALIZ_ID" | jq
```

### Senaryo 2: Sistem Yönetimi

```bash
# Admin token al
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/auth/giris \
  -H "Content-Type: application/json" \
  -d '{"kullanici_adi": "admin", "sifre": "admin123"}' | \
  jq -r '.access_token')

# Sistem durumunu kontrol et
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/admin/sistem-durumu | jq

# Yedek oluştur
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/admin/yedek-olustur | jq

# Yedekleri listele
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/admin/yedekler | jq

# Yeni kullanıcı oluştur
curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kullanici_adi": "yenikullanici", "email": "yeni@example.com", "sifre": "sifre123", "rol": "standart"}' \
  http://localhost:8000/auth/kullanici-olustur | jq
```

## 📝 Notlar

1. **Token Süresi:** Access token'lar 30 dakika, refresh token'lar 7 gün geçerlidir.

2. **Dosya Limitleri:** 
   - Maksimum dosya boyutu: 100MB
   - Desteklenen formatlar: JPG, PNG, TIF, TIFF

3. **GPU Modu:** 
   - GPU mevcut değilse otomatik olarak CPU moduna geçer
   - GPU bellek kullanımı yanıtlarda raporlanır

4. **Rate Limiting:** 
   - IP bazlı limitler uygulanır
   - Aşım durumunda geçici bloklamalar yapılır

5. **Güvenlik:** 
   - Tüm admin işlemleri JWT token gerektirir
   - Token'lar blacklist ile yönetilir
   - API istekleri loglanır

6. **Monitoring:** 
   - Tüm API istekleri performance bilgileri ile loglanır
   - Sistem durumu endpoint'i ile monitoring yapılabilir

Bu dokümantasyon, API'nin tüm özelliklerini kapsamaktadır. Daha detaylı bilgi için kaynak kodları incelenebilir.