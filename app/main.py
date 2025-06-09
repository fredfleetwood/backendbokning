"""
FastAPI Application Entry Point - Main API server for VPS automation
"""
import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis
from typing import Dict, Any, Optional

from app.config import get_settings
from app.models import (
    BookingRequest, BookingResponse, JobStatusResponse, CancelJobRequest,
    SystemHealth, ErrorResponse, JobStatus
)
from app.workers.celery_app import celery_app, health_check as celery_health_check
from app.workers.booking_worker import (
    process_booking_job, cancel_booking_job, cleanup_job_resources,
    JobManager
)
from app.utils.logging import (
    get_logger, LoggingMiddleware, generate_job_id, set_request_context
)
from app.utils.notifications import (
    send_system_alert, verify_webhook_signature, start_webhook_batch_flusher,
    cleanup_webhook_client
)
from app.api.booking import router as booking_router
from app.api.status import router as status_router
from app.api.webhooks import router as webhooks_router

settings = get_settings()
logger = get_logger(__name__)

# Security
security = HTTPBearer(auto_error=False)

# Redis client for rate limiting and caching
redis_client = redis.Redis.from_url(settings.REDIS_URL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    
    logger.info("Starting VPS Automation Server", version=settings.APP_VERSION)
    
    # Startup tasks
    try:
        # Test Redis connection
        await asyncio.to_thread(redis_client.ping)
        logger.info("Redis connection established")
        
        # Start webhook batch flusher
        webhook_task = asyncio.create_task(start_webhook_batch_flusher())
        
        # Send startup alert
        await send_system_alert(
            alert_type="startup",
            message="VPS Automation Server started successfully",
            severity="info",
            metadata={
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "max_concurrent_jobs": settings.MAX_CONCURRENT_JOBS
            }
        )
        
        logger.info("Application startup completed")
        
        yield
        
    except Exception as e:
        logger.error("Application startup failed", error=str(e))
        raise
    
    finally:
        # Shutdown tasks
        logger.info("Shutting down VPS Automation Server")
        
        try:
            # Cancel webhook task
            webhook_task.cancel()
            
            # Cleanup webhook client
            await cleanup_webhook_client()
            
            # Send shutdown alert
            await send_system_alert(
                alert_type="shutdown",
                message="VPS Automation Server shutting down",
                severity="info"
            )
            
        except Exception as e:
            logger.error("Error during shutdown", error=str(e))
        
        logger.info("Application shutdown completed")


# Initialize FastAPI app
app = FastAPI(
    title="VPS Automation Server",
    description="Production-ready automation server for Swedish driving test booking",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else ["https://snabbtkörprov.se"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(LoggingMiddleware, logger=logger)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware"""
    
    # Skip rate limiting for health checks
    if request.url.path in ["/health", "/health/detailed"]:
        return await call_next(request)
    
    # Get client IP
    client_ip = request.client.host
    
    # Rate limit key
    rate_limit_key = f"rate_limit:{client_ip}"
    
    try:
        # Check current request count
        current_count = redis_client.get(rate_limit_key)
        
        if current_count is None:
            # First request in window
            redis_client.setex(rate_limit_key, settings.RATE_LIMIT_WINDOW, 1)
        else:
            current_count = int(current_count)
            
            if current_count >= settings.RATE_LIMIT_REQUESTS:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "RateLimitExceeded",
                        "message": "Too many requests. Please try again later.",
                        "retry_after": settings.RATE_LIMIT_WINDOW
                    }
                )
            
            # Increment counter
            redis_client.incr(rate_limit_key)
        
    except Exception as e:
        logger.error("Rate limiting error", error=str(e))
        # Continue on error (fail open)
    
    return await call_next(request)


# Authentication dependency
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API token"""
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if credentials.credentials != settings.API_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    return credentials.credentials


# Root endpoint
@app.get("/", response_model=Dict[str, Any])
async def root():
    """Root endpoint with API information"""
    
    return {
        "service": "VPS Automation Server",
        "version": settings.APP_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "booking": "/api/v1/booking",
            "status": "/api/v1/status", 
            "health": "/health",
            "docs": "/docs" if settings.DEBUG else None
        }
    }


# Health check endpoints
@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Basic health check"""
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health/detailed", response_model=SystemHealth)
async def detailed_health_check():
    """Detailed health check with system metrics"""
    
    try:
        import psutil
        
        # Get system metrics
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Check Redis
        try:
            redis_client.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "disconnected"
        
        # Check Celery
        celery_health = celery_health_check()
        
        # Count active jobs
        active_jobs = 0
        queue_size = 0
        
        try:
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active() or {}
            scheduled_tasks = inspect.scheduled() or {}
            
            active_jobs = sum(len(tasks) for tasks in active_tasks.values())
            queue_size = sum(len(tasks) for tasks in scheduled_tasks.values())
            
        except Exception as e:
            logger.error("Error getting job counts", error=str(e))
        
        # Determine overall status
        overall_status = "healthy"
        if redis_status != "connected":
            overall_status = "unhealthy"
        elif celery_health.get('status') != 'healthy':
            overall_status = "unhealthy"
        elif memory_info.percent > 90 or cpu_percent > 95:
            overall_status = "degraded"
        
        return SystemHealth(
            status=overall_status,
            redis_status=redis_status,
            browser_status="available",  # Would need to check actual browser availability
            queue_status=celery_health.get('status', 'unknown'),
            active_jobs=active_jobs,
            queue_size=queue_size,
            memory_usage=memory_info.percent,
            cpu_usage=cpu_percent,
            disk_usage=(disk_info.used / disk_info.total) * 100,
            browser_instances=0,  # Would need to get from JobManager
            browser_memory=0.0
        )
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        
        return SystemHealth(
            status="unhealthy",
            redis_status="unknown",
            browser_status="unknown",
            queue_status="unknown",
            active_jobs=0,
            queue_size=0,
            memory_usage=0.0,
            cpu_usage=0.0,
            disk_usage=0.0,
            browser_instances=0,
            browser_memory=0.0
        )


# Main booking endpoints
@app.post("/api/v1/booking/start", response_model=BookingResponse)
async def start_booking(
    request: BookingRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_token)
) -> BookingResponse:
    """
    Start a new booking automation job
    """
    
    logger.info("Starting booking job", user_id=request.user_id, license_type=request.license_type)
    
    try:
        # Generate job ID
        job_id = generate_job_id()
        
        # Check queue capacity
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}
        active_count = sum(len(tasks) for tasks in active_tasks.values())
        
        if active_count >= settings.MAX_CONCURRENT_JOBS:
            raise HTTPException(
                status_code=503,
                detail="Server at capacity. Please try again later."
            )
        
        # Prepare job configuration
        job_config = {
            'user_id': request.user_id,
            'license_type': request.license_type,
            'exam_type': request.exam_type,
            'vehicle_options': request.vehicle_options,
            'locations': request.locations,
            'date_ranges': request.date_ranges,
            'webhook_url': request.webhook_url,
            'auto_book': request.auto_book,
            'browser_type': request.browser_type.value if request.browser_type else None,
            'headless': request.headless
        }
        
        # Submit job to Celery
        task = process_booking_job.apply_async(
            args=[job_id, request.user_id, job_config],
            queue='booking',
            priority=request.priority.value,
            task_id=job_id
        )
        
        # Estimate start time based on queue position
        scheduled_tasks = inspect.scheduled() or {}
        queue_position = sum(len(tasks) for tasks in scheduled_tasks.values()) + 1
        estimated_start_time = datetime.utcnow()
        
        logger.info("Booking job queued", job_id=job_id, queue_position=queue_position)
        
        return BookingResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message="Job queued successfully",
            estimated_start_time=estimated_start_time,
            queue_position=queue_position
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error starting booking job", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start booking job: {str(e)}")


@app.get("/api/v1/booking/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    token: str = Depends(verify_token)
) -> JobStatusResponse:
    """
    Get status of a booking job
    """
    
    try:
        # Get job state from Redis
        job_state = JobManager.get_job_state(job_id)
        
        if not job_state:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get current QR code if available
        qr_code_url = None
        if job_state.get('status') == JobStatus.QR_WAITING.value:
            # Would get QR code from active session
            pass
        
        return JobStatusResponse(
            job_id=job_id,
            user_id=job_state['user_id'],
            status=JobStatus(job_state['status']),
            progress=job_state.get('progress', 0),
            message=job_state.get('message', ''),
            created_at=datetime.fromisoformat(job_state['started_at']),
            started_at=datetime.fromisoformat(job_state['started_at']) if job_state.get('started_at') else None,
            updated_at=datetime.fromisoformat(job_state.get('updated_at', job_state['started_at'])),
            booking_details=job_state.get('result', {}).get('booking_result'),
            error_details=job_state.get('error'),
            qr_code_url=qr_code_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting job status", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get job status: {str(e)}")


@app.post("/api/v1/booking/cancel/{job_id}")
async def cancel_booking(
    job_id: str,
    request: CancelJobRequest,
    token: str = Depends(verify_token)
) -> Dict[str, Any]:
    """
    Cancel a booking job
    """
    
    logger.info("Cancelling booking job", job_id=job_id, reason=request.reason)
    
    try:
        # Submit cancellation task
        result = cancel_booking_job.delay(job_id, request.reason)
        
        # Wait for result (should be quick)
        cancellation_result = result.get(timeout=30)
        
        if cancellation_result.get('success'):
            return {
                "success": True,
                "message": "Job cancelled successfully",
                "job_id": job_id,
                "cancelled_at": cancellation_result['cancelled_at']
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=cancellation_result.get('error', 'Failed to cancel job')
            )
            
    except Exception as e:
        logger.error("Error cancelling job", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@app.get("/api/v1/queue/status")
async def get_queue_status(token: str = Depends(verify_token)) -> Dict[str, Any]:
    """
    Get current queue status
    """
    
    try:
        inspect = celery_app.control.inspect()
        
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        
        # Count tasks by queue
        queue_stats = {}
        
        for worker, tasks in active_tasks.items():
            for task in tasks:
                queue = task.get('delivery_info', {}).get('routing_key', 'default')
                queue_stats.setdefault(queue, {'active': 0, 'scheduled': 0, 'reserved': 0})
                queue_stats[queue]['active'] += 1
        
        for worker, tasks in scheduled_tasks.items():
            for task in tasks:
                queue = task.get('delivery_info', {}).get('routing_key', 'default')
                queue_stats.setdefault(queue, {'active': 0, 'scheduled': 0, 'reserved': 0})
                queue_stats[queue]['scheduled'] += 1
        
        for worker, tasks in reserved_tasks.items():
            for task in tasks:
                queue = task.get('delivery_info', {}).get('routing_key', 'default')
                queue_stats.setdefault(queue, {'active': 0, 'scheduled': 0, 'reserved': 0})
                queue_stats[queue]['reserved'] += 1
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_active": sum(len(tasks) for tasks in active_tasks.values()),
            "total_scheduled": sum(len(tasks) for tasks in scheduled_tasks.values()),
            "total_reserved": sum(len(tasks) for tasks in reserved_tasks.values()),
            "queue_details": queue_stats,
            "worker_count": len(active_tasks),
            "capacity": settings.MAX_CONCURRENT_JOBS
        }
        
    except Exception as e:
        logger.error("Error getting queue status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get queue status: {str(e)}")


# Include API routers
app.include_router(booking_router, prefix="/api/v1/booking", tags=["booking"])
app.include_router(status_router, prefix="/api/v1/status", tags=["status"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__
    )
    
    # Send error alert
    try:
        await send_system_alert(
            alert_type="unhandled_exception",
            message=f"Unhandled exception in {request.method} {request.url.path}: {str(exc)}",
            severity="error",
            metadata={
                "path": request.url.path,
                "method": request.method,
                "error_type": type(exc).__name__
            }
        )
    except Exception:
        pass  # Don't fail on alert sending
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 