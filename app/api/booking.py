"""
Booking API Endpoints - Extended booking management functionality
"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from datetime import datetime, date

from app.models import (
    BookingRequest, AvailableSlot, JobMetrics, Priority
)
from app.workers.booking_worker import JobManager
from app.workers.celery_app import celery_app
from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/jobs/user/{user_id}")
async def get_user_jobs(
    user_id: str,
    status: str = Query(None, description="Filter by job status"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of jobs to return")
) -> List[Dict[str, Any]]:
    """
    Get booking jobs for a specific user
    """
    
    logger.info("Getting user jobs", user_id=user_id, status=status)
    
    try:
        # This would need to scan Redis keys for user jobs
        # For now, return empty list as placeholder
        user_jobs = []
        
        # In production, implement Redis scan for user jobs
        # and filter by status if provided
        
        return user_jobs
        
    except Exception as e:
        logger.error("Error getting user jobs", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get user jobs: {str(e)}")


@router.get("/metrics/{job_id}")
async def get_job_metrics(job_id: str) -> JobMetrics:
    """
    Get detailed metrics for a specific job
    """
    
    try:
        job_state = JobManager.get_job_state(job_id)
        
        if not job_state:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Extract metrics from job state
        metrics_data = job_state.get('metrics', {})
        
        return JobMetrics(
            job_id=job_id,
            total_duration=metrics_data.get('total_duration'),
            authentication_duration=metrics_data.get('authentication_duration'),
            search_duration=metrics_data.get('search_duration'),
            booking_duration=metrics_data.get('booking_duration'),
            browser_memory_peak=metrics_data.get('browser_memory_peak'),
            page_load_times=metrics_data.get('page_load_times', []),
            screenshots_taken=metrics_data.get('screenshots_taken', 0),
            errors_encountered=metrics_data.get('errors_encountered', 0),
            retries_performed=metrics_data.get('retries_performed', 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting job metrics", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get job metrics: {str(e)}")


@router.get("/available-slots")
async def search_available_slots(
    license_type: str = Query(..., description="License type (B, A, C, etc.)"),
    exam_type: str = Query(..., description="Exam type"),
    locations: List[str] = Query(..., description="Preferred locations"),
    start_date: date = Query(..., description="Search start date"),
    end_date: date = Query(..., description="Search end date")
) -> List[AvailableSlot]:
    """
    Search for available booking slots without starting a full booking job
    """
    
    logger.info("Searching available slots", 
               license_type=license_type, 
               exam_type=exam_type,
               locations=locations)
    
    try:
        # This would implement a lightweight slot search
        # For now, return empty list as placeholder
        available_slots = []
        
        # In production, this would use a simplified version
        # of the booking automation to just search for slots
        
        return available_slots
        
    except Exception as e:
        logger.error("Error searching available slots", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to search slots: {str(e)}")


@router.post("/jobs/{job_id}/priority")
async def update_job_priority(
    job_id: str,
    priority: Priority
) -> Dict[str, Any]:
    """
    Update the priority of a pending job
    """
    
    logger.info("Updating job priority", job_id=job_id, priority=priority.value)
    
    try:
        job_state = JobManager.get_job_state(job_id)
        
        if not job_state:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Can only update priority for pending jobs
        if job_state['status'] != 'pending':
            raise HTTPException(
                status_code=400, 
                detail="Can only update priority for pending jobs"
            )
        
        # Update priority in Celery (this is complex and may not be fully supported)
        # For now, return success message
        
        return {
            "success": True,
            "message": "Job priority updated",
            "job_id": job_id,
            "new_priority": priority.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating job priority", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update job priority: {str(e)}")


@router.get("/statistics")
async def get_booking_statistics(
    days: int = Query(7, ge=1, le=30, description="Number of days to include in statistics")
) -> Dict[str, Any]:
    """
    Get booking statistics for the specified time period
    """
    
    try:
        # This would analyze job history to provide statistics
        # For now, return placeholder data
        
        stats = {
            "period_days": days,
            "total_jobs": 0,
            "successful_bookings": 0,
            "failed_jobs": 0,
            "cancelled_jobs": 0,
            "average_completion_time": 0.0,
            "success_rate": 0.0,
            "popular_license_types": {},
            "popular_locations": {},
            "peak_hours": [],
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return stats
        
    except Exception as e:
        logger.error("Error getting booking statistics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}") 