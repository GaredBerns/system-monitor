#!/usr/bin/env python3
"""Firefox worker for registration - uses Selenium + geckodriver.

Supports two modes:
1. Launch Firefox with custom profile (with VPN extension pre-installed)
2. Attach to existing Firefox via Marionette (remote debugging)

To use existing Firefox:
1. Start Firefox with: firefox -marionette -start-debugger-server 2828
2. Or set in about:config: marionette.default.port = 2828
"""

import sys
import json
import os
import time
import random
import string
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import centralized utilities
from src.utils.common import generate_identity
from src.mail.tempmail import mail_manager

from src.utils.logger import get_logger, log_function, log_api_endpoint, LogContext

# Initialize logger
log = get_logger(__name__)


try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not installed. Run: pip install selenium")


class FirefoxDriver:
    """Wrapper for Firefox WebDriver with profile support."""
    
    def __init__(self, headless=False, profile_path=None, marionette_port=None, log_fn=None):
        self.driver = None
        self.headless = headless
        self.profile_path = profile_path
        self.marionette_port = marionette_port
        self.log = log_fn or (lambda x: None)
        
    def start(self):
        """Start Firefox driver."""
        if not SELENIUM_AVAILABLE:
            raise RuntimeError("Selenium not installed")
        
        options = FirefoxOptions()
        
        options.binary_location = "/usr/bin/firefox-esr"
        
        # Download settings (same as batch_legacy.py)
        download_dir = str(Path.home() / "Downloads")
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", download_dir)
        options.set_preference("browser.download.useDownloadDir", True)
        options.set_preference("browser.download.always_ask_before_handling_new_types", False)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/json,application/octet-stream,text/json")
        
        if self.headless:
            options.add_argument("--headless")
        
        # Window size
        options.add_argument("--width=390")
        options.add_argument("--height=844")
        
        # Custom profile with VPN extension
        if self.profile_path and Path(self.profile_path).exists():
            self.log(f"Using profile: {self.profile_path}")
            options.add_argument("-profile")
            options.add_argument(self.profile_path)
        
        # Marionette settings for remote debugging
        if self.marionette_port:
            self.log(f"Connecting to Firefox on port {self.marionette_port}")
            options.set_preference("marionette.port", self.marionette_port)
            options.add_argument("--connect-existing")
        
        # Fast startup
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("useAutomationExtension", False)
        
        # Try to find geckodriver
        geckodriver_paths = [
            str(Path.home() / ".cache" / "selenium" / "geckodriver" / "linux64" / "0.36.0" / "geckodriver"),
            "/usr/local/bin/geckodriver",
            "/usr/bin/geckodriver",
            "/opt/geckodriver",
            str(Path.home() / ".local" / "bin" / "geckodriver"),
            "geckodriver",  # in PATH
        ]
        
        executable_path = None
        for path in geckodriver_paths:
            if Path(path).exists() or path == "geckodriver":
                executable_path = path
                break
        
        try:
            if executable_path and executable_path != "geckodriver":
                from selenium.webdriver.firefox.service import Service
                service = Service(executable_path=executable_path)
                self.driver = webdriver.Firefox(options=options, service=service)
            else:
                self.driver = webdriver.Firefox(options=options)
            
            self.log("✓ Firefox started")
            return self.driver
            
        except Exception as e:
            self.log(f"✗ Firefox start failed: {e}")
            return None
    
    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def get(self, url):
        return self.driver.get(url)
    
    def find_element(self, by, value, timeout=10):
        if timeout:
            wait = WebDriverWait(self.driver, timeout)
            return wait.until(EC.presence_of_element_located((by, value)))
        return self.driver.find_element(by, value)
    
    def find_elements(self, by, value):
        return self.driver.find_elements(by, value)
    
    def execute_script(self, script, *args):
        return self.driver.execute_script(script, *args)
    
    @property
    def current_url(self):
        return self.driver.current_url
    
    @property
    def page_source(self):
        return self.driver.page_source


