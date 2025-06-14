from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import sqlite3
import hashlib
import secrets
import logging
from .config import settings
from .database import get_db_connection

logger = logging.getLogger(__name__)

# JWT ayarları
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Token blacklist (production'da Redis kullanılabilir)
token_blacklist = set()

class AuthManager:
    def __init__(self):
        self.init_auth_tables()
    
    def init_auth_tables(self):
        """Kimlik doğrulama tablolarını oluştur"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Kullanıcılar tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kullanicilar (
                kullanici_id INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici_adi TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                sifre_hash TEXT NOT NULL,
                rol TEXT DEFAULT 'standart',
                aktif BOOLEAN DEFAULT 1,
                olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
                son_giris TEXT
            )
        ''')
        
        # Refresh token tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_id TEXT PRIMARY KEY,
                kullanici_id INTEGER,
                token_hash TEXT NOT NULL,
                olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
                son_kullanim TEXT DEFAULT CURRENT_TIMESTAMP,
                aktif BOOLEAN DEFAULT 1,
                FOREIGN KEY (kullanici_id) REFERENCES kullanicilar (kullanici_id)
            )
        ''')
        
        # API log tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarih_saat TEXT DEFAULT CURRENT_TIMESTAMP,
                kullanici_id INTEGER,
                ip_adresi TEXT,
                endpoint TEXT,
                method TEXT,
                durum_kodu INTEGER,
                islem_suresi REAL,
                user_agent TEXT,
                request_size INTEGER,
                response_size INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Varsayılan admin kullanıcısı oluştur
        self.create_default_admin()
    
    def create_default_admin(self):
        """Varsayılan admin kullanıcısı oluştur"""
        try:
            admin_password = "admin123"  # Production'da değiştirilmeli
            if not self.get_user_by_username("admin"):
                self.create_user(
                    username="admin",
                    email="admin@zeytinanaliz.com",
                    password=admin_password,
                    role="admin"
                )
                logger.info("Varsayılan admin kullanıcısı oluşturuldu")
        except Exception as e:
            logger.error(f"Admin kullanıcısı oluşturma hatası: {e}")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Şifre doğrulama"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Şifre hash'leme"""
        return pwd_context.hash(password)
    
    def create_user(self, username: str, email: str, password: str, role: str = "standart") -> bool:
        """Yeni kullanıcı oluştur"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            password_hash = self.get_password_hash(password)
            
            cursor.execute('''
                INSERT INTO kullanicilar (kullanici_adi, email, sifre_hash, rol)
                VALUES (?, ?, ?, ?)
            ''', (username, email, password_hash, role))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
        except Exception as e:
            logger.error(f"Kullanıcı oluşturma hatası: {e}")
            return False
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Kullanıcı adına göre kullanıcı getir"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT kullanici_id, kullanici_adi, email, sifre_hash, rol, aktif
            FROM kullanicilar WHERE kullanici_adi = ? AND aktif = 1
        ''', (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "kullanici_id": row[0],
                "kullanici_adi": row[1],
                "email": row[2],
                "sifre_hash": row[3],
                "rol": row[4],
                "aktif": row[5]
            }
        return None
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Kullanıcı kimlik doğrulama"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not self.verify_password(password, user["sifre_hash"]):
            return None
        
        # Son giriş tarihini güncelle
        self.update_last_login(user["kullanici_id"])
        return user
    
    def update_last_login(self, user_id: int):
        """Son giriş tarihini güncelle"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE kullanicilar SET son_giris = CURRENT_TIMESTAMP
            WHERE kullanici_id = ?
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """Access token oluştur"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def create_refresh_token(self, user_id: int) -> str:
        """Refresh token oluştur"""
        token_id = secrets.token_urlsafe(32)
        token_data = {
            "user_id": user_id,
            "token_id": token_id,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        }
        
        refresh_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        
        # Veritabanına kaydet
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO refresh_tokens (token_id, kullanici_id, token_hash)
            VALUES (?, ?, ?)
        ''', (token_id, user_id, token_hash))
        
        conn.commit()
        conn.close()
        
        return refresh_token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Token doğrulama"""
        try:
            # Blacklist kontrolü
            if token in token_blacklist:
                return None
            
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: int = payload.get("user_id")
            token_type: str = payload.get("type")
            
            if user_id is None or token_type != "access":
                return None
            
            return payload
        except JWTError:
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Access token yenileme"""
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: int = payload.get("user_id")
            token_id: str = payload.get("token_id")
            token_type: str = payload.get("type")
            
            if not all([user_id, token_id, token_type == "refresh"]):
                return None
            
            # Refresh token veritabanında var mı kontrol et
            conn = get_db_connection()
            cursor = conn.cursor()
            
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            cursor.execute('''
                SELECT aktif FROM refresh_tokens 
                WHERE token_id = ? AND token_hash = ? AND aktif = 1
            ''', (token_id, token_hash))
            
            if not cursor.fetchone():
                conn.close()
                return None
            
            # Son kullanım tarihini güncelle
            cursor.execute('''
                UPDATE refresh_tokens SET son_kullanim = CURRENT_TIMESTAMP
                WHERE token_id = ?
            ''', (token_id,))
            
            conn.commit()
            conn.close()
            
            # Yeni access token oluştur
            access_token = self.create_access_token({"user_id": user_id})
            return access_token
            
        except JWTError:
            return None
    
    def revoke_token(self, token: str):
        """Token iptal etme"""
        token_blacklist.add(token)
    
    def log_api_request(self, user_id: Optional[int], ip_address: str, endpoint: str, 
                       method: str, status_code: int, duration: float, 
                       user_agent: str = "", request_size: int = 0, response_size: int = 0):
        """API isteğini logla"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO api_logs 
                (kullanici_id, ip_adresi, endpoint, method, durum_kodu, islem_suresi, 
                 user_agent, request_size, response_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, ip_address, endpoint, method, status_code, duration, 
                  user_agent, request_size, response_size))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"API log hatası: {e}")

# Global auth manager instance
auth_manager = AuthManager()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mevcut kullanıcıyı getir"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = auth_manager.verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception
    
    user = auth_manager.get_user_by_username(token_data.get("username"))
    if user is None:
        raise credentials_exception
    
    return user

async def get_admin_user(current_user: dict = Depends(get_current_user)):
    """Admin yetkisi kontrolü"""
    if current_user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli"
        )
    return current_user

# Optional dependency - kimlik doğrulama olmadan da çalışabilir
async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Opsiyonel kullanıcı bilgisi"""
    if not credentials:
        return None
    
    try:
        token_data = auth_manager.verify_token(credentials.credentials)
        if token_data:
            return auth_manager.get_user_by_username(token_data.get("username"))
    except:
        pass
    
    return None