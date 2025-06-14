#!/bin/bash

# Zeytin Ağacı Analiz Sistemi - Production Deployment Script
# Ubuntu 22.04 LTS için

set -e

echo "🫒 Zeytin Ağacı Analiz Sistemi Production Deployment Başlatılıyor..."

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

# Yapılandırma
APP_DIR="/opt/zeytin-analiz"
BACKUP_DIR="/backups"
LOG_FILE="/var/log/zeytin-deploy.log"

# Log fonksiyonu
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Root kontrolü
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "Bu script root yetkileri ile çalıştırılmalıdır"
        exit 1
    fi
}

# Sistem güncellemesi
update_system() {
    print_status "Sistem güncelleniyor..."
    log_message "Sistem güncellemesi başlatıldı"
    
    apt-get update -y
    apt-get upgrade -y
    apt-get install -y curl wget git software-properties-common apt-transport-https ca-certificates gnupg lsb-release
    
    print_success "Sistem güncellendi"
    log_message "Sistem güncellemesi tamamlandı"
}

# Docker kurulumu
install_docker() {
    print_status "Docker kurulumu kontrol ediliyor..."
    
    if ! command -v docker &> /dev/null; then
        print_status "Docker kuruluyor..."
        log_message "Docker kurulumu başlatıldı"
        
        # Docker GPG key
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
        
        # Docker repository
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
        
        # Docker kurulumu
        apt-get update
        apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        
        # Docker servisini başlat
        systemctl start docker
        systemctl enable docker
        
        # Kullanıcıyı docker grubuna ekle
        usermod -aG docker $SUDO_USER 2>/dev/null || true
        
        print_success "Docker kuruldu"
        log_message "Docker kurulumu tamamlandı"
    else
        print_warning "Docker zaten kurulu"
        log_message "Docker zaten mevcut"
    fi
}

# Docker Compose kurulumu
install_docker_compose() {
    print_status "Docker Compose kurulumu kontrol ediliyor..."
    
    if ! command -v docker-compose &> /dev/null; then
        print_status "Docker Compose kuruluyor..."
        log_message "Docker Compose kurulumu başlatıldı"
        
        # En son sürümü al
        COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
        curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        
        print_success "Docker Compose kuruldu"
        log_message "Docker Compose kurulumu tamamlandı"
    else
        print_warning "Docker Compose zaten kurulu"
        log_message "Docker Compose zaten mevcut"
    fi
}

# Nginx kurulumu
install_nginx() {
    print_status "Nginx kurulumu kontrol ediliyor..."
    
    if ! command -v nginx &> /dev/null; then
        print_status "Nginx kuruluyor..."
        log_message "Nginx kurulumu başlatıldı"
        
        apt-get install -y nginx
        systemctl enable nginx
        
        print_success "Nginx kuruldu"
        log_message "Nginx kurulumu tamamlandı"
    else
        print_warning "Nginx zaten kurulu"
        log_message "Nginx zaten mevcut"
    fi
}

# Fail2ban kurulumu
install_fail2ban() {
    print_status "Fail2ban kurulumu..."
    log_message "Fail2ban kurulumu başlatıldı"
    
    apt-get install -y fail2ban
    
    # Fail2ban yapılandırması
    cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
backend = auto

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 5

[nginx-botsearch]
enabled = true
filter = nginx-botsearch
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
EOF

    systemctl enable fail2ban
    systemctl start fail2ban
    
    print_success "Fail2ban kuruldu ve yapılandırıldı"
    log_message "Fail2ban kurulumu tamamlandı"
}

# Firewall ayarları
setup_firewall() {
    print_status "Firewall ayarları yapılandırılıyor..."
    log_message "Firewall yapılandırması başlatıldı"
    
    # UFW kurulumu
    apt-get install -y ufw
    
    # Varsayılan kurallar
    ufw --force reset
    ufw default deny incoming
    ufw default allow outgoing
    
    # İzin verilen portlar
    ufw allow ssh
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # UFW'yi etkinleştir
    ufw --force enable
    
    print_success "Firewall yapılandırıldı"
    log_message "Firewall yapılandırması tamamlandı"
}

