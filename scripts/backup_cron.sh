#!/bin/bash

# Zeytin Ağacı Analiz Sistemi - Otomatik Yedekleme Scripti
# Cron job ile günlük çalıştırılması için tasarlanmıştır

set -e

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

# Yapılandırma - Environment variable'lardan al
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DATA_DIR="${DATA_PATH:-/opt/zeytin-analiz/data}"
APP_DIR="${APP_DIR:-/opt/zeytin-analiz}"
LOG_FILE="${LOG_FILE:-/var/log/zeytin-backup.log}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
COMPRESSION="${BACKUP_COMPRESSION:-true}"

# Email ayarları
EMAIL_ENABLED="${EMAIL_ENABLED:-false}"
EMAIL_TO="${EMAIL_TO:-}"
EMAIL_FROM="${EMAIL_FROM:-}"

# Uzak yedekleme ayarları
REMOTE_BACKUP_ENABLED="${REMOTE_BACKUP_ENABLED:-false}"
REMOTE_TYPE="${REMOTE_TYPE:-sftp}"
REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_USER="${REMOTE_USER:-}"
REMOTE_PATH="${REMOTE_PATH:-}"
S3_BUCKET="${S3_BUCKET:-}"
S3_PREFIX="${S3_PREFIX:-zeytin-backups}"

# Log fonksiyonu
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Email bildirimi gönder
send_notification() {
    local status="$1"
    local message="$2"
    
    if [ "$EMAIL_ENABLED" = "true" ] && [ -n "$EMAIL_TO" ]; then
        local subject="Zeytin Analiz Sistemi - Yedekleme $status"
        echo "$message" | mail -s "$subject" -r "$EMAIL_FROM" "$EMAIL_TO" 2>/dev/null || {
            log_message "Email bildirimi gönderilemedi"
        }
    fi
}

# Disk alanı kontrolü
check_disk_space() {
    local required_space_gb=2
    local available_space_kb=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4}')
    local available_space_gb=$((available_space_kb / 1024 / 1024))
    
    if [ "$available_space_gb" -lt "$required_space_gb" ]; then
        print_warning "Yetersiz disk alanı: ${available_space_gb}GB mevcut, ${required_space_gb}GB gerekli"
        log_message "UYARI: Yetersiz disk alanı"
        
        # Eski yedekleri temizle
        cleanup_old_backups
        
        # Tekrar kontrol et
        available_space_kb=$(df "$BACKUP_DIR" | awk 'NR==2 {print $4}')
        available_space_gb=$((available_space_kb / 1024 / 1024))
        
        if [ "$available_space_gb" -lt "$required_space_gb" ]; then
            print_error "Disk alanı hala yetersiz"
            log_message "HATA: Disk alanı yetersiz, yedekleme iptal edildi"
            send_notification "HATA" "Disk alanı yetersiz: ${available_space_gb}GB"
            return 1
        fi
    fi
    
    return 0
}

# Servis durumu kontrolü
check_service_status() {
    if docker-compose -f "$APP_DIR/docker-compose.yml" ps 2>/dev/null | grep -q "Up"; then
        log_message "Servisler çalışıyor"
        return 0
    else
        print_warning "Servisler çalışmıyor"
        log_message "UYARI: Servisler çalışmıyor"
        return 1
    fi
}

# Veritabanı tutarlılık kontrolü
check_database_integrity() {
    local db_path="$DATA_DIR/analiz.db"
    
    if [ -f "$db_path" ]; then
        if sqlite3 "$db_path" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
            log_message "Veritabanı tutarlılık kontrolü: OK"
            return 0
        else
            print_error "Veritabanı tutarlılık hatası"
            log_message "HATA: Veritabanı tutarlılık hatası"
            return 1
        fi
    else
        print_warning "Veritabanı dosyası bulunamadı: $db_path"
        log_message "UYARI: Veritabanı dosyası bulunamadı"
        return 1
    fi
}

