#!/usr/bin/env python3
"""
Kaggle GPU Activator via Selenium + Firefox (same as firefox_worker.py)
Requires phone verification for GPU access - uses SMS services.
"""

import sys
import json
import time
import os
from pathlib import Path

# Selenium + Firefox (same setup as firefox_worker.py)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Selenium not installed. Run: pip install selenium")

# SMS verification
try:
    from sms_verify import SMSVerifier, verify_kaggle_phone
    SMS_AVAILABLE = True
except ImportError:
    SMS_AVAILABLE = False


def create_firefox_driver(headless=True, profile_path=None, log_fn=None):
    """Create Firefox driver - same as firefox_worker.py."""
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("Selenium not installed")
    
    log = log_fn or (lambda x: None)
    options = FirefoxOptions()
    
    # Use system Firefox
    options.binary_location = "/usr/bin/firefox-esr"
    
    # Download settings
    download_dir = str(Path.home() / "Downloads")
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.dir", download_dir)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference("browser.download.always_ask_before_handling_new_types", False)
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/json,application/octet-stream,text/json")
    
    if headless:
        options.add_argument("--headless")
    
    # Window size
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    
    # Custom profile with VPN extension
    if profile_path and Path(profile_path).exists():
        log(f"Using profile: {profile_path}")
        options.add_argument("-profile")
        options.add_argument(profile_path)
    
    # Anti-detect
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    options.set_preference("general.useragent.override", "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0")
    
    driver = webdriver.Firefox(options=options)
    driver.implicitly_wait(10)
    
    return driver


