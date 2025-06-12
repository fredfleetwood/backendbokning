from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
from discord_webhook import DiscordWebhook
import config
import time

times = []

class PlaywrightDriver:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context(
            permissions=["geolocation"],
            geolocation={"latitude": 59.3293, "longitude": 18.0686},  # example: Stockholm coordinates
            locale="sv-SE"
        )
        self.page = self.context.new_page()
        self.page.goto('https://fp.trafikverket.se/boka/#/')
        self.accept_cookies()

    def accept_cookies(self):
        try:
            self.page.wait_for_selector("button.btn.btn-primary:has-text('Godkänn nödvändiga')", timeout=5000)
            self.page.click("button.btn.btn-primary:has-text('Godkänn nödvändiga')")
            print("✅ Accepted mandatory cookies.")
        except Exception as e:
            print("⚠️ Cookie popup not found or already accepted.")

    def close(self):
        self.browser.close()
        self.playwright.stop()

    def login(self):
        try:
            self.page.wait_for_selector("button[title='Boka prov']", timeout=10000)
            self.page.click("button[title='Boka prov']")
            print("✅ Clicked 'Boka prov' button.")
        except Exception as e:
            print(f"❌ Error clicking 'Boka prov': {e}")

    def enter_social_security(self):
        try:
            self.page.wait_for_selector("text='Fortsätt'", timeout=10000)
            self.page.click("text='Fortsätt'")
            time.sleep(5)
        except Exception as e:
            print(f"❌ Error during BankID login: {e}")
            print("⏳ Waiting 1 minute before retrying...")
            time.sleep(60)

    def select_exam(self):
        try:
            self.page.wait_for_selector(f"[title='{config.license_type}']", timeout=10000)
            self.page.click(f"[title='{config.license_type}']")
            print(f"✅ Selected license type: {config.license_type}")
            return True
        except:
            print("❌ Could not find license type. Check config.license_type.")
            return False

    def select_exam_type(self):
        try:
            print("🔍 Selecting exam type...")
            dropdown = self.page.locator('#examination-type-select')
            dropdown.wait_for(state="visible", timeout=5000)
            dropdown.click()
            self.page.wait_for_timeout(500)

            option = self.page.locator(f"text={config.exam}")
            option.wait_for(state="visible", timeout=3000)
            option.click()
            print(f"✅ Selected exam type: {config.exam}")
        except Exception as e:
            print(f"❌ Error selecting exam type: {e}")

    def select_rent_or_language(self, rent_or_language):
        try:
            self.page.select_option("#vehicle-select", label=rent_or_language)
            print(f"✅ Selected vehicle/language: {rent_or_language}")
        except:
            print(f"❌ Could not select rent/language option: {rent_or_language}")

    def open_location_selector(self):
        try:
            print("🔍 Looking for location selector...")
            button = self.page.locator('#select-location-search')

            if button.count() > 0:
                button.wait_for(state="visible", timeout=10000)
                button.scroll_into_view_if_needed()
                self.page.wait_for_timeout(1000)
                button.click(force=True)
                print("✅ Opened location selector.")
                return
            else:
                fallback = self.page.locator('button[title="Välj provort"]')
                if fallback.count() > 0:
                    fallback.wait_for(state="visible", timeout=10000)
                    fallback.scroll_into_view_if_needed()
                    self.page.wait_for_timeout(1000)
                    fallback.click(force=True)
                    print("✅ Opened location selector (fallback).")
                else:
                    print("❌ Could not find location selector.")
        except Exception as e:
            print(f"❌ Error opening location selector: {e}")

    def select_location(self, location):
        try:
            self.open_location_selector()
            self.page.wait_for_timeout(1000)

            # Click all "Ta bort" buttons if present BEFORE selecting new location
            remove_buttons = self.page.locator("text=Ta bort")
            remove_count = remove_buttons.count()
            if remove_count > 0:
                for i in range(remove_count):
                    try:
                        remove_buttons.nth(i).click()
                        print(f"🗑️ Clicked 'Ta bort' button #{i+1} to remove previous selection.")
                        self.page.wait_for_timeout(500)
                    except Exception as remove_err:
                        print(f"❌ Failed to click 'Ta bort' button #{i+1}: {remove_err}")
            else:
                print("ℹ️ No 'Ta bort' buttons found; no previous selections to remove.")

            # Now type and select the location
            input_field = self.page.locator("#location-search-input")
            input_field.wait_for(state="visible", timeout=8000)

            self.page.evaluate("""
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

            self.page.wait_for_timeout(1500)

            items = self.page.locator(".select-item.mb-2")
            items.wait_for(state="visible", timeout=8000)
            count = items.count()

            if count == 0:
                print(f"⚠️ No selectable items found for location: {location}")
                return

            for i in range(count):
                try:
                    items.nth(i).click()
                    print(f"✅ Selected location item {i+1} for: {location}")
                    self.page.wait_for_timeout(500)
                except Exception as click_err:
                    print(f"❌ Failed to click item {i+1} for {location}: {click_err}")

            self.page.locator("text=Bekräfta").click()
            print("✅ Confirmed location selection.")

        except Exception as e:
            print(f"❌ Error selecting location '{location}': {e}")


    def select_time(self, first_date, last_date):
        try:
            self.page.wait_for_selector("text='Lediga provtider'", timeout=10000)
            start = datetime.strptime(first_date, '%Y-%m-%d').date()
            end = datetime.strptime(last_date, '%Y-%m-%d').date()

            while start <= end:
                try:
                    date_element = self.page.query_selector(f"text={str(start)}")
                    if date_element:
                        times.append(date_element.text_content())
                except:
                    pass
                start += timedelta(days=1)
        except:
            print("❌ Error during time selection.")

    def book_exam(self):
        try:
            book_button = self.page.wait_for_selector("button.btn.btn-lg.btn-primary.col-xs-12", timeout=10000)
            book_button.click()
            print("✅ Clicked 'Book' button.")
        except:
            print("❌ Book button not found.")

    def refresh_page(self):
        self.page.reload()

def find_exam(driver):
    driver.login()
    time.sleep(5)
    driver.enter_social_security()
    time.sleep(5)
    
    if driver.select_exam():
        for location in config.locations:
            try:
                driver.select_exam_type()
                time.sleep(3)  # slower here
                for rent_or_language in config.rent_or_language:
                    driver.select_rent_or_language(rent_or_language)
                    time.sleep(3)  # slower here
                    driver.select_location(location)
                    time.sleep(3)  # slower here

                    # Select time range as before to populate times list
                    for i in range(0, len(config.dates), 2):
                        driver.select_time(config.dates[i], config.dates[i + 1])
                        time.sleep(3)  # slower here

                    if times:
                        print(f"📅 Found {len(times)} time slots for {location} and {rent_or_language}.")
                        
                        # Click the first "Välj" button
                        try:
                            driver.page.wait_for_selector("button.btn.btn-primary:has-text('Välj')", timeout=10000)
                            buttons = driver.page.query_selector_all("button.btn.btn-primary:has-text('Välj')")
                            if buttons:
                                buttons[0].click()
                                print("✅ Clicked first 'Välj' button.")
                                time.sleep(4)  # longer pause
                            else:
                                print("❌ No 'Välj' buttons found.")
                                continue
                        except Exception as e:
                            print(f"❌ Error clicking 'Välj' button: {e}")
                            continue
                        
                        # Click the "Gå vidare" button
                        try:
                            driver.page.wait_for_selector("#cart-continue-button", timeout=10000)
                            driver.page.click("#cart-continue-button")
                            print("✅ Clicked 'Gå vidare' button.")
                            time.sleep(4)  # longer pause
                        except Exception as e:
                            print(f"❌ Error clicking 'Gå vidare' button: {e}")
                            continue
                        
                        # Click the "Betala senare" button
                        try:
                            driver.page.wait_for_selector("#pay-invoice-button", timeout=10000)
                            driver.page.click("#pay-invoice-button")
                            print("✅ Clicked 'Betala senare' button.")
                            
                            # Close browser and stop script immediately after booking step
                            time.sleep(3)  # small pause before closing
                            driver.close()
                            print("👋 Booking completed, exiting script.")
                            exit(0)

                        except Exception as e:
                            print(f"❌ Error clicking 'Betala senare' button: {e}")

                    else:
                        print(f"⚠️ No available time slots found for {location} and {rent_or_language}.")

            except Exception as e:
                print(f"❌ Error processing location '{location}': {e}")
            time.sleep(3)  # slower here too



if __name__ == '__main__':
    driver = PlaywrightDriver()
    try:
        find_exam(driver)
    finally:
        driver.close()