# Ana yedekleme fonksiyonu
create_backup() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local backup_name="zeytin_analiz_auto_${timestamp}"
    local backup_path="$BACKUP_DIR/${backup_name}.tar"
    
    print_status "Otomatik yedekleme başlatılıyor..."
    log_message "Otomatik yedekleme başlatıldı: $backup_name"
    
    # Backup dizinini oluştur
    mkdir -p "$BACKUP_DIR"
    
    # Geçici dizin oluştur
    local temp_dir=$(mktemp -d)
    local backup_temp="$temp_dir/$backup_name"
    mkdir -p "$backup_temp"
    
    # Yedeklenecek dosyaları kopyala
    print_status "Dosyalar kopyalanıyor..."
    
    # Veri dizini
    if [ -d "$DATA_DIR" ]; then
        cp -r "$DATA_DIR" "$backup_temp/" 2>/dev/null || {
            log_message "UYARI: Veri dizini kopyalanamadı"
        }
    fi
    
    # Konfigürasyon dosyaları
    local config_files=(
        "$APP_DIR/.env"
        "$APP_DIR/docker-compose.yml"
        "$APP_DIR/nginx/nginx.conf"
        "$APP_DIR/requirements.txt"
    )
    
    mkdir -p "$backup_temp/config"
    for config_file in "${config_files[@]}"; do
        if [ -f "$config_file" ]; then
            cp "$config_file" "$backup_temp/config/" 2>/dev/null || {
                log_message "UYARI: $config_file kopyalanamadı"
            }
        fi
    done
    
    # Metadata dosyası oluştur
    cat > "$backup_temp/backup_info.txt" << EOF
Zeytin Ağacı Analiz Sistemi - Yedek Bilgileri
=============================================

Yedek Tarihi: $(date)
Yedek Türü: Otomatik
Sistem: $(uname -a)
Docker Sürümü: $(docker --version 2>/dev/null || echo "Bilinmiyor")
Disk Kullanımı: $(df -h / | awk 'NR==2{print $5}')
Bellek Kullanımı: $(free -h | awk 'NR==2{print $3"/"$2}')

Yedeklenen Dizinler:
- Veri dizini: $DATA_DIR
- Konfigürasyon dosyaları

Servis Durumu:
$(docker-compose -f "$APP_DIR/docker-compose.yml" ps 2>/dev/null || echo "Docker Compose bilgisi alınamadı")
EOF
    
    # Tar arşivi oluştur
    print_status "Arşiv oluşturuluyor..."
    if tar -cf "$backup_path" -C "$temp_dir" "$backup_name" 2>/dev/null; then
        
        # Sıkıştırma
        if [ "$COMPRESSION" = "true" ]; then
            print_status "Sıkıştırılıyor..."
            gzip "$backup_path"
            backup_path="${backup_path}.gz"
        fi
        
        local backup_size=$(du -h "$backup_path" | cut -f1)
        print_success "Yedek oluşturuldu: $backup_path ($backup_size)"
        log_message "Yedek başarıyla oluşturuldu: $backup_path ($backup_size)"
        
        # Uzak yedekleme
        if [ "$REMOTE_BACKUP_ENABLED" = "true" ]; then
            upload_to_remote "$backup_path"
        fi
        
        # Geçici dizini temizle
        rm -rf "$temp_dir"
        
        echo "$backup_path"
        return 0
    else
        print_error "Yedek oluşturma hatası"
        log_message "HATA: Yedek oluşturulamadı"
        rm -rf "$temp_dir"
        return 1
    fi
}

