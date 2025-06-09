"""
Structured Logging - Production-ready logging system with JSON formatting and performance tracking
"""
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union
from contextvars import ContextVar
import structlog
import logging
from pythonjsonlogger import jsonlogger

from app.config import get_settings

settings = get_settings()

# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')
job_id_var: ContextVar[str] = ContextVar('job_id', default='')


class CorrelationIDProcessor:
    """Add correlation IDs to log records"""
    
    def __call__(self, logger, method_name, event_dict):
        # Add request/user/job IDs from context
        if request_id_var.get():
            event_dict['request_id'] = request_id_var.get()
        if user_id_var.get():
            event_dict['user_id'] = user_id_var.get()
        if job_id_var.get():
            event_dict['job_id'] = job_id_var.get()
        
        return event_dict


class PerformanceProcessor:
    """Add performance metrics to log records"""
    
    def __call__(self, logger, method_name, event_dict):
        # Add timestamp
        event_dict['timestamp'] = datetime.utcnow().isoformat()
        
        # Add performance data if available
        if 'duration' in event_dict:
            # Convert to milliseconds for readability
            if isinstance(event_dict['duration'], (int, float)):
                event_dict['duration_ms'] = round(event_dict['duration'] * 1000, 2)
        
        return event_dict


class ErrorEnrichmentProcessor:
    """Enrich error logs with additional context"""
    
    def __call__(self, logger, method_name, event_dict):
        # Add error details for exceptions
        if 'exc_info' in event_dict and event_dict['exc_info']:
            exc = event_dict['exc_info']
            if hasattr(exc, '__class__'):
                event_dict['error_type'] = exc.__class__.__name__
            if hasattr(exc, 'args') and exc.args:
                event_dict['error_message'] = str(exc.args[0])
        
        # Add severity level
        if method_name in ['error', 'critical', 'exception']:
            event_dict['severity'] = 'error'
        elif method_name == 'warning':
            event_dict['severity'] = 'warning'
        elif method_name == 'info':
            event_dict['severity'] = 'info'
        else:
            event_dict['severity'] = 'debug'
        
        return event_dict


def configure_logging():
    """Configure structured logging for the application"""
    
    # Set log level from configuration
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    if settings.LOG_FORMAT.lower() == 'json':
        # JSON logging for production
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            CorrelationIDProcessor(),
            PerformanceProcessor(),
            ErrorEnrichmentProcessor(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ]
        
        # Configure standard library logging
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=log_level,
        )
        
    else:
        # Human-readable logging for development
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            CorrelationIDProcessor(),
            PerformanceProcessor(),
            ErrorEnrichmentProcessor(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
            structlog.dev.ConsoleRenderer()
        ]
        
        # Configure standard library logging
        logging.basicConfig(
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            level=log_level,
        )
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


