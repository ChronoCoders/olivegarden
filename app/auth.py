import sqlite3
import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from fastapi import HTTPException, status
import logging
from .config import settings
from .database import get_db_connection

logger = logging.getLogger(__name__)

class AuthManager:
    """Complete Authentication Manager for Zeytin Detection System"""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
        self.blacklisted_tokens = set()  # In production, use Redis
        self._init_admin_user()
    
    def _init_admin_user(self):
        """Initialize default admin user if not exists"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if admin exists
            cursor.execute("SELECT kullanici_id FROM users WHERE kullanici_adi = ?", ("admin",))
            if not cursor.fetchone():
                # Create default admin
                hashed_password = self.get_password_hash("admin123")
                cursor.execute("""
                    INSERT INTO users (kullanici_adi, email, hashed_password, rol, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, ("admin", "admin@zeytinanaliz.com", hashed_password, "admin", datetime.now().isoformat()))
                conn.commit()
                logger.info("Default admin user created")
            
            conn.close()
        except Exception as e:
            logger.error(f"Admin user initialization error: {e}")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return self.pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return self.pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access"})
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error(f"Token creation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )
    
    def create_refresh_token(self, user_id: int) -> str:
        """Create JWT refresh token"""
        to_encode = {
            "user_id": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        }
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            
            # Store refresh token in database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_sessions (user_id, refresh_token, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            """, (
                user_id, 
                encoded_jwt, 
                datetime.now().isoformat(),
                (datetime.now() + timedelta(days=self.refresh_token_expire_days)).isoformat()
            ))
            conn.commit()
            conn.close()
            
            return encoded_jwt
        except Exception as e:
            logger.error(f"Refresh token creation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Refresh token creation failed"
            )
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        if token in self.blacklisted_tokens:
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.JWTError as e:
            logger.warning(f"Token verification error: {e}")
            return None
    
    def revoke_token(self, token: str):
        """Revoke token (add to blacklist)"""
        self.blacklisted_tokens.add(token)
        # In production, store in Redis with TTL
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with username and password"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT kullanici_id, kullanici_adi, email, hashed_password, rol, is_active
                FROM users WHERE kullanici_adi = ? OR email = ?
            """, (username, username))
            
            user = cursor.fetchone()
            conn.close()
            
            if not user:
                logger.warning(f"User not found: {username}")
                return None
            
            user_dict = dict(user)
            
            if not user_dict.get('is_active', True):
                logger.warning(f"Inactive user login attempt: {username}")
                return None
            
            if not self.verify_password(password, user_dict['hashed_password']):
                logger.warning(f"Invalid password for user: {username}")
                return None
            
            # Log successful login
            self.log_api_request(
                user_id=user_dict['kullanici_id'],
                endpoint="/auth/login",
                method="POST",
                status_code=200,
                ip_address="unknown"
            )
            
            # Remove sensitive data
            del user_dict['hashed_password']
            return user_dict
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT kullanici_id, kullanici_adi, email, rol, is_active, created_at, last_login
                FROM users WHERE kullanici_id = ?
            """, (user_id,))
            
            user = cursor.fetchone()
            conn.close()
            
            return dict(user) if user else None
            
        except Exception as e:
            logger.error(f"Get user error: {e}")
            return None
    
    def create_user(self, username: str, email: str, password: str, role: str = "standart") -> bool:
        """Create new user"""
        try:
            # Validate input
            if len(username) < 3 or len(password) < 8:
                return False
            
            if role not in ["admin", "premium", "standart"]:
                role = "standart"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("""
                SELECT kullanici_id FROM users 
                WHERE kullanici_adi = ? OR email = ?
            """, (username, email))
            
            if cursor.fetchone():
                conn.close()
                return False
            
            # Create user
            hashed_password = self.get_password_hash(password)
            cursor.execute("""
                INSERT INTO users (kullanici_adi, email, hashed_password, rol, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, email, hashed_password, role, datetime.now().isoformat(), True))
            
            conn.commit()
            conn.close()
            
            logger.info(f"User created: {username} ({role})")
            return True
            
        except Exception as e:
            logger.error(f"User creation error: {e}")
            return False
    
    def update_last_login(self, user_id: int):
        """Update user's last login timestamp"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users SET last_login = ? WHERE kullanici_id = ?
            """, (datetime.now().isoformat(), user_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Update last login error: {e}")
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Refresh access token using refresh token"""
        try:
            # Verify refresh token
            payload = self.verify_token(refresh_token)
            if not payload or payload.get("type") != "refresh":
                return None
            
            user_id = payload.get("user_id")
            if not user_id:
                return None
            
            # Check if refresh token exists in database
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT session_id FROM user_sessions 
                WHERE user_id = ? AND refresh_token = ? AND expires_at > ?
            """, (user_id, refresh_token, datetime.now().isoformat()))
            
            if not cursor.fetchone():
                conn.close()
                return None
            
            # Get user data
            user = self.get_user_by_id(user_id)
            if not user:
                conn.close()
                return None
            
            conn.close()
            
            # Create new access token
            return self.create_access_token({
                "user_id": user["kullanici_id"],
                "username": user["kullanici_adi"],
                "role": user["rol"]
            })
            
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return None
    
    def generate_api_key(self, user_id: int) -> Optional[str]:
        """Generate API key for premium users"""
        try:
            user = self.get_user_by_id(user_id)
            if not user or user["rol"] not in ["admin", "premium"]:
                return None
            
            api_key = f"zeytin_{secrets.token_urlsafe(32)}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO api_keys (user_id, api_key, created_at, is_active)
                VALUES (?, ?, ?, ?)
            """, (user_id, api_key, datetime.now().isoformat(), True))
            
            conn.commit()
            conn.close()
            
            return api_key
            
        except Exception as e:
            logger.error(f"API key generation error: {e}")
            return None
    
    def verify_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Verify API key"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT u.kullanici_id, u.kullanici_adi, u.rol, ak.is_active
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.kullanici_id
                WHERE ak.api_key = ? AND ak.is_active = 1 AND u.is_active = 1
            """, (api_key,))
            
            result = cursor.fetchone()
            conn.close()
            
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"API key verification error: {e}")
            return None
    
    def log_api_request(self, user_id: Optional[int], endpoint: str, method: str, 
                       status_code: int, ip_address: str, duration: float = 0.0,
                       user_agent: str = "", request_size: int = 0, response_size: int = 0):
        """Log API request for monitoring and rate limiting"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO api_usage_logs 
                (user_id, endpoint, method, status_code, ip_address, duration, 
                 user_agent, request_size, response_size, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, endpoint, method, status_code, ip_address, duration,
                user_agent, request_size, response_size, datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"API logging error: {e}")
    
    def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get analysis count
            cursor.execute("""
                SELECT COUNT(*) as analysis_count
                FROM analizler WHERE kullanici_id = ?
            """, (user_id,))
            analysis_count = cursor.fetchone()['analysis_count']
            
            # Get API usage count (last 30 days)
            thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) as api_calls
                FROM api_usage_logs 
                WHERE user_id = ? AND timestamp > ?
            """, (user_id, thirty_days_ago))
            api_calls = cursor.fetchone()['api_calls']
            
            conn.close()
            
            return {
                "analysis_count": analysis_count,
                "api_calls_30_days": api_calls,
                "user_id": user_id
            }
            
        except Exception as e:
            logger.error(f"User stats error: {e}")
            return {"analysis_count": 0, "api_calls_30_days": 0, "user_id": user_id}

# Global auth manager instance
auth_manager = AuthManager()

# Dependency functions for FastAPI
def get_current_user(token: str) -> Dict[str, Any]:
    """Get current user from token (dependency)"""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required"
        )
    
    payload = auth_manager.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = auth_manager.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user

def get_admin_user(token: str) -> Dict[str, Any]:
    """Get admin user from token (dependency)"""
    user = get_current_user(token)
    
    if user["rol"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için admin yetkisi gerekli"
        )
    
    return user

def get_current_user_optional(token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get current user from token (optional dependency)"""
    if not token:
        return None
    
    try:
        return get_current_user(token)
    except HTTPException:
        return None