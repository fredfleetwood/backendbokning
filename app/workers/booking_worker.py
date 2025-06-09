"""
Background Booking Tasks - Celery worker for processing booking automation jobs
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import json
import psutil
from urllib.parse import urljoin

from celery import Celery
from celery.exceptions import Retry

from ..config import settings
from ..models import JobStatus, JobMetrics, WebhookPayload
from ..automation.playwright_driver import EnhancedPlaywrightDriver
from ..automation.exceptions import BrowserError, AuthenticationError, BookingError
from ..utils.logging import get_logger
from ..utils.performance import PerformanceTimer
from ..utils.notifications import send_webhook_sync
from .celery_app import celery_app
from .redis_client import redis_client
from ..utils.logging import get_logger, set_request_context, generate_job_id
from ..utils.notifications import send_webhook

logger = get_logger(__name__)

# Active browser sessions tracking
active_sessions: Dict[str, EnhancedPlaywrightDriver] = {}


class JobManager:
    """Manages job state and browser sessions"""
    
    @staticmethod
    def get_job_key(job_id: str) -> str:
        """Get Redis key for job data"""
        return f"job:{job_id}"
    
    @staticmethod
    def get_session_key(job_id: str) -> str:
        """Get Redis key for session data"""
        return f"session:{job_id}"
    
    @staticmethod
    def save_job_state(job_id: str, state: Dict[str, Any]) -> None:
        """Save job state to Redis"""
        try:
            redis_client.setex(
                JobManager.get_job_key(job_id),
                settings.JOB_TIMEOUT + 300,  # Extra 5 minutes
                json.dumps(state, default=str)
            )
        except Exception as e:
            logger.error("Failed to save job state", job_id=job_id, error=str(e))
    
    @staticmethod
    def get_job_state(job_id: str) -> Optional[Dict[str, Any]]:
        """Get job state from Redis"""
        try:
            data = redis_client.get(JobManager.get_job_key(job_id))
            return json.loads(data) if data else None
        except Exception as e:
            logger.error("Failed to get job state", job_id=job_id, error=str(e))
            return None
    
    @staticmethod
    def register_session(job_id: str, driver: EnhancedPlaywrightDriver) -> None:
        """Register active browser session"""
        active_sessions[job_id] = driver
        
        # Save session info to Redis
        session_info = {
            'job_id': job_id,
            'user_id': driver.user_id,
            'session_id': driver.session_id,
            'created_at': datetime.utcnow().isoformat(),
            'browser_type': driver.current_browser_type.value if driver.current_browser_type else None
        }
        
        redis_client.setex(
            JobManager.get_session_key(job_id),
            settings.JOB_TIMEOUT + 300,
            json.dumps(session_info)
        )
    
    @staticmethod
    def unregister_session(job_id: str) -> None:
        """Unregister browser session"""
        if job_id in active_sessions:
            del active_sessions[job_id]
        
        redis_client.delete(JobManager.get_session_key(job_id))
    
    @staticmethod
    def get_active_sessions() -> List[Dict[str, Any]]:
        """Get list of active sessions"""
        sessions = []
        for key in redis_client.scan_iter(match="session:*"):
            try:
                data = redis_client.get(key)
                if data:
                    sessions.append(json.loads(data))
            except Exception:
                continue
        return sessions


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_booking_job(self, job_id: str, user_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main task for processing booking automation jobs
    
    Args:
        job_id: Unique job identifier
        user_id: User identifier  
        config: Booking configuration
        
    Returns:
        Job result with booking details or error information
    """
    
    # Set logging context
    set_request_context(job_id=job_id, user_id=user_id)
    task_logger = logger.bind(job_id=job_id, user_id=user_id, task_id=self.request.id)
    
    task_logger.info("Starting booking job processing")
    
    start_time = datetime.utcnow()
    driver = None
    
    try:
        # Initialize job state
        job_state = {
            'job_id': job_id,
            'user_id': user_id,
            'status': JobStatus.RUNNING.value,
            'started_at': start_time.isoformat(),
            'task_id': self.request.id,
            'config': config,
            'progress': 0,
            'message': 'Initializing browser automation'
        }
        JobManager.save_job_state(job_id, job_state)
        
        # Send initial status webhook
        _send_status_webhook_sync(job_id, user_id, JobStatus.RUNNING, "Starting booking automation", config)
        
        # Create status callback
        def status_callback_sync(status: JobStatus, message: str):
            nonlocal job_state
            job_state.update({
                'status': status.value,
                'message': message,
                'updated_at': datetime.utcnow().isoformat(),
                'progress': _calculate_progress(status)
            })
            JobManager.save_job_state(job_id, job_state)
            _send_status_webhook_sync(job_id, user_id, status, message, config)
        
        # Create webhook callback for QR codes
        def webhook_callback_sync(qr_update):
            _send_qr_webhook_sync(qr_update, config)
        
        # Initialize Playwright driver
        task_logger.info("Initializing Playwright driver")
        driver = EnhancedPlaywrightDriver(
            user_id=user_id,
            job_id=job_id,
            config=config,
            status_callback=status_callback_sync,
            webhook_callback=webhook_callback_sync
        )
        
        # Register session
        JobManager.register_session(job_id, driver)
        
        # Run the booking automation
        with PerformanceTimer(task_logger, "booking_automation", job_id=job_id):
            # Run async context in event loop
            async def run_automation():
                async with driver:
                    return await driver.run_booking_automation()
            
            booking_result = asyncio.run(run_automation())
        
        # Calculate metrics
        end_time = datetime.utcnow()
        total_duration = (end_time - start_time).total_seconds()
        
        metrics = JobMetrics(
            job_id=job_id,
            total_duration=total_duration,
            errors_encountered=0,
            retries_performed=self.request.retries
        )
        
        # Prepare successful result
        result = {
            'success': True,
            'job_id': job_id,
            'booking_result': booking_result.dict(),
            'metrics': metrics.dict(),
            'completed_at': end_time.isoformat()
        }
        
        # Update final job state
        job_state.update({
            'status': JobStatus.COMPLETED.value,
            'message': 'Booking completed successfully',
            'progress': 100,
            'completed_at': end_time.isoformat(),
            'result': result
        })
        JobManager.save_job_state(job_id, job_state)
        
        # Send success webhook
        _send_completion_webhook_sync(job_id, user_id, True, booking_result.dict(), config)
        
        task_logger.info("Booking job completed successfully", 
                        booking_id=booking_result.booking_id,
                        duration=total_duration)
        
        return result
        
    except (BrowserError, AuthenticationError, BookingError) as e:
        # Expected automation errors
        task_logger.error("Booking automation failed", error=str(e), error_type=type(e).__name__)
        
        # Update job state
        error_result = {
            'success': False,
            'job_id': job_id,
            'error': str(e),
            'error_type': type(e).__name__,
            'failed_at': datetime.utcnow().isoformat(),
            'retries': self.request.retries
        }
        
        job_state = JobManager.get_job_state(job_id) or {}
        job_state.update({
            'status': JobStatus.FAILED.value,
            'message': f'Booking failed: {str(e)}',
            'error': error_result,
            'failed_at': datetime.utcnow().isoformat()
        })
        JobManager.save_job_state(job_id, job_state)
        
        # Send failure webhook
        _send_completion_webhook_sync(job_id, user_id, False, {'error': str(e)}, config)
        
        # Don't retry for these specific errors
        return error_result
        
    except Exception as e:
        # Unexpected errors - may be worth retrying
        task_logger.error("Unexpected error in booking job", error=str(e), error_type=type(e).__name__)
        
        # Check if we should retry
        if self.request.retries < self.max_retries:
            task_logger.info("Retrying booking job", retry_count=self.request.retries + 1)
            
            # Update job state for retry
            job_state = JobManager.get_job_state(job_id) or {}
            job_state.update({
                'status': JobStatus.FAILED.value,
                'message': f'Job failed, retrying... (attempt {self.request.retries + 1})',
                'last_error': str(e),
                'retry_at': (datetime.utcnow() + timedelta(seconds=60)).isoformat()
            })
            JobManager.save_job_state(job_id, job_state)
            
            raise self.retry(countdown=60, exc=e)
        
        # Final failure after all retries
        error_result = {
            'success': False,
            'job_id': job_id,
            'error': str(e),
            'error_type': type(e).__name__,
            'failed_at': datetime.utcnow().isoformat(),
            'retries_exhausted': True
        }
        
        job_state = JobManager.get_job_state(job_id) or {}
        job_state.update({
            'status': JobStatus.FAILED.value,
            'message': f'Booking failed after all retries: {str(e)}',
            'error': error_result,
            'failed_at': datetime.utcnow().isoformat()
        })
        JobManager.save_job_state(job_id, job_state)
        
        # Send failure webhook
        _send_completion_webhook_sync(job_id, user_id, False, {'error': str(e)}, config)
        
        return error_result
        
    finally:
        # Cleanup resources
        try:
            if driver:
                # Run cleanup in event loop
                asyncio.run(driver.cleanup())
                JobManager.unregister_session(job_id)
                
            task_logger.info("Job cleanup completed")
            
        except Exception as cleanup_error:
            task_logger.error("Error during job cleanup", error=str(cleanup_error))


