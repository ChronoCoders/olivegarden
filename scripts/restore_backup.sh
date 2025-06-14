#!/bin/bash

# Zeytin Ağacı Analiz Sistemi - Yedekten Geri Yükleme Scripti

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

# Yapılandırma
BACKUP_DIR="/backups"
RESTORE_DIR="/opt/zeytin-analiz"
LOG_FILE="/var/log/zeytin-restore.log"

# Log fonksiyonu
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

# Kullanım bilgisi
show_usage() {
    echo "Kullanım: $0 [SEÇENEKLER] YEDEK_DOSYASI"
    echo ""
    echo "Seçenekler:"
    echo "  -h, --help          Bu yardım mesajını göster"
    echo "  -l, --list          Mevcut yedekleri listele"
    echo "  -f, --force         Onay almadan geri yükle"
    echo "  -d, --dry-run       Sadece test et, gerçek geri yükleme yapma"
    echo ""
    echo "Örnekler:"
    echo "  $0 -l                                    # Yedekleri listele"
    echo "  $0 /backups/zeytin_analiz_20240101.tar.gz  # Belirtilen yedekten geri yükle"
    echo "  $0 -f backup.tar.gz                     # Onay almadan geri yükle"
}

# Mevcut yedekleri listele
list_backups() {
    print_status "Mevcut yedekler:"
    echo ""
    
    if [ ! -d "$BACKUP_DIR" ]; then
        print_warning "Yedek dizini bulunamadı: $BACKUP_DIR"
        return 1
    fi
    
    local backup_files=($(ls -1t "$BACKUP_DIR"/zeytin_analiz_*.tar.gz 2>/dev/null))
    
    if [ ${#backup_files[@]} -eq 0 ]; then
        print_warning "Hiç yedek dosyası bulunamadı"
        return 1
    fi
    
    printf "%-5s %-30s %-15s %-20s\n" "No" "Dosya Adı" "Boyut" "Tarih"
    printf "%-5s %-30s %-15s %-20s\n" "---" "----------" "-----" "-----"
    
    local i=1
    for backup_file in "${backup_files[@]}"; do
        local filename=$(basename "$backup_file")
        local size=$(du -h "$backup_file" | cut -f1)
        local date=$(stat -c %y "$backup_file" | cut -d' ' -f1,2 | cut -d'.' -f1)
        
        printf "%-5s %-30s %-15s %-20s\n" "$i" "$filename" "$size" "$date"
        ((i++))
    done
    
    echo ""
    print_status "Toplam ${#backup_files[@]} yedek dosyası bulundu"
}

# Yedek dosyası doğrulama
validate_backup() {
    local backup_path="$1"
    
    print_status "Yedek dosyası doğrulanıyor..."
    
    # Dosya var mı?
    if [ ! -f "$backup_path" ]; then
        print_error "Yedek dosyası bulunamadı: $backup_path"
        return 1
    fi
    
    # Dosya geçerli bir tar.gz mi?
    if ! tar -tzf "$backup_path" >/dev/null 2>&1; then
        print_error "Geçersiz yedek dosyası (tar.gz formatında değil)"
        return 1
    fi
    
    # İçerik kontrolü
    local contents=$(tar -tzf "$backup_path" | head -10)
    if ! echo "$contents" | grep -q "data/"; then
        print_warning "Yedek dosyasında veri dizini bulunamadı"
    fi
    
    print_success "Yedek dosyası doğrulandı"
    return 0
}

# Mevcut sistem yedeği
backup_current_system() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local current_backup="$BACKUP_DIR/zeytin_analiz_pre_restore_${timestamp}.tar.gz"
    
    print_status "Mevcut sistem yedekleniyor..."
    
    if tar -czf "$current_backup" \
        -C "$(dirname "$RESTORE_DIR")" "$(basename "$RESTORE_DIR")" \
        2>/dev/null; then
        
        print_success "Mevcut sistem yedeklendi: $current_backup"
        log_message "Geri yükleme öncesi sistem yedeği: $current_backup"
        echo "$current_backup"
        return 0
    else
        print_error "Mevcut sistem yedeklenemedi"
        return 1
    fi
}

# Servisleri durdur
stop_services() {
    print_status "Servisler durduruluyor..."
    
    if docker-compose -f "$RESTORE_DIR/docker-compose.yml" down 2>/dev/null; then
        print_success "Servisler durduruldu"
        log_message "Servisler durduruldu"
        return 0
    else
        print_warning "Servisler durdurulamadı veya zaten durdurulmuş"
        return 0
    fi
}

# Servisleri başlat
start_services() {
    print_status "Servisler başlatılıyor..."
    
    if docker-compose -f "$RESTORE_DIR/docker-compose.yml" up -d 2>/dev/null; then
        print_success "Servisler başlatıldı"
        log_message "Servisler başlatıldı"
        
        # Servis durumunu kontrol et
        sleep 10
        if docker-compose -f "$RESTORE_DIR/docker-compose.yml" ps | grep -q "Up"; then
            print_success "Servisler başarıyla çalışıyor"
            return 0
        else
            print_warning "Servisler başlatıldı ama durumu belirsiz"
            return 1
        fi
    else
        print_error "Servisler başlatılamadı"
        return 1
    fi
}

# Geri yükleme işlemi
restore_backup() {
    local backup_path="$1"
    local dry_run="$2"
    
    print_status "Geri yükleme başlatılıyor..."
    log_message "Geri yükleme başlatıldı: $backup_path"
    
    if [ "$dry_run" = "true" ]; then
        print_warning "DRY RUN modu - gerçek geri yükleme yapılmayacak"
        
        # Sadece içeriği listele
        print_status "Yedek dosyası içeriği:"
        tar -tzf "$backup_path" | head -20
        
        print_status "DRY RUN tamamlandı"
        return 0
    fi
    
    # Mevcut sistemi yedekle
    local current_backup
    if ! current_backup=$(backup_current_system); then
        print_error "Mevcut sistem yedeklenemedi, geri yükleme iptal edildi"
        return 1
    fi
    
    # Servisleri durdur
    stop_services
    
    # Geçici dizin oluştur
    local temp_dir="/tmp/zeytin_restore_$$"
    mkdir -p "$temp_dir"
    
    # Yedekten dosyaları çıkar
    print_status "Yedek dosyası çıkarılıyor..."
    if tar -xzf "$backup_path" -C "$temp_dir" 2>/dev/null; then
        print_success "Yedek dosyası çıkarıldı"
    else
        print_error "Yedek dosyası çıkarılamadı"
        rm -rf "$temp_dir"
        start_services
        return 1
    fi
    
    # Veri dizinini geri yükle
    if [ -d "$temp_dir/data" ]; then
        print_status "Veri dizini geri yükleniyor..."
        
        # Mevcut veri dizinini yedekle
        if [ -d "$RESTORE_DIR/data" ]; then
            mv "$RESTORE_DIR/data" "$RESTORE_DIR/data.backup.$(date +%s)" 2>/dev/null || true
        fi
        
        # Yeni veri dizinini kopyala
        if cp -r "$temp_dir/data" "$RESTORE_DIR/"; then
            print_success "Veri dizini geri yüklendi"
        else
            print_error "Veri dizini geri yüklenemedi"
            rm -rf "$temp_dir"
            start_services
            return 1
        fi
    fi
    
    # Konfigürasyon dosyalarını geri yükle
    print_status "Konfigürasyon dosyaları geri yükleniyor..."
    
    local config_files=("app/config.py" "nginx/nginx.conf" "gunicorn.conf.py" "docker-compose.yml" "requirements.txt")
    
    for config_file in "${config_files[@]}"; do
        if [ -f "$temp_dir/$config_file" ]; then
            local target_path="$RESTORE_DIR/$config_file"
            local target_dir=$(dirname "$target_path")
            
            # Hedef dizini oluştur
            mkdir -p "$target_dir"
            
            # Mevcut dosyayı yedekle
            if [ -f "$target_path" ]; then
                cp "$target_path" "$target_path.backup.$(date +%s)" 2>/dev/null || true
            fi
            
            # Yeni dosyayı kopyala
            if cp "$temp_dir/$config_file" "$target_path"; then
                print_status "Geri yüklendi: $config_file"
            else
                print_warning "Geri yüklenemedi: $config_file"
            fi
        fi
    done
    
    # Geçici dizini temizle
    rm -rf "$temp_dir"
    
    # Servisleri başlat
    if start_services; then
        print_success "Geri yükleme başarıyla tamamlandı"
        log_message "Geri yükleme başarıyla tamamlandı"
        
        print_status "Mevcut sistem yedeği: $current_backup"
        print_status "Sorun yaşarsanız bu yedekten geri dönebilirsiniz"
        
        return 0
    else
        print_error "Geri yükleme tamamlandı ama servisler başlatılamadı"
        print_status "Manuel olarak servisleri kontrol edin"
        return 1
    fi
}

# Onay al
confirm_restore() {
    local backup_path="$1"
    
    echo ""
    print_warning "DİKKAT: Bu işlem mevcut sistemi tamamen değiştirecek!"
    print_status "Geri yüklenecek yedek: $(basename "$backup_path")"
    print_status "Mevcut sistem otomatik olarak yedeklenecek"
    echo ""
    
    read -p "Devam etmek istediğinizden emin misiniz? (evet/hayır): " -r
    if [[ $REPLY =~ ^[Ee][Vv][Ee][Tt]$ ]]; then
        return 0
    else
        print_status "İşlem iptal edildi"
        return 1
    fi
}

# Ana fonksiyon
main() {
    local backup_path=""
    local force=false
    local dry_run=false
    local list_only=false
    
    # Parametreleri parse et
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -l|--list)
                list_only=true
                shift
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -d|--dry-run)
                dry_run=true
                shift
                ;;
            -*)
                print_error "Bilinmeyen seçenek: $1"
                show_usage
                exit 1
                ;;
            *)
                backup_path="$1"
                shift
                ;;
        esac
    done
    
    # Sadece listeleme
    if [ "$list_only" = true ]; then
        list_backups
        exit $?
    fi
    
    # Yedek dosyası belirtilmemiş
    if [ -z "$backup_path" ]; then
        print_error "Yedek dosyası belirtilmedi"
        echo ""
        show_usage
        exit 1
    fi
    
    # Yedek dosyası doğrulama
    if ! validate_backup "$backup_path"; then
        exit 1
    fi
    
    # Onay al (force modu değilse)
    if [ "$force" = false ] && [ "$dry_run" = false ]; then
        if ! confirm_restore "$backup_path"; then
            exit 0
        fi
    fi
    
    # Geri yükleme
    log_message "=== Geri Yükleme Başlatıldı ==="
    
    if restore_backup "$backup_path" "$dry_run"; then
        log_message "=== Geri Yükleme Tamamlandı ==="
        exit 0
    else
        log_message "=== Geri Yükleme Başarısız ==="
        exit 1
    fi
}

# Root kontrolü
if [ "$EUID" -ne 0 ]; then
    print_error "Bu script root yetkileri ile çalıştırılmalıdır"
    exit 1
fi

# Script'i çalıştır
main "$@"