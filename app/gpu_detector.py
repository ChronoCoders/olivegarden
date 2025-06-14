import torch
import logging
import subprocess
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class GPUDetector:
    """GPU detection and management class"""
    
    def __init__(self):
        self.gpu_available = False
        self.cuda_available = False
        self.gpu_info = {}
        self._detect_gpu()
    
    def _detect_gpu(self):
        """Detect GPU availability and capabilities"""
        try:
            # Check CUDA availability
            self.cuda_available = torch.cuda.is_available()
            
            if self.cuda_available:
                self.gpu_available = True
                self.gpu_info = {
                    'cuda_version': torch.version.cuda,
                    'device_count': torch.cuda.device_count(),
                    'current_device': torch.cuda.current_device(),
                    'device_name': torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else 'Unknown',
                    'memory_total': torch.cuda.get_device_properties(0).total_memory if torch.cuda.device_count() > 0 else 0,
                    'memory_available': torch.cuda.memory_reserved(0) if torch.cuda.device_count() > 0 else 0
                }
                logger.info(f"GPU detected: {self.gpu_info['device_name']}")
            else:
                logger.info("No CUDA-compatible GPU detected")
                
        except Exception as e:
            logger.warning(f"GPU detection error: {str(e)}")
            self.gpu_available = False
            self.cuda_available = False
    
    def get_optimal_device(self, requested_mode: str = "cpu") -> str:
        """Get optimal device based on request and availability"""
        if requested_mode.lower() == "gpu" and self.gpu_available:
            return "cuda"
        elif requested_mode.lower() == "gpu" and not self.gpu_available:
            logger.warning("GPU requested but not available, falling back to CPU")
            return "cpu"
        else:
            return "cpu"
    
    def get_gpu_status(self) -> Dict:
        """Get current GPU status"""
        status = {
            'gpu_available': self.gpu_available,
            'cuda_available': self.cuda_available,
            'gpu_info': self.gpu_info
        }
        
        if self.gpu_available:
            try:
                status['memory_usage'] = {
                    'allocated': torch.cuda.memory_allocated(0),
                    'cached': torch.cuda.memory_reserved(0),
                    'free': self.gpu_info.get('memory_total', 0) - torch.cuda.memory_allocated(0)
                }
            except Exception as e:
                logger.warning(f"Could not get GPU memory info: {str(e)}")
        
        return status
    
    def clear_gpu_cache(self):
        """Clear GPU cache if available"""
        if self.gpu_available:
            try:
                torch.cuda.empty_cache()
                logger.info("GPU cache cleared")
            except Exception as e:
                logger.warning(f"Could not clear GPU cache: {str(e)}")

# Global GPU detector instance
gpu_detector = GPUDetector()