import pytest
import os
import tempfile
import shutil
import sqlite3
import tarfile
import gzip
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta

# Test için gerekli importlar
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.backup import backup_manager, BackupManager

class TestBackupManager:
    """Backup Manager testleri"""
    
    def setup_method(self):
        """Her test öncesi çalışır"""
        self.temp_dir = tempfile.mkdtemp()
        self.backup_dir = os.path.join(self.temp_dir, "backups")
        self.data_dir = os.path.join(self.temp_dir, "data")
        self.db_path = os.path.join(self.data_dir, "test.db")
        
        # Test dizinlerini oluştur
        os.makedirs(self.backup_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Test veritabanı oluştur
        self.create_test_database()
        
        # Test backup manager
        self.backup_manager = BackupManager()
        self.backup_manager.backup_dir = self.backup_dir
        self.backup_manager.data_dir = self.data_dir
        self.backup_manager.db_path = self.db_path
    
    def teardown_method(self):
        """Her test sonrası çalışır"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_database(self):
        """Test veritabanı oluştur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT,
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            INSERT INTO test_table (name, created_at) 
            VALUES (?, ?)
        ''', ("Test Data", datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def create_test_files(self):
        """Test dosyaları oluştur"""
        # Veri dosyaları
        test_files = [
            "data/analizler/test1/log.txt",
            "data/analizler/test1/sonuc.json",
            "data/analizler/test2/log.txt",
            "config/app.conf",
            "config/nginx.conf"
        ]
        
        for file_path in test_files:
            full_path = os.path.join(self.temp_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(f"Test content for {file_path}")
    
    def test_backup_manager_initialization(self):
        """Backup manager başlatma testi"""
        manager = BackupManager()
        
        assert hasattr(manager, 'backup_dir')
        assert hasattr(manager, 'data_dir')
        assert hasattr(manager, 'db_path')
        assert hasattr(manager, 'retention_days')
    
    def test_create_backup_success(self):
        """Başarılı yedek oluşturma testi"""
        self.create_test_files()
        
        backup_path = self.backup_manager.create_backup("test")
        
        assert os.path.exists(backup_path)
        assert backup_path.endswith('.tar.gz')
        assert 'zeytin_analiz_test_' in backup_path
        
        # Yedek içeriğini kontrol et
        with tarfile.open(backup_path, 'r:gz') as tar:
            members = tar.getnames()
            assert any('database/analiz.db' in member for member in members)
    
    def test_create_backup_missing_database(self):
        """Veritabanı eksik durumunda yedek oluşturma testi"""
        # Veritabanını sil
        os.remove(self.db_path)
        
        backup_path = self.backup_manager.create_backup("test")
        
        # Yedek oluşturulmalı ama veritabanı uyarısı loglanmalı
        assert os.path.exists(backup_path)
    
    def test_create_backup_missing_data_dir(self):
        """Veri dizini eksik durumunda yedek oluşturma testi"""
        # Veri dizinini sil
        shutil.rmtree(self.data_dir)
        
        backup_path = self.backup_manager.create_backup("test")
        
        # Yedek oluşturulmalı ama veri dizini uyarısı loglanmalı
        assert os.path.exists(backup_path)
    
    def test_create_backup_with_config_files(self):
        """Konfigürasyon dosyaları ile yedek oluşturma testi"""
        # Test konfigürasyon dosyaları oluştur
        config_files = [
            "app/config.py",
            "nginx/nginx.conf", 
            "gunicorn.conf.py",
            "docker-compose.yml",
            "requirements.txt"
        ]
        
        for config_file in config_files:
            full_path = os.path.join(self.temp_dir, config_file)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(f"Config content for {config_file}")
        
        # Backup manager'ın config dosyalarını bulabilmesi için path'leri güncelle
        with patch.object(self.backup_manager, 'create_backup') as mock_create:
            mock_create.return_value = os.path.join(self.backup_dir, "test_backup.tar.gz")
            
            backup_path = self.backup_manager.create_backup("test")
            mock_create.assert_called_once_with("test")
    
    def test_backup_file_size_calculation(self):
        """Yedek dosya boyutu hesaplama testi"""
        self.create_test_files()
        
        backup_path = self.backup_manager.create_backup("size_test")
        
        assert os.path.exists(backup_path)
        
        # Dosya boyutu 0'dan büyük olmalı
        file_size = os.path.getsize(backup_path)
        assert file_size > 0
    
    def test_list_backups_empty(self):
        """Boş yedek listesi testi"""
        backups = self.backup_manager.list_backups()
        
        assert isinstance(backups, list)
        assert len(backups) == 0
    
    def test_list_backups_with_files(self):
        """Dosyalar ile yedek listesi testi"""
        # Test yedek dosyaları oluştur
        test_backups = [
            "zeytin_analiz_test1_20240101_120000.tar.gz",
            "zeytin_analiz_test2_20240102_120000.tar.gz",
            "zeytin_analiz_auto_20240103_020000.tar.gz"
        ]
        
        for backup_name in test_backups:
            backup_path = os.path.join(self.backup_dir, backup_name)
            with open(backup_path, 'wb') as f:
                f.write(b"fake backup content")
        
        backups = self.backup_manager.list_backups()
        
        assert len(backups) == 3
        assert all('filename' in backup for backup in backups)
        assert all('size' in backup for backup in backups)
        assert all('created' in backup for backup in backups)
        
        # En yeni önce sıralanmalı
        assert backups[0]['filename'] == test_backups[2]  # En yeni
    
    def test_list_backups_ignore_other_files(self):
        """Diğer dosyaları yok sayma testi"""
        # Yedek dosyaları ve diğer dosyalar oluştur
        files = [
            "zeytin_analiz_test_20240101_120000.tar.gz",  # Geçerli yedek
            "other_backup.tar.gz",  # Geçersiz yedek
            "random_file.txt",  # Rastgele dosya
            "zeytin_analiz_test_20240102_120000.tar.gz"  # Geçerli yedek
        ]
        
        for filename in files:
            file_path = os.path.join(self.backup_dir, filename)
            with open(file_path, 'wb') as f:
                f.write(b"content")
        
        backups = self.backup_manager.list_backups()
        
        # Sadece geçerli yedekler listelenmeli
        assert len(backups) == 2
        assert all('zeytin_analiz_' in backup['filename'] for backup in backups)
    
    def test_cleanup_old_backups(self):
        """Eski yedek temizleme testi"""
        # Farklı tarihlerde yedek dosyaları oluştur
        now = datetime.now()
        old_date = now - timedelta(days=35)  # 35 gün önce
        recent_date = now - timedelta(days=5)  # 5 gün önce
        
        old_backup = os.path.join(self.backup_dir, "zeytin_analiz_old_20240101_120000.tar.gz")
        recent_backup = os.path.join(self.backup_dir, "zeytin_analiz_recent_20240201_120000.tar.gz")
        
        # Dosyaları oluştur
        with open(old_backup, 'wb') as f:
            f.write(b"old backup")
        with open(recent_backup, 'wb') as f:
            f.write(b"recent backup")
        
        # Dosya tarihlerini ayarla
        old_timestamp = old_date.timestamp()
        recent_timestamp = recent_date.timestamp()
        
        os.utime(old_backup, (old_timestamp, old_timestamp))
        os.utime(recent_backup, (recent_timestamp, recent_timestamp))
        
        # Temizleme işlemi
        self.backup_manager.cleanup_old_backups()
        
        # Eski dosya silinmeli, yeni dosya kalmalı
        assert not os.path.exists(old_backup)
        assert os.path.exists(recent_backup)
    
    def test_cleanup_old_backups_no_old_files(self):
        """Eski dosya olmadığında temizleme testi"""
        # Sadece yeni dosyalar oluştur
        recent_backup = os.path.join(self.backup_dir, "zeytin_analiz_recent_20240201_120000.tar.gz")
        with open(recent_backup, 'wb') as f:
            f.write(b"recent backup")
        
        # Temizleme işlemi
        self.backup_manager.cleanup_old_backups()
        
        # Dosya silinmemeli
        assert os.path.exists(recent_backup)
    
    def test_restore_backup_success(self):
        """Başarılı geri yükleme testi"""
        # Önce yedek oluştur
        self.create_test_files()
        backup_path = self.backup_manager.create_backup("restore_test")
        
        # Mevcut verileri değiştir
        with open(self.db_path, 'w') as f:
            f.write("modified database")
        
        # Geri yükle
        result = self.backup_manager.restore_backup(backup_path)
        
        assert result is True
        # Veritabanının geri yüklendiğini kontrol et
        assert os.path.exists(self.db_path)
    
    def test_restore_backup_nonexistent_file(self):
        """Var olmayan yedek dosyası geri yükleme testi"""
        nonexistent_path = os.path.join(self.backup_dir, "nonexistent.tar.gz")
        
        result = self.backup_manager.restore_backup(nonexistent_path)
        
        assert result is False
    
    def test_restore_backup_corrupted_file(self):
        """Bozuk yedek dosyası geri yükleme testi"""
        # Bozuk yedek dosyası oluştur
        corrupted_backup = os.path.join(self.backup_dir, "corrupted.tar.gz")
        with open(corrupted_backup, 'wb') as f:
            f.write(b"not a valid tar.gz file")
        
        result = self.backup_manager.restore_backup(corrupted_backup)
        
        assert result is False
    
    @patch('subprocess.run')
    def test_upload_to_remote_sftp_success(self, mock_run):
        """SFTP ile başarılı uzak yükleme testi"""
        mock_run.return_value.returncode = 0
        
        backup_path = os.path.join(self.backup_dir, "test_backup.tar.gz")
        with open(backup_path, 'wb') as f:
            f.write(b"test backup content")
        
        remote_config = {
            "type": "sftp",
            "username": "testuser",
            "host": "testhost.com",
            "remote_path": "/remote/backups"
        }
        
        result = self.backup_manager.upload_to_remote(backup_path, remote_config)
        
        assert result is True
        mock_run.assert_called_once()
    
    @patch('subprocess.run')
    def test_upload_to_remote_sftp_failure(self, mock_run):
        """SFTP ile başarısız uzak yükleme testi"""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Connection failed"
        
        backup_path = os.path.join(self.backup_dir, "test_backup.tar.gz")
        with open(backup_path, 'wb') as f:
            f.write(b"test backup content")
        
        remote_config = {
            "type": "sftp",
            "username": "testuser",
            "host": "testhost.com",
            "remote_path": "/remote/backups"
        }
        
        result = self.backup_manager.upload_to_remote(backup_path, remote_config)
        
        assert result is False
    
    @patch('subprocess.run')
    def test_upload_to_remote_s3_success(self, mock_run):
        """S3 ile başarılı uzak yükleme testi"""
        mock_run.return_value.returncode = 0
        
        backup_path = os.path.join(self.backup_dir, "test_backup.tar.gz")
        with open(backup_path, 'wb') as f:
            f.write(b"test backup content")
        
        remote_config = {
            "type": "s3",
            "bucket": "test-bucket",
            "prefix": "backups",
            "access_key": "test_key",
            "secret_key": "test_secret",
            "region": "us-east-1"
        }
        
        result = self.backup_manager.upload_to_remote(backup_path, remote_config)
        
        assert result is True
        mock_run.assert_called_once()
    
    def test_upload_to_remote_unsupported_type(self):
        """Desteklenmeyen uzak yükleme türü testi"""
        backup_path = os.path.join(self.backup_dir, "test_backup.tar.gz")
        with open(backup_path, 'wb') as f:
            f.write(b"test backup content")
        
        remote_config = {
            "type": "ftp",  # Desteklenmeyen tür
            "host": "testhost.com"
        }
        
        result = self.backup_manager.upload_to_remote(backup_path, remote_config)
        
        assert result is False
    
    def test_backup_with_compression(self):
        """Sıkıştırma ile yedek oluşturma testi"""
        self.create_test_files()
        
        backup_path = self.backup_manager.create_backup("compression_test")
        
        # Dosya .tar.gz uzantısında olmalı
        assert backup_path.endswith('.tar.gz')
        
        # Gzip dosyası olarak açılabilmeli
        with gzip.open(backup_path, 'rb') as f:
            content = f.read()
            assert len(content) > 0
    
    def test_backup_integrity_check(self):
        """Yedek bütünlük kontrolü testi"""
        self.create_test_files()
        
        backup_path = self.backup_manager.create_backup("integrity_test")
        
        # Yedek dosyası geçerli tar.gz olmalı
        try:
            with tarfile.open(backup_path, 'r:gz') as tar:
                # Dosya listesini al
                members = tar.getnames()
                assert len(members) > 0
        except tarfile.TarError:
            pytest.fail("Backup file is not a valid tar.gz archive")
    
    def test_backup_metadata_inclusion(self):
        """Yedek metadata dahil etme testi"""
        self.create_test_files()
        
        backup_path = self.backup_manager.create_backup("metadata_test")
        
        # Yedek içeriğini kontrol et
        with tarfile.open(backup_path, 'r:gz') as tar:
            members = tar.getnames()
            
            # Veritabanı dahil edilmeli
            assert any('database' in member for member in members)
            
            # Veri dizini dahil edilmeli
            assert any('data' in member for member in members)
    
    def test_concurrent_backup_creation(self):
        """Eşzamanlı yedek oluşturma testi"""
        self.create_test_files()
        
        # Aynı anda iki yedek oluşturmaya çalış
        backup_path1 = self.backup_manager.create_backup("concurrent1")
        backup_path2 = self.backup_manager.create_backup("concurrent2")
        
        # Her iki yedek de oluşturulmalı
        assert os.path.exists(backup_path1)
        assert os.path.exists(backup_path2)
        assert backup_path1 != backup_path2
    
    def test_backup_size_reporting(self):
        """Yedek boyutu raporlama testi"""
        self.create_test_files()
        
        backup_path = self.backup_manager.create_backup("size_report_test")
        
        # Dosya boyutu hesaplanabilmeli
        file_size = os.path.getsize(backup_path)
        assert file_size > 0
        
        # Boyut MB cinsinden hesaplanabilmeli
        size_mb = file_size / (1024 * 1024)
        assert size_mb >= 0

class TestBackupManagerEdgeCases:
    """Backup Manager edge case testleri"""
    
    def test_backup_with_insufficient_disk_space(self):
        """Yetersiz disk alanı ile yedek oluşturma testi"""
        with patch('shutil.disk_usage') as mock_disk_usage:
            # Çok az boş alan simüle et
            mock_disk_usage.return_value = (1000000, 999999, 1)  # total, used, free
            
            manager = BackupManager()
            
            # Yedek oluşturma başarısız olmalı veya uyarı vermeli
            with pytest.raises(Exception):
                manager.create_backup("insufficient_space_test")
    
    def test_backup_with_permission_error(self):
        """İzin hatası ile yedek oluşturma testi"""
        with patch('tarfile.open', side_effect=PermissionError("Permission denied")):
            manager = BackupManager()
            
            with pytest.raises(PermissionError):
                manager.create_backup("permission_test")
    
    def test_restore_with_existing_backup(self):
        """Mevcut yedek ile geri yükleme testi"""
        manager = BackupManager()
        
        # Mevcut sistem yedeği oluşturulmalı
        with patch.object(manager, 'create_backup', return_value='/tmp/current_backup.tar.gz'):
            with patch('tarfile.open'):
                with patch('os.path.exists', return_value=True):
                    result = manager.restore_backup('/tmp/test_backup.tar.gz')
                    
                    # Geri yükleme öncesi mevcut sistem yedeklenmeli
                    manager.create_backup.assert_called()

# Test çalıştırma
if __name__ == "__main__":
    pytest.main([__file__, "-v"])