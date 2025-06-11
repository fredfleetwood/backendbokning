"""
Production FastAPI Application - Complete VPS Automation System
"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
from uuid import uuid4
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our automation system
from app.automation.enhanced_booking import start_enhanced_booking as start_automated_booking
from app.utils.webhooks import initialize_webhook_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting VPS Automation Server...")
    
    # Initialize webhook manager
    if redis_client:
        await initialize_webhook_manager(redis_client)
        print("✅ Webhook manager initialized")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down VPS Automation Server...")

# Simple app with full production features
app = FastAPI(
    title="VPS Automation Server - Production",
    description="Complete Swedish driving test booking automation with real-time QR streaming",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Tillåter alla domäner
        "https://lovable.dev",
        "https://*.lovable.app", 
        "http://localhost:3000",  # För lokal utveckling
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Security
security = HTTPBearer(auto_error=False)

# Redis connection
try:
    redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
except Exception:
    redis_client = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, job_id: str):
        await websocket.accept()
        self.active_connections[job_id] = websocket
    
    def disconnect(self, job_id: str):
        if job_id in self.active_connections:
            del self.active_connections[job_id]
    
    async def send_qr_update(self, job_id: str, qr_data: Dict[str, Any]):
        if job_id in self.active_connections:
            try:
                await self.active_connections[job_id].send_text(json.dumps(qr_data))
            except:
                self.disconnect(job_id)

manager = ConnectionManager()

# Background job storage
active_jobs: Dict[str, asyncio.Task] = {}

# Authentication
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API token"""
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    expected_token = os.getenv("API_SECRET_TOKEN", "test-secret-token-12345")
    if credentials.credentials != expected_token:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    
    return credentials.credentials

# QR Code streaming callback
async def qr_streaming_callback(job_id: str, qr_image_data: str, qr_metadata: Dict[str, Any]):
    """Callback function for QR code streaming"""
    
    qr_update = {
        "type": "qr_update",
        "job_id": job_id,
        "image_data": qr_image_data,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": qr_metadata
    }
    
    # Send to WebSocket client
    await manager.send_qr_update(job_id, qr_update)
    
    # Store in Redis for HTTP polling fallback (extended timeout for better UX)
    if redis_client:
        redis_client.setex(f"qr_latest:{job_id}", 180, json.dumps(qr_update))  # 3 minutes timeout instead of 1

@app.get("/")
async def root():
    return {
        "service": "VPS Automation Server - Production",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "features": [
            "real_automation", 
            "qr_streaming", 
            "concurrent_jobs", 
            "websockets",
            "webhooks",
            "monitoring",
            "authentication"
        ],
        "endpoints": {
            "docs": "/docs",
            "booking": "/api/v1/booking/start",
            "websocket": "/ws/{job_id}",
            "qr_polling": "/api/v1/booking/{job_id}/qr",
            "monitoring": "/health/detailed"
        }
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
        "active_jobs": len(active_jobs),
        "websocket_connections": len(manager.active_connections)
    }

@app.get("/health/detailed")
async def detailed_health():
    """Comprehensive health check and monitoring"""
    
    redis_status = "disconnected"
    redis_memory = 0
    if redis_client:
        try:
            redis_client.ping()
            redis_status = "connected"
            info = redis_client.info('memory')
            redis_memory = info.get('used_memory_human', '0B')
        except Exception:
            pass
    
    # Get system metrics
    import psutil
    
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "redis_status": redis_status,
            "redis_memory": redis_memory,
            "browser_status": "available",
            "queue_status": "healthy"
        },
        "jobs": {
            "active_jobs": len(active_jobs),
            "job_details": list(active_jobs.keys())
        },
        "connections": {
            "websocket_connections": len(manager.active_connections),
            "connected_jobs": list(manager.active_connections.keys())
        },
        "performance": {
            "memory_usage": psutil.virtual_memory().percent,
            "cpu_usage": psutil.cpu_percent(interval=1),
            "disk_usage": psutil.disk_usage('/').percent
        }
    }

@app.post("/api/v1/booking/start")
async def start_booking(request: Dict[str, Any], token: str = Depends(verify_token)):
    """
    Start a new booking automation job with real browser automation and webhook support
    
    Expected request format:
    {
        "user_id": "string",
        "license_type": "B|A|C|D", 
        "exam_type": "Körprov|Kunskapsprov",
        "locations": ["Stockholm", "Göteborg"],
        "personal_number": "YYYYMMDD-XXXX" (optional for demo),
        "webhook_url": "https://your-app.supabase.co/functions/v1/webhook" (optional)
    }
    """
    
    # Validation
    required_fields = ["user_id", "license_type", "exam_type", "locations"]
    for field in required_fields:
        if field not in request:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
    
    # Check concurrent job limit
    if len(active_jobs) >= 10:  # Max 10 concurrent jobs
        raise HTTPException(status_code=503, detail="Server at capacity. Please try again later.")
    
    # Generate job ID
    job_id = f"job_{uuid4().hex[:16]}"
    
    # Extract webhook URL if provided
    webhook_url = request.get("webhook_url")
    
    # Start automation in background
    task = asyncio.create_task(
        start_automated_booking(
            job_id=job_id,
            user_config=request,
            redis_client=redis_client,
            qr_callback=qr_streaming_callback,
            webhook_url=webhook_url  # Pass webhook URL to automation
        )
    )
    
    # Store active job
    active_jobs[job_id] = task
    
    # Set up task completion callback
    def on_job_complete(task):
        if job_id in active_jobs:
            del active_jobs[job_id]
        manager.disconnect(job_id)
    
    task.add_done_callback(on_job_complete)
    
    return {
        "job_id": job_id,
        "status": "starting",
        "message": "Booking automation started",
        "timestamp": datetime.utcnow().isoformat(),
        "websocket_url": f"/ws/{job_id}",
        "qr_polling_url": f"/api/v1/booking/{job_id}/qr",
        "webhook_configured": webhook_url is not None,
        "estimated_duration": "60-120 seconds"
    }

