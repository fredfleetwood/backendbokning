"""
Supabase Webhook Handlers - Handle incoming webhooks from external systems
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Request, Header, Depends
from datetime import datetime
import json

from app.utils.logging import get_logger
from app.utils.notifications import verify_webhook_signature
from app.workers.booking_worker import cancel_booking_job, JobManager
from app.config import get_settings

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()


async def verify_supabase_webhook(
    request: Request,
    x_webhook_signature: str = Header(None, alias="X-Webhook-Signature")
) -> str:
    """
    Verify Supabase webhook signature
    """
    
    if not x_webhook_signature:
        raise HTTPException(status_code=401, detail="Missing webhook signature")
    
    # Get raw body
    body = await request.body()
    body_str = body.decode('utf-8')
    
    # Verify signature
    is_valid = await verify_webhook_signature(
        body_str, 
        x_webhook_signature, 
        settings.SUPABASE_SECRET_KEY
    )
    
    if not is_valid:
        logger.warning("Invalid webhook signature received")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    
    return body_str


@router.post("/supabase")
async def handle_supabase_webhook(
    request: Request,
    body: str = Depends(verify_supabase_webhook)
) -> Dict[str, Any]:
    """
    Handle incoming webhooks from Supabase
    """
    
    try:
        # Parse webhook payload
        payload = json.loads(body)
        event_type = payload.get('type')
        data = payload.get('record', {})
        
        logger.info("Received Supabase webhook", event_type=event_type)
        
        # Route to appropriate handler
        if event_type == 'INSERT':
            return await handle_booking_request(data)
        elif event_type == 'UPDATE':
            return await handle_booking_update(data)
        elif event_type == 'DELETE':
            return await handle_booking_cancellation(data)
        else:
            logger.warning("Unknown webhook event type", event_type=event_type)
            return {"status": "ignored", "reason": f"Unknown event type: {event_type}"}
    
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in webhook payload", error=str(e))
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    except Exception as e:
        logger.error("Error processing Supabase webhook", error=str(e))
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


async def handle_booking_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle new booking request from Supabase
    """
    
    try:
        user_id = data.get('user_id')
        booking_id = data.get('id')
        
        logger.info("Processing booking request", user_id=user_id, booking_id=booking_id)
        
        # Extract booking parameters
        license_type = data.get('license_type')
        exam_type = data.get('exam_type')
        locations = data.get('locations', [])
        date_ranges = data.get('date_ranges', [])
        
        # Validate required fields
        if not all([user_id, license_type, exam_type, locations]):
            return {
                "status": "error",
                "message": "Missing required booking parameters",
                "booking_id": booking_id
            }
        
        # Create job configuration
        job_config = {
            'user_id': user_id,
            'license_type': license_type,
            'exam_type': exam_type,
            'locations': locations,
            'date_ranges': date_ranges,
            'webhook_url': data.get('webhook_url'),
            'auto_book': data.get('auto_book', True),
            'priority': data.get('priority', 'normal')
        }
        
        # Submit to booking queue
        from app.workers.booking_worker import process_booking_job
        from app.utils.logging import generate_job_id
        
        job_id = generate_job_id()
        task = process_booking_job.apply_async(
            args=[job_id, user_id, job_config],
            queue='booking',
            task_id=job_id
        )
        
        logger.info("Booking job queued from webhook", job_id=job_id, booking_id=booking_id)
        
        return {
            "status": "queued",
            "job_id": job_id,
            "booking_id": booking_id,
            "message": "Booking automation started"
        }
        
    except Exception as e:
        logger.error("Error handling booking request", error=str(e))
        return {
            "status": "error",
            "message": str(e),
            "booking_id": data.get('id')
        }