# Uygulama dizinini hazırla
setup_app_directory() {
    print_status "Uygulama dizini hazırlanıyor..."
    log_message "Uygulama dizini kurulumu başlatıldı"
    
    # Dizinleri oluştur
    mkdir -p "$APP_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p /var/log/zeytin-analiz
    
    # Mevcut dizindeki dosyaları kopyala
    if [ -f "docker-compose.yml" ]; then
        print_status "Uygulama dosyaları kopyalanıyor..."
        cp -r . "$APP_DIR/"
        cd "$APP_DIR"
    else
        print_error "docker-compose.yml bulunamadı. Script'i proje dizininde çalıştırın."
        exit 1
    fi
    
    # .env dosyasını oluştur
    if [ ! -f ".env" ]; then
        print_status ".env dosyası oluşturuluyor..."
        cp .env.example .env
        
        # Güvenli secret key oluştur
        SECRET_KEY=$(openssl rand -base64 32)
        sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
        sed -i "s/ENVIRONMENT=.*/ENVIRONMENT=production/" .env
        sed -i "s/DEBUG=.*/DEBUG=False/" .env
        
        print_warning ".env dosyası oluşturuldu. Lütfen ayarları kontrol edin!"
    fi
    
    # İzinleri ayarla
    chown -R $SUDO_USER:$SUDO_USER "$APP_DIR" 2>/dev/null || true
    chmod -R 755 "$APP_DIR"
    
    print_success "Uygulama dizini hazırlandı"
    log_message "Uygulama dizini kurulumu tamamlandı"
}

# SSL sertifikaları oluştur
setup_ssl() {
    print_status "SSL sertifikaları kontrol ediliyor..."
    log_message "SSL kurulumu başlatıldı"
    
    SSL_DIR="$APP_DIR/nginx/ssl"
    mkdir -p "$SSL_DIR"
    
    if [ ! -f "$SSL_DIR/cert.pem" ] || [ ! -f "$SSL_DIR/key.pem" ]; then
        print_status "Self-signed SSL sertifikaları oluşturuluyor..."
        
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$SSL_DIR/key.pem" \
            -out "$SSL_DIR/cert.pem" \
            -subj "/C=TR/ST=Turkey/L=Istanbul/O=ZeytinAnaliz/CN=localhost" \
            2>/dev/null
        
        chmod 600 "$SSL_DIR/key.pem"
        chmod 644 "$SSL_DIR/cert.pem"
        
        print_success "SSL sertifikaları oluşturuldu"
        print_warning "Production'da geçerli SSL sertifikaları kullanın!"
    else
        print_warning "SSL sertifikaları zaten mevcut"
    fi
    
    log_message "SSL kurulumu tamamlandı"
}

# Docker imajlarını oluştur ve başlat
deploy_application() {
    print_status "Uygulama deploy ediliyor..."
    log_message "Uygulama deployment başlatıldı"
    
    cd "$APP_DIR"
    
    # Eski container'ları durdur
    docker-compose down 2>/dev/null || true
    
    # İmajları oluştur
    print_status "Docker imajları oluşturuluyor..."
    docker-compose build --no-cache
    
    # Servisleri başlat
    print_status "Servisler başlatılıyor..."
    docker-compose up -d
    
    # Servislerin başlamasını bekle
    print_status "Servislerin başlaması bekleniyor..."
    sleep 30
    
    # Sağlık kontrolü
    if docker-compose ps | grep -q "Up"; then
        print_success "Servisler başarıyla başlatıldı"
        log_message "Servisler başarıyla başlatıldı"
    else
        print_error "Servis başlatma hatası"
        docker-compose logs
        log_message "Servis başlatma hatası"
        exit 1
    fi
}

# Systemd servisi oluştur
setup_systemd_service() {
    print_status "Systemd servisi oluşturuluyor..."
    log_message "Systemd servis kurulumu başlatıldı"
    
    cat > /etc/systemd/system/zeytin-analiz.service << EOF
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
TimeoutStartSec=300
User=root

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable zeytin-analiz.service
    
    print_success "Systemd servisi oluşturuldu"
    log_message "Systemd servis kurulumu tamamlandı"
}

# Monitoring scriptleri kur
setup_monitoring() {
    print_status "Monitoring scriptleri kuruluyor..."
    log_message "Monitoring kurulumu başlatıldı"
    
    # Sistem durumu script'i
    cat > /usr/local/bin/zeytin-monitor.sh << 'EOF'
#!/bin/bash

# Zeytin Analiz Sistemi Monitoring

echo "=== Zeytin Analiz Sistemi Durum Raporu ==="
echo "Tarih: $(date)"
echo

echo "Docker Servisleri:"
cd /opt/zeytin-analiz
docker-compose ps
echo

echo "Sistem Kaynakları:"
echo "CPU Kullanımı: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
echo "RAM Kullanımı: $(free | grep Mem | awk '{printf("%.1f%%\n", $3*100/$2)}')"
echo "Disk Kullanımı: $(df -h / | awk 'NR==2{printf "%s\n", $5}')"
echo

echo "Port Durumu:"
ss -tulpn | grep -E ':80|:443|:8000'
echo

echo "Son 10 Log Satırı:"
docker-compose logs --tail=10
EOF

    chmod +x /usr/local/bin/zeytin-monitor.sh
    
    # Cron job ekle
    (crontab -l 2>/dev/null; echo "0 */6 * * * /usr/local/bin/zeytin-monitor.sh >> /var/log/zeytin-monitor.log 2>&1") | crontab -
    
    print_success "Monitoring scriptleri kuruldu"
    log_message "Monitoring kurulumu tamamlandı"
}

