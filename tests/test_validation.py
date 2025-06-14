import pytest
import asyncio
import io
import os
from unittest.mock import MagicMock, patch
from PIL import Image
import numpy as np

# Test için gerekli importlar
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.validation import file_validator

class TestFileValidation:
    
    def create_test_image(self, width=1024, height=768, format='JPEG'):
        """Test için sahte görsel oluştur"""
        # RGB görsel oluştur
        image = Image.new('RGB', (width, height), color='red')
        
        # BytesIO buffer'a kaydet
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
    async def test_valid_jpeg_image(self):
        """Geçerli JPEG görsel testi"""
        content = self.create_test_image(1024, 768, 'JPEG')
        mock_file = self.create_mock_upload_file("test.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert result['file_type'] == 'image'
        assert result['metadata']['width'] == 1024
        assert result['metadata']['height'] == 768
        assert len(result['errors']) == 0
    
    @pytest.mark.asyncio
    async def test_valid_png_image(self):
        """Geçerli PNG görsel testi"""
        content = self.create_test_image(800, 600, 'PNG')
        mock_file = self.create_mock_upload_file("test.png", content, "image/png")
        
        with patch('magic.from_buffer', return_value='image/png'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert result['file_type'] == 'image'
        assert result['metadata']['format'] == 'PNG'
    
    @pytest.mark.asyncio
    async def test_image_too_small(self):
        """Çok küçük görsel testi"""
        content = self.create_test_image(256, 256, 'JPEG')  # Minimum 512x512
        mock_file = self.create_mock_upload_file("small.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('çözünürlüğü çok düşük' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_image_too_large(self):
        """Çok büyük görsel testi"""
        content = self.create_test_image(12000, 12000, 'JPEG')  # Maximum 10000x10000
        mock_file = self.create_mock_upload_file("large.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        # Büyük görsel uyarı vermeli ama geçerli olmalı
        assert result['valid'] is True
        assert any('çözünürlüğü çok yüksek' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """Çok büyük dosya testi"""
        # 150MB'lık sahte içerik (limit 100MB)
        large_content = b'x' * (150 * 1024 * 1024)
        mock_file = self.create_mock_upload_file("large.jpg", large_content, "image/jpeg")
        
        result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Dosya çok büyük' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_invalid_extension(self):
        """Geçersiz uzantı testi"""
        content = self.create_test_image()
        mock_file = self.create_mock_upload_file("test.bmp", content, "image/bmp")
        
        result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Desteklenmeyen dosya uzantısı' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_invalid_mime_type(self):
        """Geçersiz MIME type testi"""
        content = self.create_test_image()
        mock_file = self.create_mock_upload_file("test.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='application/pdf'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Desteklenmeyen MIME type' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_corrupted_image(self):
        """Bozuk görsel testi"""
        corrupted_content = b'not an image'
        mock_file = self.create_mock_upload_file("corrupted.jpg", corrupted_content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('validasyon hatası' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_multispectral_file(self):
        """Multispektral dosya testi"""
        # Sahte TIFF içeriği
        tiff_content = b'II*\x00'  # TIFF header
        mock_file = self.create_mock_upload_file("multispectral.tif", tiff_content, "image/tiff")
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('rasterio.open') as mock_rasterio:
            
            # Mock rasterio dataset
            mock_dataset = MagicMock()
            mock_dataset.width = 1024
            mock_dataset.height = 768
            mock_dataset.count = 4  # 4 band
            mock_dataset.dtypes = ['uint16']
            mock_dataset.crs = 'EPSG:4326'
            mock_dataset.bounds = (0, 0, 1, 1)
            
            mock_rasterio.return_value.__enter__.return_value = mock_dataset
            
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert result['file_type'] == 'multispectral'
        assert result['metadata']['band_count'] == 4
        assert result['metadata']['has_nir'] is True
    
    @pytest.mark.asyncio
    async def test_multispectral_no_crs(self):
        """CRS bilgisi olmayan multispektral dosya testi"""
        tiff_content = b'II*\x00'
        mock_file = self.create_mock_upload_file("no_crs.tif", tiff_content, "image/tiff")
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('rasterio.open') as mock_rasterio:
            
            mock_dataset = MagicMock()
            mock_dataset.width = 1024
            mock_dataset.height = 768
            mock_dataset.count = 3
            mock_dataset.dtypes = ['uint8']
            mock_dataset.crs = None  # CRS yok
            mock_dataset.bounds = (0, 0, 1, 1)
            
            mock_rasterio.return_value.__enter__.return_value = mock_dataset
            
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert any('Koordinat sistemi bilgisi bulunamadı' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_multiple_files_validation(self):
        """Çoklu dosya validasyon testi"""
        # Geçerli dosyalar
        valid_content1 = self.create_test_image(1024, 768, 'JPEG')
        valid_content2 = self.create_test_image(800, 600, 'PNG')
        
        # Geçersiz dosya
        invalid_content = b'not an image'
        
        files = [
            self.create_mock_upload_file("valid1.jpg", valid_content1, "image/jpeg"),
            self.create_mock_upload_file("valid2.png", valid_content2, "image/png"),
            self.create_mock_upload_file("invalid.jpg", invalid_content, "image/jpeg")
        ]
        
        with patch('magic.from_buffer') as mock_magic:
            # İlk iki dosya için geçerli MIME type
            mock_magic.side_effect = ['image/jpeg', 'image/png', 'image/jpeg']
            
            result = await file_validator.validate_multiple_files(files)
        
        assert result['valid'] is False  # Bir dosya geçersiz
        assert result['summary']['total_files'] == 3
        assert result['summary']['valid_files'] == 2
        assert result['summary']['invalid_files'] == 1
    
    @pytest.mark.asyncio
    async def test_duplicate_files(self):
        """Duplicate dosya testi"""
        content = self.create_test_image()
        
        files = [
            self.create_mock_upload_file("file1.jpg", content, "image/jpeg"),
            self.create_mock_upload_file("file2.jpg", content, "image/jpeg")  # Aynı içerik
        ]
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_multiple_files(files)
        
        assert any('Duplicate dosya' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_no_rgb_files(self):
        """RGB dosya olmayan durum testi"""
        tiff_content = b'II*\x00'
        
        files = [
            self.create_mock_upload_file("multispectral.tif", tiff_content, "image/tiff")
        ]
        
        with patch('magic.from_buffer', return_value='image/tiff'), \
             patch('rasterio.open') as mock_rasterio:
            
            mock_dataset = MagicMock()
            mock_dataset.width = 1024
            mock_dataset.height = 768
            mock_dataset.count = 4
            mock_dataset.dtypes = ['uint16']
            mock_dataset.crs = 'EPSG:4326'
            mock_dataset.bounds = (0, 0, 1, 1)
            
            mock_rasterio.return_value.__enter__.return_value = mock_dataset
            
            result = await file_validator.validate_multiple_files(files)
        
        assert any('RGB görsel bulunamadı' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_no_multispectral_files(self):
        """Multispektral dosya olmayan durum testi"""
        content = self.create_test_image()
        
        files = [
            self.create_mock_upload_file("image.jpg", content, "image/jpeg")
        ]
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_multiple_files(files)
        
        assert any('Multispektral dosya bulunamadı' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_empty_filename(self):
        """Boş dosya adı testi"""
        content = self.create_test_image()
        mock_file = self.create_mock_upload_file("", content, "image/jpeg")
        
        result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is False
        assert any('Dosya adı boş' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_file_hash_generation(self):
        """Dosya hash oluşturma testi"""
        content = self.create_test_image()
        mock_file = self.create_mock_upload_file("test.jpg", content, "image/jpeg")
        
        with patch('magic.from_buffer', return_value='image/jpeg'):
            result = await file_validator.validate_file(mock_file)
        
        assert result['valid'] is True
        assert 'file_hash' in result['metadata']
        assert len(result['metadata']['file_hash']) == 32  # MD5 hash length

# Test çalıştırma
if __name__ == "__main__":
    pytest.main([__file__, "-v"])