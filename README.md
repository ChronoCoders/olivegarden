# 🫒 Zeytin Ağacı Analiz Sistemi

**Production-Grade** AI destekli zeytin bahçesi analizi ve raporlama sistemi. Python FastAPI, YOLOv8, multispektral görüntü analizi ve kapsamlı raporlama özellikleri ile geliştirilmiştir.

## 🚀 Özellikler

### 🤖 AI/ML Analiz
- **YOLOv8** ile RGB görsellerde zeytin ağacı ve zeytin tespiti
- **Multispektral Analiz**: NDVI, GNDVI, NDRE hesaplama
- **Hibrit CPU/GPU Desteği**: Otomatik fallback ile güvenilir çalışma
- Ağaç çapı hesaplama ve sağlık durumu analizi
- Toplam zeytin sayısı ve tahmini miktar hesaplama

### 🔒 Güvenlik ve Kimlik Doğrulama
- **JWT** tabanlı kimlik doğrulama sistemi
- **Admin/Standart** kullanıcı rolleri
- **Rate Limiting** ve IP bloklama
- **Fail2ban** entegrasyonu
- **SSL/HTTPS** desteği

### 📊 Monitoring ve Raporlama
- **Prometheus** uyumlu metrics endpoint
- **Gelişmiş Health Check** (DB, disk, GPU, bellek)
- **PDF ve Excel** rapor üretimi
- **GeoJSON** harita verisi
- **Real-time** analiz durumu takibi

### 🐳 Production-Ready Deployment
- **Docker & Docker Compose** yapılandırması
- **Nginx** reverse proxy ve rate limiting
- **Otomatik SSL** sertifika yönetimi
- **Systemd** servis entegrasyonu
- **Otomatik yedekleme** sistemi

## 📋 Sistem Gereksinimleri

### Minimum (CPU Modu)
- **CPU**: 4 core
- **RAM**: 8GB
- **Storage**: 50GB SSD
- **OS**: Ubuntu 22.04 LTS

### Önerilen (GPU Modu)
- **CPU**: 8 core
- **RAM**: 16GB
- **GPU**: NVIDIA GPU (CUDA 12.1+ desteği)
- **Storage**: 100GB SSD
- **OS**: Ubuntu 22.04 LTS

## 🛠️ Hızlı Kurulum

### 1. Repository'yi Klonlayın
```bash
git clone <repository-url>
cd zeytin-analiz-sistemi
```

### 2. Production Deployment (Önerilen)
```bash
# Tek komutla tam kurulum
sudo bash scripts/deploy.sh
```

Bu script otomatik olarak:
- ✅ Sistem güncellemesi
- ✅ Docker ve Docker Compose kurulumu
- ✅ Nginx ve Fail2ban kurulumu
- ✅ Firewall yapılandırması
- ✅ SSL sertifikaları oluşturma
- ✅ Uygulama deployment
- ✅ Systemd servis kurulumu
- ✅ Monitoring scriptleri

### 3. GPU Desteği (Opsiyonel)
```bash
# NVIDIA GPU kurulumu
sudo bash scripts/cuda_setup.sh

# GPU testini çalıştır
python3 /usr/local/bin/gpu-test.py
```

## 🔧 Manuel Kurulum

### Development Ortamı
```bash
# Python sanal ortamı
python3.10 -m venv venv
source venv/bin/activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Gerekli dizinleri oluştur
mkdir -p data/analizler models

# YOLOv8 modelini indir
cd models
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
cd ..

# .env dosyasını oluştur
cp .env.example .env

# Uygulamayı başlat
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker ile Kurulum
```bash
# .env dosyasını oluştur
cp .env.example .env

# SSL sertifikaları oluştur (development için)
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/key.pem \
    -out nginx/ssl/cert.pem \
    -subj "/C=TR/ST=Turkey/L=Istanbul/O=ZeytinAnaliz/CN=localhost"

# Docker imajlarını oluştur ve başlat
docker-compose build
docker-compose up -d

