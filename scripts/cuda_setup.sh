#!/bin/bash

# CUDA ve GPU Setup Script for Zeytin Ağacı Analiz Sistemi
# NVIDIA GPU, CUDA, CuDNN kurulumu ve yapılandırması

set -e

echo "🚀 CUDA ve GPU Kurulum Scripti Başlatılıyor..."

# Renkli çıktı için
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Log dosyası
LOG_FILE="/var/log/cuda-setup.log"

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

# GPU kontrolü
check_gpu() {
    print_status "GPU kontrolü yapılıyor..."
    log_message "GPU kontrolü başlatıldı"
    
    if lspci | grep -i nvidia >/dev/null 2>&1; then
        GPU_INFO=$(lspci | grep -i nvidia | head -1)
        print_success "NVIDIA GPU tespit edildi: $GPU_INFO"
        log_message "NVIDIA GPU tespit edildi: $GPU_INFO"
        return 0
    else
        print_error "NVIDIA GPU tespit edilemedi"
        log_message "NVIDIA GPU tespit edilemedi"
        print_status "Desteklenen GPU'lar:"
        echo "- NVIDIA GeForce GTX 1060 ve üzeri"
        echo "- NVIDIA RTX serisi"
        echo "- NVIDIA Tesla serisi"
        echo "- NVIDIA Quadro serisi"
        exit 1
    fi
}

# Mevcut NVIDIA driver kontrolü
check_existing_drivers() {
    print_status "Mevcut NVIDIA driver'ları kontrol ediliyor..."
    log_message "Mevcut driver kontrolü başlatıldı"
    
    if command -v nvidia-smi &> /dev/null; then
        DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits | head -1)
        print_warning "NVIDIA driver zaten kurulu: v$DRIVER_VERSION"
        log_message "Mevcut NVIDIA driver: v$DRIVER_VERSION"
        
        # Driver versiyonu kontrolü (CUDA 12.1 için minimum 525.60.13)
        if [ "$(echo "$DRIVER_VERSION >= 525.60" | bc -l)" -eq 1 ]; then
            print_success "Driver versiyonu CUDA 12.1 için uygun"
            return 0
        else
            print_warning "Driver versiyonu eski, güncelleme gerekebilir"
            return 1
        fi
    else
        print_status "NVIDIA driver bulunamadı, kurulum gerekli"
        log_message "NVIDIA driver bulunamadı"
        return 1
    fi
}

# NVIDIA driver kurulumu
install_nvidia_driver() {
    print_status "NVIDIA driver kurulumu başlatılıyor..."
    log_message "NVIDIA driver kurulumu başlatıldı"
    
    # Nouveau driver'ı devre dışı bırak
    print_status "Nouveau driver devre dışı bırakılıyor..."
    echo 'blacklist nouveau' | tee /etc/modprobe.d/blacklist-nouveau.conf
    echo 'options nouveau modeset=0' | tee -a /etc/modprobe.d/blacklist-nouveau.conf
    update-initramfs -u
    
    # Sistem güncellemesi
    apt-get update
    
    # NVIDIA driver repository ekle
    add-apt-repository ppa:graphics-drivers/ppa -y
    apt-get update
    
    # En son driver'ı kur
    print_status "NVIDIA driver kuruluyor..."
    apt-get install -y nvidia-driver-535 nvidia-dkms-535
    
    print_success "NVIDIA driver kuruldu"
    print_warning "Sistem yeniden başlatılması gerekiyor"
    log_message "NVIDIA driver kurulumu tamamlandı"
}

# CUDA Toolkit kurulumu
install_cuda() {
    print_status "CUDA Toolkit kurulumu başlatılıyor..."
    log_message "CUDA kurulumu başlatıldı"
    
    # CUDA repository ekle
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
    dpkg -i cuda-keyring_1.0-1_all.deb
    apt-get update
    
    # CUDA 12.1 kurulumu
    print_status "CUDA 12.1 kuruluyor..."
    apt-get install -y cuda-toolkit-12-1
    
    # Environment variables
    echo 'export PATH=/usr/local/cuda-12.1/bin${PATH:+:${PATH}}' >> /etc/environment
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' >> /etc/environment
    
    # Bashrc'ye de ekle
    echo 'export PATH=/usr/local/cuda-12.1/bin${PATH:+:${PATH}}' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' >> ~/.bashrc
    
    # Symlink oluştur
    ln -sf /usr/local/cuda-12.1 /usr/local/cuda
    
    print_success "CUDA Toolkit kuruldu"
    log_message "CUDA kurulumu tamamlandı"
}