@app.get("/api/v1/booking/status/{job_id}")
async def get_job_status(job_id: str, token: str = Depends(verify_token)):
    """Get detailed status of a booking job"""
    
    # Check if job is active
    is_active = job_id in active_jobs
    
    # Get status from Redis
    if redis_client:
        try:
            job_data = redis_client.get(f"job:{job_id}")
            if job_data:
                status_data = json.loads(job_data)
                status_data["is_active"] = is_active
                return status_data
        except Exception as e:
            print(f"Redis error: {e}")
    
    # Default response
    return {
        "job_id": job_id,
        "status": "unknown",
        "message": "Job not found or expired",
        "is_active": is_active,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/booking/{job_id}/qr")
async def get_latest_qr(job_id: str, token: str = Depends(verify_token)):
    """Get the latest QR code for a job (polling fallback for WebSocket)"""
    
    if redis_client:
        try:
            qr_data = redis_client.get(f"qr_latest:{job_id}")
            if qr_data:
                return json.loads(qr_data)
        except Exception as e:
            print(f"Redis error: {e}")
    
    return {
        "job_id": job_id,
        "message": "No QR code available - waiting for BankID authentication or QR expired",
        "timestamp": datetime.utcnow().isoformat(),
        "qr_status": "expired_or_pending"
    }

@app.post("/api/v1/booking/stop")  
async def stop_booking(request: Dict[str, Any], token: str = Depends(verify_token)):
    """Stop an active booking job (matches expected API format)"""
    
    job_id = request.get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing job_id")
    
    if job_id in active_jobs:
        # Cancel the task
        active_jobs[job_id].cancel()
        del active_jobs[job_id]
        
        # Update status in Redis
        if redis_client:
            cancel_data = {
                "job_id": job_id,
                "status": "cancelled",
                "message": "Job cancelled by user",
                "timestamp": datetime.utcnow().isoformat()
            }
            redis_client.setex(f"job:{job_id}", 300, json.dumps(cancel_data))
        
        # Disconnect WebSocket
        manager.disconnect(job_id)
        
        return {
            "success": True,
            "message": "Job cancelled successfully",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        return {
            "success": False,
            "message": "Job not found or already completed",
            "job_id": job_id
        }

@app.post("/api/v1/booking/cancel/{job_id}")
async def cancel_booking(job_id: str, token: str = Depends(verify_token)):
    """Cancel an active booking job (legacy endpoint)"""
    
    if job_id in active_jobs:
        # Cancel the task
        active_jobs[job_id].cancel()
        del active_jobs[job_id]
        
        # Update status in Redis
        if redis_client:
            cancel_data = {
                "job_id": job_id,
                "status": "cancelled",
                "message": "Job cancelled by user",
                "timestamp": datetime.utcnow().isoformat()
            }
            redis_client.setex(f"job:{job_id}", 300, json.dumps(cancel_data))
        
        # Disconnect WebSocket
        manager.disconnect(job_id)
        
        return {
            "success": True,
            "message": "Job cancelled successfully",
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    else:
        return {
            "success": False,
            "message": "Job not found or already completed",
            "job_id": job_id
        }

@app.get("/api/v1/booking/status")
async def list_all_jobs(token: str = Depends(verify_token)):
    """List all active jobs (for admin/monitoring purposes)"""
    
    jobs = []
    for job_id in active_jobs.keys():
        if redis_client:
            try:
                job_data = redis_client.get(f"job:{job_id}")
                if job_data:
                    job_info = json.loads(job_data)
                    jobs.append({
                        "job_id": job_id,
                        "status": job_info.get("status", "unknown"),
                        "user_id": job_info.get("user_id", "unknown"),
                        "created_at": job_info.get("created_at"),
                        "is_active": True
                    })
            except Exception as e:
                jobs.append({
                    "job_id": job_id,
                    "status": "error",
                    "error": str(e),
                    "is_active": True
                })
    
    return {
        "active_jobs": jobs,
        "total_count": len(jobs),
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/v1/queue/status")
async def get_queue_status(token: str = Depends(verify_token)):
    """Get current system and queue status"""
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "capacity": {
            "max_concurrent_jobs": 10,
            "current_active": len(active_jobs),
            "available_slots": 10 - len(active_jobs)
        },
        "active_jobs": [
            {
                "job_id": job_id,
                "status": "running",
                "duration": "unknown"  # Could calculate from start time
            }
            for job_id in active_jobs.keys()
        ],
        "websocket_connections": len(manager.active_connections),
        "system_health": "healthy"
    }

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time QR code streaming
    
    Connect to this endpoint to receive real-time QR code updates:
    ws://localhost:8080/ws/{job_id}
    """
    
    await manager.connect(websocket, job_id)
    
    try:
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "job_id": job_id,
            "message": "Connected to QR stream",
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for messages (ping/pong, etc.)
                data = await websocket.receive_text()
                
                # Echo back for connection health
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                }))
                
            except WebSocketDisconnect:
                break
            except:
                break
    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(job_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 