"""
Simplified Data Models - Basic version for testing
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    QR_WAITING = "qr_waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    """Job priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class BookingRequest(BaseModel):
    """Simple request model for starting a booking job"""
    
    user_id: str = Field(..., description="User identifier")
    license_type: str = Field(..., description="License type")
    exam_type: str = Field(..., description="Exam type")
    locations: List[str] = Field(..., description="Preferred locations")


class BookingResponse(BaseModel):
    """Simple response model for booking job creation"""
    
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Job status")
    message: str = Field(..., description="Status message")


class JobStatusResponse(BaseModel):
    """Simple response model for job status queries"""
    
    job_id: str = Field(..., description="Job identifier")
    user_id: str = Field(..., description="User identifier")
    status: JobStatus = Field(..., description="Job status")
    progress: float = Field(..., description="Progress percentage")
    message: str = Field(..., description="Status message")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")


class SystemHealth(BaseModel):
    """Simple model for system health status"""
    
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    redis_status: str = Field(..., description="Redis status")
    browser_status: str = Field(..., description="Browser status")
    queue_status: str = Field(..., description="Queue status")
    active_jobs: int = Field(..., description="Active jobs")
    queue_size: int = Field(..., description="Queue size")
    memory_usage: float = Field(..., description="Memory usage %")
    cpu_usage: float = Field(..., description="CPU usage %")
    disk_usage: float = Field(..., description="Disk usage %")
    browser_instances: int = Field(..., description="Browser instances")
    browser_memory: float = Field(..., description="Browser memory MB")


class ErrorResponse(BaseModel):
    """Simple model for API error responses"""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CancelJobRequest(BaseModel):
    """Simple request model for job cancellation"""
    
    reason: Optional[str] = Field(default="User requested", description="Cancellation reason")
    force: bool = Field(default=False, description="Force cancellation") 