# Log rotation ayarları
setup_log_rotation() {
    print_status "Log rotation ayarları yapılandırılıyor..."
    log_message "Log rotation kurulumu başlatıldı"
    
    cat > /etc/logrotate.d/zeytin-analiz << 'EOF'
/var/log/zeytin-analiz/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    copytruncate
    create 644 root root
    maxage 30
}

/var/log/zeytin-*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    copytruncate
    create 644 root root
}
EOF

    print_success "Log rotation ayarlandı"
    log_message "Log rotation kurulumu tamamlandı"
}

# Sistem optimizasyonları
optimize_system() {
    print_status "Sistem optimizasyonları yapılıyor..."
    log_message "Sistem optimizasyonu başlatıldı"
    
    # Sysctl optimizasyonları
    cat >> /etc/sysctl.conf << 'EOF'

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
fs.file-max = 2097152
EOF

    sysctl -p
    
    # Docker daemon optimizasyonları
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json << 'EOF'
{
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "10m",
        "max-file": "3"
    },
    "storage-driver": "overlay2",
    "live-restore": true
}
EOF

    systemctl restart docker
    
    print_success "Sistem optimizasyonları tamamlandı"
    log_message "Sistem optimizasyonu tamamlandı"
}

# Son kontroller
final_checks() {
    print_status "Son kontroller yapılıyor..."
    log_message "Son kontroller başlatıldı"
    
    # Servis durumları
    echo "Docker durumu: $(systemctl is-active docker)"
    echo "Nginx durumu: $(systemctl is-active nginx)"
    echo "Fail2ban durumu: $(systemctl is-active fail2ban)"
    echo "UFW durumu: $(ufw status | head -1)"
    
    # Port kontrolü
    if ss -tulpn | grep -q ":80\|:443"; then
        print_success "Web portları açık"
    else
        print_warning "Web portları kapalı olabilir"
    fi
    
    # Health check
    sleep 10
    if curl -f http://localhost/health >/dev/null 2>&1; then
        print_success "Health check başarılı"
    else
        print_warning "Health check başarısız - servisler henüz hazır olmayabilir"
    fi
    
    log_message "Son kontroller tamamlandı"
}

# Ana fonksiyon
main() {
    log_message "=== Deployment başlatıldı ==="
    
    check_root
    update_system
    install_docker
    install_docker_compose
    install_nginx
    install_fail2ban
    setup_firewall
    setup_app_directory
    setup_ssl
    deploy_application
    setup_systemd_service
    setup_monitoring
    setup_log_rotation
    optimize_system
    final_checks
    
    # Sunucu IP'sini al
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "localhost")
    
    print_success "🎉 Deployment tamamlandı!"
    echo
    echo "=== BAĞLANTI BİLGİLERİ ==="
    echo "HTTP:  http://$SERVER_IP"
    echo "HTTPS: https://$SERVER_IP"
    echo "Local: http://localhost"
    echo
    echo "=== YÖNETİM KOMUTLARI ==="
    echo "Logları görüntüle:    docker-compose -f $APP_DIR/docker-compose.yml logs -f"
    echo "Servisleri yeniden başlat: systemctl restart zeytin-analiz"
    echo "Servisleri durdur:    systemctl stop zeytin-analiz"
    echo "Servisleri başlat:    systemctl start zeytin-analiz"
    echo "Sistem durumu:        /usr/local/bin/zeytin-monitor.sh"
    echo
    echo "=== GÜVENLİK NOTLARı ==="
    echo "- .env dosyasındaki ayarları kontrol edin"
    echo "- SSL sertifikalarını production için değiştirin"
    echo "- Düzenli sistem güncellemelerini yapmayı unutmayın"
    echo "- Log dosyalarını düzenli kontrol edin"
    echo "- Backup stratejinizi planlayın"
    echo
    
    log_message "=== Deployment tamamlandı ==="
    print_success "🫒 Zeytin Ağacı Analiz Sistemi hazır!"
}

# Script'i çalıştır
main "$@"