@celery_app.task
def cancel_booking_job(job_id: str, reason: str = "User requested") -> Dict[str, Any]:
    """
    Cancel an active booking job
    
    Args:
        job_id: Job identifier to cancel
        reason: Cancellation reason
        
    Returns:
        Cancellation result
    """
    
    task_logger = logger.bind(job_id=job_id)
    task_logger.info("Cancelling booking job", reason=reason)
    
    try:
        # Get job state
        job_state = JobManager.get_job_state(job_id)
        if not job_state:
            return {'success': False, 'error': 'Job not found'}
        
        # Check if job is cancellable
        current_status = job_state.get('status')
        if current_status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value]:
            return {'success': False, 'error': f'Job already in final state: {current_status}'}
        
        # Cancel the task
        task_id = job_state.get('task_id')
        if task_id:
            celery_app.control.revoke(task_id, terminate=True)
        
        # Cleanup browser session
        if job_id in active_sessions:
            driver = active_sessions[job_id]
            asyncio.run(driver.cleanup())
            JobManager.unregister_session(job_id)
        
        # Update job state
        job_state.update({
            'status': JobStatus.CANCELLED.value,
            'message': f'Job cancelled: {reason}',
            'cancelled_at': datetime.utcnow().isoformat(),
            'cancellation_reason': reason
        })
        JobManager.save_job_state(job_id, job_state)
        
        # Send cancellation webhook
        user_id = job_state.get('user_id')
        config = job_state.get('config', {})
        _send_status_webhook_sync(job_id, user_id, JobStatus.CANCELLED, f"Job cancelled: {reason}", config)
        
        task_logger.info("Job cancelled successfully")
        
        return {
            'success': True,
            'job_id': job_id,
            'cancelled_at': datetime.utcnow().isoformat(),
            'reason': reason
        }
        
    except Exception as e:
        task_logger.error("Error cancelling job", error=str(e))
        return {'success': False, 'error': str(e)}


