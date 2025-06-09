"""
Webhook Notifications - Send real-time updates to external services
"""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
import httpx
from httpx import AsyncClient, Timeout

from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class WebhookError(Exception):
    """Custom exception for webhook-related errors"""
    pass


class WebhookClient:
    """
    Enhanced webhook client with retry logic, authentication, and monitoring
    """
    
    def __init__(self):
        self.client: Optional[AsyncClient] = None
        self.timeout = Timeout(30.0, connect=10.0)  # 30s total, 10s connect
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def send_webhook(self, url: str, payload: Dict[str, Any], 
                          secret: Optional[str] = None, 
                          headers: Optional[Dict[str, str]] = None,
                          max_retries: int = 3) -> Dict[str, Any]:
        """
        Send webhook with retry logic and authentication
        
        Args:
            url: Webhook URL
            payload: JSON payload to send
            secret: Secret for HMAC signature (optional)
            headers: Additional headers
            max_retries: Maximum retry attempts
            
        Returns:
            Response information
        """
        
        if not self.client:
            raise WebhookError("WebhookClient not initialized")
        
        # Prepare headers
        request_headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'{settings.APP_NAME}/{settings.APP_VERSION}',
            'X-Webhook-Timestamp': str(int(time.time())),
            'X-Webhook-ID': f"webhook_{int(time.time() * 1000000)}"
        }
        
        if headers:
            request_headers.update(headers)
        
        # Create JSON payload
        json_payload = json.dumps(payload, separators=(',', ':'), default=str)
        
        # Add HMAC signature if secret provided
        if secret:
            signature = self._create_signature(json_payload, secret)
            request_headers['X-Webhook-Signature'] = signature
        
        # Retry logic
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                
                response = await self.client.post(
                    url,
                    content=json_payload,
                    headers=request_headers
                )
                
                duration = time.time() - start_time
                
                # Log the webhook attempt
                logger.info(
                    "Webhook sent",
                    url=url,
                    status_code=response.status_code,
                    duration=duration,
                    attempt=attempt + 1,
                    payload_size=len(json_payload)
                )
                
                # Check response status
                if response.is_success:
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'response_time': duration,
                        'attempt': attempt + 1,
                        'response_text': response.text[:500] if response.text else None
                    }
                else:
                    # Log non-success status codes
                    logger.warning(
                        "Webhook returned non-success status",
                        url=url,
                        status_code=response.status_code,
                        response_text=response.text[:500] if response.text else None
                    )
                    
                    # Don't retry for client errors (4xx)
                    if 400 <= response.status_code < 500:
                        return {
                            'success': False,
                            'status_code': response.status_code,
                            'error': f"Client error: {response.status_code}",
                            'response_text': response.text[:500] if response.text else None
                        }
                    
                    # Retry for server errors (5xx)
                    last_exception = WebhookError(f"Server error: {response.status_code}")
                    
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as e:
                last_exception = e
                logger.warning(
                    "Webhook network error",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1
                )
                
            except Exception as e:
                last_exception = e
                logger.error(
                    "Webhook unexpected error",
                    url=url,
                    error=str(e),
                    attempt=attempt + 1
                )
            
            # Wait before retry (exponential backoff)
            if attempt < max_retries:
                wait_time = min(2 ** attempt, 30)  # Max 30 seconds
                await asyncio.sleep(wait_time)
        
        # All retries failed
        logger.error(
            "Webhook failed after all retries",
            url=url,
            max_retries=max_retries,
            final_error=str(last_exception)
        )
        
        return {
            'success': False,
            'error': str(last_exception),
            'retries_exhausted': True,
            'max_retries': max_retries
        }
    
    def _create_signature(self, payload: str, secret: str) -> str:
        """Create HMAC signature for payload"""
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"


# Global webhook client instance
_webhook_client: Optional[WebhookClient] = None


async def get_webhook_client() -> WebhookClient:
    """Get or create webhook client instance"""
    global _webhook_client
    
    if _webhook_client is None:
        _webhook_client = WebhookClient()
        await _webhook_client.__aenter__()
    
    return _webhook_client