def kaggle_register_firefox(identity, email_data, log_fn, headless=False, 
                            profile_path=None, marionette_port=None, proxy=None):
    """Kaggle registration using Firefox."""
    
    log_fn("Starting Firefox...")
    
    driver = FirefoxDriver(
        headless=headless,
        profile_path=profile_path,
        marionette_port=marionette_port,
        log_fn=log_fn
    )
    
    if not driver.start():
        return {"verified": False, "error": "firefox_init_failed", "error_type": "browser"}
    
    try:
        log_fn("Loading Kaggle...")
        driver.get("https://www.kaggle.com/account/login?phase=emailRegister&returnUrl=%2F")
        
        wait = WebDriverWait(driver.driver, 15)
        
        # Wait for page ready
        time.sleep(1)
        log_fn("✓ Page loaded")
        
        # Fill email - FAST
        try:
            email_input = driver.find_element(By.NAME, "email", timeout=10)
            email_input.clear()
            email_input.send_keys(identity['email'])  # Fast send
            log_fn(f"✓ Email: {identity['email']}")
        except Exception as e:
            log_fn(f"✗ Email field not found: {e}")
            driver.quit()
            return {"verified": False, "error": "email_field_not_found"}
        
        # Fill password - FAST
        try:
            pwd_input = driver.find_element(By.NAME, "password", timeout=5)
            pwd_input.clear()
            pwd_input.send_keys(identity['password'])  # Fast send
            log_fn("✓ Password filled")
        except Exception as e:
            log_fn(f"✗ Password field not found: {e}")
        
        # Fill display name - FAST
        display_name = identity["username"].replace("_", " ")
        try:
            name_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder*='full name' i]", timeout=3)
            name_input.clear()
            name_input.send_keys(display_name)  # Fast send
            log_fn(f"✓ Display name: {display_name}")
        except Exception as e:
            log_fn(f"⚠ Display name skipped: {e}")
        
        time.sleep(0.5)
        
        log_fn(">>> Clicking captcha checkbox...")
        
        # Try to click reCAPTCHA checkbox automatically
        try:
            # Switch to recaptcha iframe and click checkbox
            iframes = driver.driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    if "recaptcha" in iframe.get_attribute("src") or iframe.get_attribute("title", "").lower().find("captcha") >= 0:
                        driver.driver.switch_to.frame(iframe)
                        checkbox = driver.driver.find_element(By.CSS_SELECTOR, ".recaptcha-checkbox-border, #recaptcha-anchor")
                        if checkbox:
                            checkbox.click()
                            log_fn("✓ Captcha checkbox clicked")
                        driver.driver.switch_to.default_content()
                        break
                except:
                    driver.driver.switch_to.default_content()
        except Exception as e:
            log_fn(f"⚠ Captcha click failed: {e}")
        
        time.sleep(2)
        
        log_fn(">>> Solve captcha if needed, then registration will continue...")
        
        # Wait for user to solve captcha (up to 3 minutes)
        captcha_solved = False
        for i in range(180):  # 3 minutes
            time.sleep(1)
            
            # Check if form is ready to submit
            try:
                # Look for recaptcha response or submit button enabled
                state = driver.execute_script("""
                    var recaptcha = document.querySelector('textarea[name="g-recaptcha-response"]');
                    var submit = document.querySelector('button[type="submit"]');
                    return {
                        recaptcha: recaptcha && recaptcha.value && recaptcha.value.length > 10,
                        submitEnabled: submit && !submit.disabled
                    };
                """)
                
                if state.get('recaptcha') or (state.get('submitEnabled') and i > 10):
                    if i % 15 == 0:
                        log_fn(f"[CAPTCHA] {i}s elapsed...")
                    
                    if state.get('recaptcha') and state.get('submitEnabled'):
                        log_fn("✓ Captcha appears solved")
                        captcha_solved = True
                        break
                        
            except Exception as e:
                pass
        
        # Try to submit
        try:
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']", timeout=5)
            submit_btn.click()
            log_fn("✓ Submitted")
        except:
            # Try Enter key
            try:
                driver.find_element(By.NAME, "email").send_keys(Keys.RETURN)
                log_fn("✓ Submitted (Enter)")
            except:
                log_fn("✗ Submit failed")
        
        time.sleep(3)
        
        # Handle "I Agree" if appears
        try:
            agree_btn = driver.execute_script("""
                for(var b of document.querySelectorAll('button'))
                    if(b.textContent.trim() === 'I Agree') { b.click(); return true; }
                return false;
            """)
            if agree_btn:
                log_fn("✓ I Agree clicked")
                time.sleep(1)
        except:
            pass
        
        # Dismiss any popups/modals after registration
        try:
            log_fn("Dismissing popups...")
            # Click dimiss/close on any modal
            for _ in range(3):
                dismissed = driver.execute_script('''
                // Try various close buttons
                var closeBtns = document.querySelectorAll('[aria-label="Close"], [aria-label="Dismiss"], button.close, .modal-close, .dismiss');
                for(var btn of closeBtns) {
                    btn.click();
                    return 'clicked';
                }
                // Try clicking outside modal
                var overlay = document.querySelector('.modal-overlay, .MuiBackdrop-root, [role="presentation"]');
                if(overlay) { overlay.click(); return 'overlay_clicked'; }
                return null;
                ''')
                if dismissed:
                    log_fn(f"✓ Dismissed: {dismissed}")
                    time.sleep(0.5)
                else:
                    break
        except:
            pass
        
        # Wait for verification
        log_fn("Waiting for verification email...")
        code_found = {"value": None}
        link_found = {"value": None}
        
        import threading
        
        def check_email():
            if email_data and email_data.get("email"):
                email_addr = email_data["email"]
                start = time.time()
                while time.time() - start < 120 and not code_found["value"] and not link_found["value"]:
                    time.sleep(2)
                    try:
                        inbox = mail_manager.check_inbox(email_addr)
                        for msg in inbox:
                            subj = (msg.get("subject") or "").lower()
                            if "kaggle" not in subj and "verif" not in subj:
                                continue
                            body = (msg.get("body") or "") + "\n" + (msg.get("html") or "")
                            code = mail_manager.extract_code(body) if body else ""
                            link = mail_manager.extract_link(body) if body else ""
                            if link and "kaggle.com" in link:
                                link_found["value"] = link
                                log_fn(f"✓ Link found: {link[:60]}...")
                                return
                            if code and len(code) >= 4:
                                code_found["value"] = code
                                log_fn(f"✓ Code found: {code}")
                                return
                    except Exception as ex:
                        pass
        
        email_thread = threading.Thread(target=check_email, daemon=True)
        email_thread.start()
        
        # Wait for email
        start_wait = time.time()
        while time.time() - start_wait < 120 and not code_found["value"] and not link_found["value"]:
            time.sleep(1)
        
        # Verify with link
        if link_found["value"]:
            log_fn(f"Opening verification link...")
            driver.get(link_found["value"])
            time.sleep(3)
            log_fn("✓ Verification link opened")
        
        # Or enter code
        elif code_found["value"]:
            log_fn(f"Entering code: {code_found['value']}")
            try:
                code_input = driver.find_element(By.CSS_SELECTOR, 
                    "input[name*='code'], input[placeholder*='code'], input[maxlength='6']", timeout=5)
                code_input.clear()
                code_input.send_keys(code_found["value"])
                time.sleep(0.5)
                
                # Click Next
                next_btn = driver.execute_script("""
                    for(var b of document.querySelectorAll('button'))
                        if(b.textContent.trim().toLowerCase() === 'next') { b.click(); return true; }
                    return false;
                """)
                if next_btn:
                    log_fn("✓ Next clicked")
                time.sleep(2)
            except Exception as e:
                log_fn(f"Code entry failed: {e}")
        
        # Go to settings for API key
        log_fn("Navigating to settings...")
        driver.get("https://www.kaggle.com/settings")
        time.sleep(2)
        
        # ===== 1. Expire existing tokens =====
        log_fn("Expiring existing tokens...")
        driver.execute_script("window.scrollTo(0, 600);")
        time.sleep(1)
        
        expired_count = 0
        for attempt in range(5):
            # Find more_vert button
            found = driver.execute_script('''
            var buttons = document.querySelectorAll('button[aria-label="Actions"], button[title="Actions"]');
            for(var btn of buttons) {
                if(btn.textContent.includes('more_vert')) {
                    btn.click();
                    return 'menu_opened';
                }
            }
            var btns = document.querySelectorAll('button.google-symbols');
            for(var btn of btns) {
                if(btn.textContent.includes('more_vert')) {
                    btn.click();
                    return 'menu_opened';
                }
            }
            return null;
            ''')
            
            if not found:
                break
            
            time.sleep(0.5)
            
            # Click Expire Token
            expired = driver.execute_script('''
            var items = document.querySelectorAll('li[role="menuitem"], .MuiMenuItem-root');
            for(var item of items) {
                if(item.textContent.includes('Expire Token')) {
                    item.click();
                    return 'expire_clicked';
                }
            }
            return null;
            ''')
            
            if not expired:
                break
            
            time.sleep(0.5)
            
            # Click Expire button to confirm
            confirmed = driver.execute_script('''
            var btns = document.querySelectorAll('button');
            for(var btn of btns) {
                if(btn.textContent.trim() === 'Expire') {
                    btn.click();
                    return 'confirmed';
                }
            }
            return null;
            ''')
            
            if confirmed:
                expired_count += 1
                log_fn(f"✓ Expired token #{expired_count}")
                time.sleep(1)
            else:
                break
        
        if expired_count:
            log_fn(f"✓ Expired {expired_count} tokens")
        
        # ===== 2. Generate New Token =====
        log_fn("Generating New Token...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        
        # Click Generate New Token
        result = driver.execute_script('''
        var buttons = document.querySelectorAll('button');
        for(var b of buttons) {
            if(b.textContent.includes('Generate New Token')) {
                b.click();
                return 'clicked';
            }
        }
        return null;
        ''')
        
        new_token = None
        if not result:
            log_fn("✗ Generate New Token button not found!")
        else:
            log_fn("✓ Clicked Generate New Token")
            time.sleep(1)
            
            # Fill token name "now"
            name_result = driver.execute_script('''
            var inp = document.querySelector('input[placeholder="Enter Token Name"]');
            if(inp) {
                inp.focus();
                inp.value = 'now';
                inp.dispatchEvent(new Event('input', {bubbles: true}));
                return 'found';
            }
            return null;
            ''')
            
            if name_result:
                log_fn("✓ Set token name to 'now'")
            else:
                log_fn("⚠ Name input not found")
            
            time.sleep(0.3)
            
            # Click Generate
            gen_result = driver.execute_script('''
            var buttons = document.querySelectorAll('button');
            for(var b of buttons) {
                if(b.textContent.trim() === 'Generate') {
                    b.click();
                    return 'clicked';
                }
            }
            return null;
            ''')
            
            if gen_result:
                log_fn("✓ Clicked Generate")
            else:
                log_fn("✗ Generate button not found")
            
            time.sleep(1)
            
            # Extract API Token
            new_token = driver.execute_script('''
            var inp = document.querySelector('input[placeholder="API TOKEN"]');
            if(inp) return inp.value;
            return null;
            ''')
            
            if new_token:
                log_fn(f"✓ API Token: {new_token[:20]}...")
            else:
                log_fn("⚠ API Token not found")
            
            # Click Close
            driver.execute_script('''
            var buttons = document.querySelectorAll('button');
            for(var b of buttons) {
                if(b.textContent.trim() === 'Close') {
                    b.click();
                    return 'clicked';
                }
            }
            return null;
            ''')
            time.sleep(1)
        
        # ===== 3. Create Legacy API Key =====
        log_fn("Creating Legacy API Key...")
        
        # Click Create Legacy API Key
        result = driver.execute_script('''
        var buttons = document.querySelectorAll('button');
        for(var b of buttons) {
            if(b.textContent.includes('Create Legacy API Key')) {
                b.click();
                return 'clicked';
            }
        }
        return null;
        ''')
        
        legacy_key = None
        kaggle_username = None
        
        if not result:
            log_fn("✗ Create Legacy API Key button not found")
        else:
            log_fn("✓ Clicked Create Legacy API Key")
            time.sleep(1)
            
            # Click Continue
            cont_result = driver.execute_script('''
            var buttons = document.querySelectorAll('button');
            for(var b of buttons) {
                if(b.textContent.trim() === 'Continue') {
                    b.click();
                    return 'clicked';
                }
            }
            return null;
            ''')
            
            if cont_result:
                log_fn("✓ Clicked Continue")
            else:
                log_fn("⚠ Continue button not found")
            
            time.sleep(3)  # Wait for download
        
        # ===== 4. Read kaggle.json =====
        import glob
        import json as json_mod
        
        downloads_dir = str(Path.home() / "Downloads")
        
        # Wait for download
        for _ in range(10):
            time.sleep(0.3)
            files = glob.glob(os.path.join(downloads_dir, "kaggle*.json"))
            if files:
                kaggle_json_path = max(files, key=os.path.getctime)
                try:
                    with open(kaggle_json_path) as f:
                        kaggle_data = json_mod.load(f)
                    legacy_key = kaggle_data.get("key", "")
                    kaggle_username = kaggle_data.get("username", "")
                    log_fn(f"✓ Legacy Key: {legacy_key[:20]}...")
                    log_fn(f"✓ Username: {kaggle_username}")
                    os.remove(kaggle_json_path)
                except Exception as e:
                    log_fn(f"Error reading kaggle.json: {e}")
                break
        
        driver.quit()
        
        if legacy_key or new_token:
            return {
                "verified": True,
                "api_key": legacy_key or new_token,
                "api_key_legacy": legacy_key,
                "api_key_new": new_token,
                "kaggle_username": kaggle_username,
                "error_type": "success"
            }
        
        return {"verified": False, "error": "api_key_failed"}
        
    except Exception as e:
        log_fn(f"ERROR: {e}")
        traceback.print_exc()
        try:
            driver.quit()
        except:
            pass
        return {"verified": False, "error": str(e), "error_type": "unknown"}


def devin_ai_register_firefox(identity, email_data, log_fn, headless=False, profile_path=None, marionette_port=None, proxy=None):
    """Devin AI registration via Firefox - Auth0 passwordless flow."""
    import threading
    
    driver_wrapper = FirefoxDriver(headless=headless, profile_path=profile_path, marionette_port=marionette_port, log_fn=log_fn)
    
    try:
        log_fn("Starting Firefox...")
        driver = driver_wrapper.start()
        if not driver:
            return {"verified": False, "error": "Firefox failed to start", "error_type": "browser"}
        log_fn("✓ Firefox started")
        
        # Load Devin AI login page
        log_fn("Loading Devin AI login...")
        driver.get("https://app.devin.ai/login")
        time.sleep(3)
        
        # Wait for Auth0 redirect
        log_fn(f"URL: {driver.current_url}")
        
        # Fill email - Auth0 uses #username
        log_fn("Filling email...")
        try:
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#username"))
            )
            email_input.clear()
            email_input.send_keys(identity['email'])
            log_fn(f"✓ Email filled: {identity['email']}")
        except Exception as e:
            log_fn(f"✗ Email field error: {e}")
            driver.quit()
            return {"verified": False, "error": "email_field_not_found", "error_type": "browser"}
        
        time.sleep(0.5)
        
        # Click Continue
        log_fn("Clicking Continue...")
        try:
            btns = driver.find_elements(By.TAG_NAME, "button")
            for btn in btns:
                if btn.is_displayed() and "continue" in btn.text.lower():
                    btn.click()
                    log_fn("✓ Continue clicked")
                    break
        except Exception as e:
            log_fn(f"Continue click error: {e}")
        
        time.sleep(3)
        log_fn(f"Current URL: {driver.current_url}")
        
        # Start email monitoring for verification code
        code_found = {"value": None}
        
        def check_email_async():
            if email_data and email_data.get("email"):
                email_addr = email_data["email"]
                log_fn(f"Monitoring inbox for {email_addr}")
                
                start = time.time()
                poll_count = 0
                while time.time() - start < 120 and not code_found["value"]:
                    time.sleep(2)
                    poll_count += 1
                    try:
                        inbox = mail_manager.check_inbox(email_addr)
                        
                        if poll_count % 5 == 0:
                            log_fn(f"Poll #{poll_count}: {len(inbox)} messages")
                        
                        for msg in inbox:
                            subj = (msg.get("subject") or "").lower()
                            from_addr = (msg.get("from") or "").lower()
                            
                            if "devin" not in subj and "verif" not in subj and "code" not in subj and "otp" not in subj and "devin" not in from_addr:
                                continue
                            
                            body = (msg.get("body") or "") + "\n" + (msg.get("html") or "")
                            code = mail_manager.extract_code(body) if body else ""
                            
                            if code and len(code) >= 4:
                                code_found["value"] = code
                                log_fn(f"✓ CODE FOUND: {code}")
                                return
                    
                    except Exception as ex:
                        if poll_count % 10 == 0:
                            log_fn(f"⚠ Error: {str(ex)[:60]}")
                
                if not code_found["value"]:
                    log_fn(f"✗ Email timeout")
        
        email_thread = threading.Thread(target=check_email_async, daemon=True)
        email_thread.start()
        
        # Wait for code
        log_fn("Waiting for verification code...")
        start_wait = time.time()
        while time.time() - start_wait < 120 and not code_found["value"]:
            time.sleep(1)
            elapsed = int(time.time() - start_wait)
            if elapsed % 15 == 0 and elapsed > 0:
                log_fn(f"[{elapsed}s] Waiting...")
        
        if code_found["value"]:
            log_fn(f"Entering verification code: {code_found['value']}")
            
            time.sleep(1)
            
            # Find code input
            code_selectors = [
                "input[autocomplete='one-time-code']",
                "input[name*='code']",
                "input[name*='otp']",
                "input[type='text'][maxlength='6']",
                "input[type='text'][maxlength='8']",
            ]
            
            code_entered = False
            for sel in code_selectors:
                try:
                    inputs = driver.find_elements(By.CSS_SELECTOR, sel)
                    for inp in inputs:
                        if inp.is_displayed() and inp.is_enabled():
                            inp.clear()
                            inp.send_keys(code_found["value"])
                            log_fn(f"✓ Code entered")
                            code_entered = True
                            break
                    if code_entered:
                        break
                except:
                    continue
            
            if not code_entered:
                # Try generic text input
                try:
                    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
                    for inp in inputs:
                        if inp.is_displayed():
                            inp.clear()
                            inp.send_keys(code_found["value"])
                            log_fn("✓ Code entered via generic input")
                            break
                except:
                    pass
            
            time.sleep(1)
            
            # Submit
            try:
                btns = driver.find_elements(By.TAG_NAME, "button")
                for btn in btns:
                    if btn.is_displayed() and ("continue" in btn.text.lower() or "verify" in btn.text.lower()):
                        btn.click()
                        log_fn("✓ Submit clicked")
                        break
            except:
                pass
            
            time.sleep(3)
        
        # Check result
        log_fn("Checking result...")
        page_url = driver.current_url.lower()
        
        verified = False
        if "devin.ai" in page_url and "login" not in page_url and "auth" not in page_url and "challenge" not in page_url:
            verified = True
            log_fn("✓ Redirected to app - success!")
        elif code_found["value"]:
            verified = True
            log_fn("✓ Code was entered")
        
        driver.quit()
        log_fn("✓ Browser closed")
        
        if verified:
            log_fn("=" * 50)
            log_fn("✓✓✓ SUCCESS! Devin AI account registered ✓✓✓")
            log_fn("=" * 50)
            return {
                "verified": True,
                "email": identity["email"],
                "password": identity.get("password", ""),
                "username": identity["username"],
                "error_type": "success"
            }
        
        log_fn("✗ Registration incomplete")
        return {"verified": False, "error": "no_code_received", "error_type": "email"}
    
    except Exception as e:
        log_fn(f"ERROR: {e}")
        traceback.print_exc()
        try:
            driver.quit()
        except:
            pass
        return {"verified": False, "error": str(e), "error_type": "unknown"}