# Uzak sunucuya yükleme
upload_to_remote() {
    local backup_path="$1"
    local filename=$(basename "$backup_path")
    
    print_status "Uzak sunucuya yükleniyor..."
    log_message "Uzak yükleme başlatıldı: $filename"
    
    case "$REMOTE_TYPE" in
        "sftp")
            if [ -n "$REMOTE_HOST" ] && [ -n "$REMOTE_USER" ] && [ -n "$REMOTE_PATH" ]; then
                if scp -o StrictHostKeyChecking=no -o ConnectTimeout=30 "$backup_path" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/" 2>/dev/null; then
                    print_success "SFTP yükleme başarılı"
                    log_message "SFTP yükleme başarılı: $filename"
                else
                    print_error "SFTP yükleme hatası"
                    log_message "HATA: SFTP yükleme başarısız: $filename"
                fi
            else
                log_message "UYARI: SFTP ayarları eksik"
            fi
            ;;
        "s3")
            if [ -n "$S3_BUCKET" ] && command -v aws &> /dev/null; then
                if aws s3 cp "$backup_path" "s3://${S3_BUCKET}/${S3_PREFIX}/$filename" 2>/dev/null; then
                    print_success "S3 yükleme başarılı"
                    log_message "S3 yükleme başarılı: $filename"
                else
                    print_error "S3 yükleme hatası"
                    log_message "HATA: S3 yükleme başarısız: $filename"
                fi
            else
                log_message "UYARI: S3 ayarları eksik veya AWS CLI bulunamadı"
            fi
            ;;
        *)
            log_message "UYARI: Bilinmeyen uzak yedekleme türü: $REMOTE_TYPE"
            ;;
    esac
}

# Eski yedekleri temizle
cleanup_old_backups() {
    print_status "Eski yedekler temizleniyor..."
    log_message "Eski yedek temizleme başlatıldı"
    
    local deleted_count=0
    local total_size_freed=0
    
    # Local yedekleri temizle
    while IFS= read -r -d '' file; do
        local file_size=$(stat -c%s "$file" 2>/dev/null || echo 0)
        if rm "$file" 2>/dev/null; then
            print_status "Silindi: $(basename "$file")"
            log_message "Eski yedek silindi: $(basename "$file")"
            ((deleted_count++))
            total_size_freed=$((total_size_freed + file_size))
        fi
    done < <(find "$BACKUP_DIR" -name "zeytin_analiz_*.tar*" -type f -mtime +$RETENTION_DAYS -print0 2>/dev/null)
    
    if [ $deleted_count -gt 0 ]; then
        local size_freed_mb=$((total_size_freed / 1024 / 1024))
        print_success "$deleted_count eski yedek temizlendi (${size_freed_mb}MB alan açıldı)"
        log_message "$deleted_count eski yedek temizlendi (${size_freed_mb}MB)"
    else
        print_status "Temizlenecek eski yedek bulunamadı"
        log_message "Temizlenecek eski yedek bulunamadı"
    fi
}

# Yedek doğrulama
verify_backup() {
    local backup_path="$1"
    
    print_status "Yedek doğrulanıyor..."
    
    if [ ! -f "$backup_path" ]; then
        log_message "HATA: Yedek dosyası bulunamadı: $backup_path"
        return 1
    fi
    
    # Dosya bütünlüğü kontrolü
    if [[ "$backup_path" == *.gz ]]; then
        if gzip -t "$backup_path" 2>/dev/null; then
            log_message "Yedek dosyası bütünlük kontrolü: OK"
            return 0
        else
            log_message "HATA: Yedek dosyası bozuk"
            return 1
        fi
    else
        if tar -tf "$backup_path" >/dev/null 2>&1; then
            log_message "Yedek dosyası bütünlük kontrolü: OK"
            return 0
        else
            log_message "HATA: Yedek dosyası bozuk"
            return 1
        fi
    fi
}

