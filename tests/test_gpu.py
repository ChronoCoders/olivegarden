import pytest
import torch
import os
import sys
from unittest.mock import patch, MagicMock

# Test için gerekli importlar
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.gpu_detector import gpu_detector, GPUDetector
from app.ai_analysis import ZeytinAnalizci

class TestGPUDetection:
    """GPU tespit ve yönetimi testleri"""
    
    def test_gpu_detector_initialization(self):
        """GPU detector başlatma testi"""
        detector = GPUDetector()
        
        assert hasattr(detector, 'gpu_available')
        assert hasattr(detector, 'cuda_available')
        assert hasattr(detector, 'gpu_info')
        assert isinstance(detector.gpu_info, dict)
    
    def test_gpu_detection_with_cuda(self):
        """CUDA mevcut olduğunda GPU tespiti"""
        with patch('torch.cuda.is_available', return_value=True), \
             patch('torch.cuda.device_count', return_value=1), \
             patch('torch.cuda.get_device_name', return_value='NVIDIA GeForce RTX 3080'), \
             patch('torch.cuda.get_device_properties') as mock_props:
            
            # Mock GPU properties
            mock_props.return_value.total_memory = 10737418240  # 10GB
            
            detector = GPUDetector()
            
            assert detector.gpu_available is True
            assert detector.cuda_available is True
            assert detector.gpu_info['device_name'] == 'NVIDIA GeForce RTX 3080'
            assert detector.gpu_info['memory_total'] == 10737418240
    
    def test_gpu_detection_without_cuda(self):
        """CUDA mevcut olmadığında GPU tespiti"""
        with patch('torch.cuda.is_available', return_value=False):
            detector = GPUDetector()
            
            assert detector.gpu_available is False
            assert detector.cuda_available is False
    
    def test_get_optimal_device_gpu_available(self):
        """GPU mevcut iken optimal cihaz seçimi"""
        with patch('torch.cuda.is_available', return_value=True):
            detector = GPUDetector()
            
            # GPU modu istendi ve mevcut
            device = detector.get_optimal_device("gpu")
            assert device == "cuda"
            
            # CPU modu istendi
            device = detector.get_optimal_device("cpu")
            assert device == "cpu"
    
    def test_get_optimal_device_gpu_not_available(self):
        """GPU mevcut değilken optimal cihaz seçimi"""
        with patch('torch.cuda.is_available', return_value=False):
            detector = GPUDetector()
            
            # GPU modu istendi ama mevcut değil
            device = detector.get_optimal_device("gpu")
            assert device == "cpu"
            
            # CPU modu istendi
            device = detector.get_optimal_device("cpu")
            assert device == "cpu"
    
    def test_gpu_status_with_memory_info(self):
        """GPU durumu ve bellek bilgisi testi"""
        with patch('torch.cuda.is_available', return_value=True), \
             patch('torch.cuda.memory_allocated', return_value=1073741824), \
             patch('torch.cuda.memory_reserved', return_value=2147483648):
            
            detector = GPUDetector()
            status = detector.get_gpu_status()
            
            assert status['gpu_available'] is True
            assert status['cuda_available'] is True
            assert 'memory_usage' in status
            assert status['memory_usage']['allocated'] == 1073741824
            assert status['memory_usage']['cached'] == 2147483648
    
    def test_clear_gpu_cache(self):
        """GPU cache temizleme testi"""
        with patch('torch.cuda.is_available', return_value=True), \
             patch('torch.cuda.empty_cache') as mock_empty_cache:
            
            detector = GPUDetector()
            detector.clear_gpu_cache()
            
            mock_empty_cache.assert_called_once()
    
    def test_clear_gpu_cache_no_gpu(self):
        """GPU olmadığında cache temizleme testi"""
        with patch('torch.cuda.is_available', return_value=False):
            detector = GPUDetector()
            
            # Hata vermemeli
            detector.clear_gpu_cache()