def run_registration_firefox(platform: str, headless: bool = True, 
                             profile_path: str = None, marionette_port: int = None,
                             proxy: str = None, input_data: dict = None):
    """Run single registration using Firefox and return result."""
    
    start_time = time.time()
    result = {
        "success": False,
        "identity": None,
        "email": None,
        "account": None,
        "logs": [],
        "error": None,
        "error_type": None,
        "duration_sec": 0,
    }
    
    def log(msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        result["logs"].append(f"[{ts}] [{level}] {msg}")
        try:
            print(f"[{ts}] [Firefox] {msg}", flush=True)
        except (BrokenPipeError, IOError):
            pass  # Ignore if stdout is closed (Flask context)
    
    if not SELENIUM_AVAILABLE:
        result["error"] = "Selenium not installed. Run: pip install selenium"
        result["error_type"] = "config"
        return result
    
    try:
        # Generate or use provided identity
        if input_data and input_data.get("identity"):
            identity = input_data["identity"]
            log(f"Identity: {identity['username']}")
        else:
            identity = generate_identity()
            log(f"Identity: {identity['username']}")
        result["identity"] = identity
        
        # Email
        if input_data and input_data.get("email"):
            email = input_data["email"]
            email_data = input_data.get("email_data", {})
            log(f"Email: {email}")
        else:
            log("Creating temp email...")
            email_data = mail_manager.create_email()
            email = email_data["email"]
            log(f"✓ Email: {email}")
        identity["email"] = email
        result["email"] = email
        
        # Run registration
        log(">>> Starting browser...")
        if platform == "kaggle":
            account = kaggle_register_firefox(
                identity, email_data, log, 
                headless=headless,
                profile_path=profile_path,
                marionette_port=marionette_port,
                proxy=proxy
            )
        elif platform == "devin_ai":
            account = devin_ai_register_firefox(
                identity, email_data, log,
                headless=headless,
                profile_path=profile_path,
                marionette_port=marionette_port,
                proxy=proxy
            )
        else:
            account = {"verified": False, "error": f"Platform '{platform}' not implemented", "error_type": "config"}
        
        result["account"] = account
        result["success"] = account.get("verified", False)
        
        if account.get("api_key"):
            result["api_key"] = account["api_key"]
        if account.get("api_key_legacy"):
            result["api_key_legacy"] = account["api_key_legacy"]
        if account.get("api_key_new"):
            result["api_key_new"] = account["api_key_new"]
        if account.get("kaggle_username"):
            result["kaggle_username"] = account["kaggle_username"]
        
        if not result["success"] and account.get("error"):
            result["error"] = account["error"]
            result["error_type"] = account.get("error_type", "unknown")
    
    except Exception as e:
        error_str = str(e)
        result["error"] = error_str
        result["logs"].append(f"ERROR: {error_str}")
        result["logs"].append(traceback.format_exc()[-500:])
        
        if "firefox" in error_str.lower() or "gecko" in error_str.lower():
            result["error_type"] = "browser"
        else:
            result["error_type"] = "unknown"
    
    result["duration_sec"] = round(time.time() - start_time, 1)
    return result


if __name__ == "__main__":
    # Run as: python firefox_worker.py kaggle [headless] [profile_path] [marionette_port]
    platform = sys.argv[1] if len(sys.argv) > 1 else "kaggle"
    headless = sys.argv[2].lower() == "true" if len(sys.argv) > 2 else False
    profile_path = sys.argv[3] if len(sys.argv) > 3 else None
    marionette_port = int(sys.argv[4]) if len(sys.argv) > 4 else None
    
    result = run_registration_firefox(platform, headless, profile_path, marionette_port)
    print("---RESULT---")
    print(json.dumps(result))
