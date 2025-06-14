from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
from typing import Callable
from .auth import auth_manager
from .rate_limiter import rate_limiter

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """API isteklerini loglama middleware'i"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # İstek bilgileri
        ip_address = rate_limiter.get_client_ip(request)
        method = request.method
        endpoint = str(request.url.path)
        user_agent = request.headers.get("user-agent", "")
        
        # İstek boyutu
        request_size = 0
        if hasattr(request, "body"):
            try:
                body = await request.body()
                request_size = len(body)
            except:
                pass
        
        # Kullanıcı bilgisi (varsa)
        user_id = None
        try:
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                token_data = auth_manager.verify_token(token)
                if token_data:
                    user_id = token_data.get("user_id")
        except:
            pass
        
        # İsteği işle
        response = await call_next(request)
        
        # İşlem süresi
        process_time = time.time() - start_time
        
        # Yanıt boyutu
        response_size = 0
        if hasattr(response, "body"):
            try:
                response_size = len(response.body)
            except:
                pass
        
        # Rate limit bilgilerini header'a ekle
        try:
            rate_info = rate_limiter.get_rate_limit_info(request, endpoint)
            response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
            response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])
        except:
            pass
        
        # İşlem süresini header'a ekle
        response.headers["X-Process-Time"] = str(process_time)
        
        # Loglama
        auth_manager.log_api_request(
            user_id=user_id,
            ip_address=ip_address,
            endpoint=endpoint,
            method=method,
            status_code=response.status_code,
            duration=process_time,
            user_agent=user_agent,
            request_size=request_size,
            response_size=response_size
        )
        
        # Console log
        logger.info(
            f"{ip_address} - {method} {endpoint} - "
            f"{response.status_code} - {process_time:.3f}s - "
            f"User: {user_id or 'Anonymous'}"
        )
        
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Güvenlik header'ları ekleyen middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Güvenlik header'ları
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # CORS header'ları (gerekirse)
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        
        return response