async def handle_booking_update(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle booking update from Supabase
    """
    
    try:
        booking_id = data.get('id')
        user_id = data.get('user_id')
        status = data.get('status')
        
        logger.info("Processing booking update", booking_id=booking_id, status=status)
        
        # Handle status changes
        if status == 'cancelled':
            # Find and cancel associated job
            job_id = data.get('job_id')
            if job_id:
                cancellation_result = cancel_booking_job.delay(
                    job_id, 
                    "Cancelled via Supabase update"
                )
                
                logger.info("Job cancelled via webhook", job_id=job_id, booking_id=booking_id)
                
                return {
                    "status": "cancelled",
                    "job_id": job_id,
                    "booking_id": booking_id,
                    "message": "Job cancellation initiated"
                }
        
        return {
            "status": "processed",
            "booking_id": booking_id,
            "message": f"Update processed for status: {status}"
        }
        
    except Exception as e:
        logger.error("Error handling booking update", error=str(e))
        return {
            "status": "error",
            "message": str(e),
            "booking_id": data.get('id')
        }


async def handle_booking_cancellation(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle booking cancellation from Supabase
    """
    
    try:
        booking_id = data.get('id')
        job_id = data.get('job_id')
        
        logger.info("Processing booking cancellation", booking_id=booking_id, job_id=job_id)
        
        if job_id:
            # Cancel the job
            cancellation_result = cancel_booking_job.delay(
                job_id,
                "Booking deleted in Supabase"
            )
            
            logger.info("Job cancelled due to deletion", job_id=job_id, booking_id=booking_id)
        
        return {
            "status": "deleted",
            "job_id": job_id,
            "booking_id": booking_id,
            "message": "Booking cancellation processed"
        }
        
    except Exception as e:
        logger.error("Error handling booking cancellation", error=str(e))
        return {
            "status": "error",
            "message": str(e),
            "booking_id": data.get('id')
        }


@router.post("/user-action")
async def handle_user_action(
    request: Request,
    body: str = Depends(verify_supabase_webhook)
) -> Dict[str, Any]:
    """
    Handle user action webhooks (e.g., cancellation requests)
    """
    
    try:
        payload = json.loads(body)
        action = payload.get('action')
        user_id = payload.get('user_id')
        job_id = payload.get('job_id')
        
        logger.info("Received user action", action=action, user_id=user_id, job_id=job_id)
        
        if action == 'cancel_job' and job_id:
            # Cancel the specified job
            result = cancel_booking_job.delay(job_id, "User requested cancellation")
            
            return {
                "status": "success",
                "action": action,
                "job_id": job_id,
                "message": "Cancellation request processed"
            }
        
        elif action == 'cancel_all_jobs' and user_id:
            # Cancel all jobs for user (would need implementation)
            return {
                "status": "success",
                "action": action,
                "user_id": user_id,
                "message": "All jobs cancellation not implemented"
            }
        
        else:
            return {
                "status": "error",
                "message": f"Unknown action or missing parameters: {action}"
            }
    
    except Exception as e:
        logger.error("Error handling user action", error=str(e))
        raise HTTPException(status_code=500, detail=f"User action processing failed: {str(e)}")


@router.post("/system-command")
async def handle_system_command(
    request: Request,
    body: str = Depends(verify_supabase_webhook)
) -> Dict[str, Any]:
    """
    Handle system administration commands via webhook
    """
    
    try:
        payload = json.loads(body)
        command = payload.get('command')
        parameters = payload.get('parameters', {})
        
        logger.info("Received system command", command=command)
        
        if command == 'maintenance_cleanup':
            # Trigger maintenance cleanup
            from app.workers.booking_worker import cleanup_stale_jobs
            
            result = cleanup_stale_jobs.delay()
            cleanup_result = result.get(timeout=60)
            
            return {
                "status": "success",
                "command": command,
                "result": cleanup_result,
                "message": "Maintenance cleanup completed"
            }
        
        elif command == 'restart_workers':
            # Restart Celery workers (would need implementation)
            return {
                "status": "error",
                "command": command,
                "message": "Worker restart not implemented"
            }
        
        elif command == 'update_config':
            # Update configuration (would need implementation)
            return {
                "status": "error",
                "command": command,
                "message": "Config update not implemented"
            }
        
        else:
            return {
                "status": "error",
                "message": f"Unknown system command: {command}"
            }
    
    except Exception as e:
        logger.error("Error handling system command", error=str(e))
        raise HTTPException(status_code=500, detail=f"System command processing failed: {str(e)}")


@router.get("/health")
async def webhook_health_check() -> Dict[str, Any]:
    """
    Health check endpoint for webhook system
    """
    
    return {
        "status": "healthy",
        "service": "webhook_handler",
        "timestamp": datetime.utcnow().isoformat(),
        "supported_events": [
            "booking_request",
            "booking_update", 
            "booking_cancellation",
            "user_action",
            "system_command"
        ]
    }


@router.post("/test")
async def test_webhook(
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Test endpoint for webhook development (no signature verification)
    """
    
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    logger.info("Test webhook received", payload=payload)
    
    return {
        "status": "received",
        "message": "Test webhook processed successfully",
        "received_payload": payload,
        "timestamp": datetime.utcnow().isoformat()
    } 