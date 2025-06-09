"""
Status and Monitoring Endpoints - System health and performance monitoring
"""
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from datetime import datetime
import psutil

from app.models import SystemHealth
from app.workers.celery_app import celery_app, health_check as celery_health_check
from app.workers.booking_worker import JobManager
from app.utils.logging import get_logger
from app.config import get_settings

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()


@router.get("/system")
async def get_system_status() -> SystemHealth:
    """
    Get comprehensive system status
    """
    
    try:
        # Get system metrics
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Check services
        redis_status = "connected"  # Would check Redis connection
        browser_status = "available"  # Would check browser availability
        
        # Check Celery
        celery_health = celery_health_check()
        queue_status = celery_health.get('status', 'unknown')
        
        # Get job counts
        inspect = celery_app.control.inspect()
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        
        active_jobs = sum(len(tasks) for tasks in active_tasks.values())
        queue_size = sum(len(tasks) for tasks in scheduled_tasks.values())
        
        # Get browser session count
        active_sessions = JobManager.get_active_sessions()
        browser_instances = len(active_sessions)
        
        # Calculate browser memory usage
        browser_memory = sum(
            session.get('memory_usage', 0) 
            for session in active_sessions
        )
        
        # Determine overall status
        overall_status = "healthy"
        if redis_status != "connected" or queue_status != "healthy":
            overall_status = "unhealthy"
        elif memory_info.percent > 90 or cpu_percent > 95:
            overall_status = "degraded"
        elif active_jobs >= settings.MAX_CONCURRENT_JOBS:
            overall_status = "at_capacity"
        
        return SystemHealth(
            status=overall_status,
            redis_status=redis_status,
            browser_status=browser_status,
            queue_status=queue_status,
            active_jobs=active_jobs,
            queue_size=queue_size,
            memory_usage=memory_info.percent,
            cpu_usage=cpu_percent,
            disk_usage=(disk_info.used / disk_info.total) * 100,
            browser_instances=browser_instances,
            browser_memory=browser_memory
        )
        
    except Exception as e:
        logger.error("Error getting system status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get system status: {str(e)}")


