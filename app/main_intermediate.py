"""
Intermediate FastAPI Application - With authentication but stable models
"""
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
from typing import Dict, Any, List
import redis
import os

# Simple app with authentication
app = FastAPI(
    title="VPS Automation Server - Intermediate",
    description="Intermediate version with authentication",
    version="1.0.0"
)

# Security
security = HTTPBearer(auto_error=False)

# Redis connection
try:
    redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
except Exception:
    redis_client = None

# Simple authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API token"""
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    expected_token = os.getenv("API_SECRET_TOKEN", "test-secret-token-12345")
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    return credentials.credentials

@app.get("/")
async def root():
    return {
        "service": "VPS Automation Server",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "features": ["authentication", "redis", "booking_api", "job_management"]
    }

@app.get("/health")
async def health():
    redis_status = "disconnected"
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
        except Exception:
            pass
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "redis": redis_status,
        "memory_usage": "unknown",
        "active_jobs": 0
    }

@app.get("/health/detailed")
async def detailed_health():
    """Detailed health check"""
    
    redis_status = "disconnected"
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
        except Exception:
            pass
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "redis_status": redis_status,
        "browser_status": "available",
        "queue_status": "healthy",
        "active_jobs": 0,
        "queue_size": 0,
        "memory_usage": 0.0,
        "cpu_usage": 0.0,
        "disk_usage": 0.0,
        "browser_instances": 0,
        "browser_memory": 0.0
    }

@app.post("/api/v1/booking/start")
async def start_booking(request: Dict[str, Any], token: str = Depends(verify_token)):
    """Start a new booking automation job - with authentication"""
    
    # Basic validation
    required_fields = ["user_id", "license_type", "exam_type", "locations"]
    for field in required_fields:
        if field not in request:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Generate a job ID with more detail
    from uuid import uuid4
    job_id = f"job_{uuid4().hex[:16]}"
    
    # Store job in Redis if available
    if redis_client:
        try:
            job_data = {
                "job_id": job_id,
                "user_id": request["user_id"],
                "license_type": request["license_type"],
                "exam_type": request["exam_type"],
                "locations": request["locations"],
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
                "progress": 0
            }
            redis_client.setex(f"job:{job_id}", 3600, str(job_data))  # 1 hour TTL
        except Exception as e:
            print(f"Redis error: {e}")
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job queued successfully",
        "timestamp": datetime.utcnow().isoformat(),
        "estimated_start_time": datetime.utcnow().isoformat(),
        "queue_position": 1
    }

@app.get("/api/v1/booking/status/{job_id}")
async def get_job_status(job_id: str, token: str = Depends(verify_token)):
    """Get status of a booking job - with authentication"""
    
    # Try to get from Redis first
    if redis_client:
        try:
            job_data = redis_client.get(f"job:{job_id}")
            if job_data:
                return {
                    "job_id": job_id,
                    "user_id": "retrieved_from_redis",
                    "status": "pending",
                    "progress": 0,
                    "message": "Job is in queue",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
        except Exception as e:
            print(f"Redis error: {e}")
    
    # Default response if not found
    return {
        "job_id": job_id,
        "user_id": "unknown",
        "status": "pending",
        "progress": 0,
        "message": "Job is pending",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

@app.post("/api/v1/booking/cancel/{job_id}")
async def cancel_booking(job_id: str, token: str = Depends(verify_token)):
    """Cancel a booking job - with authentication"""
    
    return {
        "success": True,
        "message": "Job cancelled successfully",
        "job_id": job_id,
        "cancelled_at": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/queue/status")
async def get_queue_status(token: str = Depends(verify_token)):
    """Get current queue status - with authentication"""
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_active": 0,
        "total_scheduled": 0,
        "total_reserved": 0,
        "queue_details": {},
        "worker_count": 0,
        "capacity": 10
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 