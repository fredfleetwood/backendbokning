"""
QR Code Capture Utilities - Advanced QR code detection and streaming for BankID authentication
"""
import asyncio
import base64
import io
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np
from playwright.async_api import Page, ElementHandle
import structlog

from app.config import get_settings
from app.models import QRCodeUpdate
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class QRCodeCapture:
    """
    Advanced QR code detection and streaming system for BankID authentication
    """
    
    def __init__(self, user_id: str, job_id: str, webhook_callback: Optional[Callable] = None):
        self.user_id = user_id
        self.job_id = job_id
        self.webhook_callback = webhook_callback
        self.logger = logger.bind(user_id=user_id, job_id=job_id)
        
        # QR detection state
        self.current_qr_data: Optional[str] = None
        self.qr_detected_at: Optional[datetime] = None
        self.capture_count = 0
        self.retry_count = 0
        self.is_capturing = False
        
        # Detection strategies
        self.detection_selectors = [
            # Primary BankID QR code selectors
            "img[alt*='QR']",
            "img[alt*='qr']", 
            "img[src*='qr']",
            "img[src*='QR']",
            
            # Canvas elements (some sites render QR codes on canvas)
            "canvas[id*='qr']",
            "canvas[class*='qr']",
            "canvas[id*='bankid']",
            
            # Common BankID selectors
            ".qr-code img",
            ".qr-code canvas", 
            "#qr-code",
            "#qr-image",
            "#bankid-qr",
            ".bankid-qr",
            
            # Generic image selectors as fallback
            "img[width='200']",  # Common QR code size
            "img[height='200']",
            "img[width='300']",
            "img[height='300']"
        ]

    async def detect_qr_code(self, page: Page) -> Optional[str]:
        """
        Detect QR code using multiple strategies and return base64 encoded image
        
        Args:
            page: Playwright page instance
            
        Returns:
            Base64 encoded QR code image or None if not found
        """
        try:
            self.logger.info("Starting QR code detection")
            
            # Strategy 1: Try specific QR code selectors
            qr_data = await self._detect_by_selectors(page)
            if qr_data:
                self.logger.info("QR code detected using selectors")
                return qr_data
            
            # Strategy 2: Search for images that might be QR codes
            qr_data = await self._detect_by_image_analysis(page)
            if qr_data:
                self.logger.info("QR code detected using image analysis")
                return qr_data
            
            # Strategy 3: Full page screenshot and search for QR patterns
            qr_data = await self._detect_in_full_page(page)
            if qr_data:
                self.logger.info("QR code detected in full page screenshot")
                return qr_data
                
            self.logger.debug("No QR code detected")
            return None
            
        except Exception as e:
            self.logger.error("Error during QR code detection", error=str(e))
            return None

    async def _detect_by_selectors(self, page: Page) -> Optional[str]:
        """Detect QR code using CSS selectors"""
        
        for selector in self.detection_selectors:
            try:
                # Wait briefly for element to appear
                element = await page.wait_for_selector(selector, timeout=1000)
                if element:
                    # Take screenshot of the element
                    screenshot_bytes = await element.screenshot()
                    
                    # Verify it's actually a QR code
                    if await self._is_qr_code_image(screenshot_bytes):
                        # Convert to base64
                        base64_data = self._bytes_to_base64(screenshot_bytes)
                        self.logger.info("QR code found", selector=selector)
                        return base64_data
                        
            except Exception as e:
                # Timeout or element not found - continue to next selector
                continue
                
        return None

    async def _detect_by_image_analysis(self, page: Page) -> Optional[str]:
        """Detect QR code by analyzing all images on the page"""
        
        try:
            # Get all images on the page
            images = await page.query_selector_all("img")
            
            for img in images:
                try:
                    # Get image dimensions and src
                    box = await img.bounding_box()
                    if not box:
                        continue
                    
                    # Skip very small images (likely not QR codes)
                    if box['width'] < 100 or box['height'] < 100:
                        continue
                    
                    # Skip very large images (likely not QR codes)
                    if box['width'] > 500 or box['height'] > 500:
                        continue
                    
                    # Take screenshot of the image
                    screenshot_bytes = await img.screenshot()
                    
                    # Check if it's a QR code
                    if await self._is_qr_code_image(screenshot_bytes):
                        base64_data = self._bytes_to_base64(screenshot_bytes)
                        self.logger.info("QR code found in image analysis")
                        return base64_data
                        
                except Exception as e:
                    continue
                    
        except Exception as e:
            self.logger.error("Error in image analysis detection", error=str(e))
            
        return None

    async def _detect_in_full_page(self, page: Page) -> Optional[str]:
        """Detect QR code in full page screenshot as last resort"""
        
        try:
            # Take full page screenshot
            screenshot_bytes = await page.screenshot(full_page=True)
            
            # Use computer vision to find QR code patterns
            qr_region = await self._find_qr_in_image(screenshot_bytes)
            if qr_region:
                base64_data = self._bytes_to_base64(qr_region)
                self.logger.info("QR code found in full page screenshot")
                return base64_data
                
        except Exception as e:
            self.logger.error("Error in full page QR detection", error=str(e))
            
        return None

    async def _is_qr_code_image(self, image_bytes: bytes) -> bool:
        """
        Analyze image bytes to determine if it contains a QR code
        
        Args:
            image_bytes: Raw image data
            
        Returns:
            True if image appears to contain a QR code
        """
        try:
            # Convert bytes to numpy array for OpenCV
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return False
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Look for QR code patterns
            # QR codes have specific patterns: finder patterns (squares in corners)
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
            
            # Find contours
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Look for square-like shapes (QR code finder patterns)
            squares = 0
            for contour in contours:
                # Approximate contour to polygon
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Check if it's roughly square (4 corners)
                if len(approx) == 4:
                    # Check if it's roughly square in shape
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = float(w) / h
                    
                    # Square-ish shape (QR codes have square finder patterns)
                    if 0.8 <= aspect_ratio <= 1.2 and w > 10 and h > 10:
                        squares += 1
            
            # QR codes typically have at least 3 finder patterns (corners)
            # Plus various data modules that appear as squares
            is_qr = squares >= 3
            
            # Additional check: look for high frequency of black/white transitions
            # QR codes have many alternating patterns
            if not is_qr:
                # Count transitions in a central row
                center_row = gray[gray.shape[0] // 2, :]
                transitions = 0
                for i in range(1, len(center_row)):
                    if abs(int(center_row[i]) - int(center_row[i-1])) > 50:
                        transitions += 1
                
                # QR codes have many transitions
                transition_ratio = transitions / len(center_row)
                is_qr = transition_ratio > 0.1
            
            return is_qr
            
        except Exception as e:
            self.logger.error("Error analyzing QR code image", error=str(e))
            return False

    async def _find_qr_in_image(self, image_bytes: bytes) -> Optional[bytes]:
        """Find and extract QR code region from full page image"""
        
        try:
            # Convert to OpenCV format
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                return None
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Try to detect QR codes using specialized detector
            detector = cv2.QRCodeDetector()
            data, points, _ = detector.detectAndDecode(gray)
            
            if points is not None and len(points) > 0:
                # Extract the QR code region
                points = points[0].astype(int)
                
                # Get bounding box
                x = min(points[:, 0])
                y = min(points[:, 1])
                w = max(points[:, 0]) - x
                h = max(points[:, 1]) - y
                
                # Add some padding
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(img.shape[1] - x, w + 2 * padding)
                h = min(img.shape[0] - y, h + 2 * padding)
                
                # Extract region
                qr_region = img[y:y+h, x:x+w]
                
                # Convert back to bytes
                _, buffer = cv2.imencode('.png', qr_region)
                return buffer.tobytes()
                
        except Exception as e:
            self.logger.error("Error finding QR in image", error=str(e))
            
        return None

    def _bytes_to_base64(self, image_bytes: bytes) -> str:
        """Convert image bytes to base64 data URL"""
        
        try:
            # Enhance image quality before encoding
            enhanced_bytes = self._enhance_qr_image(image_bytes)
            
            # Convert to base64
            base64_string = base64.b64encode(enhanced_bytes).decode('utf-8')
            
            # Create data URL
            data_url = f"data:image/png;base64,{base64_string}"
            
            return data_url
            
        except Exception as e:
            self.logger.error("Error converting to base64", error=str(e))
            # Fallback to original bytes
            base64_string = base64.b64encode(image_bytes).decode('utf-8')
            return f"data:image/png;base64,{base64_string}"

    def _enhance_qr_image(self, image_bytes: bytes) -> bytes:
        """Enhance QR code image quality for better readability"""
        
        try:
            # Load image with PIL
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to grayscale for better contrast
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(1.2)
            
            # Resize if too small (for better visibility)
            if image.width < settings.QR_MAX_SIZE:
                scale_factor = min(2.0, settings.QR_MAX_SIZE / image.width)
                new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = io.BytesIO()
            image.save(output, format='PNG', quality=settings.QR_IMAGE_QUALITY)
            return output.getvalue()
            
        except Exception as e:
            self.logger.error("Error enhancing QR image", error=str(e))
            return image_bytes

    async def stream_qr_updates(self, page: Page, webhook_url: Optional[str] = None) -> None:
        """
        Continuously monitor and stream QR code updates
        
        Args:
            page: Playwright page instance
            webhook_url: Custom webhook URL for this job
        """
        
        self.is_capturing = True
        self.logger.info("Starting QR code streaming")
        
        last_qr_data = None
        consecutive_failures = 0
        max_failures = 10
        
        try:
            while self.is_capturing:
                try:
                    # Detect QR code
                    qr_data = await self.detect_qr_code(page)
                    
                    if qr_data:
                        consecutive_failures = 0
                        
                        # Check if QR code has changed
                        if qr_data != last_qr_data:
                            self.capture_count += 1
                            last_qr_data = qr_data
                            self.current_qr_data = qr_data
                            self.qr_detected_at = datetime.utcnow()
                            
                            # Send webhook update
                            await self._send_qr_update(qr_data, webhook_url)
                            
                            self.logger.info("QR code updated", capture_count=self.capture_count)
                        
                    else:
                        consecutive_failures += 1
                        
                        # If we've had too many failures, QR might have expired
                        if consecutive_failures >= max_failures:
                            self.logger.warning("Too many consecutive QR detection failures")
                            
                            # Check if page still has BankID elements
                            bankid_present = await self._check_bankid_page(page)
                            if not bankid_present:
                                self.logger.info("BankID authentication may have completed")
                                break
                    
                    # Wait before next capture - USE BANKID INTERVAL FOR QR CODES!
                    await asyncio.sleep(settings.BANKID_QR_REFRESH_INTERVAL)
                    
                except Exception as e:
                    self.logger.error("Error during QR streaming iteration", error=str(e))
                    consecutive_failures += 1
                    
                    if consecutive_failures >= max_failures:
                        self.logger.error("Too many streaming errors, stopping QR capture")
                        break
                    
                    # Wait before retry
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            self.logger.info("QR streaming cancelled")
        except Exception as e:
            self.logger.error("Fatal error in QR streaming", error=str(e))
        finally:
            self.is_capturing = False
            self.logger.info("QR streaming stopped", total_captures=self.capture_count)

    async def _send_qr_update(self, qr_data: str, webhook_url: Optional[str] = None) -> None:
        """Send QR code update via webhook"""
        
        try:
            # Create update model
            update = QRCodeUpdate(
                job_id=self.job_id,
                user_id=self.user_id,
                qr_code_data=qr_data,
                retry_count=self.retry_count
            )
            
            # Use callback if available
            if self.webhook_callback:
                await self.webhook_callback(update)
            
            # Send to custom webhook URL if provided
            if webhook_url:
                # Import here to avoid circular imports
                from app.utils.notifications import send_webhook
                await send_webhook(webhook_url, update.dict())
                
        except Exception as e:
            self.logger.error("Error sending QR update", error=str(e))

    async def _check_bankid_page(self, page: Page) -> bool:
        """Check if page still shows BankID authentication"""
        
        try:
            # Look for BankID-specific elements
            bankid_selectors = [
                "text='BankID'",
                "text='Legitimering'", 
                "text='Identifiering'",
                ".bankid",
                "#bankid",
                "[data-bankid]"
            ]
            
            for selector in bankid_selectors:
                element = await page.query_selector(selector)
                if element:
                    return True
            
            # Check current URL for BankID indicators
            url = page.url
            if 'bankid' in url.lower() or 'auth' in url.lower():
                return True
                
            return False
            
        except Exception as e:
            self.logger.error("Error checking BankID page", error=str(e))
            return True  # Assume still on BankID page if error

    def stop_streaming(self) -> None:
        """Stop QR code streaming"""
        self.is_capturing = False
        self.logger.info("QR streaming stop requested")

    def get_current_qr_data(self) -> Optional[str]:
        """Get the most recent QR code data"""
        return self.current_qr_data

    def get_capture_stats(self) -> Dict[str, Any]:
        """Get QR capture statistics"""
        return {
            "capture_count": self.capture_count,
            "retry_count": self.retry_count,
            "is_capturing": self.is_capturing,
            "last_detected_at": self.qr_detected_at.isoformat() if self.qr_detected_at else None
        } 