async def send_webhook(url: str, payload: Dict[str, Any], 
                      secret: Optional[str] = None,
                      headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Send webhook notification
    
    Args:
        url: Webhook URL
        payload: Data to send
        secret: HMAC secret (uses default if not provided)
        headers: Additional headers
        
    Returns:
        Response information
    """
    
    webhook_client = await get_webhook_client()
    
    # Use default secret if not provided
    if secret is None:
        secret = settings.WEBHOOK_SECRET
    
    return await webhook_client.send_webhook(url, payload, secret, headers)


async def send_supabase_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send webhook to Supabase with default configuration
    
    Args:
        payload: Data to send
        
    Returns:
        Response information
    """
    
    return await send_webhook(
        url=settings.SUPABASE_WEBHOOK_URL,
        payload=payload,
        secret=settings.SUPABASE_SECRET_KEY,
        headers={
            'X-Source': 'vps-automation-server',
            'X-Environment': settings.ENVIRONMENT
        }
    )


async def send_status_update(job_id: str, user_id: str, status: str, 
                           message: str, progress: float = 0,
                           extra_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Send job status update webhook
    
    Args:
        job_id: Job identifier
        user_id: User identifier
        status: Current status
        message: Status message
        progress: Progress percentage (0-100)
        extra_data: Additional data to include
        
    Returns:
        Response information
    """
    
    payload = {
        'event_type': 'status_update',
        'job_id': job_id,
        'user_id': user_id,
        'timestamp': datetime.utcnow().isoformat(),
        'data': {
            'status': status,
            'message': message,
            'progress': progress,
            **(extra_data or {})
        }
    }
    
    return await send_supabase_webhook(payload)


async def send_qr_code_update(job_id: str, user_id: str, qr_code_data: str,
                             retry_count: int = 0) -> Dict[str, Any]:
    """
    Send QR code update webhook
    
    Args:
        job_id: Job identifier
        user_id: User identifier
        qr_code_data: Base64 encoded QR code image
        retry_count: Number of retry attempts
        
    Returns:
        Response information
    """
    
    payload = {
        'event_type': 'qr_code_update',
        'job_id': job_id,
        'user_id': user_id,
        'timestamp': datetime.utcnow().isoformat(),
        'data': {
            'qr_code_data': qr_code_data,
            'retry_count': retry_count,
            'image_size': len(qr_code_data) if qr_code_data else 0
        }
    }
    
    return await send_supabase_webhook(payload)


async def send_booking_completion(job_id: str, user_id: str, success: bool,
                                 booking_result: Optional[Dict[str, Any]] = None,
                                 error: Optional[str] = None) -> Dict[str, Any]:
    """
    Send booking completion webhook
    
    Args:
        job_id: Job identifier
        user_id: User identifier
        success: Whether booking was successful
        booking_result: Booking details if successful
        error: Error message if failed
        
    Returns:
        Response information
    """
    
    payload = {
        'event_type': 'booking_completed' if success else 'booking_failed',
        'job_id': job_id,
        'user_id': user_id,
        'timestamp': datetime.utcnow().isoformat(),
        'data': {
            'success': success,
            'booking_result': booking_result,
            'error': error
        }
    }
    
    return await send_supabase_webhook(payload)


async def send_system_alert(alert_type: str, message: str, severity: str = 'info',
                           metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Send system alert webhook
    
    Args:
        alert_type: Type of alert
        message: Alert message
        severity: Alert severity (info, warning, error, critical)
        metadata: Additional metadata
        
    Returns:
        Response information
    """
    
    payload = {
        'event_type': 'system_alert',
        'timestamp': datetime.utcnow().isoformat(),
        'data': {
            'alert_type': alert_type,
            'message': message,
            'severity': severity,
            'metadata': metadata or {}
        }
    }
    
    return await send_supabase_webhook(payload)


async def send_health_check(health_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send health check data webhook
    
    Args:
        health_data: Health check information
        
    Returns:
        Response information
    """
    
    payload = {
        'event_type': 'health_check',
        'timestamp': datetime.utcnow().isoformat(),
        'data': health_data
    }
    
    return await send_supabase_webhook(payload)


class WebhookBatch:
    """
    Batch multiple webhooks for efficient sending
    """
    
    def __init__(self, max_size: int = 10, flush_interval: float = 5.0):
        self.max_size = max_size
        self.flush_interval = flush_interval
        self.webhooks: List[Dict[str, Any]] = []
        self.last_flush = time.time()
        
    def add_webhook(self, url: str, payload: Dict[str, Any], 
                   secret: Optional[str] = None) -> None:
        """Add webhook to batch"""
        
        self.webhooks.append({
            'url': url,
            'payload': payload,
            'secret': secret,
            'added_at': time.time()
        })
        
        # Auto-flush if batch is full
        if len(self.webhooks) >= self.max_size:
            asyncio.create_task(self.flush())
    
    async def flush(self) -> List[Dict[str, Any]]:
        """Send all webhooks in batch"""
        
        if not self.webhooks:
            return []
        
        webhooks_to_send = self.webhooks.copy()
        self.webhooks.clear()
        self.last_flush = time.time()
        
        # Send webhooks concurrently
        tasks = []
        for webhook in webhooks_to_send:
            task = asyncio.create_task(
                send_webhook(
                    webhook['url'],
                    webhook['payload'],
                    webhook['secret']
                )
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log batch results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
        failed = len(results) - successful
        
        logger.info(
            "Webhook batch completed",
            total_webhooks=len(webhooks_to_send),
            successful=successful,
            failed=failed
        )
        
        return results
    
    def should_flush(self) -> bool:
        """Check if batch should be flushed"""
        return (
            len(self.webhooks) >= self.max_size or
            (self.webhooks and time.time() - self.last_flush >= self.flush_interval)
        )


# Global webhook batch instance
webhook_batch = WebhookBatch()


async def send_webhook_batched(url: str, payload: Dict[str, Any], 
                              secret: Optional[str] = None) -> None:
    """
    Add webhook to batch for efficient sending
    
    Args:
        url: Webhook URL
        payload: Data to send
        secret: HMAC secret
    """
    
    webhook_batch.add_webhook(url, payload, secret)
    
    # Flush if needed
    if webhook_batch.should_flush():
        await webhook_batch.flush()


async def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Verify webhook signature
    
    Args:
        payload: Raw payload string
        signature: Received signature
        secret: HMAC secret
        
    Returns:
        True if signature is valid
    """
    
    try:
        # Extract algorithm and signature
        if not signature.startswith('sha256='):
            return False
        
        received_signature = signature[7:]  # Remove 'sha256=' prefix
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Secure comparison
        return hmac.compare_digest(received_signature, expected_signature)
        
    except Exception as e:
        logger.error("Error verifying webhook signature", error=str(e))
        return False


async def cleanup_webhook_client() -> None:
    """Cleanup webhook client resources"""
    global _webhook_client
    
    if _webhook_client:
        await _webhook_client.__aexit__(None, None, None)
        _webhook_client = None


# Auto-flush webhook batch periodically
async def start_webhook_batch_flusher():
    """Start background task to flush webhook batch periodically"""
    
    while True:
        try:
            await asyncio.sleep(webhook_batch.flush_interval)
            if webhook_batch.should_flush():
                await webhook_batch.flush()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Error in webhook batch flusher", error=str(e))


def send_webhook_sync(url: str, payload: Dict[str, Any], 
                     secret: Optional[str] = None,
                     headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Send webhook notification synchronously
    
    Args:
        url: Webhook URL
        payload: Data to send
        secret: HMAC secret (uses default if not provided)
        headers: Additional headers
        
    Returns:
        Response information
    """
    
    try:
        import requests
        
        # Use default secret if not provided
        if secret is None:
            secret = settings.WEBHOOK_SECRET
            
        # Prepare headers
        request_headers = {
            'Content-Type': 'application/json',
            'User-Agent': f'{settings.APP_NAME}/{settings.APP_VERSION}',
            'X-Webhook-Timestamp': str(int(time.time())),
            'X-Webhook-ID': f"webhook_{int(time.time() * 1000000)}"
        }
        
        if headers:
            request_headers.update(headers)
        
        # Create JSON payload
        json_payload = json.dumps(payload, separators=(',', ':'), default=str)
        
        # Add HMAC signature if secret provided
        if secret:
            signature = hmac.new(
                secret.encode('utf-8'),
                json_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            request_headers['X-Webhook-Signature'] = f"sha256={signature}"
        
        # Send request with timeout
        start_time = time.time()
        response = requests.post(
            url,
            data=json_payload,
            headers=request_headers,
            timeout=30  # 30 second timeout
        )
        duration = time.time() - start_time
        
        # Log the webhook attempt
        logger.info(
            "Webhook sent (sync)",
            url=url,
            status_code=response.status_code,
            duration=duration,
            payload_size=len(json_payload)
        )
        
        # Check response status
        if response.status_code < 400:
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': duration,
                'response_text': response.text[:500] if response.text else None
            }
        else:
            logger.warning(
                "Webhook returned error status (sync)",
                url=url,
                status_code=response.status_code,
                response_text=response.text[:500] if response.text else None
            )
            return {
                'success': False,
                'status_code': response.status_code,
                'error': f"HTTP {response.status_code}",
                'response_text': response.text[:500] if response.text else None
            }
            
    except Exception as e:
        logger.error("Webhook sync error", url=url, error=str(e))
        return {
            'success': False,
            'error': str(e)
        }


# Export main functions
__all__ = [
    'send_webhook',
    'send_webhook_sync',
    'send_supabase_webhook',
    'send_status_update',
    'send_qr_code_update',
    'send_booking_completion',
    'send_system_alert',
    'send_health_check',
    'verify_webhook_signature',
    'WebhookError'
] 