# Yedek istatistikleri
backup_statistics() {
    local backup_count=$(find "$BACKUP_DIR" -name "zeytin_analiz_*.tar*" -type f 2>/dev/null | wc -l)
    local total_size=$(find "$BACKUP_DIR" -name "zeytin_analiz_*.tar*" -type f -exec du -cb {} + 2>/dev/null | tail -1 | cut -f1)
    local total_size_mb=$((total_size / 1024 / 1024))
    
    log_message "Yedek istatistikleri: $backup_count dosya, ${total_size_mb}MB toplam boyut"
}

# Ana fonksiyon
main() {
    log_message "=== Otomatik Yedekleme Başlatıldı ==="
    
    # Ön kontroller
    if ! check_disk_space; then
        send_notification "HATA" "Disk alanı yetersiz"
        exit 1
    fi
    
    if ! check_database_integrity; then
        send_notification "UYARI" "Veritabanı tutarlılık problemi tespit edildi"
    fi
    
    check_service_status
    
    # Yedekleme
    if backup_path=$(create_backup); then
        
        # Yedek doğrulama
        if verify_backup "$backup_path"; then
            print_success "Yedek doğrulandı"
        else
            print_warning "Yedek doğrulama başarısız"
            log_message "UYARI: Yedek doğrulama başarısız"
        fi
        
        # Eski yedekleri temizle
        cleanup_old_backups
        
        # İstatistikler
        backup_statistics
        
        # Başarı bildirimi
        local backup_count=$(find "$BACKUP_DIR" -name "zeytin_analiz_*.tar*" -type f 2>/dev/null | wc -l)
        local message="Yedekleme başarıyla tamamlandı.
Yedek dosyası: $(basename "$backup_path")
Toplam yedek sayısı: $backup_count
Disk kullanımı: $(df -h "$BACKUP_DIR" | awk 'NR==2{print $5}')"
        
        print_success "Yedekleme tamamlandı"
        log_message "Yedekleme başarıyla tamamlandı"
        send_notification "BAŞARILI" "$message"
        
        log_message "=== Otomatik Yedekleme Tamamlandı ==="
        exit 0
    else
        local message="Yedekleme başarısız oldu. Log dosyasını kontrol edin: $LOG_FILE"
        print_error "Yedekleme başarısız"
        log_message "HATA: Yedekleme başarısız"
        send_notification "HATA" "$message"
        
        log_message "=== Otomatik Yedekleme Başarısız ==="
        exit 1
    fi
}

# Kullanım bilgisi
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Zeytin Ağacı Analiz Sistemi - Otomatik Yedekleme Scripti"
    echo
    echo "Kullanım: $0 [seçenekler]"
    echo
    echo "Seçenekler:"
    echo "  --help, -h    Bu yardım mesajını göster"
    echo "  --test        Test modu (yedek oluşturmadan kontrolleri yap)"
    echo "  --cleanup     Sadece eski yedekleri temizle"
    echo
    echo "Environment Variables:"
    echo "  BACKUP_DIR              Yedek dizini (varsayılan: /backups)"
    echo "  DATA_PATH               Veri dizini (varsayılan: /opt/zeytin-analiz/data)"
    echo "  BACKUP_RETENTION_DAYS   Yedek saklama süresi (varsayılan: 30)"
    echo "  EMAIL_ENABLED           Email bildirimi (varsayılan: false)"
    echo "  REMOTE_BACKUP_ENABLED   Uzak yedekleme (varsayılan: false)"
    echo
    echo "Cron örneği (günlük 02:00):"
    echo "0 2 * * * $0 >> /var/log/zeytin-backup.log 2>&1"
    exit 0
fi

# Test modu
if [ "$1" = "--test" ]; then
    echo "Test modu - sadece kontroller yapılıyor..."
    check_disk_space
    check_database_integrity
    check_service_status
    echo "Test tamamlandı"
    exit 0
fi

# Sadece temizlik
if [ "$1" = "--cleanup" ]; then
    echo "Eski yedekler temizleniyor..."
    cleanup_old_backups
    backup_statistics
    exit 0
fi

# Ana fonksiyonu çalıştır
main "$@"