#!/bin/bash

# Zeytin Ağacı Analiz Sistemi - Deployment Script
# DigitalOcean Ubuntu 22.04 LTS için

set -e

echo "🫒 Zeytin Ağacı Analiz Sistemi Deployment Başlatılıyor..."

# Renkli çıktı için
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonksiyonlar
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Sistem güncellemesi
print_status "Sistem güncelleniyor..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Gerekli paketleri yükle
print_status "Gerekli sistem paketleri yükleniyor..."
sudo apt-get install -y \
    curl \
    wget \
    git \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    htop \
    nano \
    unzip

# Docker kurulumu
print_status "Docker kurulumu başlatılıyor..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
    sudo usermod -aG docker $USER
    print_success "Docker kuruldu"
else
    print_warning "Docker zaten kurulu"
fi

# Docker Compose kurulumu
print_status "Docker Compose kurulumu başlatılıyor..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    print_success "Docker Compose kuruldu"
else
    print_warning "Docker Compose zaten kurulu"
fi

# Python 3.10 kurulumu
print_status "Python 3.10 kurulumu kontrol ediliyor..."
if ! python3.10 --version &> /dev/null; then
    sudo add-apt-repository ppa:deadsnakes/ppa -y
    sudo apt-get update
    sudo apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip
    print_success "Python 3.10 kuruldu"
else
    print_warning "Python 3.10 zaten kurulu"
fi

# Uygulama dizinini oluştur
APP_DIR="/opt/zeytin-analiz"
print_status "Uygulama dizini oluşturuluyor: $APP_DIR"
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR

# Mevcut dizindeki dosyaları kopyala
print_status "Uygulama dosyları kopyalanıyor..."
cp -r . $APP_DIR/
cd $APP_DIR

# Data ve models dizinlerini oluştur
print_status "Veri dizinleri oluşturuluyor..."
mkdir -p data/analizler
mkdir -p models
mkdir -p nginx/ssl

# SSL sertifikaları oluştur (self-signed)
print_status "SSL sertifikaları oluşturuluyor..."
if [ ! -f nginx/ssl/cert.pem ]; then
    sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/key.pem \
        -out nginx/ssl/cert.pem \
        -subj "/C=TR/ST=Turkey/L=Istanbul/O=ZeytinAnaliz/CN=localhost"
    print_success "SSL sertifikaları oluşturuldu"
fi

# Firewall ayarları
print_status "Firewall ayarları yapılandırılıyor..."
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force reload
print_success "Firewall ayarlandı"

# Fail2Ban ayarları
print_status "Fail2Ban ayarları yapılandırılıyor..."
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
print_success "Fail2Ban ayarlandı"

# YOLOv8 modelini indir
print_status "YOLOv8 modeli indiriliyor..."
if [ ! -f models/yolov8n.pt ]; then
    cd models
    wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
    cd ..
    print_success "YOLOv8 modeli indirildi"
fi

# Docker imajlarını oluştur
print_status "Docker imajları oluşturuluyor..."
docker-compose build --no-cache

# Servisleri başlat
print_status "Servisler başlatılıyor..."
docker-compose up -d

# Sistem servisini oluştur
print_status "Systemd servisi oluşturuluyor..."
sudo tee /etc/systemd/system/zeytin-analiz.service > /dev/null <<EOF
[Unit]
Description=Zeytin Ağacı Analiz Sistemi
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable zeytin-analiz.service
print_success "Systemd servisi oluşturuldu"

# Log rotation ayarları
print_status "Log rotation ayarları yapılandırılıyor..."
sudo tee /etc/logrotate.d/zeytin-analiz > /dev/null <<EOF
/var/lib/docker/containers/*/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    copytruncate
    maxage 7
}
EOF

# Sistem optimizasyonları
print_status "Sistem optimizasyonları yapılıyor..."

# Docker logging ayarları
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    }
}
EOF

sudo systemctl restart docker

# Sysctl optimizasyonları
sudo tee -a /etc/sysctl.conf > /dev/null <<EOF

# Zeytin Analiz Sistemi optimizasyonları
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 10
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 10
vm.swappiness = 10
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
EOF

sudo sysctl -p

# Monitoring scriptini oluştur
print_status "Monitoring scripti oluşturuluyor..."
sudo tee /usr/local/bin/zeytin-monitor.sh > /dev/null <<'EOF'
#!/bin/bash

# Sistem durumunu kontrol et
check_system() {
    echo "=== Zeytin Analiz Sistemi Durum Raporu ==="
    echo "Tarih: $(date)"
    echo
    
    echo "Docker Servisleri:"
    docker-compose -f /opt/zeytin-analiz/docker-compose.yml ps
    echo
    
    echo "Sistem Kaynakları:"
    echo "CPU Kullanımı: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
    echo "RAM Kullanımı: $(free | grep Mem | awk '{printf("%.1f%%\n", $3*100/$2)}')"
    echo "Disk Kullanımı: $(df -h / | awk 'NR==2{printf "%s\n", $5}')"
    echo
    
    echo "Port Durumu:"
    ss -tulpn | grep -E ':80|:443|:8000'
    echo
}

check_system
EOF

sudo chmod +x /usr/local/bin/zeytin-monitor.sh

# Cron job ekle
print_status "Cron job ekleniyor..."
(crontab -l 2>/dev/null; echo "0 */6 * * * /usr/local/bin/zeytin-monitor.sh >> /var/log/zeytin-monitor.log 2>&1") | crontab -

# Servis durumunu kontrol et
print_status "Servis durumları kontrol ediliyor..."
sleep 10

if docker-compose ps | grep -q "Up"; then
    print_success "Servisler başarıyla başlatıldı"
else
    print_error "Servis başlatma hatası"
    docker-compose logs
    exit 1
fi

# Son bilgiler
SERVER_IP=$(curl -s ifconfig.me)
print_success "Deployment tamamlandı!"
echo
echo "=== BAĞLANTI BİLGİLERİ ==="
echo "HTTP:  http://$SERVER_IP"
echo "HTTPS: https://$SERVER_IP"
echo "Local: http://localhost"
echo
echo "=== YÖNETİM KOMUTLARI ==="
echo "Logları görüntüle:    docker-compose -f $APP_DIR/docker-compose.yml logs -f"
echo "Servisleri yeniden başlat: docker-compose -f $APP_DIR/docker-compose.yml restart"
echo "Servisleri durdur:    docker-compose -f $APP_DIR/docker-compose.yml down"
echo "Servisleri başlat:    docker-compose -f $APP_DIR/docker-compose.yml up -d"
echo "Sistem durumu:        /usr/local/bin/zeytin-monitor.sh"
echo
echo "=== GÜVENLİK NOTLARı ==="
echo "- SSL sertifikası self-signed olarak oluşturuldu"
echo "- Production ortamında geçerli SSL sertifikası kullanın"
echo "- Düzenli sistem güncellemelerini yapmayı unutmayın"
echo "- Log dosyalarını düzenli kontrol edin"
echo
print_success "🫒 Zeytin Ağacı Analiz Sistemi hazır!"