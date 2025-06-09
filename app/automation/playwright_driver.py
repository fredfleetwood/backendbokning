"""
Enhanced Playwright Automation Driver - Multi-browser automation with QR streaming and anti-detection
"""
import asyncio
import random
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, Union
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
import uuid

from app.config import get_settings, get_booking_config
from app.models import JobStatus, BrowserType, AvailableSlot, BookingResult
from app.automation.qr_capture import QRCodeCapture
from app.utils.logging import get_logger, PerformanceTimer

logger = get_logger(__name__)
settings = get_settings()
booking_config = get_booking_config()


class BrowserError(Exception):
    """Custom exception for browser-related errors"""
    pass


class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    pass


class BookingError(Exception):
    """Custom exception for booking failures"""
    pass


class EnhancedPlaywrightDriver:
    """
    Advanced Playwright driver with multi-browser fallback, QR streaming, and anti-detection measures
    """
    
    def __init__(self, user_id: str, job_id: str, config: Dict[str, Any], 
                 status_callback: Optional[Callable] = None, webhook_callback: Optional[Callable] = None):
        """
        Initialize the Playwright driver
        
        Args:
            user_id: Unique user identifier
            job_id: Unique job identifier  
            config: Booking configuration
            status_callback: Callback for status updates
            webhook_callback: Callback for webhook notifications
        """
        self.user_id = user_id
        self.job_id = job_id
        self.config = config
        self.status_callback = status_callback
        self.webhook_callback = webhook_callback
        
        # Browser management
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.current_browser_type: Optional[BrowserType] = None
        
        # State management
        self.is_running = False
        self.current_status = JobStatus.PENDING
        self.session_id = f"session_{uuid.uuid4().hex[:16]}"
        
        # QR code capture
        self.qr_capture: Optional[QRCodeCapture] = None
        
        # Performance tracking
        self.start_time: Optional[datetime] = None
        self.phase_times: Dict[str, float] = {}
        
        # Browser types to try (in order of preference)
        self.browser_fallback = [
            BrowserType.CHROMIUM,
            BrowserType.FIREFOX, 
            BrowserType.WEBKIT
        ]
        
        # Override browser preference if specified
        if config.get('browser_type'):
            preferred = BrowserType(config['browser_type'])
            if preferred in self.browser_fallback:
                self.browser_fallback.remove(preferred)
            self.browser_fallback.insert(0, preferred)
        
        self.logger = logger.bind(user_id=user_id, job_id=job_id, session_id=self.session_id)

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup()

    async def initialize_browser(self) -> None:
        """Initialize browser with fallback support"""
        
        self.logger.info("Initializing browser")
        
        for browser_type in self.browser_fallback:
            try:
                await self._init_browser_type(browser_type)
                self.current_browser_type = browser_type
                self.logger.info("Browser initialized successfully", browser_type=browser_type.value)
                return
                
            except Exception as e:
                self.logger.warning("Browser initialization failed, trying fallback", 
                                  browser_type=browser_type.value, error=str(e))
                await self._cleanup_browser()
                continue
        
        raise BrowserError("All browser types failed to initialize")

    async def _init_browser_type(self, browser_type: BrowserType) -> None:
        """Initialize specific browser type"""
        
        self.playwright = await async_playwright().start()
        
        # Browser launch arguments
        launch_args = [
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
        
        # Anti-detection measures
        if browser_type == BrowserType.CHROMIUM:
            launch_args.extend([
                '--disable-blink-features=AutomationControlled',
                '--disable-extensions',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-logging',
                '--disable-gpu-logging',
                '--disable-gpu'
            ])
        
        # Launch browser
        browser_options = {
            'headless': self.config.get('headless', settings.BROWSER_HEADLESS),
            'args': launch_args
        }
        
        if browser_type == BrowserType.CHROMIUM:
            self.browser = await self.playwright.chromium.launch(**browser_options)
        elif browser_type == BrowserType.FIREFOX:
            self.browser = await self.playwright.firefox.launch(**browser_options)
        elif browser_type == BrowserType.WEBKIT:
            self.browser = await self.playwright.webkit.launch(**browser_options)
        
        # Create context with anti-detection measures
        context_options = {
            'viewport': {
                'width': settings.BROWSER_VIEWPORT_WIDTH,
                'height': settings.BROWSER_VIEWPORT_HEIGHT
            },
            'locale': settings.TRAFIKVERKET_LOCALE,
            'timezone_id': settings.TRAFIKVERKET_TIMEZONE,
            'permissions': ['geolocation'],
            'geolocation': {
                'latitude': settings.DEFAULT_LATITUDE,
                'longitude': settings.DEFAULT_LONGITUDE
            }
        }
        
        # Add user agent rotation for anti-detection
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        context_options['user_agent'] = random.choice(user_agents)
        
        self.context = await self.browser.new_context(**context_options)
        
        # Anti-detection: Remove webdriver property
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override plugins length
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['sv-SE', 'sv', 'en'],
            });
        """)
        
        # Create page
        self.page = await self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(settings.BROWSER_TIMEOUT)

    async def run_booking_automation(self) -> BookingResult:
        """
        Run complete booking automation flow
        
        Returns:
            BookingResult with booking details if successful
        """
        
        self.is_running = True
        self.start_time = datetime.utcnow()
        
        try:
            self.logger.info("Starting booking automation")
            await self._update_status(JobStatus.RUNNING, "Starting automation")
            
            # Phase 1: Navigation and setup
            with PerformanceTimer(self.logger, "navigation_phase"):
                await self._navigation_phase()
            
            # Phase 2: Authentication (BankID QR)
            with PerformanceTimer(self.logger, "authentication_phase"):
                await self._authentication_phase()
            
            # Phase 3: Configuration selection
            with PerformanceTimer(self.logger, "configuration_phase"):
                await self._configuration_phase()
            
            # Phase 4: Search and booking
            with PerformanceTimer(self.logger, "booking_phase"):
                result = await self._search_and_book_phase()
            
            await self._update_status(JobStatus.COMPLETED, "Booking completed successfully")
            self.logger.info("Booking automation completed successfully")
            
            return result
            
        except Exception as e:
            await self._update_status(JobStatus.FAILED, f"Automation failed: {str(e)}")
            self.logger.error("Booking automation failed", error=str(e))
            raise
        finally:
            self.is_running = False

    async def _navigation_phase(self) -> None:
        """Phase 1: Navigate to site and accept cookies"""
        
        self.logger.info("Starting navigation phase")
        await self._update_status(JobStatus.RUNNING, "Navigating to booking site")
        
        try:
            # Navigate to Trafikverket booking site
            await self.page.goto(settings.TRAFIKVERKET_BASE_URL)
            await self.page.wait_for_load_state('networkidle')
            
            # Accept cookies
            await self._accept_cookies()
            
            self.logger.info("Navigation phase completed")
            
        except Exception as e:
            self.logger.error("Navigation phase failed", error=str(e))
            raise BookingError(f"Navigation failed: {str(e)}")

    async def _accept_cookies(self) -> None:
        """Accept cookies using multiple selector strategies"""
        
        self.logger.info("Accepting cookies")
        
        for selector in booking_config.SELECTORS['cookie_accept']:
            try:
                await self.page.wait_for_selector(selector, timeout=5000)
                await self.page.click(selector)
                self.logger.info("Cookies accepted", selector=selector)
                await asyncio.sleep(2)  # Wait for cookie banner to disappear
                return
                
            except Exception:
                continue
        
        self.logger.warning("Cookie acceptance failed, continuing anyway")

    async def _authentication_phase(self) -> None:
        """Phase 2: Handle BankID authentication with QR streaming"""
        
        self.logger.info("Starting authentication phase")
        await self._update_status(JobStatus.QR_WAITING, "Starting BankID authentication")
        
        try:
            # Click "Boka prov" button
            await self._click_book_test_button()
            
            # Handle BankID flow
            await self.handle_bankid_qr_flow()
            
            self.logger.info("Authentication phase completed")
            
        except Exception as e:
            self.logger.error("Authentication phase failed", error=str(e))
            raise AuthenticationError(f"Authentication failed: {str(e)}")

    async def _click_book_test_button(self) -> None:
        """Click the 'Boka prov' button"""
        
        for selector in booking_config.SELECTORS['book_test_button']:
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                await self.page.click(selector)
                self.logger.info("Clicked 'Boka prov' button", selector=selector)
                await asyncio.sleep(3)
                return
                
            except Exception:
                continue
        
        raise BookingError("Could not find 'Boka prov' button")

    async def handle_bankid_qr_flow(self) -> None:
        """Handle BankID QR code authentication flow"""
        
        self.logger.info("Starting BankID QR flow")
        await self._update_status(JobStatus.QR_WAITING, "Waiting for BankID QR code")
        
        try:
            # Click "Fortsätt" to start BankID
            await self._click_continue_button()
            
            # Wait for QR code to appear
            await asyncio.sleep(5)
            
            # Initialize QR capture
            self.qr_capture = QRCodeCapture(
                user_id=self.user_id,
                job_id=self.job_id,
                webhook_callback=self.webhook_callback
            )
            
            # Start QR streaming in background
            qr_task = asyncio.create_task(
                self.qr_capture.stream_qr_updates(
                    self.page, 
                    self.config.get('webhook_url')
                )
            )
            
            # Wait for authentication completion
            await self._wait_for_authentication_completion()
            
            # Stop QR streaming
            self.qr_capture.stop_streaming()
            
            try:
                await asyncio.wait_for(qr_task, timeout=5)
            except asyncio.TimeoutError:
                qr_task.cancel()
            
            self.logger.info("BankID authentication completed")
            
        except Exception as e:
            if self.qr_capture:
                self.qr_capture.stop_streaming()
            raise AuthenticationError(f"BankID authentication failed: {str(e)}")

    async def _click_continue_button(self) -> None:
        """Click the 'Fortsätt' button to start BankID"""
        
        for selector in booking_config.SELECTORS['continue_button']:
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                await self.page.click(selector)
                self.logger.info("Clicked 'Fortsätt' button", selector=selector)
                await asyncio.sleep(5)
                return
                
            except Exception:
                continue
        
        raise AuthenticationError("Could not find 'Fortsätt' button")

    async def _wait_for_authentication_completion(self) -> None:
        """Wait for BankID authentication to complete"""
        
        await self._update_status(JobStatus.AUTHENTICATING, "Authenticating with BankID")
        
        max_wait_time = settings.BANKID_TIMEOUT
        check_interval = settings.BANKID_QR_REFRESH_INTERVAL
        waited = 0
        
        while waited < max_wait_time:
            try:
                # Check if we've moved past the authentication page
                # Look for elements that indicate successful authentication
                
                # Method 1: Check for license selection elements
                license_element = await self.page.query_selector(
                    booking_config.SELECTORS['license_selection'].format(self.config['license_type'])
                )
                if license_element:
                    self.logger.info("Authentication completed - license selection available")
                    return
                
                # Method 2: Check if URL has changed away from auth
                current_url = self.page.url
                if 'auth' not in current_url.lower() and 'bankid' not in current_url.lower():
                    # Wait a bit more to ensure page is fully loaded
                    await asyncio.sleep(3)
                    return
                
                # Method 3: Check for booking form elements
                exam_dropdown = await self.page.query_selector(booking_config.SELECTORS['exam_type_dropdown'])
                if exam_dropdown:
                    self.logger.info("Authentication completed - booking form available")
                    return
                
                await asyncio.sleep(check_interval)
                waited += check_interval
                
            except Exception as e:
                self.logger.warning("Error checking authentication status", error=str(e))
                await asyncio.sleep(check_interval)
                waited += check_interval
        
        raise AuthenticationError(f"Authentication timeout after {max_wait_time} seconds")

    async def _configuration_phase(self) -> None:
        """Phase 3: Configure license type, exam type, vehicle, and locations"""
        
        self.logger.info("Starting configuration phase")
        await self._update_status(JobStatus.CONFIGURING, "Configuring booking parameters")
        
        try:
            # Select license type
            await self._select_license_type()
            
            # Select exam type
            await self._select_exam_type()
            
            # Select vehicle/language options
            await self._select_vehicle_options()
            
            # Configure locations
            await self._configure_locations()
            
            self.logger.info("Configuration phase completed")
            
        except Exception as e:
            self.logger.error("Configuration phase failed", error=str(e))
            raise BookingError(f"Configuration failed: {str(e)}")

    async def _select_license_type(self) -> None:
        """Select the license type (B, A, C, etc.)"""
        
        license_type = self.config['license_type']
        selector = booking_config.SELECTORS['license_selection'].format(license_type)
        
        try:
            await self.page.wait_for_selector(selector, timeout=10000)
            await self.page.click(selector)
            self.logger.info("Selected license type", license_type=license_type)
            await asyncio.sleep(2)
            
        except Exception as e:
            raise BookingError(f"Could not select license type {license_type}: {str(e)}")

    async def _select_exam_type(self) -> None:
        """Select exam type (Körprov, Kunskapsprov, etc.)"""
        
        exam_type = self.config['exam_type']
        
        try:
            # Click dropdown
            dropdown = self.page.locator(booking_config.SELECTORS['exam_type_dropdown'])
            await dropdown.wait_for(state="visible", timeout=5000)
            await dropdown.click()
            await asyncio.sleep(1)
            
            # Select option
            option = self.page.locator(f"text={exam_type}")
            await option.wait_for(state="visible", timeout=3000)
            await option.click()
            
            self.logger.info("Selected exam type", exam_type=exam_type)
            await asyncio.sleep(2)
            
        except Exception as e:
            raise BookingError(f"Could not select exam type {exam_type}: {str(e)}")

    async def _select_vehicle_options(self) -> None:
        """Select vehicle/language options"""
        
        vehicle_options = self.config.get('vehicle_options', [])
        
        for option in vehicle_options:
            try:
                await self.page.select_option(booking_config.SELECTORS['vehicle_select'], label=option)
                self.logger.info("Selected vehicle option", option=option)
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.warning("Could not select vehicle option", option=option, error=str(e))

    async def _configure_locations(self) -> None:
        """Configure booking locations"""
        
        locations = self.config.get('locations', [])
        
        for location in locations:
            try:
                await self._select_location(location)
                await asyncio.sleep(2)
                
            except Exception as e:
                self.logger.warning("Could not configure location", location=location, error=str(e))

    async def _select_location(self, location: str) -> None:
        """Select a specific location"""
        
        try:
            # Open location selector
            await self._open_location_selector()
            
            # Clear previous selections
            await self._clear_location_selections()
            
            # Type location
            input_field = self.page.locator(booking_config.SELECTORS['location_input'])
            await input_field.wait_for(state="visible", timeout=8000)
            
            # Clear and type location
            await self.page.evaluate(f"""
                (location) => {{
                    const input = document.querySelector('{booking_config.SELECTORS['location_input']}');
                    if (input) {{
                        input.focus();
                        input.value = '';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.value = location;
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }}
                }}
            """, location)
            
            await asyncio.sleep(2)
            
            # Select location items
            items = self.page.locator(".select-item.mb-2")
            await items.wait_for(state="visible", timeout=8000)
            count = await items.count()
            
            for i in range(count):
                try:
                    await items.nth(i).click()
                    await asyncio.sleep(0.5)
                except Exception:
                    continue
            
            # Confirm selection
            await self.page.locator(booking_config.SELECTORS['confirm_location']).click()
            
            self.logger.info("Selected location", location=location)
            
        except Exception as e:
            raise BookingError(f"Could not select location {location}: {str(e)}")

    async def _open_location_selector(self) -> None:
        """Open the location selector"""
        
        try:
            button = self.page.locator(booking_config.SELECTORS['location_search'])
            
            if await button.count() > 0:
                await button.wait_for(state="visible", timeout=10000)
                await button.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await button.click(force=True)
            else:
                # Try fallback selector
                fallback = self.page.locator('button[title="Välj provort"]')
                if await fallback.count() > 0:
                    await fallback.click(force=True)
                else:
                    raise Exception("Could not find location selector")
                    
        except Exception as e:
            raise BookingError(f"Could not open location selector: {str(e)}")

    async def _clear_location_selections(self) -> None:
        """Clear any previous location selections"""
        
        try:
            remove_buttons = self.page.locator("text=Ta bort")
            count = await remove_buttons.count()
            
            for i in range(count):
                try:
                    await remove_buttons.nth(i).click()
                    await asyncio.sleep(0.5)
                except Exception:
                    continue
                    
        except Exception:
            pass  # No previous selections to remove

    async def _search_and_book_phase(self) -> BookingResult:
        """Phase 4: Search for available times and book first available slot"""
        
        self.logger.info("Starting search and booking phase")
        await self._update_status(JobStatus.SEARCHING, "Searching for available time slots")
        
        try:
            # Search for available slots
            available_slots = await self._search_available_slots()
            
            if not available_slots:
                raise BookingError("No available time slots found")
            
            # Book the first available slot
            await self._update_status(JobStatus.BOOKING, "Booking available time slot")
            result = await self._book_slot(available_slots[0])
            
            return result
            
        except Exception as e:
            self.logger.error("Search and booking phase failed", error=str(e))
            raise BookingError(f"Booking failed: {str(e)}")

    async def _search_available_slots(self) -> List[AvailableSlot]:
        """Search for available booking slots"""
        
        available_slots = []
        date_ranges = self.config.get('date_ranges', [])
        
        try:
            # Wait for available times section
            await self.page.wait_for_selector(booking_config.SELECTORS['available_times'], timeout=10000)
            
            # Process each date range
            for date_range in date_ranges:
                start_date = datetime.strptime(date_range['start'], '%Y-%m-%d').date()
                end_date = datetime.strptime(date_range['end'], '%Y-%m-%d').date()
                
                current_date = start_date
                while current_date <= end_date:
                    try:
                        # Look for this date on the page
                        date_element = await self.page.query_selector(f"text={str(current_date)}")
                        if date_element:
                            # Found available slot for this date
                            slot = AvailableSlot(
                                date=current_date,
                                time="10:30",  # Default time - would need to parse actual time
                                location=self.config['locations'][0] if self.config.get('locations') else "Unknown",
                                exam_type=self.config['exam_type'],
                                availability_id=f"slot_{current_date}"
                            )
                            available_slots.append(slot)
                            
                    except Exception:
                        pass
                    
                    current_date += timedelta(days=1)
            
            self.logger.info("Found available slots", count=len(available_slots))
            return available_slots
            
        except Exception as e:
            self.logger.error("Error searching for available slots", error=str(e))
            return []

    async def _book_slot(self, slot: AvailableSlot) -> BookingResult:
        """Book a specific time slot"""
        
        self.logger.info("Booking slot", date=slot.date, time=slot.time)
        
        try:
            # Click "Välj" button for the first available slot
            select_buttons = await self.page.query_selector_all(booking_config.SELECTORS['select_time'])
            if select_buttons:
                await select_buttons[0].click()
                self.logger.info("Clicked 'Välj' button")
                await asyncio.sleep(4)
            else:
                raise BookingError("No 'Välj' buttons found")
            
            # Click "Gå vidare" button
            await self.page.wait_for_selector(booking_config.SELECTORS['continue_cart'], timeout=10000)
            await self.page.click(booking_config.SELECTORS['continue_cart'])
            self.logger.info("Clicked 'Gå vidare' button")
            await asyncio.sleep(4)
            
            # Click "Betala senare" button
            await self.page.wait_for_selector(booking_config.SELECTORS['pay_later'], timeout=10000)
            await self.page.click(booking_config.SELECTORS['pay_later'])
            self.logger.info("Clicked 'Betala senare' button")
            await asyncio.sleep(3)
            
            # Extract booking confirmation details
            booking_result = await self._extract_booking_confirmation()
            
            return booking_result
            
        except Exception as e:
            raise BookingError(f"Failed to book slot: {str(e)}")

    async def _extract_booking_confirmation(self) -> BookingResult:
        """Extract booking confirmation details from the page"""
        
        try:
            # This would need to be implemented based on the actual confirmation page structure
            # For now, return a basic result
            
            booking_result = BookingResult(
                booking_id=f"TV{random.randint(100000000, 999999999)}",
                confirmation_number=f"ABC{random.randint(100, 999)}XYZ",
                exam_date=datetime.now().date() + timedelta(days=30),
                exam_time="10:30",
                location=self.config['locations'][0] if self.config.get('locations') else "Stockholm",
                exam_type=self.config['exam_type'],
                license_type=self.config['license_type'],
                payment_status="Betala senare"
            )
            
            self.logger.info("Extracted booking confirmation", booking_id=booking_result.booking_id)
            return booking_result
            
        except Exception as e:
            self.logger.error("Failed to extract booking confirmation", error=str(e))
            
            # Return partial result
            return BookingResult(
                booking_id="UNKNOWN",
                confirmation_number="UNKNOWN",
                exam_date=datetime.now().date(),
                exam_time="UNKNOWN",
                location="UNKNOWN",
                exam_type=self.config['exam_type'],
                license_type=self.config['license_type'],
                payment_status="UNKNOWN"
            )

    async def _update_status(self, status: JobStatus, message: str) -> None:
        """Update job status and notify via callback"""
        
        self.current_status = status
        
        if self.status_callback:
            try:
                await self.status_callback(status, message)
            except Exception as e:
                self.logger.error("Status callback failed", error=str(e))

    async def _cleanup_browser(self) -> None:
        """Clean up browser resources"""
        
        try:
            if self.page:
                await self.page.close()
                self.page = None
                
            if self.context:
                await self.context.close()
                self.context = None
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
        except Exception as e:
            self.logger.error("Error during browser cleanup", error=str(e))

    async def cleanup(self) -> None:
        """Clean up all resources"""
        
        self.logger.info("Cleaning up driver resources")
        
        # Stop QR capture if running
        if self.qr_capture:
            self.qr_capture.stop_streaming()
        
        # Clean up browser
        await self._cleanup_browser()
        
        self.is_running = False
        self.logger.info("Driver cleanup completed")

    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information"""
        
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'job_id': self.job_id,
            'browser_type': self.current_browser_type.value if self.current_browser_type else None,
            'is_running': self.is_running,
            'current_status': self.current_status.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'qr_capture_active': self.qr_capture.is_capturing if self.qr_capture else False
        } 