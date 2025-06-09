"""
Celery Configuration - Background job processing with Redis backend
"""
import os
from celery import Celery
from celery.signals import worker_ready, worker_shutdown, task_prerun, task_postrun, task_failure, task_success
from kombu import Queue

from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Initialize Celery app
celery_app = Celery(
    "vps_automation_server",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.workers.booking_worker'
    ]
)

# Celery Configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        'app.workers.booking_worker.process_booking_job': {'queue': 'booking'},
        'app.workers.booking_worker.cancel_booking_job': {'queue': 'booking'},
        'app.workers.booking_worker.cleanup_stale_jobs': {'queue': 'maintenance'},
        'app.workers.booking_worker.health_check_worker': {'queue': 'health'},
    },
    
    # Queue configuration
    task_default_queue='default',
    task_create_missing_queues=True,
    
    # Define queues with different priorities
    task_queues=(
        Queue('booking', routing_key='booking'),
        Queue('maintenance', routing_key='maintenance'),
        Queue('health', routing_key='health'),
        Queue('default', routing_key='default'),
    ),
    
    # Task execution settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone=settings.TRAFIKVERKET_TIMEZONE,
    enable_utc=True,
    
    # Worker configuration
    worker_concurrency=settings.WORKER_CONCURRENCY,
    worker_prefetch_multiplier=settings.WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
    worker_disable_rate_limits=False,
    
    # Task result settings
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=True,
    result_compression='gzip',
    
    # Task routing and retry configuration
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,
    task_soft_time_limit=settings.JOB_TIMEOUT - 60,  # Soft timeout (29 minutes)
    task_time_limit=settings.JOB_TIMEOUT,  # Hard timeout (30 minutes)
    task_max_retries=3,
    task_default_retry_delay=60,  # Retry after 1 minute
    
    # Monitoring and logging
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_track_started=True,
    
    # Security
    task_always_eager=False,  # Set to True for testing only
    task_eager_propagates=True,
    task_store_eager_result=True,
    
    # Resource management
    worker_max_memory_per_child=512000,  # 512MB per worker
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'cleanup-stale-jobs': {
            'task': 'app.workers.booking_worker.cleanup_stale_jobs',
            'schedule': 300.0,  # Every 5 minutes
            'options': {'queue': 'maintenance'}
        },
        'health-check': {
            'task': 'app.workers.booking_worker.health_check_worker',
            'schedule': 60.0,  # Every minute
            'options': {'queue': 'health'}
        },
    },
)


# Custom Celery configuration for different environments
if settings.ENVIRONMENT == 'development':
    # Development settings
    celery_app.conf.update(
        task_always_eager=False,  # Still use Redis even in development
        worker_log_level='DEBUG',
        task_send_sent_event=True,
    )
elif settings.ENVIRONMENT == 'production':
    # Production settings
    celery_app.conf.update(
        worker_log_level='INFO',
        worker_optimization='fair',
        task_send_sent_event=True,
        worker_disable_rate_limits=False,
    )


# Signal handlers for monitoring and logging
@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Log when worker is ready"""
    logger.info("Celery worker is ready", worker_id=sender.hostname)


@worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Log when worker is shutting down"""
    logger.info("Celery worker is shutting down", worker_id=sender.hostname)


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log before task execution"""
    logger.info(
        "Starting task execution",
        task_id=task_id,
        task_name=task.name,
        args_count=len(args) if args else 0,
        kwargs_keys=list(kwargs.keys()) if kwargs else []
    )


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                        retval=None, state=None, **kwds):
    """Log after task execution"""
    logger.info(
        "Completed task execution",
        task_id=task_id,
        task_name=task.name,
        state=state,
        success=state == 'SUCCESS'
    )


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
    """Log task failures"""
    logger.error(
        "Task execution failed",
        task_id=task_id,
        task_name=sender.name,
        error=str(exception),
        error_type=type(exception).__name__
    )


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Log successful task completion"""
    logger.info(
        "Task completed successfully",
        task_name=sender.name,
        result_type=type(result).__name__ if result else None
    )


# Custom task base class with enhanced error handling
class BaseTask(celery_app.Task):
    """Base task class with enhanced error handling and logging"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 60}
    retry_backoff = True
    retry_backoff_max = 700
    retry_jitter = False
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails"""
        logger.error(
            "Task failed after all retries",
            task_id=task_id,
            task_name=self.name,
            exception=str(exc),
            args=args,
            kwargs=kwargs
        )
        
        # Cleanup any resources associated with this task
        try:
            from app.workers.booking_worker import cleanup_job_resources
            if args and len(args) > 0:
                job_id = args[0] if isinstance(args[0], str) else None
                if job_id:
                    cleanup_job_resources.delay(job_id)
        except Exception as cleanup_error:
            logger.error("Failed to cleanup job resources", error=str(cleanup_error))
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when task is retried"""
        logger.warning(
            "Task is being retried",
            task_id=task_id,
            task_name=self.name,
            exception=str(exc),
            retry_count=self.request.retries
        )
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds"""
        logger.info(
            "Task completed successfully",
            task_id=task_id,
            task_name=self.name,
            result_type=type(retval).__name__ if retval else None
        )


# Set the base task class
celery_app.Task = BaseTask


# Utility functions for task management
def get_active_tasks():
    """Get list of active tasks"""
    inspect = celery_app.control.inspect()
    return inspect.active()


def get_scheduled_tasks():
    """Get list of scheduled tasks"""
    inspect = celery_app.control.inspect()
    return inspect.scheduled()


def get_reserved_tasks():
    """Get list of reserved tasks"""
    inspect = celery_app.control.inspect()
    return inspect.reserved()


def get_worker_stats():
    """Get worker statistics"""
    inspect = celery_app.control.inspect()
    return inspect.stats()


def revoke_task(task_id: str, terminate: bool = False):
    """Revoke a specific task"""
    celery_app.control.revoke(task_id, terminate=terminate)
    logger.info("Task revoked", task_id=task_id, terminate=terminate)


def purge_queue(queue_name: str):
    """Purge all tasks from a specific queue"""
    celery_app.control.purge()
    logger.info("Queue purged", queue_name=queue_name)


def shutdown_workers(signal: str = 'TERM'):
    """Shutdown all workers"""
    celery_app.control.broadcast('shutdown', arguments={'signal': signal})
    logger.info("Worker shutdown requested", signal=signal)


# Health check function
def health_check():
    """Check Celery health status"""
    try:
        # Check if broker is accessible
        inspect = celery_app.control.inspect()
        stats = inspect.stats()
        
        if not stats:
            return {'status': 'unhealthy', 'reason': 'No workers available'}
        
        # Check worker status
        for worker, stat in stats.items():
            if not stat:
                return {'status': 'unhealthy', 'reason': f'Worker {worker} not responding'}
        
        return {
            'status': 'healthy',
            'workers': len(stats),
            'active_tasks': sum(len(tasks) for tasks in get_active_tasks().values()),
            'scheduled_tasks': sum(len(tasks) for tasks in get_scheduled_tasks().values())
        }
        
    except Exception as e:
        return {'status': 'unhealthy', 'reason': str(e)}


# Export the Celery app
__all__ = ['celery_app', 'health_check', 'get_active_tasks', 'revoke_task'] 