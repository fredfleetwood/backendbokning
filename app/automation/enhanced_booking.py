"""
Enhanced Booking Automation - Based on Proven Working Script
Combines battle-tested selectors with full system integration
Simplified from 1,459 lines to ~450 lines with proven logic
"""
import asyncio
import base64
import json
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from playwright.async_api import async_playwright, Page, Browser, Playwright
import redis
from app.utils.webhooks import webhook_manager


class BrowserError(Exception):
    """Browser launch or operation failed"""
    pass


class AuthenticationError(Exception):
    """BankID authentication failed"""
    pass


class BookingError(Exception):
    """Booking process failed"""
    pass


class EnhancedBookingAutomation:
    """
    Enhanced booking automation using proven working script logic
    Combines battle-tested selectors with web service architecture
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
        """Main entry point - start complete booking session"""
        
        self.job_id = job_id
        self.user_id = user_config.get("user_id", "unknown")
        
        try:
            # Send booking started webhook
            if self.webhook_url:
                await webhook_manager.send_booking_started(
                    self.webhook_url, job_id, self.user_id, user_config
                )
            
            await self._update_job_status("starting", "Initializing browser", 5)
            
            # Initialize browser using proven approach
            await self._initialize_browser()
            
            # Navigate and setup
            await self._navigate_to_trafikverket()
            
            # Execute the proven booking flow
            result = await self._execute_proven_booking_flow(user_config)
            
            # Send completion webhook
            if self.webhook_url:
                await webhook_manager.send_booking_completed(
                    self.webhook_url, job_id, self.user_id, 
                    result.get("success", False), result.get("booking_details")
                )
            
            return result
            
        except Exception as e:
            await self._update_job_status("failed", f"Booking failed: {str(e)}", 0)
            
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
            await self.cleanup()

    async def _initialize_browser(self):
        """Initialize browser with VNC support - try WebKit first like working script"""
        
        await self._update_job_status("starting", "Launching browser", 8)
        
        self.playwright = await async_playwright().start()
        
        # Check for VNC monitoring
        vnc_monitoring = os.getenv("VNC_MONITORING_ENABLED", "false").lower() == "true"
        vnc_display = os.getenv("VNC_DISPLAY", ":99")
        
        if vnc_monitoring:
            headless_mode = False
            os.environ['DISPLAY'] = vnc_display
            print(f"[{self.job_id}] 🖥️ VNC monitoring enabled: display={vnc_display}")
        else:
            headless_mode = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
        
        # Try browsers in working script order: WebKit → Firefox → Chromium
        browser_types = [
            ('webkit', self.playwright.webkit),
            ('firefox', self.playwright.firefox),
            ('chromium', self.playwright.chromium)
        ]
        
        for browser_name, browser_launcher in browser_types:
            try:
                print(f"[{self.job_id}] 🚀 Launching {browser_name}...")
                
                self.browser = await browser_launcher.launch(
                    headless=headless_mode,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                
                # Create context with Swedish settings (like working script)
                self.context = await self.browser.new_context(
                    permissions=["geolocation"],
                    geolocation={"latitude": 59.3293, "longitude": 18.0686},  # Stockholm
                    locale="sv-SE"
                )
                
                self.page = await self.context.new_page()
                print(f"[{self.job_id}] ✅ {browser_name.title()} launched successfully")
                break
                
            except Exception as e:
                print(f"[{self.job_id}] ❌ {browser_name.title()} failed: {e}")
                if browser_name == 'chromium':  # Last option
                    raise BrowserError("All browser types failed to launch")
                continue
        
    async def _navigate_to_trafikverket(self):
        """Navigate to Trafikverket and accept cookies - EXACT from working script"""
        
        await self._update_job_status("navigating", "Opening Trafikverket", 10)
        
        # Navigate - EXACT URL from working script
        await self.page.goto('https://fp.trafikverket.se/boka/#/')
        await self._accept_cookies()

    async def _accept_cookies(self):
        """Accept cookies - EXACT from working script"""
        
        try:
            await self.page.wait_for_selector("button.btn.btn-primary:has-text('Godkänn nödvändiga')", timeout=5000)
            await self.page.click("button.btn.btn-primary:has-text('Godkänn nödvändiga')")
            print(f"[{self.job_id}] ✅ Accepted mandatory cookies.")
        except Exception as e:
            print(f"[{self.job_id}] ⚠️ Cookie popup not found or already accepted.")

    async def _execute_proven_booking_flow(self, user_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the complete proven booking flow - EXACT sequence from working script"""
        
        # Step 1: Login - EXACT from working script
        await self._update_job_status("login", "Starting booking process", 15)
        await self._login()
        await asyncio.sleep(5)  # EXACT timing from working script
        
        # Step 2: BankID authentication with QR streaming
        await self._update_job_status("bankid", "BankID authentication", 20)
        await self._handle_bankid_with_qr_streaming()
        await asyncio.sleep(5)  # EXACT timing from working script
        
        # Step 3: Select exam - EXACT from working script
        await self._update_job_status("configuring", "Selecting license type", 35)
        if not await self._select_exam(user_config.get("license_type", "B")):
            raise BookingError("Could not select license type")
        
        # Continue with proven flow - EXACT from working script
        for location in user_config.get("locations", ["Stockholm"]):
            try:
                await self._process_location_booking(user_config, location)
                # If we get here, booking succeeded
                return {
                    "success": True,
                    "booking_details": {
                        "location": location,
                        "timestamp": datetime.utcnow().isoformat(),
                        "message": "Booking completed successfully"
                    },
                    "message": "Booking completed successfully"
                }
            except Exception as e:
                print(f"[{self.job_id}] ❌ Failed for location {location}: {e}")
                continue
        
        # If we get here, no location worked
        return {
            "success": False,
            "message": "No available times found for any location"
        }

    async def _login(self):
        """Click 'Boka prov' button - EXACT from working script"""
        
        try:
            await self.page.wait_for_selector("button[title='Boka prov']", timeout=10000)
            await self.page.click("button[title='Boka prov']")
            print(f"[{self.job_id}] ✅ Clicked 'Boka prov' button.")
        except Exception as e:
            raise BookingError(f"Error clicking 'Boka prov': {e}")

    async def _handle_bankid_with_qr_streaming(self):
        """Handle BankID - PROPER authentication waiting with QR streaming"""
        
        try:
            # Step 1: Start BankID flow
            await self.page.wait_for_selector("text='Fortsätt'", timeout=10000)
            await self.page.click("text='Fortsätt'")
            print(f"[{self.job_id}] ✅ Started BankID flow")
            
            # Step 2: Start QR streaming for frontend (async task)
            qr_task = asyncio.create_task(self._stream_qr_codes())
            
            # Step 3: ACTUALLY WAIT FOR AUTHENTICATION (not fake 5-second timeout!)
            print(f"[{self.job_id}] 🔄 Waiting for BankID authentication...")
            await self._update_job_status("waiting_bankid", "Waiting for BankID authentication", 25)
            
            authentication_success = await self._wait_for_bankid_completion()
            
            # Step 4: Cancel QR streaming once authentication is done
            qr_task.cancel()
            
            if authentication_success:
                await self._update_job_status("authenticated", "BankID authentication successful", 30)
                print(f"[{self.job_id}] ✅ BankID authentication completed successfully")
            else:
                raise AuthenticationError("BankID authentication timeout or failed")
            
        except Exception as e:
            # Make sure to cancel QR streaming on any error
            try:
                qr_task.cancel()
            except:
                pass
            raise AuthenticationError(f"BankID authentication failed: {e}")

    async def _wait_for_bankid_completion(self) -> bool:
        """Wait for actual BankID authentication completion - NO MORE FAKE TIMEOUTS!"""
        
        # Wait up to 5 minutes for BankID completion
        timeout_seconds = 300  # 5 minutes
        check_interval = 2  # Check every 2 seconds
        elapsed = 0
        
        while elapsed < timeout_seconds:
            try:
                # Method 1: Check if we've moved past BankID page
                # Look for elements that appear after successful authentication
                post_auth_selectors = [
                    "[title='B']",  # License selection appears after auth
                    "#examination-type-select",  # Exam type selector
                    "text='Välj körkortstyp'"  # License type text
                ]
                
                for selector in post_auth_selectors:
                    try:
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            print(f"[{self.job_id}] ✅ Authentication confirmed - found post-auth element: {selector}")
                            return True
                    except:
                        continue
                
                # Method 2: Check if BankID error messages appeared
                error_selectors = [
                    "text='Fel vid inloggning'",
                    "text='BankID-fel'", 
                    "text='Tekniskt fel'",
                    ".alert-danger"
                ]
                
                for error_selector in error_selectors:
                    try:
                        error_element = await self.page.query_selector(error_selector)
                        if error_element and await error_element.is_visible():
                            print(f"[{self.job_id}] ❌ BankID error detected: {error_selector}")
                            return False
                    except:
                        continue
                
                # Method 3: Check URL change (authentication might redirect)
                current_url = self.page.url
                if "boka" in current_url and "#/" not in current_url:
                    print(f"[{self.job_id}] ✅ URL changed after authentication: {current_url}")
                    return True
                
                # Method 4: Check if QR code disappeared (might indicate completion)
                qr_element = await self.page.query_selector(".qrcode canvas")
                if not qr_element:
                    # QR disappeared, wait a bit more to see if we get to next step
                    await asyncio.sleep(3)
                    
                    # Check again for post-auth elements
                    for selector in post_auth_selectors:
                        try:
                            element = await self.page.query_selector(selector)
                            if element and await element.is_visible():
                                print(f"[{self.job_id}] ✅ Authentication confirmed after QR disappeared")
                                return True
                        except:
                            continue
                
                # Update status periodically
                if elapsed % 30 == 0 and elapsed > 0:
                    await self._update_job_status("waiting_bankid", f"Still waiting for BankID... ({elapsed}s)", 25)
                    print(f"[{self.job_id}] 🕐 Still waiting for BankID authentication ({elapsed}s elapsed)")
                
                await asyncio.sleep(check_interval)
                elapsed += check_interval
                
            except Exception as e:
                print(f"[{self.job_id}] ⚠️ Error checking BankID status: {e}")
                await asyncio.sleep(check_interval)
                elapsed += check_interval
        
        # Timeout reached
        print(f"[{self.job_id}] ❌ BankID authentication timeout after {elapsed}s")
        return False

    async def _stream_qr_codes(self):
        """Ultra-responsive QR detection using canvas monitoring and MutationObserver"""
        
        try:
            # Set up MutationObserver for immediate DOM changes
            await self.page.evaluate("""
                () => {
                    window.qrChanges = [];
                    window.qrObserver = new MutationObserver((mutations) => {
                        mutations.forEach((mutation) => {
                            if (mutation.type === 'childList' || mutation.type === 'attributes') {
                                const qrElement = document.querySelector('.qrcode canvas') || document.querySelector('canvas');
                                if (qrElement) {
                                    window.qrChanges.push({
                                        timestamp: Date.now(),
                                        type: 'dom_change',
                                        canvas_detected: true
                                    });
                                }
                            }
                        });
                    });
                    
                    // Start observing the entire document for QR changes
                    window.qrObserver.observe(document.body, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        attributeFilter: ['class', 'style', 'src']
                    });
                }
            """)
            
            last_qr_hash = None
            attempts = 0
            
            for attempt in range(120):  # 2 minutes max
                try:
                    # Check for DOM changes from MutationObserver
                    changes = await self.page.evaluate("() => window.qrChanges.splice(0)")
                    
                    if changes:
                        print(f"[{self.job_id}] 🔍 DOM changes detected: {len(changes)} changes")
                    
                    # Look for QR canvas element
                    qr_element = await self.page.query_selector(".qrcode canvas")
                    if not qr_element:
                        qr_element = await self.page.query_selector("canvas")
                    
                    if qr_element:
                        # Capture canvas content for hash comparison
                        canvas_data = await self.page.evaluate("""
                            (element) => {
                                try {
                                    return element.toDataURL();
                                } catch (e) {
                                    return null;
                                }
                            }
                        """, qr_element)
                        
                        if canvas_data:
                            # Generate hash to detect actual visual changes
                            import hashlib
                            qr_hash = hashlib.md5(canvas_data.encode()).hexdigest()
                            
                            # Only send if QR actually changed
                            if qr_hash != last_qr_hash:
                                attempts += 1
                                last_qr_hash = qr_hash
                                
                                # Take high-quality screenshot
                                qr_screenshot = await qr_element.screenshot()
                                qr_data_url = f"data:image/png;base64,{base64.b64encode(qr_screenshot).decode()}"
                                
                                await self._send_qr_update(qr_data_url, f"bankid_qr_{attempts}")
                                print(f"[{self.job_id}] 📱 NEW QR detected and sent (#{attempts})")
                            else:
                                # QR unchanged, shorter polling interval
                                await asyncio.sleep(0.5)
                                continue
                    
                    # Adaptive polling based on QR presence
                    if qr_element:
                        await asyncio.sleep(0.8)  # Fast polling when QR is present
                    else:
                        await asyncio.sleep(2.0)  # Slower when waiting for QR to appear
                    
                except asyncio.CancelledError:
                    print(f"[{self.job_id}] 🔄 QR streaming stopped")
                    break
                except Exception as e:
                    print(f"[{self.job_id}] ❌ QR streaming error: {e}")
                    await asyncio.sleep(1)
                    
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up MutationObserver
            try:
                await self.page.evaluate("() => { if (window.qrObserver) window.qrObserver.disconnect(); }")
            except:
                pass

    async def _send_qr_update(self, qr_image_data: str, auth_ref: str):
        """Send QR code update to frontend via multiple channels"""
        
        qr_metadata = {
            "auth_ref": auth_ref,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # WebSocket callback
        if self.qr_callback:
            await self.qr_callback(self.job_id, qr_image_data, qr_metadata)
        
        # Webhook to Supabase
        if self.webhook_url:
            await webhook_manager.send_qr_code_update(
                self.webhook_url, self.job_id, self.user_id, qr_image_data, auth_ref
            )
        
        # Redis storage
        qr_key = f"qr:{self.job_id}"
        self.redis_client.setex(qr_key, 30, json.dumps({
            "image_data": qr_image_data,
            "timestamp": datetime.utcnow().isoformat(),
            "auth_ref": auth_ref
        }))

    async def _select_exam(self, license_type: str) -> bool:
        """Select license type - EXACT from working script"""
        
        try:
            # EXACT selector from working script
            selector = f"[title='{license_type}']"
            await self.page.wait_for_selector(selector, timeout=10000)
            await self.page.click(selector)
            print(f"[{self.job_id}] ✅ Selected license type: {license_type}")
            return True
        except Exception as e:
            print(f"[{self.job_id}] ❌ Could not find license type: {license_type}")
            return False

    async def _process_location_booking(self, user_config: Dict[str, Any], location: str):
        """Process booking for one location - EXACT sequence from working script"""
        
        await self._update_job_status("configuring", f"Processing {location}", 40)
        
        # Step 1: Select exam type - EXACT from working script
        await self._select_exam_type(user_config.get("exam_type", "Körprov"))
        await asyncio.sleep(3)  # EXACT timing from working script
        
        # Step 2: Select vehicle/language - EXACT from working script
        for rent_or_language in user_config.get("rent_or_language", ["Egen bil"]):
            await self._select_rent_or_language(rent_or_language)
            await asyncio.sleep(3)  # EXACT timing from working script
        
        # Step 3: Select location - EXACT from working script
        await self._select_location(location)
        await asyncio.sleep(3)  # EXACT timing from working script
        
        # Step 4: Select time and search
        await self._update_job_status("searching", f"Searching times for {location}", 60)
        await self._select_time_range(user_config.get("date_ranges", []))
        await asyncio.sleep(3)  # EXACT timing from working script
        
        # Step 5: Try to book if times available
        if await self._check_and_book_available_times():
            await self._update_job_status("completed", "Booking completed", 100)
            return True
        else:
            raise BookingError(f"No available times for {location}")

    async def _select_exam_type(self, exam_type: str):
        """Select exam type - EXACT from working script"""
        
        try:
            print(f"[{self.job_id}] 🔍 Selecting exam type...")
            # EXACT selector from working script
            dropdown = self.page.locator('#examination-type-select')
            await dropdown.wait_for(state="visible", timeout=5000)
            await dropdown.click()
            await asyncio.sleep(0.5)  # Brief pause
            
            option = self.page.locator(f"text={exam_type}")
            await option.wait_for(state="visible", timeout=3000)
            await option.click()
            print(f"[{self.job_id}] ✅ Selected exam type: {exam_type}")
        except Exception as e:
            print(f"[{self.job_id}] ❌ Error selecting exam type: {e}")

    async def _select_rent_or_language(self, rent_or_language: str):
        """Select vehicle/language - EXACT from working script"""
        
        try:
            # EXACT selector from working script
            await self.page.select_option("#vehicle-select", label=rent_or_language)
            print(f"[{self.job_id}] ✅ Selected vehicle/language: {rent_or_language}")
        except Exception as e:
            print(f"[{self.job_id}] ❌ Could not select rent/language: {rent_or_language}")

    async def _select_location(self, location: str):
        """Select location - EXACT method from working script"""
        
        try:
            await self._open_location_selector()
            await asyncio.sleep(1)  # EXACT timing
            
            # Clear existing selections - EXACT from working script
            remove_buttons = await self.page.query_selector_all("text=Ta bort")
            for button in remove_buttons:
                try:
                    await button.click()
                    print(f"[{self.job_id}] 🗑️ Removed previous selection")
                    await asyncio.sleep(0.5)
                except:
                    pass

            # Type location - EXACT method from working script
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

            await asyncio.sleep(1.5)  # EXACT timing
            
            # Select all items - EXACT from working script
            items = await self.page.query_selector_all(".select-item.mb-2")
            for i, item in enumerate(items):
                try:
                    await item.click()
                    print(f"[{self.job_id}] ✅ Selected location item {i+1} for: {location}")
                    await asyncio.sleep(0.5)
                except:
                    pass
            
            # Confirm - EXACT from working script
            await self.page.click("text=Bekräfta")
            print(f"[{self.job_id}] ✅ Confirmed location selection")

        except Exception as e:
            print(f"[{self.job_id}] ❌ Error selecting location: {e}")

    async def _open_location_selector(self):
        """Open location selector - EXACT from working script"""
        
        try:
            # Try primary selector - EXACT from working script
            button = self.page.locator('#select-location-search')
            if await button.count() > 0:
                await button.wait_for(state="visible", timeout=10000)
                await button.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                await button.click(force=True)
                print(f"[{self.job_id}] ✅ Opened location selector")
            else:
                # Fallback - EXACT from working script
                fallback = self.page.locator('button[title="Välj provort"]')
                await fallback.wait_for(state="visible", timeout=10000)
                await fallback.click(force=True)
                print(f"[{self.job_id}] ✅ Opened location selector (fallback)")
        except Exception as e:
            print(f"[{self.job_id}] ❌ Error opening location selector: {e}")

    async def _select_time_range(self, date_ranges: List[Dict]):
        """Select time ranges - EXACT from working script approach"""
        
        try:
            # Wait for time selection area - EXACT from working script
            await self.page.wait_for_selector("text='Lediga provtider'", timeout=10000)
            
            # Populate available times list like working script
            for date_range in date_ranges:
                if isinstance(date_range, dict) and 'from' in date_range and 'to' in date_range:
                    start_date = datetime.fromisoformat(date_range['from']).date()
                    end_date = datetime.fromisoformat(date_range['to']).date()
                    
                    current = start_date
                    while current <= end_date:
                        try:
                            date_element = await self.page.query_selector(f"text={str(current)}")
                            if date_element:
                                content = await date_element.text_content()
                                self.available_times.append(content)
                        except:
                            pass
                        current += timedelta(days=1)
            
            print(f"[{self.job_id}] ✅ Time selection area loaded")
        except Exception as e:
            print(f"[{self.job_id}] ❌ Error in time selection: {e}")

    async def _check_and_book_available_times(self) -> bool:
        """Check for available times and book - EXACT sequence from working script"""
        
        try:
            # Look for "Välj" buttons - EXACT from working script
            await self.page.wait_for_selector("button.btn.btn-primary:has-text('Välj')", timeout=10000)
            buttons = await self.page.query_selector_all("button.btn.btn-primary:has-text('Välj')")
            
            if not buttons:
                print(f"[{self.job_id}] ❌ No 'Välj' buttons found")
                return False
            
            print(f"[{self.job_id}] 📅 Found {len(buttons)} time slots available")
            
            # Click first button - EXACT from working script
            await buttons[0].click()
            print(f"[{self.job_id}] ✅ Clicked first 'Välj' button")
            await asyncio.sleep(4)  # EXACT timing
            
            # Click "Gå vidare" - EXACT from working script
            await self.page.wait_for_selector("#cart-continue-button", timeout=10000)
            await self.page.click("#cart-continue-button")
            print(f"[{self.job_id}] ✅ Clicked 'Gå vidare' button")
            await asyncio.sleep(4)  # EXACT timing
            
            # Click "Betala senare" - EXACT from working script
            await self.page.wait_for_selector("#pay-invoice-button", timeout=10000)
            await self.page.click("#pay-invoice-button")
            print(f"[{self.job_id}] ✅ Clicked 'Betala senare' button")
            
            # Final wait - EXACT from working script
            await asyncio.sleep(3)
            print(f"[{self.job_id}] 👋 Booking completed successfully!")
            
            return True
            
        except Exception as e:
            print(f"[{self.job_id}] ❌ Booking process failed: {e}")
            return False

    async def _update_job_status(self, status: str, message: str, progress: int):
        """Update job status in Redis and send webhook"""
        
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
        
        if self.webhook_url:
            await webhook_manager.send_status_update(
                self.webhook_url, self.job_id, self.user_id, status, message, progress
            )

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


# Main entry point for compatibility with existing system
async def start_enhanced_booking(job_id: str, user_config: Dict[str, Any], 
                               redis_client: redis.Redis, qr_callback: Optional[Callable] = None,
                               webhook_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point for enhanced booking automation using proven working script logic
    """
    
    automation = EnhancedBookingAutomation(redis_client, qr_callback, webhook_url)
    
    try:
        result = await automation.start_booking_session(job_id, user_config)
        return result
    finally:
        await automation.cleanup() 