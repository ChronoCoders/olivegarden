from fastapi import HTTPException, Request
from typing import Dict, Optional
import time
import asyncio
from collections import defaultdict, deque
import logging
from .config import settings

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self):
        # IP bazlı rate limiting
        self.ip_requests = defaultdict(deque)
        self.ip_blocks = {}  # Geçici bloklamalar
        
        # Endpoint bazlı limitler
        self.endpoint_limits = {
            "/analiz/yukle": {"requests": 5, "window": 300},  # 5 istek/5dk
            "/analiz/baslat": {"requests": 10, "window": 600},  # 10 istek/10dk
            "/auth/giris": {"requests": 5, "window": 300},  # 5 istek/5dk
            "default": {"requests": settings.RATE_LIMIT_REQUESTS, "window": settings.RATE_LIMIT_WINDOW}
        }
        
        # Cleanup task
        asyncio.create_task(self.cleanup_old_requests())
    
    async def cleanup_old_requests(self):
        """Eski istekleri temizle"""
        while True:
            try:
                current_time = time.time()
                
                # IP isteklerini temizle
                for ip in list(self.ip_requests.keys()):
                    requests = self.ip_requests[ip]
                    while requests and current_time - requests[0] > 3600:  # 1 saat
                        requests.popleft()
                    
                    if not requests:
                        del self.ip_requests[ip]
                
                # Bloklamaları temizle
                for ip in list(self.ip_blocks.keys()):
                    if current_time > self.ip_blocks[ip]:
                        del self.ip_blocks[ip]
                
                await asyncio.sleep(60)  # Her dakika temizle
                
            except Exception as e:
                logger.error(f"Rate limiter cleanup hatası: {e}")
                await asyncio.sleep(60)
    
    def get_client_ip(self, request: Request) -> str:
        """İstemci IP adresini al"""
        # Proxy arkasındaysa gerçek IP'yi al
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def is_blocked(self, ip: str) -> bool:
        """IP bloklanmış mı kontrol et"""
        if ip in self.ip_blocks:
            return time.time() < self.ip_blocks[ip]
        return False
    
    def block_ip(self, ip: str, duration: int = 300):
        """IP'yi geçici olarak blokla"""
        self.ip_blocks[ip] = time.time() + duration
        logger.warning(f"IP bloklandı: {ip} ({duration} saniye)")
    
    def check_rate_limit(self, request: Request, endpoint: str = None) -> bool:
        """Rate limit kontrolü"""
        ip = self.get_client_ip(request)
        current_time = time.time()
        
        # Bloklanmış IP kontrolü
        if self.is_blocked(ip):
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "IP adresi geçici olarak bloklandı",
                    "retry_after": int(self.ip_blocks[ip] - current_time)
                }
            )
        
        # Endpoint limiti al
        endpoint_key = endpoint or "default"
        limit_config = self.endpoint_limits.get(endpoint_key, self.endpoint_limits["default"])
        
        max_requests = limit_config["requests"]
        time_window = limit_config["window"]
        
        # IP için istek geçmişi
        requests = self.ip_requests[ip]
        
        # Eski istekleri temizle
        while requests and current_time - requests[0] > time_window:
            requests.popleft()
        
        # Limit kontrolü
        if len(requests) >= max_requests:
            # Çok fazla istek - IP'yi blokla
            self.block_ip(ip, 300)  # 5 dakika blok
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Çok fazla istek",
                    "limit": max_requests,
                    "window": time_window,
                    "retry_after": 300
                }
            )
        
        # İsteği kaydet
        requests.append(current_time)
        
        return True
    
    def get_rate_limit_info(self, request: Request, endpoint: str = None) -> Dict:
        """Rate limit bilgilerini getir"""
        ip = self.get_client_ip(request)
        current_time = time.time()
        
        endpoint_key = endpoint or "default"
        limit_config = self.endpoint_limits.get(endpoint_key, self.endpoint_limits["default"])
        
        max_requests = limit_config["requests"]
        time_window = limit_config["window"]
        
        requests = self.ip_requests[ip]
        
        # Eski istekleri temizle
        while requests and current_time - requests[0] > time_window:
            requests.popleft()
        
        remaining = max(0, max_requests - len(requests))
        reset_time = int(current_time + time_window) if requests else int(current_time)
        
        return {
            "limit": max_requests,
            "remaining": remaining,
            "reset": reset_time,
            "window": time_window
        }

# Global rate limiter instance
rate_limiter = RateLimiter()

async def check_rate_limit(request: Request, endpoint: str = None):
    """Rate limit middleware"""
    return rate_limiter.check_rate_limit(request, endpoint)