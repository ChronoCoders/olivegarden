import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection with row factory"""
    try:
        conn = sqlite3.connect(settings.DATABASE_URL, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Dict-like access
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def init_db():
    """Initialize database and create all tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                kullanici_id INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici_adi TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                rol TEXT DEFAULT 'standart' CHECK (rol IN ('admin', 'premium', 'standart')),
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT NOT NULL,
                last_login TEXT,
                profile_data TEXT  -- JSON string for additional profile data
            )
        ''')
        
        # User sessions table for refresh tokens
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                refresh_token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (kullanici_id) ON DELETE CASCADE
            )
        ''')
        
        # API keys table for premium users
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT,
                is_active BOOLEAN DEFAULT 1,
                usage_count INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (kullanici_id) ON DELETE CASCADE
            )
        ''')
        
        # API usage logs for monitoring and rate limiting
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_usage_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                endpoint TEXT NOT NULL,
                method TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                ip_address TEXT NOT NULL,
                duration REAL DEFAULT 0.0,
                user_agent TEXT,
                request_size INTEGER DEFAULT 0,
                response_size INTEGER DEFAULT 0,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (kullanici_id) ON DELETE SET NULL
            )
        ''')
        
        # Enhanced analyses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analizler (
                analiz_id TEXT PRIMARY KEY,
                kullanici_id INTEGER,
                tarih_saat TEXT NOT NULL,
                dosya_sayisi INTEGER DEFAULT 0,
                toplam_agac INTEGER DEFAULT 0,
                toplam_zeytin INTEGER DEFAULT 0,
                tahmini_zeytin_miktari REAL DEFAULT 0.0,
                ndvi_ortalama REAL DEFAULT 0.0,
                gndvi_ortalama REAL DEFAULT 0.0,
                ndre_ortalama REAL DEFAULT 0.0,
                saglik_durumu TEXT DEFAULT '',
                agac_cap_ortalama REAL DEFAULT 0.0,
                ndvi_path TEXT DEFAULT '',
                pdf_path TEXT DEFAULT '',
                excel_path TEXT DEFAULT '',
                geojson_path TEXT DEFAULT '',
                log_path TEXT DEFAULT '',
                durum TEXT DEFAULT 'yuklendi' CHECK (durum IN ('yuklendi', 'isleniyor', 'tamamlandi', 'hata')),
                analiz_modu TEXT DEFAULT 'cpu' CHECK (analiz_modu IN ('cpu', 'gpu')),
                kullanilan_cihaz TEXT DEFAULT 'cpu',
                analiz_suresi REAL DEFAULT 0.0,
                hata_mesaji TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (kullanici_id) REFERENCES users (kullanici_id) ON DELETE SET NULL
            )
        ''')
        
        # File uploads table for tracking uploaded files
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_uploads (
                upload_id INTEGER PRIMARY KEY AUTOINCREMENT,
                analiz_id TEXT NOT NULL,
                dosya_adi TEXT NOT NULL,
                dosya_boyutu INTEGER NOT NULL,
                dosya_tipi TEXT NOT NULL,
                dosya_hash TEXT NOT NULL,
                upload_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (analiz_id) REFERENCES analizler (analiz_id) ON DELETE CASCADE
            )
        ''')
        
        # System settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT NOT NULL,
                setting_type TEXT DEFAULT 'string' CHECK (setting_type IN ('string', 'integer', 'float', 'boolean', 'json')),
                description TEXT,
                updated_at TEXT NOT NULL,
                updated_by INTEGER,
                FOREIGN KEY (updated_by) REFERENCES users (kullanici_id) ON DELETE SET NULL
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users (kullanici_adi)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions (refresh_token)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys (api_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_logs_user ON api_usage_logs (user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_logs_timestamp ON api_usage_logs (timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analizler_user ON analizler (kullanici_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_analizler_date ON analizler (tarih_saat)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_uploads_analiz ON file_uploads (analiz_id)')
        
        # Insert default system settings
        default_settings = [
            ('max_file_size', '104857600', 'integer', 'Maximum file size in bytes (100MB)'),
            ('max_files_per_analysis', '10', 'integer', 'Maximum files per analysis'),
            ('default_analysis_mode', 'cpu', 'string', 'Default analysis mode'),
            ('rate_limit_requests', '100', 'integer', 'Rate limit requests per hour'),
            ('rate_limit_window', '3600', 'integer', 'Rate limit window in seconds'),
            ('backup_retention_days', '30', 'integer', 'Backup retention period in days'),
            ('log_retention_days', '90', 'integer', 'Log retention period in days'),
            ('maintenance_mode', 'false', 'boolean', 'System maintenance mode'),
        ]
        
        for key, value, type_, desc in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO system_settings (setting_key, setting_value, setting_type, description, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, value, type_, desc, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

def create_analysis(analiz_id: str, dosya_sayisi: int, kullanici_id: Optional[int] = None):
    """Create new analysis record"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO analizler (analiz_id, kullanici_id, tarih_saat, dosya_sayisi, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            analiz_id, 
            kullanici_id, 
            datetime.now().isoformat(), 
            dosya_sayisi,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Analysis created: {analiz_id}")
        
    except Exception as e:
        logger.error(f"Create analysis error: {e}")
        raise

def get_analysis(analiz_id: str) -> Optional[Dict]:
    """Get analysis record by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM analizler WHERE analiz_id = ?', (analiz_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        return dict(row) if row else None
        
    except Exception as e:
        logger.error(f"Get analysis error: {e}")
        return None

def update_analysis(analiz_id: str, analiz_sonuclari: Dict, rapor_sonuclari: Dict):
    """Update analysis with results"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE analizler SET
                toplam_agac = ?,
                toplam_zeytin = ?,
                tahmini_zeytin_miktari = ?,
                ndvi_ortalama = ?,
                gndvi_ortalama = ?,
                ndre_ortalama = ?,
                saglik_durumu = ?,
                agac_cap_ortalama = ?,
                ndvi_path = ?,
                pdf_path = ?,
                excel_path = ?,
                geojson_path = ?,
                durum = 'tamamlandi',
                analiz_modu = ?,
                kullanilan_cihaz = ?,
                analiz_suresi = ?,
                updated_at = ?
            WHERE analiz_id = ?
        ''', (
            analiz_sonuclari['toplam_agac'],
            analiz_sonuclari['toplam_zeytin'],
            analiz_sonuclari['tahmini_zeytin_miktari'],
            analiz_sonuclari['ndvi_ortalama'],
            analiz_sonuclari.get('gndvi_ortalama', 0.0),
            analiz_sonuclari.get('ndre_ortalama', 0.0),
            analiz_sonuclari['saglik_durumu'],
            analiz_sonuclari.get('agac_cap_ortalama', 0.0),
            analiz_sonuclari.get('ndvi_path', ''),
            rapor_sonuclari['pdf_path'],
            rapor_sonuclari['excel_path'],
            rapor_sonuclari['geojson_path'],
            analiz_sonuclari.get('analiz_modu', 'cpu'),
            analiz_sonuclari.get('kullanilan_cihaz', 'cpu'),
            analiz_sonuclari.get('analiz_suresi', 0.0),
            datetime.now().isoformat(),
            analiz_id
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Analysis updated: {analiz_id}")
        
    except Exception as e:
        logger.error(f"Update analysis error: {e}")
        raise

def update_analysis_status(analiz_id: str, durum: str, hata_mesaji: Optional[str] = None):
    """Update analysis status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE analizler SET durum = ?, hata_mesaji = ?, updated_at = ?
            WHERE analiz_id = ?
        ''', (durum, hata_mesaji, datetime.now().isoformat(), analiz_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Update analysis status error: {e}")

def get_all_analyses(kullanici_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
    """Get all analyses (optionally filtered by user)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if kullanici_id:
            cursor.execute('''
                SELECT * FROM analizler 
                WHERE kullanici_id = ? 
                ORDER BY tarih_saat DESC 
                LIMIT ?
            ''', (kullanici_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM analizler 
                ORDER BY tarih_saat DESC 
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        logger.error(f"Get all analyses error: {e}")
        return []

def add_file_upload(analiz_id: str, dosya_adi: str, dosya_boyutu: int, 
                   dosya_tipi: str, dosya_hash: str, upload_path: str):
    """Add file upload record"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO file_uploads 
            (analiz_id, dosya_adi, dosya_boyutu, dosya_tipi, dosya_hash, upload_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            analiz_id, dosya_adi, dosya_boyutu, dosya_tipi, 
            dosya_hash, upload_path, datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Add file upload error: {e}")

def get_system_setting(key: str, default_value: str = None) -> str:
    """Get system setting value"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT setting_value FROM system_settings WHERE setting_key = ?', (key,))
        row = cursor.fetchone()
        
        conn.close()
        
        return row['setting_value'] if row else default_value
        
    except Exception as e:
        logger.error(f"Get system setting error: {e}")
        return default_value

def set_system_setting(key: str, value: str, setting_type: str = 'string', 
                      description: str = '', updated_by: Optional[int] = None):
    """Set system setting value"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO system_settings 
            (setting_key, setting_value, setting_type, description, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (key, value, setting_type, description, datetime.now().isoformat(), updated_by))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Set system setting error: {e}")

def cleanup_old_sessions():
    """Clean up expired sessions"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM user_sessions 
            WHERE expires_at < ?
        ''', (datetime.now().isoformat(),))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired sessions")
        
    except Exception as e:
        logger.error(f"Session cleanup error: {e}")

def cleanup_old_logs(retention_days: int = 90):
    """Clean up old API logs"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
        
        cursor.execute('''
            DELETE FROM api_usage_logs 
            WHERE timestamp < ?
        ''', (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old log entries")
        
    except Exception as e:
        logger.error(f"Log cleanup error: {e}")

def get_user_analysis_stats(kullanici_id: int) -> Dict:
    """Get user analysis statistics"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Total analyses
        cursor.execute('''
            SELECT COUNT(*) as total_analyses,
                   COUNT(CASE WHEN durum = 'tamamlandi' THEN 1 END) as completed_analyses,
                   COUNT(CASE WHEN durum = 'hata' THEN 1 END) as failed_analyses,
                   AVG(CASE WHEN analiz_suresi > 0 THEN analiz_suresi END) as avg_duration
            FROM analizler WHERE kullanici_id = ?
        ''', (kullanici_id,))
        
        stats = dict(cursor.fetchone())
        
        # Recent analyses
        cursor.execute('''
            SELECT analiz_id, tarih_saat, durum, analiz_modu, analiz_suresi
            FROM analizler 
            WHERE kullanici_id = ? 
            ORDER BY tarih_saat DESC 
            LIMIT 5
        ''', (kullanici_id,))
        
        recent_analyses = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        stats['recent_analyses'] = recent_analyses
        return stats
        
    except Exception as e:
        logger.error(f"Get user stats error: {e}")
        return {
            'total_analyses': 0,
            'completed_analyses': 0,
            'failed_analyses': 0,
            'avg_duration': 0,
            'recent_analyses': []
        }

# Database maintenance functions
def vacuum_database():
    """Vacuum database to reclaim space"""
    try:
        conn = get_db_connection()
        conn.execute('VACUUM')
        conn.close()
        logger.info("Database vacuumed successfully")
    except Exception as e:
        logger.error(f"Database vacuum error: {e}")

def analyze_database():
    """Analyze database for query optimization"""
    try:
        conn = get_db_connection()
        conn.execute('ANALYZE')
        conn.close()
        logger.info("Database analyzed successfully")
    except Exception as e:
        logger.error(f"Database analyze error: {e}")