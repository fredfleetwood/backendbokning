"""
VPS System Logger - Sends logs to Supabase for centralized debugging
"""
import json
import time
import requests
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

class LogLevel(Enum):
    INFO = "info"
    ERROR = "error"

class VPSSystemLogger:
    def __init__(self, supabase_url: str = None):
        self.supabase_url = supabase_url or "https://kqemgnbqjrqepzkigfcx.supabase.co"
        self.trace_id = None
        self.step_counter = 0
        self.context = {}
        
        self.generate_new_trace()
        print(f"🔧 VPS Logger initialized - trace: {self.trace_id}")

    def generate_new_trace(self) -> str:
        """Generate a new trace ID for tracking requests"""
        self.trace_id = f"vps_trace_{int(time.time() * 1000)}_{id(self) % 10000}"
        self.step_counter = 0
        print(f"🆔 New VPS trace: {self.trace_id}")
        return self.trace_id

    def set_context(self, **context):
        """Set context that will be included in all subsequent logs"""
        self.context.update(context)

    def _log(self, level: LogLevel, operation: str, message: str, data: Dict[str, Any] = None, 
             error_details: Dict[str, Any] = None):
        """Internal logging method"""
        self.step_counter += 1
        
        log_entry = {
            "level": level.value,
            "component": "vps",
            "operation": operation,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace_id": self.trace_id,
            "step_number": self.step_counter,
            "data": data or {},
            **self.context
        }
        
        if error_details:
            log_entry["error_details"] = error_details

        # Print to console
        emoji = "ℹ️" if level == LogLevel.INFO else "❌"
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{emoji} [{timestamp}] [vps] [{operation}] {message}")
        if data:
            print(f"   Data: {json.dumps(data, indent=2)}")

        # Send to Supabase
        try:
            self._send_to_supabase(log_entry)
        except Exception as e:
            print(f"⚠️ Failed to send log to Supabase: {e}")

    def _send_to_supabase(self, log_entry: Dict[str, Any]):
        """Send log entry to Supabase via Edge Function"""
        try:
            url = f"{self.supabase_url}/functions/v1/system-logs?action=log"
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(url, json=log_entry, headers=headers, timeout=5)
            if response.status_code != 200:
                print(f"⚠️ Supabase log failed: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Supabase logging error: {e}")

    def info(self, operation: str, message: str, data: Dict[str, Any] = None):
        """Log info message"""
        self._log(LogLevel.INFO, operation, message, data)

    def error(self, operation: str, message: str, error: Exception = None, data: Dict[str, Any] = None):
        """Log error message"""
        error_details = None
        if error:
            error_details = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc()
            }
        self._log(LogLevel.ERROR, operation, message, data, error_details=error_details)

    # Booking-specific methods
    def log_booking_received(self, job_id: str, user_config: Dict[str, Any]):
        """Log when booking request is received"""
        self.generate_new_trace()
        self.set_context(job_id=job_id, user_id=user_config.get('user_id'))
        
        self.info('booking-received', 'VPS received booking request', {
            'job_id': job_id,
            'license_type': user_config.get('license_type'),
            'exam_type': user_config.get('exam_type'),
            'locations_count': len(user_config.get('locations', []))
        })

    def log_browser_launch(self, browser_type: str, headless: bool):
        """Log browser launch"""
        self.info('browser-launch', f'Launching {browser_type} browser', {
            'browser_type': browser_type,
            'headless': headless
        })

    def log_bankid_step(self, step: str, qr_code_present: bool = False):
        """Log BankID authentication steps"""
        self.info('bankid-auth', f'BankID step: {step}', {
            'step': step,
            'qr_code_present': qr_code_present
        })

    def log_qr_capture(self, job_id: str, qr_data_size: int):
        """Log QR code capture"""
        self.info('qr-capture', f'QR code captured for job {job_id}', {
            'job_id': job_id,
            'qr_data_size': qr_data_size
        })

    def log_booking_completion(self, job_id: str, success: bool, booking_details: Dict[str, Any] = None):
        """Log booking completion"""
        if success:
            self.info('booking-completed', f'Booking completed for job {job_id}', {
                'job_id': job_id,
                'booking_details': booking_details
            })
        else:
            self.error('booking-failed', f'Booking failed for job {job_id}', None, {
                'job_id': job_id
            })

    def get_current_trace_id(self) -> str:
        """Get current trace ID"""
        return self.trace_id

# Create singleton instance
vps_logger = VPSSystemLogger()

# Export for easy importing
__all__ = ['VPSSystemLogger', 'vps_logger'] 