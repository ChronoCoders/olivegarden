#!/bin/bash

# Zeytin Ağacı Analiz Sistemi - Test Çalıştırma Scripti

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
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$PROJECT_DIR/tests"
VENV_DIR="$PROJECT_DIR/venv"
COVERAGE_MIN=80
REPORT_DIR="$PROJECT_DIR/test_reports"

# Test rapor dizinini oluştur
mkdir -p "$REPORT_DIR"

# Kullanım bilgisi
show_usage() {
    echo "Kullanım: $0 [SEÇENEKLER]"
    echo ""
    echo "Seçenekler:"
    echo "  -h, --help          Bu yardım mesajını göster"
    echo "  -u, --unit          Sadece unit testleri çalıştır"
    echo "  -i, --integration   Sadece integration testleri çalıştır"
    echo "  -c, --coverage      Coverage raporu oluştur"
    echo "  -v, --verbose       Detaylı çıktı"
    echo "  -f, --fast          Hızlı testler (paralel çalıştırma)"
    echo "  --html              HTML raporu oluştur"
    echo "  --xml               XML raporu oluştur (CI/CD için)"
    echo ""
    echo "Örnekler:"
    echo "  $0                  # Tüm testleri çalıştır"
    echo "  $0 -c --html        # Coverage ile HTML raporu"
    echo "  $0 -u -v            # Unit testler, detaylı çıktı"
}

# Virtual environment kontrolü
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_warning "Virtual environment bulunamadı, oluşturuluyor..."
        python3 -m venv "$VENV_DIR"
    fi
    
    # Virtual environment'ı aktif et
    source "$VENV_DIR/bin/activate"
    
    # Test bağımlılıklarını yükle
    print_status "Test bağımlılıkları kontrol ediliyor..."
    pip install -q pytest pytest-asyncio pytest-cov pytest-html pytest-xdist coverage
}

# Test ortamı hazırlama
setup_test_env() {
    print_status "Test ortamı hazırlanıyor..."
    
    # Test veritabanı
    export TEST_DATABASE_URL="$PROJECT_DIR/test_data/test.db"
    mkdir -p "$(dirname "$TEST_DATABASE_URL")"
    
    # Test veri dizini
    export TEST_DATA_DIR="$PROJECT_DIR/test_data"
    mkdir -p "$TEST_DATA_DIR/analizler"
    
    # Test modelleri
    export TEST_MODEL_DIR="$PROJECT_DIR/test_data/models"
    mkdir -p "$TEST_MODEL_DIR"
    
    # Log seviyesi
    export LOG_LEVEL="WARNING"
    
    print_success "Test ortamı hazırlandı"
}

# Test temizleme
cleanup_test_env() {
    print_status "Test ortamı temizleniyor..."
    
    # Test verilerini temizle
    if [ -d "$PROJECT_DIR/test_data" ]; then
        rm -rf "$PROJECT_DIR/test_data"
    fi
    
    # Geçici dosyaları temizle
    find "$PROJECT_DIR" -name "*.pyc" -delete 2>/dev/null || true
    find "$PROJECT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    print_success "Test ortamı temizlendi"
}

# Unit testleri çalıştır
run_unit_tests() {
    print_status "Unit testleri çalıştırılıyor..."
    
    local pytest_args=()
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$FAST" = true ]; then
        pytest_args+=("-n" "auto")
    fi
    
    if [ "$COVERAGE" = true ]; then
        pytest_args+=("--cov=app" "--cov-report=term-missing")
        
        if [ "$HTML_REPORT" = true ]; then
            pytest_args+=("--cov-report=html:$REPORT_DIR/coverage_html")
        fi
        
        if [ "$XML_REPORT" = true ]; then
            pytest_args+=("--cov-report=xml:$REPORT_DIR/coverage.xml")
        fi
    fi
    
    if [ "$HTML_REPORT" = true ]; then
        pytest_args+=("--html=$REPORT_DIR/unit_tests.html" "--self-contained-html")
    fi
    
    if [ "$XML_REPORT" = true ]; then
        pytest_args+=("--junitxml=$REPORT_DIR/unit_tests.xml")
    fi
    
    # Unit test dosyalarını çalıştır
    pytest "${pytest_args[@]}" "$TEST_DIR/test_validation.py" "$TEST_DIR/test_auth.py" || return 1
    
    print_success "Unit testleri tamamlandı"
}

# Integration testleri çalıştır
run_integration_tests() {
    print_status "Integration testleri çalıştırılıyor..."
    
    local pytest_args=()
    
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v")
    fi
    
    if [ "$HTML_REPORT" = true ]; then
        pytest_args+=("--html=$REPORT_DIR/integration_tests.html" "--self-contained-html")
    fi
    
    if [ "$XML_REPORT" = true ]; then
        pytest_args+=("--junitxml=$REPORT_DIR/integration_tests.xml")
    fi
    
    # Integration test dosyalarını çalıştır
    pytest "${pytest_args[@]}" "$TEST_DIR/test_api.py" || return 1
    
    print_success "Integration testleri tamamlandı"
}