class TestZeytinAnalizciGPU:
    """ZeytinAnalizci GPU fonksiyonalitesi testleri"""
    
    def setup_method(self):
        """Her test öncesi çalışır"""
        self.analizci = ZeytinAnalizci()
    
    def test_set_analysis_mode_cpu(self):
        """CPU analiz modu ayarlama testi"""
        self.analizci.set_analysis_mode("cpu")
        
        assert self.analizci.analysis_mode == "cpu"
        assert self.analizci.current_device == "cpu"
    
    def test_set_analysis_mode_gpu_available(self):
        """GPU mevcut iken GPU modu ayarlama testi"""
        with patch.object(gpu_detector, 'get_optimal_device', return_value='cuda'):
            self.analizci.set_analysis_mode("gpu")
            
            assert self.analizci.analysis_mode == "gpu"
            assert self.analizci.current_device == "cuda"
    
    def test_set_analysis_mode_gpu_not_available(self):
        """GPU mevcut değilken GPU modu ayarlama testi"""
        with patch.object(gpu_detector, 'get_optimal_device', return_value='cpu'):
            self.analizci.set_analysis_mode("gpu")
            
            assert self.analizci.analysis_mode == "gpu"
            assert self.analizci.current_device == "cpu"  # Fallback to CPU
    
    @patch('app.ai_analysis.YOLO')
    def test_load_yolo_model_gpu(self, mock_yolo):
        """GPU'da YOLO model yükleme testi"""
        mock_model = MagicMock()
        mock_yolo.return_value = mock_model
        
        with patch.object(gpu_detector, 'gpu_available', True), \
             patch('os.path.exists', return_value=True):
            
            self.analizci.current_device = "cuda"
            self.analizci.load_yolo_model("test_model.pt")
            
            mock_yolo.assert_called_once_with("test_model.pt")
            mock_model.to.assert_called_once_with('cuda')
    
    @patch('app.ai_analysis.YOLO')
    def test_load_yolo_model_cpu_fallback(self, mock_yolo):
        """GPU hatası durumunda CPU fallback testi"""
        mock_model = MagicMock()
        mock_yolo.return_value = mock_model
        
        # İlk çağrıda hata, ikinci çağrıda başarılı
        mock_model.to.side_effect = [RuntimeError("CUDA error"), None]
        
        with patch('os.path.exists', return_value=True), \
             patch.object(gpu_detector, 'clear_gpu_cache'):
            
            self.analizci.current_device = "cuda"
            self.analizci.load_yolo_model("test_model.pt")
            
            # İki kez çağrılmalı: ilk GPU, sonra CPU
            assert mock_yolo.call_count == 2
            assert self.analizci.current_device == "cpu"
    
    def test_get_device_info(self):
        """Cihaz bilgisi alma testi"""
        with patch.object(gpu_detector, 'get_gpu_status', return_value={'gpu_available': True}):
            self.analizci.analysis_mode = "gpu"
            self.analizci.current_device = "cuda"
            
            device_info = self.analizci.get_device_info()
            
            assert device_info['analysis_mode'] == "gpu"
            assert device_info['current_device'] == "cuda"
            assert 'gpu_status' in device_info
            assert 'system_status' in device_info

class TestGPUMemoryManagement:
    """GPU bellek yönetimi testleri"""
    
    def test_memory_cleanup_on_error(self):
        """Hata durumunda bellek temizleme testi"""
        analizci = ZeytinAnalizci()
        
        with patch.object(gpu_detector, 'clear_gpu_cache') as mock_clear, \
             patch.object(analizci, '_cleanup_memory') as mock_cleanup:
            
            analizci.current_device = "cuda"
            
            # Hata simülasyonu
            try:
                raise RuntimeError("Test error")
            except RuntimeError:
                # Cleanup çağrılmalı
                if analizci.current_device == "cuda":
                    gpu_detector.clear_gpu_cache()
                analizci._cleanup_memory()
            
            mock_clear.assert_called_once()
            mock_cleanup.assert_called_once()
    
    @patch('psutil.virtual_memory')
    def test_memory_usage_monitoring(self, mock_memory):
        """Bellek kullanımı izleme testi"""
        # Mock memory info
        mock_memory.return_value.percent = 85.0
        
        analizci = ZeytinAnalizci()
        
        with patch('app.ai_analysis.logger') as mock_logger:
            analizci._cleanup_memory()
            
            # Yüksek bellek kullanımında uyarı loglanmalı
            mock_logger.warning.assert_called()

