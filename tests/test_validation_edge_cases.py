import pytest
import asyncio
import io
import os
import tempfile
from unittest.mock import MagicMock, patch, mock_open
from PIL import Image
import numpy as np

# Test için gerekli importlar
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.validation import file_validator, FileValidator
from app.constants import *

class TestFileValidationEdgeCases:
    """Dosya validasyon edge case testleri"""
    
    def create_test_image(self, width=1024, height=768, format='JPEG', mode='RGB'):
        """Test için sahte görsel oluştur"""
        image = Image.new(mode, (width, height), color='red')
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        buffer.seek(0)
        return buffer.getvalue()
    
    def create_mock_upload_file(self, filename, content, content_type):
        """Mock UploadFile oluştur"""
        mock_file = MagicMock()
        mock_file.filename = filename
        mock_file.content_type = content_type
        mock_file.read = MagicMock(return_value=content)
        mock_file.seek = MagicMock()
        return mock_file
    
    @pytest.mark.asyncio
    async def test_empty_filename(self):
        """Boş dosya adı testi"""
        content = self.create_test_image()
        mock_file = self.create_mock_upload_file("", content, "image/jpeg")
        
        result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Dosya adı boş' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_none_filename(self):
        """None dosya adı testi"""
        content = self.create_test_image()
        mock_file = self.create_mock_upload_file(None, content, "image/jpeg")
        
        result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Dosya adı boş' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_very_long_filename(self):
        """Çok uzun dosya adı testi"""
        content = self.create_test_image()
        long_filename = "a" * 300 + ".jpg"  # 300+ karakter
        mock_file = self.create_mock_upload_file(long_filename, content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        # Uzun dosya adı uyarı vermeli ama geçerli olmalı
        assert result['valid'] is True
    
    @pytest.mark.asyncio
    async def test_special_characters_in_filename(self):
        """Dosya adında özel karakter testi"""
        content = self.create_test_image()
        special_filename = "test@#$%^&*()_+.jpg"
        mock_file = self.create_mock_upload_file(special_filename, content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
    
    @pytest.mark.asyncio
    async def test_unicode_filename(self):
        """Unicode dosya adı testi"""
        content = self.create_test_image()
        unicode_filename = "türkçe_dosya_名前.jpg"
        mock_file = self.create_mock_upload_file(unicode_filename, content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
    
    @pytest.mark.asyncio
    async def test_zero_byte_file(self):
        """Sıfır byte dosya testi"""
        empty_content = b''
        mock_file = self.create_mock_upload_file("empty.jpg", empty_content, "image/jpeg")
        
        result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert result['metadata']['file_size'] == 0
    
    @pytest.mark.asyncio
    async def test_exactly_max_size_file(self):
        """Tam maksimum boyutta dosya testi"""
        max_size_content = b'x' * MAX_FILE_SIZE
        mock_file = self.create_mock_upload_file("max_size.jpg", max_size_content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        # Tam limit boyutunda olmalı, geçerli olmalı
        assert result['metadata']['file_size'] == MAX_FILE_SIZE
        # Görsel bozuk olacağı için geçersiz olabilir
    
    @pytest.mark.asyncio
    async def test_one_byte_over_limit(self):
        """Limitten 1 byte fazla dosya testi"""
        over_limit_content = b'x' * (MAX_FILE_SIZE + 1)
        mock_file = self.create_mock_upload_file("over_limit.jpg", over_limit_content, "image/jpeg")
        
        result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Dosya çok büyük' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_minimum_resolution_boundary(self):
        """Minimum çözünürlük sınırı testi"""
        # Tam minimum boyutta
        content = self.create_test_image(512, 512)
        mock_file = self.create_mock_upload_file("min_res.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert result['metadata']['width'] == 512
        assert result['metadata']['height'] == 512
    
    @pytest.mark.asyncio
    async def test_one_pixel_under_minimum(self):
        """Minimum çözünürlükten 1 piksel az testi"""
        content = self.create_test_image(511, 512)
        mock_file = self.create_mock_upload_file("under_min.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('çözünürlüğü çok düşük' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_maximum_resolution_boundary(self):
        """Maksimum çözünürlük sınırı testi"""
        # Tam maksimum boyutta
        content = self.create_test_image(10000, 10000)
        mock_file = self.create_mock_upload_file("max_res.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert any('çözünürlüğü çok yüksek' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_corrupted_image_header(self):
        """Bozuk görsel header testi"""
        # JPEG header ile başlayan ama bozuk içerik
        corrupted_content = b'\xff\xd8\xff\xe0' + b'corrupted_data' * 1000
        mock_file = self.create_mock_upload_file("corrupted.jpg", corrupted_content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('validasyon hatası' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_wrong_extension_correct_content(self):
        """Yanlış uzantı doğru içerik testi"""
        # PNG içeriği ama JPG uzantısı
        content = self.create_test_image(format='PNG')
        mock_file = self.create_mock_upload_file("test.jpg", content, "image/png")
        
        with patch('magic.from_buffer', return_value='image/png'):
            result = await file_validator.validate_file(mock_file)
        
        # MIME type PNG olduğu için geçersiz olmalı (JPG uzantısı bekleniyor)
        assert result['valid'] is False
    
    @pytest.mark.asyncio
    async def test_correct_extension_wrong_content(self):
        """Doğru uzantı yanlış içerik testi"""
        # Text içeriği ama JPG uzantısı
        text_content = b"This is not an image"
        mock_file = self.create_mock_upload_file("fake.jpg", text_content, "text/plain")
        
        with patch('magic.from_buffer', return_value='text/plain'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Desteklenmeyen MIME type' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_case_insensitive_extensions(self):
        """Büyük/küçük harf duyarsız uzantı testi"""
        content = self.create_test_image()
        
        test_cases = ["test.JPG", "test.Jpg", "test.jPg", "test.JPEG"]
        
        for filename in test_cases:
            mock_file = self.create_mock_upload_file(filename, content, "image/jpeg")
            
            with patch('magic.from_buffer', return_value='image/jpeg'):
                result = await file_validator.validate_file(mock_file)
            
            assert result['valid'] is True, f"Failed for filename: {filename}"
    
    @pytest.mark.asyncio
    async def test_grayscale_image(self):
        """Gri tonlamalı görsel testi"""
        content = self.create_test_image(mode='L')  # Grayscale
        mock_file = self.create_mock_upload_file("grayscale.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert result['metadata']['mode'] == 'L'
    
    @pytest.mark.asyncio
    async def test_rgba_image(self):
        """RGBA görsel testi"""
        content = self.create_test_image(mode='RGBA')
        mock_file = self.create_mock_upload_file("rgba.png", content, "image/png")
        
        with patch('magic.from_buffer', return_value='image/png'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert result['metadata']['mode'] == 'RGBA'
    
    @pytest.mark.asyncio
    async def test_cmyk_image(self):
        """CMYK görsel testi"""
        content = self.create_test_image(mode='CMYK')
        mock_file = self.create_mock_upload_file("cmyk.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert any('Beklenmeyen renk modu' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_multispectral_insufficient_bands(self):
        """Yetersiz band sayısı multispektral testi"""
        tiff_content = b'II*\x00'
        mock_file = self.create_mock_upload_file("insufficient.tif", tiff_content, "image/tiff")
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('rasterio.open') as mock_rasterio:
            
            mock_dataset = MagicMock()
            mock_dataset.width = 1024
            mock_dataset.height = 768
            mock_dataset.count = 2  # Sadece 2 band
            mock_dataset.dtypes = ['uint8']
            mock_dataset.crs = 'EPSG:4326'
            mock_dataset.bounds = (0, 0, 1, 1)
            
            mock_rasterio.return_value.__enter__.return_value = mock_dataset
            
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert any('Az band sayısı' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_multispectral_no_coordinate_system(self):
        """Koordinat sistemi olmayan multispektral testi"""
        tiff_content = b'II*\x00'
        mock_file = self.create_mock_upload_file("no_crs.tif", tiff_content, "image/tiff")
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('rasterio.open') as mock_rasterio:
            
            mock_dataset = MagicMock()
            mock_dataset.width = 1024
            mock_dataset.height = 768
            mock_dataset.count = 4
            mock_dataset.dtypes = ['uint16']
            mock_dataset.crs = None  # CRS yok
            mock_dataset.bounds = (0, 0, 1, 1)
            
            mock_rasterio.return_value.__enter__.return_value = mock_dataset
            
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert any('Koordinat sistemi bilgisi bulunamadı' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_multispectral_unusual_data_type(self):
        """Alışılmadık veri tipi multispektral testi"""
        tiff_content = b'II*\x00'
        mock_file = self.create_mock_upload_file("unusual_dtype.tif", tiff_content, "image/tiff")
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('rasterio.open') as mock_rasterio:
            
            mock_dataset = MagicMock()
            mock_dataset.width = 1024
            mock_dataset.height = 768
            mock_dataset.count = 4
            mock_dataset.dtypes = ['complex64']  # Alışılmadık tip
            mock_dataset.crs = 'EPSG:4326'
            mock_dataset.bounds = (0, 0, 1, 1)
            
            mock_rasterio.return_value.__enter__.return_value = mock_dataset
            
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert any('Beklenmeyen veri tipi' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_multiple_files_all_invalid(self):
        """Tüm dosyalar geçersiz çoklu dosya testi"""
        invalid_files = [
            self.create_mock_upload_file("", b"empty", "image/jpeg"),  # Boş isim
            self.create_mock_upload_file("huge.jpg", b'x' * (MAX_FILE_SIZE + 1), "image/jpeg"),  # Çok büyük
            self.create_mock_upload_file("wrong.txt", b"text", "text/plain"),  # Yanlış tip
        ]
        
        result = await file_validator.validate_multiple_files(invalid_files)
        
        assert result['valid'] is False
        assert result['summary']['valid_files'] == 0
        assert result['summary']['invalid_files'] == 3
        assert any('Hiç geçerli dosya bulunamadı' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_multiple_files_mixed_validity(self):
        """Karışık geçerlilik çoklu dosya testi"""
        valid_content = self.create_test_image()
        invalid_content = b'not an image'
        
        files = [
            self.create_mock_upload_file("valid.jpg", valid_content, "image/jpeg"),
            self.create_mock_upload_file("invalid.jpg", invalid_content, "image/jpeg"),
            self.create_mock_upload_file("valid2.png", valid_content, "image/png"),
        ]
        
        with patch('magic.from_buffer') as mock_magic:
            mock_magic.side_effect = ['image/jpeg', 'image/jpeg', 'image/png']
            
            result = await file_validator.validate_multiple_files(files)
        
        assert result['valid'] is False  # En az bir geçersiz var
        assert result['summary']['valid_files'] == 2
        assert result['summary']['invalid_files'] == 1
    
    @pytest.mark.asyncio
    async def test_duplicate_file_detection(self):
        """Duplicate dosya tespiti testi"""
        content = self.create_test_image()
        
        files = [
            self.create_mock_upload_file("file1.jpg", content, "image/jpeg"),
            self.create_mock_upload_file("file2.jpg", content, "image/jpeg"),  # Aynı içerik
            self.create_mock_upload_file("file3.jpg", content, "image/jpeg"),  # Aynı içerik
        ]
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_multiple_files(files)
        
        # Duplicate uyarıları olmalı
        duplicate_warnings = [w for w in result['warnings'] if 'Duplicate dosya' in w]
        assert len(duplicate_warnings) >= 2  # En az 2 duplicate uyarısı
    
    @pytest.mark.asyncio
    async def test_file_type_distribution_warnings(self):
        """Dosya tipi dağılımı uyarıları testi"""
        # Sadece RGB dosyalar
        rgb_content = self.create_test_image()
        rgb_files = [
            self.create_mock_upload_file(f"rgb{i}.jpg", rgb_content, "image/jpeg")
            for i in range(3)
        ]
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_multiple_files(rgb_files)
        
        assert any('Multispektral dosya bulunamadı' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_rasterio_exception_handling(self):
        """Rasterio exception handling testi"""
        tiff_content = b'II*\x00'
        mock_file = self.create_mock_upload_file("error.tif", tiff_content, "image/tiff")
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('rasterio.open', side_effect=Exception("Rasterio error")):
            
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Multispektral validasyon hatası' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_magic_library_exception(self):
        """Magic library exception handling testi"""
        content = self.create_test_image()
        mock_file = self.create_mock_upload_file("test.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', side_effect=Exception("Magic error")):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('validasyon hatası' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_pil_exception_handling(self):
        """PIL exception handling testi"""
        content = b"fake image content"
        mock_file = self.create_mock_upload_file("fake.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('validasyon hatası' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_temporary_file_cleanup(self):
        """Geçici dosya temizleme testi"""
        tiff_content = b'II*\x00'
        mock_file = self.create_mock_upload_file("cleanup_test.tif", tiff_content, "image/tiff")
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('tempfile.mktemp', return_value='/tmp/test_file'), \
             patch('os.path.exists', return_value=True), \
             patch('os.remove') as mock_remove, \
             patch('rasterio.open', side_effect=Exception("Test error")):
            
            result = await file_validator.validate_file(mock_file)
            
            # Hata durumunda bile geçici dosya temizlenmeli
            mock_remove.assert_called()

class TestFileValidatorConfiguration:
    """FileValidator yapılandırma testleri"""
    
    def test_custom_file_size_limit(self):
        """Özel dosya boyutu limiti testi"""
        validator = FileValidator()
        
        # Varsayılan limit
        assert validator.max_file_size == MAX_FILE_SIZE
        
        # Özel limit ayarlama
        validator.max_file_size = 50 * 1024 * 1024  # 50MB
        assert validator.max_file_size == 50 * 1024 * 1024
    
    def test_custom_resolution_limits(self):
        """Özel çözünürlük limitleri testi"""
        validator = FileValidator()
        
        # Varsayılan limitler
        assert validator.min_image_size == MIN_IMAGE_SIZE
        assert validator.max_image_size == MAX_IMAGE_SIZE
        
        # Özel limitler
        validator.min_image_size = (256, 256)
        validator.max_image_size = (8192, 8192)
        
        assert validator.min_image_size == (256, 256)
        assert validator.max_image_size == (8192, 8192)
    
    def test_allowed_extensions_modification(self):
        """İzin verilen uzantılar değiştirme testi"""
        validator = FileValidator()
        
        # Yeni uzantı ekleme
        validator.allowed_extensions['video'] = ['.mp4', '.avi']
        
        assert 'video' in validator.allowed_extensions
        assert '.mp4' in validator.allowed_extensions['video']

# Test çalıştırma
if __name__ == "__main__":
    pytest.main([__file__, "-v"])