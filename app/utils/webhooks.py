"""
Webhook System - Real-time communication with external services
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import httpx
import redis
from app.models import WebhookPayload


class WebhookManager:
    """Manages webhook delivery to external services"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self.timeout = 30.0
        self.max_retries = 3
        # Supabase configuration for QR Storage
        self.supabase_url = "https://kqemgnbqjrqepzkigfcx.supabase.co"
        self.supabase_anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtxZW1nbmJxanJxZXB6a2lnZmN4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkyMTQ4MDEsImV4cCI6MjA2NDc5MDgwMX0.tnPomyWLMseJX0GlrUeO63Ig9GRZSTh1O1Fi2p9q8mc"
        
    async def send_qr_code_to_storage(self, job_id: str, user_id: str, 
                                     qr_image_data: str, auth_ref: str = None) -> bool:
        """
        Send QR code to Supabase Storage for efficient handling
        Returns True if successful, False if failed
        """
        try:
            storage_url = f"{self.supabase_url}/functions/v1/qr-storage"
            
            payload = {
                "job_id": job_id,
                "qr_image_data": qr_image_data,
                "auth_ref": auth_ref,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            print(f"[WEBHOOK] 📱 Sending QR to Supabase Storage for job {job_id}")
            print(f"[WEBHOOK] 📊 QR data size: {len(qr_image_data)} characters")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.supabase_anon_key}"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(storage_url, json=payload, headers=headers)
                
                if response.status_code == 200:
                    result = response.json()
                    qr_url = result.get('qr_url', 'URL not returned')
                    print(f"[WEBHOOK] ✅ QR stored in Supabase Storage: {qr_url}")
                    return True
                else:
                    error_text = response.text
                    print(f"[WEBHOOK] ❌ QR storage failed: {response.status_code} - {error_text}")
                    return False
                    
        except Exception as e:
            print(f"[WEBHOOK] ❌ QR storage error: {e}")
            return False
        
    async def send_webhook(self, webhook_url: str, event_type: str, job_id: str, 
                          user_id: str, data: Dict[str, Any]) -> bool:
        """Send webhook to external service with retry logic"""
        
        if not webhook_url:
            return False
            
        payload = WebhookPayload(
            event_type=event_type,
            job_id=job_id,
            user_id=user_id,
            timestamp=datetime.utcnow(),
            data=data
        )
        
        # Add webhook signature for security
        webhook_secret = os.getenv("WEBHOOK_SECRET", "default-secret")
        payload_json = payload.json()
        signature = self._generate_signature(payload_json, webhook_secret)
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "VPS-Automation-Server/1.0",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event_type,
            "X-Job-ID": job_id
        }
        
        # Try to send with retries
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        webhook_url, 
                        content=payload_json,
                        headers=headers
                    )
                    
                    if response.status_code in [200, 201, 202]:
                        print(f"✅ Webhook delivered: {event_type} for job {job_id}")
                        await self._log_webhook_success(job_id, event_type, webhook_url)
                        return True
                    else:
                        print(f"⚠️ Webhook failed with status {response.status_code}: {response.text}")
                        
            except Exception as e:
                print(f"❌ Webhook attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        await self._log_webhook_failure(job_id, event_type, webhook_url)
        return False
    
    async def send_status_update(self, webhook_url: str, job_id: str, user_id: str,
                                status: str, message: str, progress: float) -> bool:
        """Send job status update webhook"""
        
        data = {
            "status": status,
            "message": message,
            "progress": progress,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        return await self.send_webhook(
            webhook_url, "status_update", job_id, user_id, data
        )
    
    async def send_qr_code_update(self, webhook_url: str, job_id: str, user_id: str,
                                 qr_code_data: str, auth_ref: str = None) -> bool:
        """
        Enhanced QR code update using Supabase Storage for efficiency
        Tries Storage first, falls back to webhook if needed
        """
        # First try to store in Supabase Storage
        storage_success = await self.send_qr_code_to_storage(
            job_id, user_id, qr_code_data, auth_ref
        )
        
        if storage_success:
            # Send lightweight webhook notification (no QR data included)
            data = {
                "qr_in_storage": True,
                "auth_ref": auth_ref,
                "timestamp": datetime.utcnow().isoformat(),
                "message": "QR code updated in storage",
                "expires_in": 180  # 3 minutes
            }
            
            print(f"[WEBHOOK] ✅ Sending lightweight QR notification (storage-based)")
            return await self.send_webhook(
                webhook_url, "qr_code_update", job_id, user_id, data
            )
        else:
            # Fallback to original method with QR in webhook
            print(f"[WEBHOOK] ⚠️ Storage failed, falling back to webhook QR")
            return await self.send_qr_code_update_fallback(
                webhook_url, job_id, user_id, qr_code_data, auth_ref
            )
    
    async def send_qr_code_update_fallback(self, webhook_url: str, job_id: str, user_id: str,
                                          qr_code_data: str, auth_ref: str = None) -> bool:
        """Original QR code update method as fallback"""
        
        data = {
            "qr_code_data": qr_code_data,
            "auth_ref": auth_ref,
            "timestamp": datetime.utcnow().isoformat(),
            "expires_in": 180,  # Extended QR timeout for better user experience (3 minutes)
            "qr_in_storage": False
        }
        
        return await self.send_webhook(
            webhook_url, "qr_code_update", job_id, user_id, data
        )
    
    async def send_booking_completed(self, webhook_url: str, job_id: str, user_id: str,
                                   success: bool, booking_result: Dict[str, Any] = None,
                                   error_message: str = None) -> bool:
        """Send booking completion webhook"""
        
        data = {
            "success": success,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        if success and booking_result:
            data["booking_result"] = booking_result
        elif not success and error_message:
            data["error_message"] = error_message
        
        return await self.send_webhook(
            webhook_url, "booking_completed", job_id, user_id, data
        )
    
    async def send_booking_started(self, webhook_url: str, job_id: str, user_id: str,
                                  booking_config: Dict[str, Any]) -> bool:
        """Send booking started webhook"""
        
        data = {
            "started_at": datetime.utcnow().isoformat(),
            "config": booking_config,
            "estimated_duration": "60-180 seconds"
        }
        
        return await self.send_webhook(
            webhook_url, "booking_started", job_id, user_id, data
        )
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook security"""
        import hmac
        import hashlib
        
        signature = hmac.new(
            secret.encode(), 
            payload.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        return f"sha256={signature}"
    
    async def _log_webhook_success(self, job_id: str, event_type: str, webhook_url: str):
        """Log successful webhook delivery"""
        if self.redis_client:
            try:
                log_data = {
                    "job_id": job_id,
                    "event_type": event_type,
                    "webhook_url": webhook_url,
                    "status": "success",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                self.redis_client.lpush(
                    f"webhook_log:{job_id}", 
                    json.dumps(log_data)
                )
                self.redis_client.expire(f"webhook_log:{job_id}", 3600)  # 1 hour
            except Exception as e:
                print(f"Failed to log webhook success: {e}")
    
    async def _log_webhook_failure(self, job_id: str, event_type: str, webhook_url: str):
        """Log failed webhook delivery"""
        if self.redis_client:
            try:
                log_data = {
                    "job_id": job_id,
                    "event_type": event_type,
                    "webhook_url": webhook_url,
                    "status": "failed",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                self.redis_client.lpush(
                    f"webhook_log:{job_id}", 
                    json.dumps(log_data)
                )
                self.redis_client.expire(f"webhook_log:{job_id}", 3600)  # 1 hour
            except Exception as e:
                print(f"Failed to log webhook failure: {e}")


# Global webhook manager instance
webhook_manager = WebhookManager()


async def initialize_webhook_manager(redis_client: redis.Redis):
    """Initialize the global webhook manager with Redis client"""
    global webhook_manager
    webhook_manager = WebhookManager(redis_client)


async def send_webhook_if_configured(webhook_url: str, event_type: str, 
                                   job_id: str, user_id: str, data: Dict[str, Any]) -> bool:
    """Utility function to send webhook if URL is configured"""
    if webhook_url:
        return await webhook_manager.send_webhook(webhook_url, event_type, job_id, user_id, data)
    return False 