class StructuredLogger:
    """
    Production logging with comprehensive event tracking and metrics
    """
    
    def __init__(self, name: str):
        self.logger = structlog.get_logger(name)
        self.name = name
        
    def bind(self, **kwargs) -> 'StructuredLogger':
        """Create a new logger with bound context"""
        new_logger = StructuredLogger(self.name)
        new_logger.logger = self.logger.bind(**kwargs)
        return new_logger
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(message, **kwargs)
    
    def log_booking_event(self, user_id: str, event: str, data: Dict[str, Any]):
        """Log booking-related events with structured data"""
        self.logger.info(
            "Booking event",
            event_type="booking",
            event=event,
            user_id=user_id,
            **data
        )
    
    def log_qr_capture(self, user_id: str, job_id: str, success: bool, image_size: int = 0):
        """Log QR code capture attempts"""
        self.logger.info(
            "QR code capture",
            event_type="qr_capture",
            user_id=user_id,
            job_id=job_id,
            success=success,
            image_size_bytes=image_size
        )
    
    def log_performance_metrics(self, operation: str, duration: float, **kwargs):
        """Track operation performance"""
        self.logger.info(
            "Performance metric",
            event_type="performance",
            operation=operation,
            duration=duration,
            **kwargs
        )
    
    def log_browser_event(self, user_id: str, job_id: str, event: str, **kwargs):
        """Log browser automation events"""
        self.logger.info(
            "Browser event",
            event_type="browser",
            browser_event=event,
            user_id=user_id,
            job_id=job_id,
            **kwargs
        )
    
    def log_api_request(self, method: str, path: str, status_code: int, duration: float, **kwargs):
        """Log API requests"""
        self.logger.info(
            "API request",
            event_type="api_request",
            method=method,
            path=path,
            status_code=status_code,
            duration=duration,
            **kwargs
        )
    
    def log_webhook_event(self, webhook_url: str, event_type: str, success: bool, **kwargs):
        """Log webhook notifications"""
        self.logger.info(
            "Webhook event",
            event_type="webhook",
            webhook_url=webhook_url,
            webhook_event_type=event_type,
            success=success,
            **kwargs
        )
    
    def log_job_state_change(self, job_id: str, user_id: str, old_status: str, new_status: str, **kwargs):
        """Log job status changes"""
        self.logger.info(
            "Job status change",
            event_type="job_status",
            job_id=job_id,
            user_id=user_id,
            old_status=old_status,
            new_status=new_status,
            **kwargs
        )
    
    def log_error_recovery(self, operation: str, error_type: str, recovery_action: str, **kwargs):
        """Log error recovery attempts"""
        self.logger.info(
            "Error recovery",
            event_type="error_recovery",
            operation=operation,
            error_type=error_type,
            recovery_action=recovery_action,
            **kwargs
        )
    
    def log_resource_usage(self, resource_type: str, current_usage: float, limit: float, **kwargs):
        """Log resource usage metrics"""
        self.logger.info(
            "Resource usage",
            event_type="resource_usage",
            resource_type=resource_type,
            current_usage=current_usage,
            limit=limit,
            usage_percentage=round((current_usage / limit) * 100, 2) if limit > 0 else 0,
            **kwargs
        )


class PerformanceTimer:
    """Context manager for measuring operation performance"""
    
    def __init__(self, logger: StructuredLogger, operation: str, **kwargs):
        self.logger = logger
        self.operation = operation
        self.kwargs = kwargs
        self.start_time = None
        
    def __enter__(self):
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            
            # Log performance with error info if exception occurred
            if exc_type:
                self.kwargs['error'] = True
                self.kwargs['error_type'] = exc_type.__name__
                
            self.logger.log_performance_metrics(
                self.operation,
                duration,
                **self.kwargs
            )


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance"""
    return StructuredLogger(name)


def set_request_context(request_id: Optional[str] = None, user_id: Optional[str] = None, job_id: Optional[str] = None):
    """Set context variables for request tracking"""
    if request_id:
        request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)
    if job_id:
        job_id_var.set(job_id)


def clear_request_context():
    """Clear all context variables"""
    request_id_var.set('')
    user_id_var.set('')
    job_id_var.set('')


def generate_request_id() -> str:
    """Generate a unique request ID"""
    return f"req_{uuid.uuid4().hex[:16]}"


def generate_job_id() -> str:
    """Generate a unique job ID"""
    return f"job_{uuid.uuid4()}"


class LoggingMiddleware:
    """Middleware for automatic request logging"""
    
    def __init__(self, logger: StructuredLogger):
        self.logger = logger
    
    async def __call__(self, request, call_next):
        # Generate request ID
        request_id = generate_request_id()
        set_request_context(request_id=request_id)
        
        # Extract user ID from request if available
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            set_request_context(user_id=user_id)
        
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Log successful request
            duration = time.time() - start_time
            self.logger.log_api_request(
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration=duration,
                success=True
            )
            
            return response
            
        except Exception as e:
            # Log failed request
            duration = time.time() - start_time
            self.logger.log_api_request(
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration=duration,
                success=False,
                error=str(e)
            )
            raise
        finally:
            # Clear context
            clear_request_context()


# Initialize logging configuration
configure_logging()

# Module-level logger will be created when first used
# logger = get_logger(__name__)
# logger.info("Logging system initialized", log_level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT) 