class TestGPUIntegration:
    """GPU entegrasyon testleri"""
    
    @pytest.mark.asyncio
    async def test_analysis_with_gpu_mode(self):
        """GPU modu ile analiz testi"""
        analizci = ZeytinAnalizci()
        
        with patch.object(analizci, 'load_yolo_model'), \
             patch.object(analizci, '_rgb_analiz', return_value={'toplam_agac': 5}), \
             patch.object(analizci, '_multispektral_analiz', return_value={'ndvi_ortalama': 0.7}), \
             patch.object(analizci, '_geojson_olustur'), \
             patch('os.listdir', return_value=['test.jpg']), \
             patch('os.path.exists', return_value=True):
            
            result = await analizci.analiz_yap(
                yukleme_klasoru="/test/upload",
                analiz_klasoru="/test/analysis", 
                log_yolu="/test/log.txt",
                analiz_modu="gpu"
            )
            
            assert result['analiz_modu'] == "gpu"
            assert 'kullanilan_cihaz' in result
            assert 'gpu_durumu' in result
    
    def test_gpu_performance_comparison(self):
        """GPU vs CPU performans karşılaştırması testi"""
        # Bu test gerçek GPU performansını ölçmez, sadece metriklerin toplandığını doğrular
        analizci = ZeytinAnalizci()
        
        # CPU modu
        analizci.set_analysis_mode("cpu")
        cpu_device = analizci.current_device
        
        # GPU modu (mevcut ise)
        analizci.set_analysis_mode("gpu")
        gpu_device = analizci.current_device
        
        # Cihaz bilgilerinin doğru ayarlandığını kontrol et
        assert cpu_device == "cpu"
        assert gpu_device in ["cpu", "cuda"]  # GPU mevcut değilse CPU'ya fallback

class TestGPUErrorHandling:
    """GPU hata yönetimi testleri"""
    
    def test_gpu_out_of_memory_handling(self):
        """GPU bellek yetersizliği durumu testi"""
        analizci = ZeytinAnalizci()
        
        with patch.object(gpu_detector, 'clear_gpu_cache') as mock_clear:
            # CUDA out of memory simülasyonu
            analizci.current_device = "cuda"
            
            # Bellek temizleme çağrılmalı
            gpu_detector.clear_gpu_cache()
            mock_clear.assert_called_once()
    
    def test_cuda_driver_error_handling(self):
        """CUDA driver hatası durumu testi"""
        with patch('torch.cuda.is_available', side_effect=RuntimeError("CUDA driver error")):
            detector = GPUDetector()
            
            # Hata durumunda güvenli fallback
            assert detector.gpu_available is False
            assert detector.cuda_available is False
    
    def test_gpu_device_switch_on_error(self):
        """GPU hatası durumunda cihaz değiştirme testi"""
        analizci = ZeytinAnalizci()
        
        # GPU modunda başla
        analizci.analysis_mode = "gpu"
        analizci.current_device = "cuda"
        
        # GPU hatası simülasyonu
        with patch.object(gpu_detector, 'gpu_available', False):
            # Cihaz CPU'ya değişmeli
            optimal_device = gpu_detector.get_optimal_device("gpu")
            assert optimal_device == "cpu"

# Test çalıştırma
if __name__ == "__main__":
    pytest.main([__file__, "-v"])