def activate_gpu_for_kernel(email: str, password: str, kernel_slug: str, headless=True, profile_path=None):
    """
    Activate GPU for a Kaggle kernel via browser automation.
    
    Steps:
    1. Login to Kaggle
    2. Navigate to kernel
    3. Set Session Options -> Environment -> Always use latest
    4. Refresh page
    5. Set Accelerator -> GPU
    6. Save and Run
    
    Returns: (success: bool, screenshot_path: str)
    """
    log = lambda x: print(f"[GPU Activator] {x}")
    
    driver = None
    try:
        log(f"Creating Firefox driver (headless={headless})...")
        driver = create_firefox_driver(headless=headless, profile_path=profile_path, log_fn=log)
        
        # Step 1: Login - using same code as server.py account_login
        log("[1/8] Navigating to Kaggle login...")
        driver.get("https://www.kaggle.com/account/login?phase=emailSignIn")
        time.sleep(3)
        
        log(f"[2/8] Logging in as {email}...")
        
        wait = WebDriverWait(driver, 15)
        
        # Click Email tab (same as server.py)
        driver.execute_script("""
        for(var b of document.querySelectorAll('button, div[role="tab"]'))
            if(b.textContent.includes('Email')) { b.click(); return true; }
        return false;
        """)
        time.sleep(0.5)
        
        # Fill email (same as server.py)
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_input.click()
        email_input.clear()
        email_input.send_keys(email)
        
        # Fill password (same as server.py)
        pwd_input = driver.find_element(By.NAME, "password")
        pwd_input.click()
        pwd_input.clear()
        pwd_input.send_keys(password)
        
        time.sleep(0.5)
        
        # Submit (same as server.py)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        log(f"  Submitted login form")
        
        # Wait for login
        time.sleep(5)
        log("[3/8] Logged in, checking page...")
        
        # Check if login succeeded
        if "login" in driver.current_url.lower():
            log("Login failed - still on login page")
            # Take screenshot for debugging
            screenshot_path = Path('/mnt/F/C2_server/data') / f'login_failed_{int(time.time())}.png'
            driver.save_screenshot(str(screenshot_path))
            return False, str(screenshot_path)
        
        # Step 2: Check if phone verification needed and do it
        log("[4/8] Checking phone verification status...")
        
        # Navigate to phone verification page to check
        driver.get(f"https://www.kaggle.com/account/phone/number?phoneVerifyAction=notebook-features&returnUrl=/code/{kernel_slug}/edit")
        time.sleep(3)
        
        # Check if already verified or needs verification
        page_html = driver.page_source
        if "phone verified" in page_html.lower() or "verified" in driver.current_url.lower():
            log("  Phone already verified, continuing...")
        elif "phone" in driver.current_url.lower() or "verify" in page_html.lower():
            # Need phone verification
            log("  Phone verification required!")
            
            sms_api_key = os.environ.get("GRIZZLY_API_KEY", "")
            if sms_api_key and SMS_AVAILABLE:
                log("  Starting SMS verification...")
                success, msg = verify_kaggle_phone(driver, sms_api_key, log)
                if success:
                    log(f"  ✓ Phone verified: {msg}")
                    # Navigate back to kernel
                    driver.get(f'https://www.kaggle.com/code/{kernel_slug}')
                    time.sleep(3)
                else:
                    log(f"  ✗ Phone verification failed: {msg}")
                    screenshot_path = Path('/mnt/F/C2_server/data') / f'phone_verify_failed_{int(time.time())}.png'
                    driver.save_screenshot(str(screenshot_path))
                    return False, f"Phone verification failed: {msg}"
            else:
                log("  ✗ No GRIZZLY_API_KEY set - cannot verify phone")
                log("  Set GRIZZLY_API_KEY environment variable to enable SMS verification")
                screenshot_path = Path('/mnt/F/C2_server/data') / f'phone_verify_needed_{int(time.time())}.png'
                driver.save_screenshot(str(screenshot_path))
                return False, "Phone verification required - set GRIZZLY_API_KEY"
        
        # Step 3: Navigate to kernel EDIT page (GPU settings are in Edit mode, not Settings tab!)
        kernel_url = f'https://www.kaggle.com/code/{kernel_slug}'
        log(f"[5/8] Navigating to kernel: {kernel_url}")
        driver.get(kernel_url)
        time.sleep(3)
        
        # Find and click Edit button to enter edit mode
        log("[6/8] Entering Edit mode...")
        
        # Click Edit button - this opens the notebook editor where Session Options are
        edit_clicked = driver.execute_script("""
        // Find Edit button
        var links = document.querySelectorAll('a[href*="/edit/"]');
        for (var link of links) {
            if (link.textContent.includes('Edit') || link.querySelector('span')) {
                link.click();
                return 'clicked edit link: ' + link.href;
            }
        }
        // Try button
        var buttons = document.querySelectorAll('button');
        for (var btn of buttons) {
            if (btn.textContent.toLowerCase().includes('edit')) {
                btn.click();
                return 'clicked edit button';
            }
        }
        return 'not found';
        """)
        log(f"  Edit click result: {edit_clicked}")
        time.sleep(5)  # Wait for editor to load
        
        # Take screenshot of edit mode
        screenshot_path = Path('/mnt/F/C2_server/data') / f'kaggle_edit_mode_{int(time.time())}.png'
        driver.save_screenshot(str(screenshot_path))
        log(f"  Saved screenshot: {screenshot_path}")
        
        # Step 4: Expand Session Options panel and Start Session
        log("[6/7] Opening Session Options...")
        
        # First expand the Session options panel (it's collapsed by default)
        expand_result = driver.execute_script("""
        // Find and click "Session options" expand button
        var buttons = document.querySelectorAll('button[aria-label*="Session options"]');
        for (var btn of buttons) {
            if (btn.getAttribute('aria-expanded') === 'false') {
                btn.click();
                return 'expanded session options panel';
            }
        }
        // Alternative: find by text
        var h3s = document.querySelectorAll('h3');
        for (var h3 of h3s) {
            if (h3.textContent === 'Session options') {
                var parent = h3.closest('div[class*="sc-"]');
                var btn = parent ? parent.querySelector('button') : null;
                if (btn && btn.getAttribute('aria-expanded') === 'false') {
                    btn.click();
                    return 'clicked expand button near h3';
                }
            }
        }
        return 'panel already expanded or not found';
        """)
        log(f"  Expand result: {expand_result}")
        time.sleep(2)
        
        # Take screenshot
        screenshot_path2 = Path('/mnt/F/C2_server/data') / f'kaggle_session_options_{int(time.time())}.png'
        driver.save_screenshot(str(screenshot_path2))
        log(f"  Saved screenshot: {screenshot_path2}")
        
        # Save HTML for analysis
        html_path = Path('/mnt/F/C2_server/data') / f'kaggle_edit_html_{int(time.time())}.html'
        html_path.write_text(driver.page_source)
        log(f"  Saved HTML: {html_path}")
        
        # Step 5: Start the session (required before GPU options appear)
        log("  Starting session...")
        
        start_result = driver.execute_script("""
        // Find Start Session button (not disabled)
        var buttons = document.querySelectorAll('button');
        for (var btn of buttons) {
            var text = btn.textContent || '';
            if (text.includes('Start Session') || text.includes('Start session')) {
                if (!btn.classList.contains('disabled') && !btn.hasAttribute('aria-disabled')) {
                    btn.click();
                    return 'clicked start session';
                }
                return 'start session button disabled';
            }
        }
        return 'start session button not found';
        """)
        log(f"  Start session result: {start_result}")
        
        if 'clicked' in start_result:
            log("  Waiting for session to start (30s)...")
            time.sleep(30)  # Session startup takes time
            
            # Take screenshot after session start
            screenshot_path3 = Path('/mnt/F/C2_server/data') / f'kaggle_after_session_start_{int(time.time())}.png'
            driver.save_screenshot(str(screenshot_path3))
            log(f"  Saved screenshot: {screenshot_path3}")
        
        # Step 6: Now look for Environment/Accelerator options
        log("  Looking for Environment settings...")
        
        # Expand Session options again if needed
        driver.execute_script("""
        var buttons = document.querySelectorAll('button[aria-label*="Session options"]');
        for (var btn of buttons) {
            if (btn.getAttribute('aria-expanded') === 'false') {
                btn.click();
                return 'expanded';
            }
        }
        return 'already expanded';
        """)
        time.sleep(1)
        
        # Set "Always use latest environment"
        log("  Setting 'Always use latest environment'...")
        
        env_set = driver.execute_script("""
        // Look for environment option
        var labels = document.querySelectorAll('label, div[role="radio"], input[type="radio"]');
        for (var el of labels) {
            var text = el.textContent || el.value || '';
            if (text.includes('Always use latest') || text.includes('latest environment')) {
                el.click();
                return 'set latest environment';
            }
        }
        // Try radio button
        var radios = document.querySelectorAll('input[type="radio"]');
        for (var r of radios) {
            var label = r.nextElementSibling || r.previousElementSibling;
            if (label && label.textContent.includes('latest')) {
                r.click();
                return 'clicked radio for latest';
            }
        }
        return 'not found';
        """)
        log(f"  Environment result: {env_set}")
        time.sleep(1)
        
        # Step 7: Refresh page (important for GPU option to appear!)
        log("[7/7] Refreshing page to enable GPU option...")
        driver.refresh()
        time.sleep(5)
        
        # Expand session options again after refresh
        driver.execute_script("""
        var buttons = document.querySelectorAll('button[aria-label*="Session options"]');
        for (var btn of buttons) {
            if (btn.getAttribute('aria-expanded') === 'false') {
                btn.click();
                return 'expanded';
            }
        }
        return 'not needed';
        """)
        time.sleep(2)
        
        # Step 7: Select GPU Accelerator
        log("Selecting GPU Accelerator...")
        
        gpu_result = driver.execute_script("""
        // Look for Accelerator dropdown/option
        var selects = document.querySelectorAll('select, [role="listbox"], [role="combobox"]');
        for (var sel of selects) {
            var label = sel.previousElementSibling || sel.parentElement.querySelector('label');
            if (label && label.textContent.toLowerCase().includes('accelerator')) {
                // Found accelerator dropdown
                sel.click();
                
                // Now look for GPU option
                setTimeout(function() {
                    var options = document.querySelectorAll('option, [role="option"], li');
                    for (var opt of options) {
                        if (opt.textContent.includes('GPU T4') || opt.textContent.includes('GPU P100')) {
                            opt.click();
                            return 'selected GPU';
                        }
                    }
                }, 500);
                return 'found accelerator dropdown';
            }
        }
        
        // Try direct GPU option
        var divs = document.querySelectorAll('div, span, li');
        for (var div of divs) {
            if (div.textContent === 'GPU T4 x2' || div.textContent === 'GPU T4' || div.textContent === 'GPU P100') {
                div.click();
                return 'clicked GPU option directly';
            }
        }
        return 'GPU option not found - may need phone verification';
        """)
        log(f"  GPU selection result: {gpu_result}")
        time.sleep(2)
        
        # Take final screenshot
        final_screenshot = Path('/mnt/F/C2_server/data') / f'kaggle_final_{int(time.time())}.png'
        driver.save_screenshot(str(final_screenshot))
        log(f"  Final screenshot: {final_screenshot}")
        
        # Check if GPU was selected
        page_content = driver.page_source
        gpu_enabled = 'GPU T4' in page_content or 'GPU P100' in page_content or 'accelerator' in page_content.lower()
        
        if gpu_enabled:
            log("✓ GPU accelerator option found on page")
            # Try to save settings
            save_result = driver.execute_script("""
            var buttons = document.querySelectorAll('button');
            for (var btn of buttons) {
                if (btn.textContent.toLowerCase().includes('save') || btn.textContent.toLowerCase().includes('apply')) {
                    btn.click();
                    return 'saved settings';
                }
            }
            return 'no save button found';
            """)
            log(f"  Save result: {save_result}")
        else:
            log("✗ GPU option not found - account may need phone verification")
        
        # Take screenshot
        screenshot_path = Path('/mnt/F/C2_server/data') / f'gpu_activation_{kernel_slug.replace("/", "_")}.png'
        driver.save_screenshot(str(screenshot_path))
        log(f"Screenshot saved: {screenshot_path}")
        
        # Check result
        page_source = driver.page_source
        
        if 'GPU' in page_source and ('T4' in page_source or 'P100' in page_source):
            log("\n✓ GPU ACTIVATION SUCCESSFUL!")
            return True, str(screenshot_path)
        else:
            log("\n✗ GPU may require phone verification or is not available")
            return False, str(screenshot_path)
    
    except Exception as e:
        log(f"Error: {e}")
        import traceback
        log(traceback.format_exc()[-500:])
        return False, None
    
    finally:
        if driver:
            driver.quit()