@celery_app.task
def cleanup_stale_jobs() -> Dict[str, Any]:
    """
    Periodic task to cleanup stale jobs and browser sessions
    
    Returns:
        Cleanup statistics
    """
    
    task_logger = logger.bind(task_name="cleanup_stale_jobs")
    task_logger.info("Starting stale job cleanup")
    
    cleaned_jobs = 0
    cleaned_sessions = 0
    errors = 0
    
    try:
        # Cleanup expired job states
        cutoff_time = datetime.utcnow() - timedelta(seconds=settings.JOB_TIMEOUT + 600)  # Extra 10 minutes
        
        for key in redis_client.scan_iter(match="job:*"):
            try:
                data = redis_client.get(key)
                if data:
                    job_data = json.loads(data)
                    started_at = datetime.fromisoformat(job_data.get('started_at', ''))
                    
                    if started_at < cutoff_time:
                        job_id = job_data.get('job_id')
                        
                        # Cleanup browser session if still active
                        if job_id in active_sessions:
                            driver = active_sessions[job_id]
                            asyncio.run(driver.cleanup())
                            JobManager.unregister_session(job_id)
                            cleaned_sessions += 1
                        
                        # Remove job state
                        redis_client.delete(key)
                        cleaned_jobs += 1
                        
                        task_logger.info("Cleaned stale job", job_id=job_id)
                        
            except Exception as e:
                errors += 1
                task_logger.error("Error cleaning job", key=key.decode(), error=str(e))
        
        # Cleanup orphaned sessions
        for key in redis_client.scan_iter(match="session:*"):
            try:
                data = redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    created_at = datetime.fromisoformat(session_data.get('created_at', ''))
                    
                    if created_at < cutoff_time:
                        job_id = session_data.get('job_id')
                        
                        if job_id in active_sessions:
                            driver = active_sessions[job_id]
                            asyncio.run(driver.cleanup())
                            del active_sessions[job_id]
                        
                        redis_client.delete(key)
                        cleaned_sessions += 1
                        
            except Exception as e:
                errors += 1
                task_logger.error("Error cleaning session", key=key.decode(), error=str(e))
        
        result = {
            'cleaned_jobs': cleaned_jobs,
            'cleaned_sessions': cleaned_sessions,
            'errors': errors,
            'cleanup_time': datetime.utcnow().isoformat()
        }
        
        task_logger.info("Stale job cleanup completed", **result)
        return result
        
    except Exception as e:
        task_logger.error("Error in stale job cleanup", error=str(e))
        return {'error': str(e), 'cleaned_jobs': cleaned_jobs, 'cleaned_sessions': cleaned_sessions}