# Performance testleri çalıştır
run_performance_tests() {
    print_status "Performance testleri çalıştırılıyor..."
    
    # Basit performance testi
    python3 -c "
import time
import requests
import statistics

# Test sunucusunun çalıştığını varsay
base_url = 'http://localhost:8000'

# Health check performance
times = []
for i in range(10):
    start = time.time()
    try:
        response = requests.get(f'{base_url}/health', timeout=5)
        if response.status_code == 200:
            times.append(time.time() - start)
    except:
        pass

if times:
    avg_time = statistics.mean(times)
    print(f'Health check ortalama süre: {avg_time:.3f}s')
    
    if avg_time > 1.0:
        print('UYARI: Health check çok yavaş')
        exit(1)
else:
    print('UYARI: Test sunucusu çalışmıyor')
    exit(1)
" || print_warning "Performance testleri başarısız (sunucu çalışmıyor olabilir)"
    
    print_success "Performance testleri tamamlandı"
}

# Coverage raporu analizi
analyze_coverage() {
    if [ "$COVERAGE" = true ] && [ -f "$REPORT_DIR/coverage.xml" ]; then
        print_status "Coverage raporu analiz ediliyor..."
        
        # Coverage yüzdesini al
        local coverage_percent=$(python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('$REPORT_DIR/coverage.xml')
    root = tree.getroot()
    coverage = float(root.attrib['line-rate']) * 100
    print(f'{coverage:.1f}')
except:
    print('0')
")
        
        print_status "Coverage: %$coverage_percent"
        
        if (( $(echo "$coverage_percent < $COVERAGE_MIN" | bc -l) )); then
            print_warning "Coverage minimum seviyenin altında (%$COVERAGE_MIN)"
            return 1
        else
            print_success "Coverage minimum seviyeyi karşılıyor"
        fi
    fi
}

# Test raporu oluştur
generate_report() {
    print_status "Test raporu oluşturuluyor..."
    
    local report_file="$REPORT_DIR/test_summary.txt"
    
    cat > "$report_file" << EOF
Zeytin Ağacı Analiz Sistemi - Test Raporu
==========================================

Tarih: $(date)
Test Dizini: $TEST_DIR
Rapor Dizini: $REPORT_DIR

Test Sonuçları:
EOF
    
    if [ "$UNIT_TESTS" = true ]; then
        echo "- Unit Testleri: ÇALIŞTIRILDI" >> "$report_file"
    fi
    
    if [ "$INTEGRATION_TESTS" = true ]; then
        echo "- Integration Testleri: ÇALIŞTIRILDI" >> "$report_file"
    fi
    
    if [ "$COVERAGE" = true ]; then
        echo "- Coverage Analizi: ÇALIŞTIRILDI" >> "$report_file"
    fi
    
    echo "" >> "$report_file"
    echo "Rapor Dosyaları:" >> "$report_file"
    
    for file in "$REPORT_DIR"/*; do
        if [ -f "$file" ]; then
            echo "- $(basename "$file")" >> "$report_file"
        fi
    done
    
    print_success "Test raporu oluşturuldu: $report_file"
}

# Ana fonksiyon
main() {
    local UNIT_TESTS=false
    local INTEGRATION_TESTS=false
    local COVERAGE=false
    local VERBOSE=false
    local FAST=false
    local HTML_REPORT=false
    local XML_REPORT=false
    local RUN_ALL=true
    
    # Parametreleri parse et
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -u|--unit)
                UNIT_TESTS=true
                RUN_ALL=false
                shift
                ;;
            -i|--integration)
                INTEGRATION_TESTS=true
                RUN_ALL=false
                shift
                ;;
            -c|--coverage)
                COVERAGE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -f|--fast)
                FAST=true
                shift
                ;;
            --html)
                HTML_REPORT=true
                shift
                ;;
            --xml)
                XML_REPORT=true
                shift
                ;;
            *)
                print_error "Bilinmeyen seçenek: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Tüm testleri çalıştır (varsayılan)
    if [ "$RUN_ALL" = true ]; then
        UNIT_TESTS=true
        INTEGRATION_TESTS=true
    fi
    
    print_status "Test çalıştırma başlatılıyor..."
    
    # Ön hazırlık
    check_venv
    setup_test_env
    
    # Cleanup trap
    trap cleanup_test_env EXIT
    
    local test_failed=false
    
    # Testleri çalıştır
    if [ "$UNIT_TESTS" = true ]; then
        if ! run_unit_tests; then
            test_failed=true
        fi
    fi
    
    if [ "$INTEGRATION_TESTS" = true ]; then
        if ! run_integration_tests; then
            test_failed=true
        fi
    fi
    
    # Performance testleri (opsiyonel)
    run_performance_tests || true
    
    # Coverage analizi
    if [ "$COVERAGE" = true ]; then
        if ! analyze_coverage; then
            test_failed=true
        fi
    fi
    
    # Rapor oluştur
    generate_report
    
    # Sonuç
    if [ "$test_failed" = true ]; then
        print_error "Bazı testler başarısız oldu"
        exit 1
    else
        print_success "Tüm testler başarıyla tamamlandı"
        
        if [ "$HTML_REPORT" = true ]; then
            print_status "HTML raporları: $REPORT_DIR/"
        fi
        
        exit 0
    fi
}

# Script'i çalıştır
main "$@"