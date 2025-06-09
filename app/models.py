"""
Data Models and Schemas - Pydantic models for API requests/responses and internal data structures
"""
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class JobStatus(str, Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    QR_WAITING = "qr_waiting"
    AUTHENTICATING = "authenticating"
    CONFIGURING = "configuring"
    SEARCHING = "searching"
    BOOKING = "booking"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Priority(str, Enum):
    """Job priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class BrowserType(str, Enum):
    """Supported browser types"""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"


# Static constants to avoid circular imports
SUPPORTED_LICENSE_TYPES = [
    "B", "A1", "A2", "A", "C1", "C", "D1", "D", "BE", "C1E", "CE", "D1E", "DE"
]

EXAM_TYPES = [
    "Körprov",
    "Kunskapsprov", 
    "Riskutbildning",
    "Introduktionsutbildning"
]


class BookingRequest(BaseModel):
    """Request model for starting a booking job"""
    
    user_id: str = Field(..., description="Unique user identifier")
    license_type: str = Field(..., description="License type (B, A, C, etc.)")
    exam_type: str = Field(..., description="Exam type (Körprov, Kunskapsprov, etc.)")
    
    # Vehicle/Language preferences
    vehicle_options: List[str] = Field(default=[], description="Vehicle/language preferences")
    
    # Location preferences
    locations: List[str] = Field(..., description="Preferred booking locations")
    
    # Date preferences
    date_ranges: Optional[List[Dict[str, str]]] = Field(
        default=None, 
        description="Date ranges in format [{'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}]. If not provided, system will search for next 6 months"
    )
    
    # Priority and preferences
    priority: Priority = Field(default=Priority.NORMAL, description="Job priority")
    webhook_url: Optional[str] = Field(default=None, description="Custom webhook URL for this job")
    auto_book: bool = Field(default=True, description="Automatically book first available slot")
    max_attempts: int = Field(default=3, description="Maximum booking attempts")
    
    # Browser preferences
    browser_type: Optional[BrowserType] = Field(default=None, description="Preferred browser type")
    headless: Optional[bool] = Field(default=None, description="Run browser in headless mode")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "12345678-1234-1234-1234-123456789abc",
                "license_type": "B",
                "exam_type": "Körprov",
                "vehicle_options": ["Trafikverkets bil"],
                "locations": ["Stockholm", "Uppsala"],
                "date_ranges": [
                    {"start": "2024-01-15", "end": "2024-01-30"},
                    {"start": "2024-02-01", "end": "2024-02-15"}
                ],
                "priority": "normal",
                "auto_book": True
            }
        }
    }

    @validator('license_type')
    def validate_license_type(cls, v):
        if v not in SUPPORTED_LICENSE_TYPES:
            raise ValueError(f"Unsupported license type: {v}")
        return v

    @validator('exam_type')
    def validate_exam_type(cls, v):
        if v not in EXAM_TYPES:
            raise ValueError(f"Unsupported exam type: {v}")
        return v

    @validator('date_ranges')
    def validate_date_ranges(cls, v):
        if v is None:
            # Provide default date range for next 6 months
            start_date = date.today() + timedelta(days=1)
            end_date = start_date + timedelta(days=180)
            return [{"start": start_date.strftime('%Y-%m-%d'), "end": end_date.strftime('%Y-%m-%d')}]
        
        for date_range in v:
            if 'start' not in date_range or 'end' not in date_range:
                raise ValueError("Each date range must have 'start' and 'end' keys")
            
            try:
                start_date = datetime.strptime(date_range['start'], '%Y-%m-%d').date()
                end_date = datetime.strptime(date_range['end'], '%Y-%m-%d').date()
                
                if start_date > end_date:
                    raise ValueError("Start date must be before or equal to end date")
                
                if start_date < date.today():
                    raise ValueError("Start date cannot be in the past")
                    
            except ValueError as e:
                if "time data" in str(e):
                    raise ValueError("Date must be in YYYY-MM-DD format")
                raise e
        
        return v


class BookingResponse(BaseModel):
    """Response model for booking job creation"""
    
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    estimated_start_time: Optional[datetime] = Field(default=None, description="Estimated job start time")
    queue_position: Optional[int] = Field(default=None, description="Position in queue")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "job_87654321-4321-4321-4321-210987654321",
                "status": "pending",
                "message": "Job added to queue successfully",
                "estimated_start_time": "2024-01-01T10:30:00Z",
                "queue_position": 3
            }
        }
    }


class JobStatusResponse(BaseModel):
    """Response model for job status queries"""
    
    job_id: str = Field(..., description="Job identifier")
    user_id: str = Field(..., description="User identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: float = Field(..., description="Progress percentage (0-100)")
    message: str = Field(..., description="Current status message")
    
    # Timestamps
    created_at: datetime = Field(..., description="Job creation time")
    started_at: Optional[datetime] = Field(default=None, description="Job start time")
    updated_at: datetime = Field(..., description="Last update time")
    estimated_completion: Optional[datetime] = Field(default=None, description="Estimated completion time")
    
    # Results
    booking_details: Optional[Dict[str, Any]] = Field(default=None, description="Booking confirmation details")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Error information if failed")
    
    # Browser session info
    browser_session_id: Optional[str] = Field(default=None, description="Browser session identifier")
    qr_code_url: Optional[str] = Field(default=None, description="Current QR code image URL")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "job_87654321-4321-4321-4321-210987654321",
                "user_id": "12345678-1234-1234-1234-123456789abc",
                "status": "qr_waiting",
                "progress": 25.0,
                "message": "Waiting for BankID authentication",
                "created_at": "2024-01-01T10:00:00Z",
                "started_at": "2024-01-01T10:05:00Z",
                "updated_at": "2024-01-01T10:07:00Z",
                "qr_code_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
            }
        }
    }


class QRCodeUpdate(BaseModel):
    """Model for QR code updates sent via webhooks"""
    
    job_id: str = Field(..., description="Job identifier")
    user_id: str = Field(..., description="User identifier")
    qr_code_data: str = Field(..., description="Base64 encoded QR code image")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Update timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="QR code expiry time")
    retry_count: int = Field(default=0, description="Number of QR refresh attempts")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "job_87654321-4321-4321-4321-210987654321",
                "user_id": "12345678-1234-1234-1234-123456789abc",
                "qr_code_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
                "timestamp": "2024-01-01T10:07:30Z",
                "retry_count": 1
            }
        }
    }


class AvailableSlot(BaseModel):
    """Model for available booking time slots"""
    
    slot_date: date = Field(..., description="Booking date")
    slot_time: str = Field(..., description="Booking time")
    location: str = Field(..., description="Test location")
    exam_type: str = Field(..., description="Exam type")
    vehicle_type: Optional[str] = Field(default=None, description="Vehicle type if applicable")
    availability_id: str = Field(..., description="Internal availability identifier")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "slot_date": "2024-01-20",
                "slot_time": "10:30",
                "location": "Stockholm",
                "exam_type": "Körprov",
                "vehicle_type": "Trafikverkets bil",
                "availability_id": "slot_123456789"
            }
        }
    }


class BookingResult(BaseModel):
    """Model for successful booking results"""
    
    booking_id: str = Field(..., description="Booking confirmation ID")
    confirmation_number: str = Field(..., description="Booking confirmation number")
    exam_date: date = Field(..., description="Scheduled exam date")
    exam_time: str = Field(..., description="Scheduled exam time")
    location: str = Field(..., description="Test location")
    address: Optional[str] = Field(default=None, description="Test location address")
    exam_type: str = Field(..., description="Type of exam booked")
    license_type: str = Field(..., description="License type")
    vehicle_type: Optional[str] = Field(default=None, description="Vehicle type")
    payment_status: str = Field(..., description="Payment status")
    instructions: Optional[str] = Field(default=None, description="Special instructions")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "booking_id": "TV123456789",
                "confirmation_number": "ABC123XYZ",
                "exam_date": "2024-01-20",
                "exam_time": "10:30",
                "location": "Stockholm Bilprovning",
                "address": "Example Street 123, Stockholm",
                "exam_type": "Körprov",
                "license_type": "B",
                "vehicle_type": "Trafikverkets bil",
                "payment_status": "Betala senare",
                "instructions": "Kom 15 minuter innan provtiden"
            }
        }
    }


class WebhookPayload(BaseModel):
    """Model for webhook notifications sent to external systems"""
    
    event_type: str = Field(..., description="Type of event")
    job_id: str = Field(..., description="Job identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Dict[str, Any] = Field(..., description="Event-specific data")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "event_type": "qr_code_update",
                "job_id": "job_87654321-4321-4321-4321-210987654321",
                "user_id": "12345678-1234-1234-1234-123456789abc",
                "timestamp": "2024-01-01T10:07:30Z",
                "data": {
                    "qr_code_data": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
                    "status": "qr_waiting"
                }
            }
        }
    }


class SystemHealth(BaseModel):
    """Model for system health status"""
    
    status: str = Field(..., description="Overall system status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    
    # Service statuses
    redis_status: str = Field(..., description="Redis connection status")
    browser_status: str = Field(..., description="Browser availability status")
    queue_status: str = Field(..., description="Job queue status")
    
    # Performance metrics
    active_jobs: int = Field(..., description="Number of active jobs")
    queue_size: int = Field(..., description="Number of jobs in queue")
    memory_usage: float = Field(..., description="Memory usage percentage")
    cpu_usage: float = Field(..., description="CPU usage percentage")
    disk_usage: float = Field(..., description="Disk usage percentage")
    
    # Browser metrics
    browser_instances: int = Field(..., description="Number of active browser instances")
    browser_memory: float = Field(..., description="Total browser memory usage in MB")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-01T10:00:00Z",
                "redis_status": "connected",
                "browser_status": "available",
                "queue_status": "running",
                "active_jobs": 3,
                "queue_size": 7,
                "memory_usage": 65.2,
                "cpu_usage": 23.8,
                "disk_usage": 45.1,
                "browser_instances": 3,
                "browser_memory": 1024.5
            }
        }
    }


class ErrorResponse(BaseModel):
    """Model for API error responses"""
    
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    request_id: Optional[str] = Field(default=None, description="Request identifier for tracking")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "ValidationError",
                "message": "Invalid license type specified",
                "details": {
                    "field": "license_type",
                    "provided": "Z",
                    "allowed": ["B", "A1", "A2", "A", "C1", "C", "D1", "D"]
                },
                "timestamp": "2024-01-01T10:00:00Z",
                "request_id": "req_123456789"
            }
        }
    }


class CancelJobRequest(BaseModel):
    """Request model for job cancellation"""
    
    reason: Optional[str] = Field(default="User requested", description="Cancellation reason")
    force: bool = Field(default=False, description="Force cancellation even if job is running")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "reason": "User changed plans",
                "force": False
            }
        }
    }


class JobMetrics(BaseModel):
    """Model for job performance metrics"""
    
    job_id: str = Field(..., description="Job identifier")
    total_duration: Optional[float] = Field(default=None, description="Total job duration in seconds")
    authentication_duration: Optional[float] = Field(default=None, description="BankID auth duration")
    search_duration: Optional[float] = Field(default=None, description="Search phase duration")
    booking_duration: Optional[float] = Field(default=None, description="Booking phase duration")
    
    # Browser metrics
    browser_memory_peak: Optional[float] = Field(default=None, description="Peak browser memory usage")
    page_load_times: List[float] = Field(default=[], description="Page load times during job")
    screenshots_taken: int = Field(default=0, description="Number of screenshots taken")
    
    # Error tracking
    errors_encountered: int = Field(default=0, description="Number of errors during job")
    retries_performed: int = Field(default=0, description="Number of retry attempts")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "job_87654321-4321-4321-4321-210987654321",
                "total_duration": 245.7,
                "authentication_duration": 120.3,
                "search_duration": 89.2,
                "booking_duration": 36.2,
                "browser_memory_peak": 156.8,
                "page_load_times": [2.3, 1.8, 3.1, 2.7],
                "screenshots_taken": 15,
                "errors_encountered": 1,
                "retries_performed": 2
            }
        }
    } 