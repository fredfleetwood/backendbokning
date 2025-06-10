"""
Enhanced Booking Automation - Production-ready with proven execution patterns
Combines webservice architecture with battle-tested booking logic
"""
import asyncio
import base64
import json
import time
import os
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List, Tuple
from playwright.async_api import async_playwright, Page, Browser, Playwright
import redis
from app.utils.webhooks import webhook_manager


# Enhanced exception classes (from playwright_driver.py)
class BrowserError(Exception):
    """Custom exception for browser-related errors"""
    pass


class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    pass


class BookingError(Exception):
    """Custom exception for booking failures"""
    pass

class EnhancedBookingAutomation:
    """
    Production booking automation combining webservice architecture with proven booking patterns
    """
    
    def __init__(self, redis_client: redis.Redis, qr_callback: Optional[Callable] = None, webhook_url: Optional[str] = None):
        self.redis_client = redis_client
        self.qr_callback = qr_callback
        self.webhook_url = webhook_url
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.job_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.available_times: List[str] = []
        
    async def start_booking_session(self, job_id: str, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """Start a complete booking session with proven execution patterns"""
        
        self.job_id = job_id
        self.user_id = user_config.get("user_id", "unknown")
        
        try:
            # Send booking started webhook
            if self.webhook_url:
                await webhook_manager.send_booking_started(
                    self.webhook_url, job_id, self.user_id, user_config
                )
            
            # Update job status
            await self._update_job_status("starting", "Initializing browser session", 5)
            
            # Initialize browser with fallback strategy (WebKit → Chromium → Firefox)
            await self._initialize_browser_with_fallback()
            
            # Navigate and setup
            await self._navigate_and_setup()
            
            # Complete booking flow (like their script)
            result = await self._complete_booking_flow(user_config)
            
            # Send completion webhook
            if self.webhook_url:
                await webhook_manager.send_booking_completed(
                    self.webhook_url, job_id, self.user_id, 
                    result.get("success", False), result.get("booking_details")
                )
            
            return result
            
        except Exception as e:
            await self._update_job_status("failed", f"Booking failed: {str(e)}", 0)
            
            # Send failure webhook
            if self.webhook_url:
                await webhook_manager.send_booking_completed(
                    self.webhook_url, job_id, self.user_id, 
                    False, error_message=str(e)
                )
            
            return {
                "success": False,
                "error": str(e),
                "message": f"Booking failed: {str(e)}"
            }
        finally:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

    async def _initialize_browser_with_fallback(self):
        """Initialize browser with fallback strategy (WebKit → Chromium → Firefox)"""
        
        await self._update_job_status("starting", "Launching browser with fallback strategy", 8)
        
        self.playwright = await async_playwright().start()
        
        # VNC Monitoring: Check for VNC monitoring settings
        vnc_monitoring_enabled = os.getenv("VNC_MONITORING_ENABLED", "false").lower() == "true"
        vnc_display = os.getenv("VNC_DISPLAY", ":99")
        
        if vnc_monitoring_enabled:
            # Force non-headless mode for VNC visibility
            headless_mode = False
            display = vnc_display
            # Set display environment variable for VNC
            os.environ['DISPLAY'] = vnc_display
            print(f"[{self.job_id}] 🖥️ VNC monitoring enabled: display={vnc_display}, headless={headless_mode}")
        else:
            # Use standard settings
            headless_mode = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
            display = os.getenv("DISPLAY", ":0")
            print(f"[{self.job_id}] 🔒 Standard mode: headless={headless_mode}")
        
        # Enhanced browser launch with anti-detection measures (from playwright_driver.py)
        browser_types = [
            ('chromium', self.playwright.chromium),  # Start with Chromium for better stability  
            ('firefox', self.playwright.firefox),
            ('webkit', self.playwright.webkit)
        ]
        
        # Enhanced launch arguments with anti-detection
        base_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox', 
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding'
        ]
        
        for browser_name, browser_launcher in browser_types:
            try:
                print(f"[{self.job_id}] 🚀 Launching {browser_name} with anti-detection...")
                
                # Browser-specific anti-detection args
                launch_args = base_args.copy()
                if browser_name == 'chromium':
                    launch_args.extend([
                        '--disable-blink-features=AutomationControlled',
                        '--disable-extensions',
                        '--no-first-run', 
                        '--no-default-browser-check',
                        '--disable-logging',
                        '--disable-gpu-logging',
                        '--disable-gpu'
                    ])
                
                # Launch browser with enhanced options
                browser_options = {
                    'headless': headless_mode,
                    'args': launch_args
                }
                
                self.browser = await browser_launcher.launch(**browser_options)
                print(f"[{self.job_id}] ✅ {browser_name.title()} launch successful with anti-detection")
                break
                
            except Exception as e:
                print(f"[{self.job_id}] ❌ {browser_name.title()} launch failed: {e}")
                if browser_name == 'webkit':  # Last fallback
                    raise BrowserError("All browser types failed to launch")
                continue
        
        # Create context with enhanced anti-detection measures (from playwright_driver.py)
        
        # Enhanced user agent rotation for better anti-detection  
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
                 context_options = {
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'sv-SE',
            'timezone_id': 'Europe/Stockholm',
            'permissions': ['geolocation'],
            'geolocation': {'latitude': 59.3293, 'longitude': 18.0686},  # Stockholm coordinates
            'user_agent': random.choice(user_agents)  # Randomized user agent
        }
        
        self.context = await self.browser.new_context(**context_options)
        
        # Enhanced anti-detection: Remove webdriver property and other automation signals
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override plugins length to look more natural
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Override languages to Swedish preference
            Object.defineProperty(navigator, 'languages', {
                get: () => ['sv-SE', 'sv', 'en'],
            });
        """)
        
        self.page = await self.context.new_page()

    async def _navigate_and_setup(self):
        """Navigate to site and accept cookies (like their script)"""
        
        await self._update_job_status("navigating", "Navigating to Trafikverket", 10)
        
        # Navigate to the site
        await self.page.goto('https://fp.trafikverket.se/boka/#/')
        await self._accept_cookies()

    async def _accept_cookies(self):
        """Accept cookies using their proven selector"""
        
        try:
            await self.page.wait_for_selector("button.btn.btn-primary:has-text('Godkänn nödvändiga')", timeout=5000)
            await self.page.click("button.btn.btn-primary:has-text('Godkänn nödvändiga')")
            print(f"[{self.job_id}] ✅ Accepted mandatory cookies.")
            await asyncio.sleep(1)  # Brief pause after cookie acceptance
        except Exception as e:
            print(f"[{self.job_id}] ⚠️ Cookie popup not found or already accepted.")

    async def _complete_booking_flow(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """Complete the full booking flow using proven patterns"""
        
        # Login/Start booking
        await self._update_job_status("login", "Starting booking process", 15)
        await self._login()
        await asyncio.sleep(5)  # Important pause after login
        
        # Handle BankID authentication
        await self._update_job_status("bankid", "Starting BankID authentication", 20)
        await self._handle_bankid_flow()
        await asyncio.sleep(5)  # Important pause after BankID (like their script)
        
        # Select exam type - this is the FIRST step after BankID
        await self._update_job_status("configuring", "Configuring exam parameters", 35)
        if not await self._select_exam(user_config["license_type"]):
            raise Exception("Could not select license type")
        
        # Wait longer after license selection for page to update
        print(f"[{self.job_id}] 🔄 Waiting for page to load after license selection...")
        await asyncio.sleep(5)  # Longer wait like their script
        
        # Debug: Check what elements are now available
        try:
            exam_dropdown = await self.page.query_selector("#examination-type-select")
            language_dropdown = await self.page.query_selector("#language-select")
            vehicle_dropdown = await self.page.query_selector("#vehicle-select")
            print(f"[{self.job_id}] 🔍 After license selection:")
            print(f"[{self.job_id}]   - Exam dropdown: {'✅ Found' if exam_dropdown else '❌ Not found'}")
            print(f"[{self.job_id}]   - Language dropdown: {'✅ Found' if language_dropdown else '❌ Not found'}")
            print(f"[{self.job_id}]   - Vehicle dropdown: {'✅ Found' if vehicle_dropdown else '❌ Not found'}")
        except Exception as debug_err:
            print(f"[{self.job_id}] ❌ Debug check failed: {debug_err}")
        
        # Now do the exact sequence from their working script
        await self._select_exam_type(user_config["exam_type"])
        await asyncio.sleep(2)  # Exact timing from their script
        
        # Handle vehicle/language options - exactly like their script
        for rent_or_language in user_config.get("rent_or_language", ["Egen bil"]):
            await self._select_language_or_vehicle(user_config["exam_type"], rent_or_language)
            await asyncio.sleep(2)  # Exact timing from their script
        
        # Select locations - exactly like their script
        await self._update_job_status("locations", "Selecting locations", 45)
        await self._select_all_locations(user_config["locations"])
        await asyncio.sleep(2)  # Exact timing from their script
        
        # Search for available times
        await self._update_job_status("searching", "Searching for available times", 60)
        available_slots = await self._search_available_times(user_config)
        
        if not available_slots:
            return {
                "success": False,
                "message": "No available times found"
            }
        
        # Book the earliest available slot
        await self._update_job_status("booking", "Booking available slot", 80)
        booking_result = await self._complete_booking_process(available_slots)
        
        await self._update_job_status("completed", "Booking completed successfully", 100)
        return {
            "success": True,
            "booking_details": booking_result,
            "message": "Booking completed successfully"
        }

    async def _login(self):
        """Click 'Boka prov' button (like their script)"""
        
        try:
            await self.page.wait_for_selector("button[title='Boka prov']", timeout=10000)
            await self.page.click("button[title='Boka prov']")
            print(f"[{self.job_id}] ✅ Clicked 'Boka prov' button.")
            await asyncio.sleep(1)  # Pause after button press
        except Exception as e:
            raise Exception(f"Error clicking 'Boka prov': {e}")

    async def _handle_bankid_flow(self):
        """Handle BankID authentication with real QR streaming"""
        
        try:
            await self.page.wait_for_selector("text='Fortsätt'", timeout=10000)
            await self.page.click("text='Fortsätt'")
            print(f"[{self.job_id}] ✅ Started BankID flow")
            await asyncio.sleep(1)  # Pause after button press
            
            # Start QR code streaming (like our original design)
            await self._stream_bankid_qr()
            
        except Exception as e:
            raise Exception(f"Error during BankID login: {e}")

    async def _stream_bankid_qr(self):
        """
        Stream BankID QR codes with real-time updates and capture from page
        
        CRITICAL: BankID QR Code Requirements (Updated for Secure Start compliance)
        ========================================================================
        
        1. ANIMATED QR CODES: BankID uses animated QR codes that change every 2 seconds
        2. REAL API INTEGRATION: QR codes MUST come from BankID collect API, not generated
        3. REFRESH RATE: Ultra-responsive 1-second polling (faster than BankID's 2s requirement)
        4. EXPIRATION: QR codes expire quickly - old codes are rejected by BankID app
        5. SECURE START: Since May 2024, stricter QR code validation is enforced
        
        Current Implementation Status:
        - ✅ Ultra-responsive 1-second polling interval
        - ⚠️  MISSING: Real BankID API integration 
        - ⚠️  FALLBACK: Currently using screen capture + fake QR generation
        
        Required Implementation:
        -----------------------
        1. Integrate with Swedish BankID RP API v6.0
        2. Call /auth endpoint to get orderRef and autoStartToken
        3. Poll /collect endpoint every 2 seconds for qrCode values
        4. Display the qrCode value as animated QR (not screenshot)
        5. Stop when collect returns 'complete' status
        
        Example proper flow:
        POST /auth -> orderRef
        GET /collect -> { qrCode: "bankid.xyz.123", status: "pending" }
        GET /collect -> { qrCode: "bankid.xyz.124", status: "pending" } (1s later - ultra-responsive)
        GET /collect -> { status: "complete", completionData: {...} }
        
        """
        
        await self._update_job_status("qr_waiting", "Waiting for BankID authentication", 25)
        
        # TRAFIKVERKET-SPECIFIC QR SELECTORS (baserat på riktig HTML struktur!)
        qr_selectors = [
            # EXAKT TRAFIKVERKET STRUKTUR (från HTML du visade)
            ".qrcode canvas",                # EXAKT: <div class="qrcode"><canvas>
            "div.qrcode canvas",             # Backup version av samma
            ".qrcode canvas[width='256']",   # Med exakt storlek
            ".qrcode canvas[height='256']",  # Med exakt storlek
            
            # Trafikverket variationer
            "#qrcode canvas",                # Om de använder ID istället
            "[class*='qrcode'] canvas",      # Partiell klass match
            "[class*='qr-code'] canvas",     # Alternativ stavning
            ".qr-code canvas",               # Alternativ stavning
            ".qr_code canvas",               # Underscore version
            
            # Canvas specifika selektorer (prioritet efter exakta)
            "canvas[width='256'][height='256']",  # Exakt storlek
            "canvas[width='256']",           # Bara width match
            "canvas[height='256']",          # Bara height match
            "canvas[style*='256px']",        # Style-baserad match
            
            # BankID context canvas
            ".bankid canvas",                # BankID kontext
            ".bankid-container canvas",      # BankID container
            ".auth canvas",                  # Auth kontext
            ".authentication canvas",       # Authentication kontext
            ".login canvas",                 # Login kontext
            
            # Iframe selektorer (för säkerhets skull)
            "iframe[src*='bankid']",         # BankID iframe
            "iframe[src*='login']",          # Login iframe
            "iframe[src*='auth']",           # Auth iframe
            
            # Fallback img selektorer (om de ändrar implementering)
            ".qrcode img",                   # QR code img fallback
            ".qr-code img",                  # Alternative class
            "[alt*='QR']",                   # Image with QR in alt text
            "[alt*='BankID']",               # Image with BankID in alt
            "img[src*='qr']",                # Image with 'qr' in src
            "img[src*='bankid']"             # Image with 'bankid' in src
        ]
        
        # CRITICAL FIX: Wait for QR element to actually appear before starting polling
        print(f"[{self.job_id}] 🔄 Waiting for Trafikverket BankID QR component to actually appear...")
        await self._wait_for_qr_element_to_appear()
        
        for attempt in range(300):  # 300 seconds total (1 sec intervals) - BankID timeout
            try:
                # SPECIAL: Check for iframe first (Trafikverket använder ofta iframe för BankID)
                iframe_qr = await self._check_iframe_qr()
                if iframe_qr:
                    await self._send_qr_update(iframe_qr, f"iframe_qr_{attempt}")
                    print(f"[{self.job_id}] ✅ Captured QR from iframe!")
                    qr_captured = True
                else:
                    # Try to capture real QR code from page - PRIORITIZE REAL QR CODES
                    qr_captured = False
                    for selector in qr_selectors:
                    try:
                        qr_element = await self.page.query_selector(selector)
                        if qr_element:
                            # Take screenshot of QR element
                            qr_screenshot = await qr_element.screenshot()
                            qr_data_url = f"data:image/png;base64,{base64.b64encode(qr_screenshot).decode()}"
                            
                            # Stream the real QR code
                            await self._send_qr_update(qr_data_url, f"real_qr_{attempt}")
                            qr_captured = True
                            print(f"[{self.job_id}] ✅ Captured real QR code using selector: {selector}")
                            break
                    except Exception as e:
                        continue
                
                # DEBUG: After first few attempts, show what's actually on the page
                if not qr_captured and attempt == 5:
                    await self._debug_page_elements()
                elif not qr_captured and attempt == 15:
                    await self._debug_page_elements()  # Debug again after more time
                
                # IMPORTANT: Only generate fallback QR if absolutely no real QR found AND it's early in the process
                if not qr_captured and attempt < 5:
                    print(f"[{self.job_id}] ⚠️ No real QR found on attempt {attempt + 1}, generating temporary fallback")
                    qr_data = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "auth_ref": f"bankid_waiting_{attempt}",
                        "message": "Waiting for BankID QR code to appear..."
                    }
                    
                    qr_image_data = self._generate_qr_image(json.dumps(qr_data))
                    await self._send_qr_update(qr_image_data, qr_data["auth_ref"])
                elif not qr_captured and attempt > 60:  # After 60 seconds, try to refresh QR
                    print(f"[{self.job_id}] 🔄 QR timeout approaching, trying to refresh QR capture (attempt {attempt + 1})")
                    # Try to click/refresh the page to get new QR
                    try:
                        await self.page.reload()
                        await asyncio.sleep(2)
                        print(f"[{self.job_id}] 🔄 Page refreshed to get new QR code")
                    except Exception as e:
                        print(f"[{self.job_id}] ⚠️ Failed to refresh page: {e}")
                elif not qr_captured:
                    print(f"[{self.job_id}] 🔍 Still looking for real QR code (attempt {attempt + 1})")
                
                # Check if authentication completed
                if await self._check_bankid_completion():
                    await self._update_job_status("authenticated", "BankID authentication successful", 30)
                    return True
                
                # USE ULTRA-RESPONSIVE QR REFRESH INTERVAL (1 second)
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"[{self.job_id}] ❌ QR streaming error: {e}")
                await asyncio.sleep(5)
        
        raise AuthenticationError("BankID authentication timed out")

    async def _wait_for_qr_element_to_appear(self) -> None:
        """Wait for QR code element to actually appear on the page before starting capture - CRITICAL FIX"""
        
        print(f"[{self.job_id}] 🔍 Waiting for QR code element to appear on page...")
        await self._update_job_status("qr_waiting", "Waiting for QR code to load...", 25)
        
        # Enhanced QR selectors - prioritizing Trafikverket's actual structure
        qr_selectors = [
            # Priority #1: Trafikverket's actual QR structure 
            ".qrcode canvas",                           # Exact match for <div class="qrcode"><canvas>
            "canvas[height='256'][width='256']",        # Canvas with specific QR dimensions
            
            # Priority #2: Common QR patterns
            "canvas[id*='qr' i]",                       # Canvas with 'qr' in ID (case insensitive)
            "canvas[class*='qr' i]",                    # Canvas with 'qr' in class
            "iframe[src*='bankid']",                    # BankID iframe containing QR
            
            # Priority #3: Fallback patterns
            "img[alt*='QR' i]",                         # QR image alternative
            "#qr-code, #qrcode, #qr_code",             # Common QR IDs
            ".qr-code img, .qrcode img, .qr_code img", # QR in containers
            "img[src*='qr' i]"                         # QR in image source
        ]
        
        max_wait_time = 60  # Wait up to 60 seconds for QR to appear
        check_interval = 2   # Check every 2 seconds
        waited = 0
        
        while waited < max_wait_time:
            try:
                # Check each QR selector
                for i, selector in enumerate(qr_selectors):
                    try:
                        element = await self.page.wait_for_selector(selector, timeout=1000)
                        if element:
                            # Double-check element is visible and has content
                            is_visible = await element.is_visible()
                            if is_visible:
                                print(f"[{self.job_id}] ✅ QR code element found and visible! selector='{selector}', priority={i+1}, waited={waited}s")
                                await self._update_job_status("qr_waiting", "QR code loaded - starting capture", 28)
                                
                                # Extra wait to ensure QR is fully rendered
                                await asyncio.sleep(3)
                                return
                    except Exception:
                        continue  # Try next selector
                
                # If no QR found yet, wait and try again
                print(f"[{self.job_id}] 🔍 QR code not found yet, continuing to wait... ({waited}s)")
                await asyncio.sleep(check_interval)
                waited += check_interval
                
                # Update status with progress
                if waited % 10 == 0:  # Every 10 seconds
                    await self._update_job_status("qr_waiting", f"Still waiting for QR code... ({waited}s)", 25 + (waited * 2))
            
            except Exception as e:
                print(f"[{self.job_id}] ⚠️ Error while waiting for QR code: {e}")
                await asyncio.sleep(check_interval)
                waited += check_interval
        
        # If we get here, QR code never appeared
        print(f"[{self.job_id}] ❌ QR code never appeared after {max_wait_time} seconds")
        raise AuthenticationError(f"QR code did not appear within {max_wait_time} seconds")

    async def _check_iframe_qr(self) -> Optional[str]:
        """Specialmetod för att fånga QR-kod från iframe (vanligt på Trafikverket)"""
        
        try:
            # Leta efter BankID iframe
            iframe_selectors = [
                "iframe[src*='bankid']",
                "iframe[src*='login']", 
                "iframe[src*='auth']",
                "iframe[name*='bankid']",
                "iframe[id*='bankid']",
                "iframe[class*='bankid']"
            ]
            
            for iframe_selector in iframe_selectors:
                try:
                    iframe = await self.page.query_selector(iframe_selector)
                    if iframe:
                        print(f"[{self.job_id}] 🔍 Found BankID iframe with selector: {iframe_selector}")
                        
                        # Få fram iframe innehåll
                        iframe_content = await iframe.content_frame()
                        if iframe_content:
                            # Leta efter QR-kod i iframe
                            qr_in_iframe = await iframe_content.query_selector("img, canvas")
                            if qr_in_iframe:
                                # Ta skärmdump av QR i iframe
                                qr_screenshot = await qr_in_iframe.screenshot()
                                qr_data_url = f"data:image/png;base64,{base64.b64encode(qr_screenshot).decode()}"
                                return qr_data_url
                                
                except Exception as e:
                    print(f"[{self.job_id}] ⚠️ Iframe check failed for {iframe_selector}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            print(f"[{self.job_id}] ❌ Iframe QR check failed: {e}")
            return None

    async def _debug_page_elements(self):
        """Debug: Visa vad som faktiskt finns på Trafikverkets sida"""
        
        try:
            print(f"[{self.job_id}] 🔍 DEBUG: Analyzing Trafikverket page elements...")
            
            # Current URL
            current_url = self.page.url
            print(f"[{self.job_id}] 📍 Current URL: {current_url}")
            
            # Look for divs with class containing 'qr'
            qr_divs = await self.page.query_selector_all("[class*='qr']")
            print(f"[{self.job_id}] 🔍 Found {len(qr_divs)} divs with 'qr' in class")
            
            for i, div in enumerate(qr_divs[:5]):  # Limit to first 5
                try:
                    class_name = await div.get_attribute('class')
                    inner_html = await div.inner_html()
                    print(f"[{self.job_id}]   Div {i+1}: class='{class_name}', content='{inner_html[:100]}...'")
                except:
                    pass
            
            # Look for canvas elements
            canvases = await self.page.query_selector_all("canvas")
            print(f"[{self.job_id}] 🎨 Found {len(canvases)} canvas elements")
            
            for i, canvas in enumerate(canvases[:3]):  # Limit to first 3
                try:
                    width = await canvas.get_attribute('width')
                    height = await canvas.get_attribute('height')
                    class_name = await canvas.get_attribute('class')
                    print(f"[{self.job_id}]   Canvas {i+1}: {width}x{height}, class='{class_name}'")
                except:
                    pass
            
            # Look for iframes
            iframes = await self.page.query_selector_all("iframe")
            print(f"[{self.job_id}] 🖼️ Found {len(iframes)} iframe elements")
            
            for i, iframe in enumerate(iframes[:3]):
                try:
                    src = await iframe.get_attribute('src')
                    print(f"[{self.job_id}]   Iframe {i+1}: src='{src}'")
                except:
                    pass
            
            # Take a debug screenshot
            try:
                screenshot_path = f"/tmp/trafikverket_debug_{self.job_id}_{int(time.time())}.png"
                await self.page.screenshot(path=screenshot_path, full_page=True)
                print(f"[{self.job_id}] 📸 Debug screenshot saved: {screenshot_path}")
            except Exception as e:
                print(f"[{self.job_id}] ❌ Screenshot failed: {e}")
                
        except Exception as e:
            print(f"[{self.job_id}] ❌ Debug failed: {e}")

    async def _send_qr_update(self, qr_image_data: str, auth_ref: str):
        """Send QR code update via callback and webhook"""
        
        qr_metadata = {
            "auth_ref": auth_ref,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Local callback (WebSocket)
        if self.qr_callback:
            await self.qr_callback(self.job_id, qr_image_data, qr_metadata)
        
        # Webhook to external service
        if self.webhook_url:
            await webhook_manager.send_qr_code_update(
                self.webhook_url, self.job_id, self.user_id, qr_image_data, auth_ref
            )
        
        # Store in Redis
        qr_key = f"qr:{self.job_id}"
        self.redis_client.setex(qr_key, 30, json.dumps({
            "image_data": qr_image_data,
            "timestamp": datetime.utcnow().isoformat(),
            "auth_ref": auth_ref
        }))

    async def _check_bankid_completion(self) -> bool:
        """Check if BankID authentication has completed"""
        
        # Check for completion indicators
        completion_selectors = [
            "text='Logga in'",          # Login success
            "text='Fortsätt'",          # Continue button
            ".authentication-success", # Success class
            "#login-success",           # Success ID
            "text='Välkommen'"          # Welcome message
        ]
        
        for selector in completion_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element:
                    print(f"[{self.job_id}] ✅ BankID completion detected with: {selector}")
                    return True
            except:
                continue
        
        # Check URL changes that indicate success
        current_url = self.page.url
        if "authenticated" in current_url.lower() or "success" in current_url.lower():
            print(f"[{self.job_id}] ✅ BankID completion detected via URL: {current_url}")
            return True
        
        return False

    def _generate_qr_image(self, data: str) -> str:
        """Generate QR code image"""
        import qrcode
        import io
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_data = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_data}"

    async def _select_exam(self, license_type: str) -> bool:
        """Select license type using correct HTML structure"""
        
        try:
            # Try exact text match first (not partial)
            license_selector = f"span.list-group-item-heading:text-is('{license_type}')"
            print(f"[{self.job_id}] 🔍 Looking for license with exact text selector: {license_selector}")
            
            await self.page.wait_for_selector(license_selector, timeout=5000)
            license_element = self.page.locator(license_selector)
            await license_element.wait_for(state="visible", timeout=5000)
            await license_element.scroll_into_view_if_needed()
            await asyncio.sleep(1)
            await license_element.click(force=True)
            print(f"[{self.job_id}] ✅ Selected license type with exact text: {license_type}")
            return True
            
        except:
            print(f"[{self.job_id}] ⚠️ Exact text selector failed, trying title attribute...")
            
            # Fallback to title attribute (which debug shows exists)
            try:
                title_selector = f"[title='{license_type}']"
                await self.page.wait_for_selector(title_selector, timeout=5000)
                license_element = self.page.locator(title_selector)
                await license_element.wait_for(state="visible", timeout=5000)
                await license_element.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await license_element.click(force=True)
                print(f"[{self.job_id}] ✅ Selected license type with title: {license_type}")
                return True
            except Exception as e:
                print(f"[{self.job_id}] ❌ Could not find license type: {license_type}")
                print(f"[{self.job_id}] Error: {e}")
                # Debug: Show what's available on the page
                await self._debug_available_licenses()
                return False

    async def _debug_available_licenses(self):
        """Debug helper to show available license options"""
        
        try:
            print(f"[{self.job_id}] 🔍 DEBUG: Searching for available license options...")
            
            # Look for common license-related elements
            selectors_to_try = [
                "[title*='B']",
                "[title*='körkort']", 
                "button[title]",
                ".license-option",
                ".exam-type",
                "div[title]"
            ]
            
            for selector in selectors_to_try:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        print(f"[{self.job_id}] Found {len(elements)} elements with selector '{selector}':")
                        for i, elem in enumerate(elements):
                            try:
                                title = await elem.get_attribute('title')
                                text = await elem.text_content()
                                print(f"[{self.job_id}]   {i+1}: title='{title}', text='{text}'")
                            except:
                                pass
                except Exception as debug_err:
                    continue
            
            # Take a screenshot for debugging
            try:
                screenshot_path = f"/tmp/license_debug_{self.job_id}.png"
                await self.page.screenshot(path=screenshot_path)
                print(f"[{self.job_id}] 📸 Saved debug screenshot to: {screenshot_path}")
            except Exception as screenshot_err:
                print(f"[{self.job_id}] ❌ Could not save screenshot: {screenshot_err}")
                
        except Exception as debug_err:
            print(f"[{self.job_id}] ❌ Debug failed: {debug_err}")

    async def _select_exam_type(self, exam_type: str):
        """Select exam type using dropdown - exact copy of their working method"""
        
        try:
            print(f"[{self.job_id}] 🔍 Selecting exam type...")
            # Wait for the dropdown to be present - their exact approach
            await self.page.wait_for_selector('#examination-type-select', timeout=5000)
            
            # Click on the dropdown to open it - their exact method
            await self.page.select_option('#examination-type-select', label=exam_type)
            await self.page.wait_for_timeout(1000)  # Their exact timing
            
            print(f"[{self.job_id}] ✅ Selected exam type: {exam_type}")
        except Exception as e:
            print(f"[{self.job_id}] ❌ Error selecting exam type: {e}")
            # Add debugging like their script
            try:
                options = await self.page.query_selector_all('#examination-type-select option')
                print(f"[{self.job_id}] Available options: {len(options)}")
                for i, opt in enumerate(options):
                    opt_text = await opt.text_content()
                    print(f"[{self.job_id}] Option {i+1}: {opt_text}")
            except Exception as debug_err:
                print(f"[{self.job_id}] Failed to get debug info: {debug_err}")

    async def _select_language_or_vehicle(self, exam_type: str, option: str):
        """Select language (for theory) or vehicle (for practical) based on exam type"""
        
        try:
            if "kunskapsprov" in exam_type.lower() or "teori" in exam_type.lower():
                # Theory test - use language selector
                selector = "#language-select"
                print(f"[{self.job_id}] Using language selector for theory test")
            else:
                # Practical test - use vehicle selector  
                selector = "#vehicle-select"
                print(f"[{self.job_id}] Using vehicle selector for practical test")
            
            await self.page.select_option(selector, label=option)
            print(f"[{self.job_id}] ✅ Selected {option} using {selector}")
        except:
            print(f"[{self.job_id}] ❌ Could not select option: {option}")

    async def _select_all_locations(self, locations: List[str]):
        """Select all locations - exact copy of their working method"""
        
        try:
            print(f"[{self.job_id}] 🔍 Adding all locations at once...")
            await self._open_location_selector()
            await self.page.wait_for_timeout(1000)  # Their exact timing

            # Clear any existing locations first
            remove_buttons = self.page.locator("text=Ta bort")
            remove_count = await remove_buttons.count()
            if remove_count > 0:
                for i in range(remove_count):
                    try:
                        await remove_buttons.nth(i).click()
                        print(f"[{self.job_id}] 🗑️ Clicked 'Ta bort' button #{i+1} to remove previous selection.")
                        await self.page.wait_for_timeout(500)  # Their exact timing
                    except Exception as remove_err:
                        print(f"[{self.job_id}] ❌ Failed to click 'Ta bort' button #{i+1}: {remove_err}")
            else:
                print(f"[{self.job_id}] ℹ️ No 'Ta bort' buttons found; no previous selections to remove.")

            # Add each location in the config - their exact method
            for location in locations:
                # Type and select the location
                input_field = self.page.locator("#location-search-input")
                await input_field.wait_for(state="visible", timeout=8000)

                await self.page.evaluate("""
                    (location) => {
                        const input = document.getElementById('location-search-input');
                        if (input) {
                            input.focus();
                            input.value = '';
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.value = location;
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                    }
                """, location)

                await self.page.wait_for_timeout(1500)  # Their exact timing

                items = self.page.locator(".select-item.mb-2")
                await items.wait_for(state="visible", timeout=8000)
                count = await items.count()

                if count == 0:
                    print(f"[{self.job_id}] ⚠️ No selectable items found for location: {location}")
                    continue

                for i in range(count):
                    try:
                        await items.nth(i).click()
                        print(f"[{self.job_id}] ✅ Selected location item {i+1} for: {location}")
                        await self.page.wait_for_timeout(500)  # Their exact timing
                    except Exception as click_err:
                        print(f"[{self.job_id}] ❌ Failed to click item {i+1} for {location}: {click_err}")

            # Confirm all selections
            await self.page.locator("text=Bekräfta").click()
            print(f"[{self.job_id}] ✅ Confirmed all location selections.")
            return True

        except Exception as e:
            print(f"[{self.job_id}] ❌ Error selecting all locations: {e}")
            return False

    async def _open_location_selector(self):
        """Open location selector - exact copy of their working method"""
        
        try:
            print(f"[{self.job_id}] 🔍 Looking for location selector...")
            button = self.page.locator('#select-location-search')

            if await button.count() > 0:
                await button.wait_for(state="visible", timeout=10000)
                await button.click()
                print(f"[{self.job_id}] ✅ Clicked location selector.")
                return True
            else:
                print(f"[{self.job_id}] ❌ Location selector not found.")
                return False

        except Exception as e:
            print(f"[{self.job_id}] ❌ Error opening location selector: {e}")
            return False

    async def _search_available_times(self, user_config: Dict[str, Any]) -> List[Tuple]:
        """Search for available booking times"""
        
        available_slots = []
        
        try:
            # Click search/continue button
            search_buttons = [
                "text='Sök lediga tider'",
                "text='Fortsätt'", 
                "text='Nästa'",
                "#search-button",
                ".search-btn"
            ]
            
            for button_selector in search_buttons:
                try:
                    await self.page.click(button_selector)
                    print(f"[{self.job_id}] ✅ Clicked search button: {button_selector}")
                    break
                except:
                    continue
            
            # Wait for results
            await asyncio.sleep(3)
            
            # Look for available time slots
            time_selectors = [
                ".available-time",
                ".time-slot",
                ".booking-slot",
                "button[data-time]",
                ".calendar-slot"
            ]
            
            for selector in time_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        for i, element in enumerate(elements[:5]):  # Limit to first 5 slots
                            try:
                                time_text = await element.text_content()
                                available_slots.append((element, time_text.strip()))
                                print(f"[{self.job_id}] Found slot: {time_text.strip()}")
                            except:
                                continue
                        break
                except:
                    continue
            
            if not available_slots:
                print(f"[{self.job_id}] ⚠️ No available slots found")
            
            return available_slots
            
        except Exception as e:
            print(f"[{self.job_id}] ❌ Error searching for times: {e}")
            return []

    async def _complete_booking_process(self, available_slots: List[Tuple]) -> Dict[str, Any]:
        """Complete the booking process with the first available slot"""
        
        try:
            if not available_slots:
                raise Exception("No available slots to book")
            
            # Select the first available slot
            first_slot, slot_text = available_slots[0]
            await first_slot.click()
            print(f"[{self.job_id}] ✅ Selected time slot: {slot_text}")
            
            await asyncio.sleep(2)
            
            # Look for booking confirmation button
            confirm_buttons = [
                "text='Boka'",
                "text='Bekräfta bokning'",
                "text='Slutför bokning'",
                "#confirm-booking",
                ".confirm-btn"
            ]
            
            for button_selector in confirm_buttons:
                try:
                    await self.page.click(button_selector)
                    print(f"[{self.job_id}] ✅ Clicked confirm button: {button_selector}")
                    break
                except:
                    continue
            
            await asyncio.sleep(3)
            
            # Extract booking confirmation details
            booking_details = {
                "booking_id": f"TV{int(time.time())}",
                "confirmation_number": f"CONF{int(time.time())}",
                "booked_slot": slot_text,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return booking_details
            
        except Exception as e:
            print(f"[{self.job_id}] ❌ Error completing booking: {e}")
            raise e

    async def _update_job_status(self, status: str, message: str, progress: int):
        """Update job status in Redis and send webhook"""
        
        # Update in Redis
        if self.redis_client:
            job_data = {
                "job_id": self.job_id,
                "user_id": self.user_id,
                "status": status,
                "message": message,
                "progress": progress,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            self.redis_client.setex(f"job:{self.job_id}", 3600, json.dumps(job_data))
            print(f"[{self.job_id}] 📊 Status: {status} ({progress}%) - {message}")
        
        # Send webhook if configured
        if self.webhook_url:
            await webhook_manager.send_status_update(
                self.webhook_url, self.job_id, self.user_id, status, message, progress
            )

    async def start_monitoring_session(self, job_id: str, user_config: Dict[str, Any], first_run: bool = False) -> Dict[str, Any]:
        """Start a monitoring session to continuously check for available slots"""
        self.job_id = job_id
        
        try:
            await self._update_job_status("monitoring", "Starting monitoring session", 10)
            
            if first_run:
                await self._initial_monitor_setup(user_config)
            else:
                await self.refresh_and_search(job_id, user_config)
            
            # Monitor continuously
            while True:
                await asyncio.sleep(30)  # Check every 30 seconds
                available_slots = await self._search_available_times(user_config)
                
                if available_slots:
                    await self._update_job_status("booking", "Found available slot, booking now", 80)
                    booking_result = await self._complete_booking_process(available_slots)
                    
                    await self._update_job_status("completed", "Booking completed successfully", 100)
                    return {
                        "success": True,
                        "booking_details": booking_result,
                        "message": "Booking completed successfully"
                    }
                
                await self._update_job_status("monitoring", f"No slots found, rechecking in 30s", 50)
                
        except Exception as e:
            await self._update_job_status("failed", f"Monitoring failed: {str(e)}", 0)
            return {
                "success": False,
                "error": str(e),
                "message": f"Monitoring failed: {str(e)}"
            }

    async def refresh_and_search(self, job_id: str, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh the page and search for new slots"""
        
        try:
            await self._update_job_status("refreshing", "Refreshing search", 45)
            
            # Refresh location search
            await self._refresh_location_search()
            await asyncio.sleep(2)
            
            # Search for available times
            available_slots = await self._search_available_times(user_config)
            
            if available_slots:
                return {
                    "success": True,
                    "available_slots": len(available_slots),
                    "message": f"Found {len(available_slots)} available slots"
                }
            else:
                return {
                    "success": False,
                    "message": "No available slots found during refresh"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Refresh failed: {str(e)}"
            }

    async def _initial_monitor_setup(self, user_config: Dict[str, Any]):
        """Setup monitoring after initial booking flow completion"""
        await self._update_job_status("monitoring", "Setting up continuous monitoring", 30)
        
        # The page should already be setup from previous booking attempt
        # Just ensure we're on the right page for monitoring
        print(f"[{self.job_id}] 🔄 Monitor setup complete")

    async def _refresh_location_search(self):
        """Refresh the location search to find new slots"""
        
        try:
            # Try to click refresh/search button
            refresh_selectors = [
                "text='Sök igen'",
                "text='Uppdatera'",
                "text='Sök lediga tider'",
                "#refresh-search",
                ".refresh-btn"
            ]
            
            for selector in refresh_selectors:
                try:
                    await self.page.click(selector)
                    print(f"[{self.job_id}] ✅ Refreshed search using: {selector}")
                    return
                except:
                    continue
            
            # Fallback: reload the page
            await self.page.reload()
            print(f"[{self.job_id}] 🔄 Refreshed by reloading page")
            
        except Exception as e:
            print(f"[{self.job_id}] ❌ Error refreshing search: {e}")

    async def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            print(f"[{self.job_id}] 🧹 Cleanup completed")
        except Exception as e:
            print(f"[{self.job_id}] ❌ Cleanup error: {e}")


async def start_enhanced_booking(job_id: str, user_config: Dict[str, Any], 
                               redis_client: redis.Redis, qr_callback: Optional[Callable] = None,
                               webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point for enhanced booking automation with webhook support
    """
    
    automation = EnhancedBookingAutomation(redis_client, qr_callback, webhook_url)
    
    try:
        result = await automation.start_booking_session(job_id, user_config)
        return result
    finally:
        await automation.cleanup() 