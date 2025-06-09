"""
Minimal FastAPI Application - Basic version without complex models
"""
from fastapi import FastAPI, HTTPException
from datetime import datetime
from typing import Dict, Any
import redis
import os

# Simple app without complex imports
app = FastAPI(
    title="VPS Automation Server - Minimal",
    description="Minimal version for testing",
    version="1.0.0"
)

# Basic Redis connection
try:
    redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
except Exception:
    redis_client = None

@app.get("/")
async def root():
    return {
        "service": "VPS Automation Server",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
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
        "redis": redis_status
    }

@app.post("/api/v1/booking/start")
async def start_booking(request: Dict[str, Any]):
    """Basic booking endpoint for testing"""
    
    # Basic validation
    required_fields = ["user_id", "license_type", "exam_type", "locations"]
    for field in required_fields:
        if field not in request:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Generate a simple job ID
    job_id = f"job_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Job queued successfully",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/booking/status/{job_id}")
async def get_job_status(job_id: str):
    """Basic status endpoint for testing"""
    
    return {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Job is pending",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 