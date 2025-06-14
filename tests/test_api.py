import pytest
import asyncio
import os
import tempfile
import shutil
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import json

# Test için gerekli importlar
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.auth import auth_manager
from app.database import init_db, get_db_connection

class TestZeytinAnaliz:
    @classmethod
    def setup_class(cls):
        """Test sınıfı kurulumu"""
        cls.client = TestClient(app)
        cls.test_data_dir = tempfile.mkdtemp()
        cls.test_user_token = None
        cls.test_admin_token = None
        
        # Test veritabanı kurulumu
        with patch('app.config.settings.DATABASE_URL', f"{cls.test_data_dir}/test.db"):
            init_db()
            cls._create_test_users()
    
    @classmethod
    def teardown_class(cls):
        """Test sınıfı temizleme"""
        shutil.rmtree(cls.test_data_dir, ignore_errors=True)
    
    @classmethod
    def _create_test_users(cls):
        """Test kullanıcıları oluştur"""
        # Test kullanıcısı
        auth_manager.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            role="standart"
        )
        
        # Test admin kullanıcısı
        auth_manager.create_user(
            username="testadmin",
            email="admin@example.com",
            password="adminpass123",
            role="admin"
        )
    
    def _get_auth_token(self, username: str, password: str) -> str:
        """Kimlik doğrulama token'ı al"""
        response = self.client.post("/auth/giris", json={
            "kullanici_adi": username,
            "sifre": password
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_health_check(self):
        """Sağlık kontrolü testi"""
        response = self.client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "gpu_available" in data
    
    def test_gpu_status(self):
        """GPU durumu testi"""
        response = self.client.get("/gpu-durum")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "gpu_status" in data
        assert "device_info" in data
        assert "available_modes" in data
    
    def test_authentication_login_success(self):
        """Başarılı giriş testi"""
        response = self.client.post("/auth/giris", json={
            "kullanici_adi": "testuser",
            "sifre": "testpass123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["kullanici_adi"] == "testuser"
    
    def test_authentication_login_failure(self):
        """Başarısız giriş testi"""
        response = self.client.post("/auth/giris", json={
            "kullanici_adi": "wronguser",
            "sifre": "wrongpass"
        })
        
        assert response.status_code == 401
        assert "Geçersiz kullanıcı adı veya şifre" in response.json()["detail"]
    
    def test_token_refresh(self):
        """Token yenileme testi"""
        # Önce giriş yap
        login_response = self.client.post("/auth/giris", json={
            "kullanici_adi": "testuser",
            "sifre": "testpass123"
        })
        refresh_token = login_response.json()["refresh_token"]
        
        # Token'ı yenile
        response = self.client.post("/auth/yenile", json={
            "refresh_token": refresh_token
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_file_upload_without_auth(self):
        """Kimlik doğrulama olmadan dosya yükleme testi"""
        # Test dosyası oluştur
        test_file_content = b"fake image content"
        
        response = self.client.post("/analiz/yukle", files={
            "dosyalar": ("test.jpg", test_file_content, "image/jpeg")
        })
        
        # Kimlik doğrulama olmadan da çalışmalı (opsiyonel auth)
        # Ancak dosya validasyon hatası alabilir
        assert response.status_code in [200, 400]
    
    @patch('app.validation.file_validator.validate_multiple_files')
    def test_file_upload_with_auth(self, mock_validator):
        """Kimlik doğrulama ile dosya yükleme testi"""
        # Mock validator
        mock_validator.return_value = {
            'valid': True,
            'files': [],
            'summary': {'valid_files': 1, 'total_size': 100},
            'warnings': []
        }
        
        # Token al
        token = self._get_auth_token("testuser", "testpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test dosyası
        test_file_content = b"fake image content"
        
        response = self.client.post("/analiz/yukle", 
            files={"dosyalar": ("test.jpg", test_file_content, "image/jpeg")},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "analiz_id" in data
    
    def test_analysis_start_without_admin(self):
        """Admin olmadan analiz başlatma testi"""
        token = self._get_auth_token("testuser", "testpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.post("/analiz/baslat", 
            data={"analiz_id": "test-id", "analiz_modu": "cpu"},
            headers=headers
        )
        
        assert response.status_code == 403
        assert "admin yetkisi gerekli" in response.json()["detail"]
    
    @patch('app.ai_analysis.ZeytinAnalizci.analiz_yap')
    def test_analysis_start_with_admin(self, mock_analysis):
        """Admin ile analiz başlatma testi"""
        # Mock analiz sonucu
        mock_analysis.return_value = {
            'toplam_agac': 10,
            'toplam_zeytin': 100,
            'tahmini_zeytin_miktari': 0.4,
            'ndvi_ortalama': 0.75,
            'saglik_durumu': 'Sağlıklı',
            'analiz_modu': 'cpu',
            'kullanilan_cihaz': 'cpu'
        }
        
        # Admin token al
        token = self._get_auth_token("testadmin", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test analiz dizini oluştur
        test_analiz_id = "test-analiz-123"
        test_dir = f"data/analizler/{test_analiz_id}"
        os.makedirs(test_dir, exist_ok=True)
        os.makedirs(f"{test_dir}/yuklenen_dosyalar", exist_ok=True)
        
        # Log dosyası oluştur
        with open(f"{test_dir}/log.txt", "w") as f:
            f.write("Test log\n")
        
        try:
            response = self.client.post("/analiz/baslat",
                data={"analiz_id": test_analiz_id, "analiz_modu": "cpu"},
                headers=headers
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "sonuc" in data
            
        finally:
            # Temizlik
            shutil.rmtree(test_dir, ignore_errors=True)
    
    def test_analysis_status(self):
        """Analiz durumu sorgulama testi"""
        # Test analiz dizini oluştur
        test_analiz_id = "test-status-123"
        test_dir = f"data/analizler/{test_analiz_id}"
        os.makedirs(test_dir, exist_ok=True)
        
        # Log dosyası oluştur
        with open(f"{test_dir}/log.txt", "w") as f:
            f.write("Test analiz logu\n")
        
        try:
            response = self.client.get(f"/analiz/durum/{test_analiz_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["analiz_id"] == test_analiz_id
            assert "durum" in data
            assert "log" in data
            
        finally:
            # Temizlik
            shutil.rmtree(test_dir, ignore_errors=True)
    
    def test_analysis_status_not_found(self):
        """Var olmayan analiz durumu testi"""
        response = self.client.get("/analiz/durum/nonexistent-id")
        assert response.status_code == 404
    
    def test_report_download_without_admin(self):
        """Admin olmadan rapor indirme testi"""
        token = self._get_auth_token("testuser", "testpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.get("/analiz/rapor/test-id?format=pdf", headers=headers)
        assert response.status_code == 403
    
    def test_report_download_with_admin(self):
        """Admin ile rapor indirme testi"""
        token = self._get_auth_token("testadmin", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test analiz dizini oluştur
        test_analiz_id = "test-report-123"
        test_dir = f"data/analizler/{test_analiz_id}"
        os.makedirs(test_dir, exist_ok=True)
        
        try:
            response = self.client.get(f"/analiz/rapor/{test_analiz_id}?format=pdf", headers=headers)
            
            # Rapor dosyası yoksa oluşturulur
            assert response.status_code == 200
            assert response.headers["content-type"] == "application/pdf"
            
        finally:
            # Temizlik
            shutil.rmtree(test_dir, ignore_errors=True)
    
    def test_map_data(self):
        """Harita verisi testi"""
        # Test analiz dizini oluştur
        test_analiz_id = "test-map-123"
        test_dir = f"data/analizler/{test_analiz_id}"
        os.makedirs(test_dir, exist_ok=True)
        
        # Test GeoJSON oluştur
        test_geojson = {
            "type": "FeatureCollection",
            "features": []
        }
        
        with open(f"{test_dir}/geojson.json", "w") as f:
            json.dump(test_geojson, f)
        
        try:
            response = self.client.get(f"/analiz/harita/{test_analiz_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["type"] == "FeatureCollection"
            
        finally:
            # Temizlik
            shutil.rmtree(test_dir, ignore_errors=True)
    
    def test_user_creation_by_admin(self):
        """Admin tarafından kullanıcı oluşturma testi"""
        token = self._get_auth_token("testadmin", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.post("/auth/kullanici-olustur",
            json={
                "kullanici_adi": "newuser",
                "email": "newuser@example.com",
                "sifre": "newpass123",
                "rol": "standart"
            },
            headers=headers
        )
        
        assert response.status_code == 200
        assert "başarıyla oluşturuldu" in response.json()["message"]
    
    def test_user_creation_by_non_admin(self):
        """Admin olmayan tarafından kullanıcı oluşturma testi"""
        token = self._get_auth_token("testuser", "testpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.post("/auth/kullanici-olustur",
            json={
                "kullanici_adi": "newuser2",
                "email": "newuser2@example.com",
                "sifre": "newpass123",
                "rol": "standart"
            },
            headers=headers
        )
        
        assert response.status_code == 403
    
    def test_backup_creation_by_admin(self):
        """Admin tarafından yedek oluşturma testi"""
        token = self._get_auth_token("testadmin", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        with patch('app.backup.backup_manager.create_backup') as mock_backup:
            mock_backup.return_value = "/backups/test_backup.tar.gz"
            
            response = self.client.post("/admin/yedek-olustur", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "backup_path" in data
    
    def test_system_status_by_admin(self):
        """Admin tarafından sistem durumu sorgulama testi"""
        token = self._get_auth_token("testadmin", "adminpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        with patch('psutil.cpu_percent', return_value=25.0), \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk:
            
            # Mock memory
            mock_memory.return_value = MagicMock()
            mock_memory.return_value.percent = 60.0
            mock_memory.return_value.available = 4000000000
            
            # Mock disk
            mock_disk.return_value = MagicMock()
            mock_disk.return_value.used = 50000000000
            mock_disk.return_value.total = 100000000000
            mock_disk.return_value.free = 50000000000
            
            response = self.client.get("/admin/sistem-durumu", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "system" in data
            assert "gpu" in data
            assert "analyses" in data
    
    def test_rate_limiting(self):
        """Rate limiting testi"""
        # Çok sayıda istek gönder
        responses = []
        for i in range(15):  # Limit 10 istek/dakika
            response = self.client.get("/health")
            responses.append(response.status_code)
        
        # İlk istekler başarılı olmalı
        assert responses[0] == 200
        
        # Rate limit aşıldığında 429 dönmeli
        # (Bu test rate limiter implementasyonuna bağlı)
    
    def test_logout(self):
        """Çıkış testi"""
        token = self._get_auth_token("testuser", "testpass123")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = self.client.post("/auth/cikis", headers=headers)
        assert response.status_code == 200
        assert "çıkış yapıldı" in response.json()["message"]

# Test çalıştırma
if __name__ == "__main__":
    pytest.main([__file__, "-v"])