# Logları kontrol et
docker-compose logs -f
```

## 🌐 Erişim Adresleri

Kurulum tamamlandıktan sonra:

- **HTTP**: http://your-server-ip
- **HTTPS**: https://your-server-ip
- **Health Check**: https://your-server-ip/health
- **Metrics**: https://your-server-ip/metrics
- **API Docs**: https://your-server-ip/docs

## 🔑 Varsayılan Giriş Bilgileri

**⚠️ Production'da mutlaka değiştirin!**

- **Kullanıcı Adı**: `admin`
- **Şifre**: `admin123`

## 📖 Kullanım Kılavuzu

### 1. Dosya Yükleme
- Desteklenen formatlar: **JPG, PNG, TIF**
- Maksimum dosya boyutu: **100MB**
- Minimum çözünürlük: **512x512**

### 2. Analiz Modları
- **CPU Modu**: Her sistemde çalışır, orta hız
- **GPU Modu**: NVIDIA GPU gerekli, yüksek hız

### 3. Analiz Sonuçları
- **Toplam ağaç sayısı**
- **Toplam zeytin sayısı**
- **Tahmini zeytin miktarı (kg)**
- **NDVI, GNDVI, NDRE değerleri**
- **Sağlık durumu sınıflandırması**

### 4. Rapor İndirme
- **PDF**: Profesyonel rapor formatı
- **Excel**: Veri analizi için uygun
- **GeoJSON**: Harita verisi

## 🔗 API Kullanımı

### GPU Durumu Kontrolü
```bash
curl -X GET http://localhost:8000/gpu-durum
```

### Dosya Yükleme
```bash
curl -X POST http://localhost:8000/analiz/yukle \
  -F "dosyalar=@ornek.jpg" \
  -F "dosyalar=@multispektral.tif"
```

### Analiz Başlatma (GPU Modu)
```bash
curl -X POST http://localhost:8000/analiz/baslat-json \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"analiz_id": "uuid-string", "analiz_modu": "gpu"}'
```

### Health Check
```bash
curl -X GET http://localhost:8000/health
```

Detaylı API dokümantasyonu için: [API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

## 🎯 Yönetim Komutları

### Docker Yönetimi
```bash
# Servisleri başlat
docker-compose up -d

# Servisleri durdur
docker-compose down

# Logları görüntüle
docker-compose logs -f

# Servisleri yeniden başlat
docker-compose restart
```

### Systemd Yönetimi (Production)
```bash
# Servis durumu
sudo systemctl status zeytin-analiz

# Servisi başlat/durdur/yeniden başlat
sudo systemctl start zeytin-analiz
sudo systemctl stop zeytin-analiz
sudo systemctl restart zeytin-analiz
```

### Yedekleme
```bash
# Manuel yedek oluştur
bash scripts/backup_cron.sh

# Eski yedekleri temizle
bash scripts/backup_cron.sh --cleanup

# Yedek test et
bash scripts/backup_cron.sh --test
```

### Monitoring
```bash
# Sistem durumu
/usr/local/bin/zeytin-monitor.sh

# GPU testi
python3 /usr/local/bin/gpu-test.py

# Metrics görüntüle
curl http://localhost:8000/metrics
```

## 🧪 Test Etme

### Tüm Testleri Çalıştır
```bash
python -m pytest tests/ -v
```

### Spesifik Test Grupları
```bash
# GPU testleri
python -m pytest tests/test_gpu.py -v

# Validation testleri
python -m pytest tests/test_validation_edge_cases.py -v

# Backup testleri
python -m pytest tests/test_backup.py -v

# API testleri
python -m pytest tests/test_api.py -v
```

### Test Coverage
```bash
python -m pytest tests/ --cov=app --cov-report=html
```

## 📊 Monitoring ve Alerting

### Prometheus Metrics
```bash
# Metrics endpoint
curl http://localhost:8000/metrics

# Örnek metrikler
zeytin_requests_total
zeytin_analysis_total
zeytin_gpu_usage_total
system_cpu_percent
system_memory_percent
gpu_available
```

### Log Dosyaları
```bash
# Uygulama logları
docker-compose logs app

# Nginx logları
docker-compose logs nginx

# Sistem logları
tail -f /var/log/zeytin-monitor.log
tail -f /var/log/zeytin-backup.log
```

### Health Check Endpoints
```bash
# Basit health check
curl http://localhost:8000/health

# Detaylı sistem durumu (admin gerekli)
curl -H "Authorization: Bearer <admin_token>" \
     http://localhost:8000/admin/sistem-durumu
```

## 🔧 Yapılandırma

### Environment Variables
Tüm yapılandırma `.env` dosyasında:

```bash
# Güvenlik
SECRET_KEY=your-super-secret-key-min-32-chars
DEBUG=False
ENVIRONMENT=production

# Veritabanı
DATABASE_URL=data/analiz.db

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600

# Backup
BACKUP_RETENTION_DAYS=30
REMOTE_BACKUP_ENABLED=false

# Email Bildirimleri
EMAIL_ENABLED=false
SMTP_HOST=smtp.gmail.com
EMAIL_TO=admin@example.com
```

### Nginx Yapılandırması
```bash
# Rate limiting ayarları
nginx/nginx.conf

# SSL sertifikaları
nginx/ssl/cert.pem
nginx/ssl/key.pem
```

### Fail2ban Yapılandırması
```bash
# Jail yapılandırması
/etc/fail2ban/jail.local