def check_gpu_availability(email: str, password: str, headless=True, profile_path=None):
    """Check if GPU options are available for the account."""
    log = lambda x: print(f"[GPU Check] {x}")
    
    driver = None
    try:
        driver = create_firefox_driver(headless=headless, profile_path=profile_path, log_fn=log)
        
        # Login
        driver.get('https://www.kaggle.com/account/login')
        time.sleep(2)
        
        try:
            email_tab = driver.find_element(By.XPATH, "//div[contains(text(), 'Email')]")
            email_tab.click()
        except:
            pass
        
        email_input = driver.find_element(By.CSS_SELECTOR, 'input[type="email"]')
        email_input.send_keys(email)
        
        password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        password_input.send_keys(password)
        
        login_btn = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        login_btn.click()
        time.sleep(5)
        
        # Create new notebook
        driver.get('https://www.kaggle.com/code/new')
        time.sleep(3)
        
        # Open settings
        try:
            settings_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label*="settings" i]')
            settings_btn.click()
            time.sleep(1)
        except:
            pass
        
        # Check accelerator options
        page_source = driver.page_source
        
        # Take screenshot
        screenshot_path = Path('/mnt/F/C2_server/data') / 'gpu_availability_check.png'
        driver.save_screenshot(str(screenshot_path))
        
        if 'Accelerator' in page_source:
            if 'disabled' in page_source.lower() or 'grayed' in page_source.lower():
                log("GPU options are DISABLED - phone verification required")
                return False, str(screenshot_path)
            else:
                log("GPU options are AVAILABLE")
                return True, str(screenshot_path)
        else:
            log("Could not determine GPU availability")
            return None, str(screenshot_path)
    
    finally:
        if driver:
            driver.quit()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Activate Kaggle GPU via Firefox automation')
    parser.add_argument('--email', required=True, help='Kaggle email')
    parser.add_argument('--password', required=True, help='Kaggle password')
    parser.add_argument('--kernel', help='Kernel slug (e.g., username/kernel-name)')
    parser.add_argument('--check', action='store_true', help='Check GPU availability only')
    parser.add_argument('--visible', action='store_true', help='Show browser window')
    parser.add_argument('--profile', help='Firefox profile path (with VPN extension)')
    
    args = parser.parse_args()
    
    if args.check:
        result, screenshot = check_gpu_availability(
            args.email, args.password,
            headless=not args.visible,
            profile_path=args.profile
        )
    elif args.kernel:
        result, screenshot = activate_gpu_for_kernel(
            args.email, args.password,
            args.kernel,
            headless=not args.visible,
            profile_path=args.profile
        )
    else:
        print("Specify --kernel or --check")
        return 1
    
    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")
    if screenshot:
        print(f"Screenshot: {screenshot}")
    
    return 0 if result else 1


if __name__ == '__main__':
    sys.exit(main())