@router.get("/performance")
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get detailed performance metrics
    """
    
    try:
        # System performance
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        memory_info = psutil.virtual_memory()
        disk_info = psutil.disk_usage('/')
        
        # Network statistics
        network_info = psutil.net_io_counters()
        
        # Process information
        process = psutil.Process()
        process_memory = process.memory_info()
        process_cpu = process.cpu_percent()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_count": cpu_count,
                "cpu_frequency": cpu_freq.current if cpu_freq else None,
                "memory_total_gb": round(memory_info.total / (1024**3), 2),
                "memory_available_gb": round(memory_info.available / (1024**3), 2),
                "memory_percent": memory_info.percent,
                "disk_total_gb": round(disk_info.total / (1024**3), 2),
                "disk_free_gb": round(disk_info.free / (1024**3), 2),
                "disk_percent": round((disk_info.used / disk_info.total) * 100, 2)
            },
            "network": {
                "bytes_sent": network_info.bytes_sent,
                "bytes_received": network_info.bytes_recv,
                "packets_sent": network_info.packets_sent,
                "packets_received": network_info.packets_recv
            },
            "process": {
                "memory_mb": round(process_memory.rss / (1024**2), 2),
                "cpu_percent": process_cpu,
                "threads": process.num_threads(),
                "connections": len(process.connections())
            }
        }
        
    except Exception as e:
        logger.error("Error getting performance metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/workers")
async def get_worker_status() -> Dict[str, Any]:
    """
    Get Celery worker status and statistics
    """
    
    try:
        inspect = celery_app.control.inspect()
        
        # Get worker stats
        stats = inspect.stats() or {}
        active_tasks = inspect.active() or {}
        scheduled_tasks = inspect.scheduled() or {}
        reserved_tasks = inspect.reserved() or {}
        registered_tasks = inspect.registered() or {}
        
        worker_details = {}
        
        for worker_name, worker_stats in stats.items():
            worker_details[worker_name] = {
                "status": "online" if worker_stats else "offline",
                "active_tasks": len(active_tasks.get(worker_name, [])),
                "scheduled_tasks": len(scheduled_tasks.get(worker_name, [])),
                "reserved_tasks": len(reserved_tasks.get(worker_name, [])),
                "registered_tasks": len(registered_tasks.get(worker_name, [])),
                "stats": worker_stats
            }
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_workers": len(stats),
            "online_workers": sum(1 for stats in stats.values() if stats),
            "total_active_tasks": sum(len(tasks) for tasks in active_tasks.values()),
            "total_scheduled_tasks": sum(len(tasks) for tasks in scheduled_tasks.values()),
            "worker_details": worker_details
        }
        
    except Exception as e:
        logger.error("Error getting worker status", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get worker status: {str(e)}")


@router.get("/browser-sessions")
async def get_browser_sessions() -> List[Dict[str, Any]]:
    """
    Get information about active browser sessions
    """
    
    try:
        active_sessions = JobManager.get_active_sessions()
        
        # Enhance session data with additional metrics
        enhanced_sessions = []
        for session in active_sessions:
            enhanced_session = session.copy()
            
            # Add calculated fields
            created_at = datetime.fromisoformat(session['created_at'])
            enhanced_session['duration_seconds'] = (datetime.utcnow() - created_at).total_seconds()
            enhanced_session['status'] = 'active'  # Would get actual status from driver
            
            enhanced_sessions.append(enhanced_session)
        
        return enhanced_sessions
        
    except Exception as e:
        logger.error("Error getting browser sessions", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get browser sessions: {str(e)}")


@router.get("/resource-usage")
async def get_resource_usage() -> Dict[str, Any]:
    """
    Get detailed resource usage information
    """
    
    try:
        # Memory usage breakdown
        memory_info = psutil.virtual_memory()
        swap_info = psutil.swap_memory()
        
        # CPU usage per core
        cpu_per_core = psutil.cpu_percent(percpu=True, interval=1)
        
        # Disk I/O statistics
        disk_io = psutil.disk_io_counters()
        
        # Network I/O statistics
        network_io = psutil.net_io_counters()
        
        # Process count
        process_count = len(psutil.pids())
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "memory": {
                "total_gb": round(memory_info.total / (1024**3), 2),
                "available_gb": round(memory_info.available / (1024**3), 2),
                "used_gb": round(memory_info.used / (1024**3), 2),
                "free_gb": round(memory_info.free / (1024**3), 2),
                "percent": memory_info.percent,
                "buffers_gb": round(getattr(memory_info, 'buffers', 0) / (1024**3), 2),
                "cached_gb": round(getattr(memory_info, 'cached', 0) / (1024**3), 2)
            },
            "swap": {
                "total_gb": round(swap_info.total / (1024**3), 2),
                "used_gb": round(swap_info.used / (1024**3), 2),
                "free_gb": round(swap_info.free / (1024**3), 2),
                "percent": swap_info.percent
            },
            "cpu": {
                "overall_percent": psutil.cpu_percent(),
                "per_core_percent": cpu_per_core,
                "core_count": len(cpu_per_core),
                "load_average": list(psutil.getloadavg()) if hasattr(psutil, 'getloadavg') else None
            },
            "disk_io": {
                "read_bytes": disk_io.read_bytes if disk_io else 0,
                "write_bytes": disk_io.write_bytes if disk_io else 0,
                "read_count": disk_io.read_count if disk_io else 0,
                "write_count": disk_io.write_count if disk_io else 0
            },
            "network_io": {
                "bytes_sent": network_io.bytes_sent,
                "bytes_recv": network_io.bytes_recv,
                "packets_sent": network_io.packets_sent,
                "packets_recv": network_io.packets_recv
            },
            "processes": {
                "total_count": process_count
            }
        }
        
    except Exception as e:
        logger.error("Error getting resource usage", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get resource usage: {str(e)}")


@router.post("/maintenance/cleanup")
async def trigger_maintenance_cleanup() -> Dict[str, Any]:
    """
    Trigger manual maintenance cleanup
    """
    
    try:
        from app.workers.booking_worker import cleanup_stale_jobs
        
        # Trigger cleanup task
        result = cleanup_stale_jobs.delay()
        cleanup_result = result.get(timeout=60)
        
        logger.info("Manual cleanup triggered", result=cleanup_result)
        
        return {
            "success": True,
            "message": "Maintenance cleanup completed",
            "cleanup_result": cleanup_result,
            "triggered_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Error triggering maintenance cleanup", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to trigger cleanup: {str(e)}")


@router.get("/logs/recent")
async def get_recent_logs(
    lines: int = 100,
    level: str = "INFO"
) -> Dict[str, Any]:
    """
    Get recent log entries (placeholder - would need log aggregation system)
    """
    
    try:
        # This would integrate with a log aggregation system
        # For now, return placeholder response
        
        return {
            "message": "Log retrieval not implemented",
            "note": "In production, this would integrate with log aggregation system",
            "requested_lines": lines,
            "requested_level": level,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Error getting recent logs", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}") 