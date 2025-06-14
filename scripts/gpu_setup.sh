#!/bin/bash

# GPU Setup Script for Zeytin Ağacı Analiz Sistemi
# CUDA, CuDNN installation and configuration

set -e

echo "🚀 GPU Kurulum Scripti Başlatılıyor..."

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

# GPU kontrolü
check_gpu() {
    print_status "GPU kontrolü yapılıyor..."
    
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi
        print_success "NVIDIA GPU tespit edildi"
        return 0
    else
        print_warning "NVIDIA GPU tespit edilemedi"
        return 1
    fi
}

# CUDA kurulumu
install_cuda() {
    print_status "CUDA kurulumu başlatılıyor..."
    
    # CUDA repository ekle
    wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.0-1_all.deb
    sudo dpkg -i cuda-keyring_1.0-1_all.deb
    sudo apt-get update
    
    # CUDA toolkit kurulumu
    sudo apt-get install -y cuda-toolkit-12-2
    
    # Environment variables
    echo 'export PATH=/usr/local/cuda-12.2/bin${PATH:+:${PATH}}' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.2/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' >> ~/.bashrc
    
    source ~/.bashrc
    
    print_success "CUDA kurulumu tamamlandı"
}

# CuDNN kurulumu
install_cudnn() {
    print_status "CuDNN kurulumu başlatılıyor..."
    
    # CuDNN için NVIDIA repository
    sudo apt-get install -y libcudnn8 libcudnn8-dev
    
    print_success "CuDNN kurulumu tamamlandı"
}

# PyTorch GPU kurulumu
install_pytorch_gpu() {
    print_status "PyTorch GPU sürümü kurulumu başlatılıyor..."
    
    # Mevcut PyTorch'u kaldır
    pip uninstall -y torch torchvision torchaudio
    
    # GPU destekli PyTorch kurulumu
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    
    print_success "PyTorch GPU sürümü kuruldu"
}

# GPU test scripti
create_gpu_test() {
    print_status "GPU test scripti oluşturuluyor..."
    
    cat > gpu_test.py << 'EOF'
#!/usr/bin/env python3
import torch
import sys

def test_gpu():
    print("🔍 GPU Test Başlatılıyor...")
    print(f"PyTorch Sürümü: {torch.__version__}")
    
    # CUDA availability
    cuda_available = torch.cuda.is_available()
    print(f"CUDA Mevcut: {'✅ Evet' if cuda_available else '❌ Hayır'}")
    
    if cuda_available:
        # GPU bilgileri
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
            print(f"GPU Bellek Kullanımı: {allocated:.1f} MB (Allocated), {cached:.1f} MB (Cached)")
            
        except Exception as e:
            print(f"❌ GPU tensor işlem hatası: {e}")
            return False
    else:
        print("⚠️  CUDA mevcut değil, CPU modu kullanılacak")
    
    return cuda_available

if __name__ == "__main__":
    success = test_gpu()
    sys.exit(0 if success else 1)
EOF
    
    chmod +x gpu_test.py
    print_success "GPU test scripti oluşturuldu: gpu_test.py"
}

# Docker GPU desteği
setup_docker_gpu() {
    print_status "Docker GPU desteği kurulumu..."
    
    # NVIDIA Container Toolkit
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    
    sudo apt-get update
    sudo apt-get install -y nvidia-container-toolkit
    
    # Docker restart
    sudo systemctl restart docker
    
    print_success "Docker GPU desteği kuruldu"
}

# Ana kurulum fonksiyonu
main() {
    print_status "GPU kurulum scripti başlatılıyor..."
    
    # Sistem güncellemesi
    print_status "Sistem güncelleniyor..."
    sudo apt-get update
    sudo apt-get upgrade -y
    
    # GPU kontrolü
    if ! check_gpu; then
        print_error "NVIDIA GPU bulunamadı. Kurulum durduruluyor."
        exit 1
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
    
    # PyTorch GPU kurulumu
    install_pytorch_gpu
    
    # Docker GPU desteği
    setup_docker_gpu
    
    # Test scripti oluştur
    create_gpu_test
    
    # GPU testi çalıştır
    print_status "GPU testi çalıştırılıyor..."
    python3 gpu_test.py
    
    print_success "🎉 GPU kurulumu tamamlandı!"
    print_status "Sistem yeniden başlatılması önerilir."
    print_status "Test için: python3 gpu_test.py"
}

# Script çalıştır
main "$@"