@celery_app.task
def cleanup_job_resources(job_id: str) -> Dict[str, Any]:
    """
    Cleanup resources for a specific job
    
    Args:
        job_id: Job identifier
        
    Returns:
        Cleanup result
    """
    
    task_logger = logger.bind(job_id=job_id, task_name="cleanup_job_resources")
    task_logger.info("Cleaning up job resources")
    
    try:
        # Cleanup browser session
        if job_id in active_sessions:
            driver = active_sessions[job_id]
            asyncio.run(driver.cleanup())
            JobManager.unregister_session(job_id)
        
        # Remove job state
        redis_client.delete(JobManager.get_job_key(job_id))
        redis_client.delete(JobManager.get_session_key(job_id))
        
        task_logger.info("Job resources cleaned up successfully")
        
        return {
            'success': True,
            'job_id': job_id,
            'cleaned_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        task_logger.error("Error cleaning up job resources", error=str(e))
        return {'success': False, 'error': str(e)}


@celery_app.task
def health_check_worker() -> Dict[str, Any]:
    """
    Health check task for monitoring worker status
    
    Returns:
        Worker health information
    """
    
    try:
        # Get system metrics
        memory_info = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=1)
        disk_info = psutil.disk_usage('/')
        
        # Get active sessions count
        active_sessions_count = len(active_sessions)
        
        # Get job queue statistics
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active()
        scheduled_tasks = inspect.scheduled()
        
        active_count = sum(len(tasks) for tasks in (active_tasks or {}).values())
        scheduled_count = sum(len(tasks) for tasks in (scheduled_tasks or {}).values())
        
        health_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy',
            'memory_usage_percent': memory_info.percent,
            'cpu_usage_percent': cpu_percent,
            'disk_usage_percent': (disk_info.used / disk_info.total) * 100,
            'active_browser_sessions': active_sessions_count,
            'active_tasks': active_count,
            'scheduled_tasks': scheduled_count,
            'worker_concurrency': settings.WORKER_CONCURRENCY
        }
        
        # Check for resource issues
        if memory_info.percent > 90:
            health_data['status'] = 'warning'
            health_data['warning'] = 'High memory usage'
        elif active_sessions_count > settings.MAX_BROWSER_INSTANCES:
            health_data['status'] = 'warning'
            health_data['warning'] = 'Too many browser sessions'
        
        return health_data
        
    except Exception as e:
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'unhealthy',
            'error': str(e)
        }


# Utility functions
def _calculate_progress(status: JobStatus) -> float:
    """Calculate progress percentage based on job status"""
    progress_map = {
        JobStatus.PENDING: 0,
        JobStatus.RUNNING: 10,
        JobStatus.QR_WAITING: 25,
        JobStatus.AUTHENTICATING: 40,
        JobStatus.CONFIGURING: 60,
        JobStatus.SEARCHING: 75,
        JobStatus.BOOKING: 90,
        JobStatus.COMPLETED: 100,
        JobStatus.FAILED: 0,
        JobStatus.CANCELLED: 0
    }
    return progress_map.get(status, 0)


def _send_status_webhook_sync(job_id: str, user_id: str, status: JobStatus, message: str, config: Dict[str, Any]) -> None:
    """Send status update webhook (synchronous)"""
    
    try:
        webhook_url = config.get('webhook_url') or settings.SUPABASE_WEBHOOK_URL
        if not webhook_url:
            return
        
        payload = WebhookPayload(
            event_type="status_update",
            job_id=job_id,
            user_id=user_id,
            data={
                'status': status.value,
                'message': message,
                'progress': _calculate_progress(status)
            }
        )
        
        send_webhook_sync(webhook_url, payload.dict())
        
    except Exception as e:
        logger.error("Failed to send status webhook", job_id=job_id, error=str(e))


def _send_qr_webhook_sync(qr_update, config: Dict[str, Any]) -> None:
    """Send QR code update webhook (synchronous)"""
    
    try:
        webhook_url = config.get('webhook_url') or settings.SUPABASE_WEBHOOK_URL
        if not webhook_url:
            return
        
        payload = WebhookPayload(
            event_type="qr_code_update",
            job_id=qr_update.job_id,
            user_id=qr_update.user_id,
            data=qr_update.dict()
        )
        
        send_webhook_sync(webhook_url, payload.dict())
        
    except Exception as e:
        logger.error("Failed to send QR webhook", job_id=qr_update.job_id, error=str(e))


def _send_completion_webhook_sync(job_id: str, user_id: str, success: bool, result: Dict[str, Any], config: Dict[str, Any]) -> None:
    """Send job completion webhook (synchronous)"""
    
    try:
        webhook_url = config.get('webhook_url') or settings.SUPABASE_WEBHOOK_URL
        if not webhook_url:
            return
        
        payload = WebhookPayload(
            event_type="job_completed" if success else "job_failed",
            job_id=job_id,
            user_id=user_id,
            data={
                'success': success,
                'result': result
            }
        )
        
        send_webhook_sync(webhook_url, payload.dict())
        
    except Exception as e:
        logger.error("Failed to send completion webhook", job_id=job_id, error=str(e))


# Export main task functions
__all__ = [
    'process_booking_job',
    'cancel_booking_job', 
    'cleanup_stale_jobs',
    'cleanup_job_resources',
    'health_check_worker'
] 