# Banned IP'ler
nginx/conf.d/blocked_ips.conf
```

## 🚨 Sorun Giderme

### Yaygın Problemler

#### 1. Port 80/443 Kullanımda
```bash
# Hangi servis kullanıyor
sudo netstat -tulpn | grep :80

# Apache'yi durdur
sudo systemctl stop apache2
sudo systemctl disable apache2

# Nginx'i yeniden başlat
docker-compose restart nginx
```

#### 2. GPU Tanınmıyor
```bash
# NVIDIA driver kontrolü
nvidia-smi

# CUDA kontrolü
nvcc --version

# GPU setup scriptini çalıştır
sudo bash scripts/cuda_setup.sh
```

#### 3. Dosya Yükleme Hatası
```bash
# Nginx dosya boyutu limiti
# nginx/nginx.conf içinde:
client_max_body_size 500M;

# Disk alanı kontrolü
df -h

# Klasör izinleri
sudo chown -R 1000:1000 data/
```

#### 4. SSL Sertifika Hatası
```bash
# Sertifikaları yeniden oluştur
sudo rm -rf nginx/ssl/*
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/key.pem \
    -out nginx/ssl/cert.pem \
    -subj "/C=TR/ST=Turkey/L=Istanbul/O=ZeytinAnaliz/CN=localhost"

# Nginx'i yeniden başlat
docker-compose restart nginx
```

### Log Analizi
```bash
# Uygulama hata logları
docker-compose logs app | grep -i error

# Nginx hata logları
docker-compose logs nginx | grep -i error

# Sistem logları
journalctl -u zeytin-analiz.service -f

# Disk kullanımı
du -sh data/analizler/*

# Bellek kullanımı
free -h
docker stats
```

## 🔄 Güncelleme

### Uygulama Güncellemesi
```bash
# Yeni kodu çek
git pull origin main

# Yedek oluştur
bash scripts/backup_cron.sh

# Servisleri durdur
docker-compose down

# Yeniden oluştur ve başlat
docker-compose build --no-cache
docker-compose up -d

# Durumu kontrol et
docker-compose ps
```

### Sistem Güncellemesi
```bash
# Sistem paketleri
sudo apt update && sudo apt upgrade -y

# Docker güncellemesi
sudo apt install docker-ce docker-ce-cli containerd.io

# Nginx güncellemesi
sudo apt install nginx
```

## 📚 Dokümantasyon

- **[API Dokümantasyonu](docs/API_DOCUMENTATION.md)**: Detaylı API referansı
- **[Kullanıcı Kılavuzu](docs/USER_GUIDE.md)**: Web arayüzü kullanım kılavuzu

## 🤝 Katkıda Bulunma

1. Fork edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakın.

## 🆘 Destek

### Teknik Destek
1. Log dosyalarını kontrol edin
2. GitHub Issues bölümünde sorun bildirin
3. Sistem gereksinimlerini kontrol edin
4. GPU driver'larını güncelleyin

### Performance İpuçları
- **GPU Kullanımı**: Büyük dosyalar için GPU modu tercih edin
- **SSD Kullanımı**: Hızlı disk I/O için SSD kullanın
- **RAM**: En az 16GB RAM önerilir
- **Network**: Yüksek bant genişliği dosya yükleme için önemli

## 🎯 Roadmap

### v1.1 (Planlanan)
- [ ] Real-time analiz streaming
- [ ] Çoklu dil desteği
- [ ] Advanced AI modelleri
- [ ] Mobile app desteği

### v1.2 (Gelecek)
- [ ] Kubernetes deployment
- [ ] Advanced analytics dashboard
- [ ] Machine learning model training
- [ ] IoT sensor entegrasyonu

---

## ⚠️ Önemli Notlar

### Production Kullanımı İçin
- ✅ `.env` dosyasındaki `SECRET_KEY`'i değiştirin
- ✅ Varsayılan admin şifresini değiştirin
- ✅ Geçerli SSL sertifikaları kullanın
- ✅ Firewall kurallarını gözden geçirin
- ✅ Düzenli backup stratejisi oluşturun
- ✅ Monitoring ve alerting kurun

### Güvenlik Kontrol Listesi
- [ ] SECRET_KEY production değeri
- [ ] Admin şifresi değiştirildi
- [ ] SSL sertifikaları geçerli
- [ ] Firewall aktif
- [ ] Fail2ban yapılandırıldı
- [ ] Rate limiting aktif
- [ ] Log rotation ayarlandı
- [ ] Backup testi yapıldı

**🫒 Zeytin Ağacı Analiz Sistemi ile modern tarımın geleceğini keşfedin!**