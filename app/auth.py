from fastapi import HTTPException, status
from passlib.context import CryptContext
from datetime import datetime, timedelta
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY", "please-set-secure-secret-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db, username: str, password: str):
    user = db.get_user(username)
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yanlış kullanıcı adı veya şifre",
        )
    return user

# Admin için sabit şifre mantığı kaldırıldı; kullanıcı yöneticisi arayüzü kullanılmalı
