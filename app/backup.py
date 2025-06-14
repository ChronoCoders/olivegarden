import os
import shutil
import sqlite3
import tarfile
import gzip
from datetime import datetime, timedelta
import logging
import subprocess
from typing import Optional
from .config import settings

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self):
        self.backup_dir = "/backups"
        self.data_dir = settings.DATA_PATH
        self.db_path = settings.DATABASE_URL
        self.retention_days = 30
        
        # Backup dizinini oluştur
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self, backup_type: str = "full") -> str:
        """Yedek oluştur"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"zeytin_analiz_{backup_type}_{timestamp}"
        backup_path = os.path.join(self.backup_dir, f"{backup_name}.tar.gz")
        
        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                # Veritabanını yedekle
                if os.path.exists(self.db_path):
                    tar.add(self.db_path, arcname="database/analiz.db")
                    logger.info(f"Veritabanı yedeklendi: {self.db_path}")
                
                # Data dizinini yedekle
                if os.path.exists(self.data_dir):
                    tar.add(self.data_dir, arcname="data")
                    logger.info(f"Veri dizini yedeklendi: {self.data_dir}")
                
                # Konfigürasyon dosyalarını yedekle
                config_files = [
                    "app/config.py",
                    "nginx/nginx.conf",
                    "gunicorn.conf.py",
                    "docker-compose.yml",
                    "requirements.txt"
                ]
                
                for config_file in config_files:
                    if os.path.exists(config_file):
                        tar.add(config_file, arcname=f"config/{os.path.basename(config_file)}")
            
            # Backup bilgilerini logla
            backup_size = os.path.getsize(backup_path)
            logger.info(f"Yedek oluşturuldu: {backup_path} ({backup_size} bytes)")
            
            return backup_path
            
        except Exception as e:
            logger.error(f"Yedek oluşturma hatası: {e}")
            if os.path.exists(backup_path):
                os.remove(backup_path)
            raise e
    
    def restore_backup(self, backup_path: str) -> bool:
        """Yedekten geri yükle"""
        try:
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"Yedek dosyası bulunamadı: {backup_path}")
            
            # Mevcut verileri yedekle
            current_backup = self.create_backup("pre_restore")
            logger.info(f"Mevcut veriler yedeklendi: {current_backup}")
            
            # Yedekten geri yükle
            with tarfile.open(backup_path, "r:gz") as tar:
                # Veritabanını geri yükle
                try:
                    tar.extract("database/analiz.db", path="/tmp")
                    shutil.move("/tmp/database/analiz.db", self.db_path)
                    logger.info("Veritabanı geri yüklendi")
                except KeyError:
                    logger.warning("Yedekte veritabanı bulunamadı")
                
                # Veri dizinini geri yükle
                try:
                    if os.path.exists(self.data_dir):
                        shutil.rmtree(self.data_dir)
                    tar.extract("data", path="/")
                    logger.info("Veri dizini geri yüklendi")
                except KeyError:
                    logger.warning("Yedekte veri dizini bulunamadı")
            
            logger.info(f"Geri yükleme tamamlandı: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Geri yükleme hatası: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Eski yedekleri temizle"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("zeytin_analiz_") and filename.endswith(".tar.gz"):
                    filepath = os.path.join(self.backup_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getctime(filepath))
                    
                    if file_time < cutoff_date:
                        os.remove(filepath)
                        logger.info(f"Eski yedek silindi: {filename}")
            
        except Exception as e:
            logger.error(f"Yedek temizleme hatası: {e}")
    
    def list_backups(self) -> list:
        """Mevcut yedekleri listele"""
        backups = []
        
        try:
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("zeytin_analiz_") and filename.endswith(".tar.gz"):
                    filepath = os.path.join(self.backup_dir, filename)
                    stat = os.stat(filepath)
                    
                    backups.append({
                        "filename": filename,
                        "path": filepath,
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
            
            # Tarihe göre sırala (en yeni önce)
            backups.sort(key=lambda x: x["created"], reverse=True)
            
        except Exception as e:
            logger.error(f"Yedek listeleme hatası: {e}")
        
        return backups
    
    def upload_to_remote(self, backup_path: str, remote_config: dict) -> bool:
        """Yedekleri uzak sunucuya yükle"""
        try:
            if remote_config.get("type") == "sftp":
                return self._upload_sftp(backup_path, remote_config)
            elif remote_config.get("type") == "s3":
                return self._upload_s3(backup_path, remote_config)
            else:
                logger.warning("Desteklenmeyen uzak depolama türü")
                return False
                
        except Exception as e:
            logger.error(f"Uzak yükleme hatası: {e}")
            return False
    
    def _upload_sftp(self, backup_path: str, config: dict) -> bool:
        """SFTP ile yükleme"""
        try:
            cmd = [
                "scp",
                "-o", "StrictHostKeyChecking=no",
                backup_path,
                f"{config['username']}@{config['host']}:{config['remote_path']}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"SFTP yükleme başarılı: {backup_path}")
                return True
            else:
                logger.error(f"SFTP yükleme hatası: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"SFTP yükleme hatası: {e}")
            return False
    
    def _upload_s3(self, backup_path: str, config: dict) -> bool:
        """S3 ile yükleme"""
        try:
            # AWS CLI kullanarak yükleme
            cmd = [
                "aws", "s3", "cp",
                backup_path,
                f"s3://{config['bucket']}/{config['prefix']}/{os.path.basename(backup_path)}"
            ]
            
            env = os.environ.copy()
            env.update({
                "AWS_ACCESS_KEY_ID": config.get("access_key", ""),
                "AWS_SECRET_ACCESS_KEY": config.get("secret_key", ""),
                "AWS_DEFAULT_REGION": config.get("region", "us-east-1")
            })
            
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                logger.info(f"S3 yükleme başarılı: {backup_path}")
                return True
            else:
                logger.error(f"S3 yükleme hatası: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"S3 yükleme hatası: {e}")
            return False

# Global backup manager instance
backup_manager = BackupManager()