# CuDNN kurulumu
install_cudnn() {
    print_status "CuDNN kurulumu başlatılıyor..."
    log_message "CuDNN kurulumu başlatıldı"
    
    # CuDNN repository ekle
    apt-get install -y libcudnn8 libcudnn8-dev
    
    print_success "CuDNN kuruldu"
    log_message "CuDNN kurulumu tamamlandı"
}

# Docker GPU desteği
setup_docker_gpu() {
    print_status "Docker GPU desteği kurulumu..."
    log_message "Docker GPU desteği kurulumu başlatıldı"
    
    # NVIDIA Container Toolkit repository
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
    apt-get update
    apt-get install -y nvidia-container-toolkit
    
    # Docker'ı yeniden yapılandır
    nvidia-ctk runtime configure --runtime=docker
    systemctl restart docker
    
    print_success "Docker GPU desteği kuruldu"
    log_message "Docker GPU desteği kurulumu tamamlandı"
}

# GPU test scripti oluştur
create_gpu_test() {
    print_status "GPU test scripti oluşturuluyor..."
    log_message "GPU test scripti oluşturma başlatıldı"
    
    cat > /usr/local/bin/gpu-test.py << 'EOF'
#!/usr/bin/env python3
"""
GPU Test Script for Zeytin Ağacı Analiz Sistemi
CUDA, PyTorch ve YOLOv8 GPU desteğini test eder
"""

import sys
import subprocess

def test_nvidia_smi():
    """NVIDIA SMI testi"""
    print("🔍 NVIDIA SMI Test...")
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ NVIDIA SMI çalışıyor")
            print(result.stdout)
            return True
        else:
            print("❌ NVIDIA SMI hatası")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("❌ NVIDIA SMI bulunamadı")
        return False

def test_cuda():
    """CUDA testi"""
    print("\n🔍 CUDA Test...")
    try:
        result = subprocess.run(['nvcc', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ CUDA Compiler çalışıyor")
            print(result.stdout)
            return True
        else:
            print("❌ CUDA Compiler hatası")
            return False
    except FileNotFoundError:
        print("❌ CUDA Compiler bulunamadı")
        return False

def test_pytorch():
    """PyTorch GPU testi"""
    print("\n🔍 PyTorch GPU Test...")
    try:
        import torch
        print(f"PyTorch Sürümü: {torch.__version__}")
        
        cuda_available = torch.cuda.is_available()
        print(f"CUDA Mevcut: {'✅ Evet' if cuda_available else '❌ Hayır'}")
        
        if cuda_available:
            gpu_count = torch.cuda.device_count()
            print(f"GPU Sayısı: {gpu_count}")
            
            for i in range(gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
                print(f"GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")
            
            # Basit tensor testi
            try:
                x = torch.randn(1000, 1000).cuda()
                y = torch.randn(1000, 1000).cuda()
                z = torch.mm(x, y)
                print("✅ GPU tensor işlemleri başarılı")
                
                # Memory info
                allocated = torch.cuda.memory_allocated(0) / 1024**2
                cached = torch.cuda.memory_reserved(0) / 1024**2
                print(f"GPU Bellek: {allocated:.1f} MB (Allocated), {cached:.1f} MB (Cached)")
                
                return True
            except Exception as e:
                print(f"❌ GPU tensor işlem hatası: {e}")
                return False
        else:
            return False
            
    except ImportError:
        print("❌ PyTorch bulunamadı")
        return False
    except Exception as e:
        print(f"❌ PyTorch test hatası: {e}")
        return False

def test_ultralytics():
    """Ultralytics YOLOv8 GPU testi"""
    print("\n🔍 YOLOv8 GPU Test...")
    try:
        from ultralytics import YOLO
        import torch
        
        if not torch.cuda.is_available():
            print("❌ CUDA mevcut değil, YOLOv8 GPU testi atlanıyor")
            return False
        
        print("YOLOv8 modeli yükleniyor...")
        model = YOLO('yolov8n.pt')  # Nano model
        
        # GPU'ya taşı
        model.to('cuda')
        print("✅ YOLOv8 modeli GPU'ya yüklendi")
        
        # Dummy prediction
        import numpy as np
        dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        
        print("GPU'da test prediction yapılıyor...")
        results = model(dummy_image, device='cuda', verbose=False)
        print("✅ YOLOv8 GPU prediction başarılı")
        
        return True
        
    except ImportError as e:
        print(f"❌ Ultralytics import hatası: {e}")
        return False
    except Exception as e:
        print(f"❌ YOLOv8 test hatası: {e}")
        return False

def test_docker_gpu():
    """Docker GPU testi"""
    print("\n🔍 Docker GPU Test...")
    try:
        result = subprocess.run([
            'docker', 'run', '--rm', '--gpus', 'all',
            'nvidia/cuda:12.1-base-ubuntu22.04',
            'nvidia-smi'
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Docker GPU desteği çalışıyor")
            return True
        else:
            print("❌ Docker GPU test hatası")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Docker GPU test timeout")
        return False
    except FileNotFoundError:
        print("❌ Docker bulunamadı")
        return False
    except Exception as e:
        print(f"❌ Docker GPU test hatası: {e}")
        return False

def main():
    """Ana test fonksiyonu"""
    print("🚀 GPU Test Suite Başlatılıyor...\n")
    
    tests = [
        ("NVIDIA SMI", test_nvidia_smi),
        ("CUDA", test_cuda),
        ("PyTorch", test_pytorch),
        ("YOLOv8", test_ultralytics),
        ("Docker GPU", test_docker_gpu)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} test exception: {e}")
            results[test_name] = False
    
    # Sonuçları özetle
    print("\n" + "="*50)
    print("📊 TEST SONUÇLARI")
    print("="*50)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ BAŞARILI" if result else "❌ BAŞARISIZ"
        print(f"{test_name:15} : {status}")
        if result:
            passed += 1
    
    print(f"\nToplam: {passed}/{total} test başarılı")
    
    if passed == total:
        print("🎉 Tüm GPU testleri başarılı!")
        return 0
    elif passed >= 3:
        print("⚠️  Bazı testler başarısız ama temel GPU desteği çalışıyor")
        return 0
    else:
        print("❌ GPU desteği düzgün çalışmıyor")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOF

    chmod +x /usr/local/bin/gpu-test.py
    
    print_success "GPU test scripti oluşturuldu: /usr/local/bin/gpu-test.py"
    log_message "GPU test scripti oluşturuldu"
}

# Sistem optimizasyonları
optimize_gpu_system() {
    print_status "GPU sistem optimizasyonları yapılıyor..."
    log_message "GPU sistem optimizasyonu başlatıldı"
    
    # GPU memory optimizasyonları
    cat >> /etc/sysctl.conf << 'EOF'

# GPU optimizasyonları
vm.zone_reclaim_mode = 0
vm.swappiness = 1
kernel.numa_balancing = 0
EOF

    sysctl -p
    
    # GPU persistence mode
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi -pm 1 2>/dev/null || true
    fi
    
    print_success "GPU sistem optimizasyonları tamamlandı"
    log_message "GPU sistem optimizasyonu tamamlandı"
}

# Ana kurulum fonksiyonu
main() {
    log_message "=== CUDA kurulumu başlatıldı ==="
    
    check_root
    check_gpu
    
    # Mevcut driver kontrolü
    if ! check_existing_drivers; then
        print_warning "NVIDIA driver kurulumu gerekli"
        read -p "NVIDIA driver kurmak istiyor musunuz? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_nvidia_driver
            print_warning "Sistem yeniden başlatılması gerekiyor"
            print_status "Yeniden başlattıktan sonra bu scripti tekrar çalıştırın"
            exit 0
        else
            print_error "NVIDIA driver olmadan devam edilemiyor"
            exit 1
        fi
    fi
    
    # CUDA kurulumu
    if ! command -v nvcc &> /dev/null; then
        install_cuda
    else
        print_warning "CUDA zaten kurulu"
        nvcc --version
    fi
    
    # CuDNN kurulumu
    install_cudnn
    
    # Docker GPU desteği
    if command -v docker &> /dev/null; then
        setup_docker_gpu
    else
        print_warning "Docker bulunamadı, GPU desteği atlanıyor"
    fi
    
    # Test scripti oluştur
    create_gpu_test
    
    # Sistem optimizasyonları
    optimize_gpu_system
    
    print_success "🎉 CUDA kurulumu tamamlandı!"
    print_status "GPU testini çalıştırmak için: python3 /usr/local/bin/gpu-test.py"
    
    # Otomatik test çalıştır
    print_status "GPU testi çalıştırılıyor..."
    if python3 /usr/local/bin/gpu-test.py; then
        print_success "GPU testleri başarılı!"
    else
        print_warning "Bazı GPU testleri başarısız"
    fi
    
    log_message "=== CUDA kurulumu tamamlandı ==="
}

# Script'i çalıştır
main "$@"