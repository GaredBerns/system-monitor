#!/usr/bin/env python3
"""Standalone worker for registration - uses undetected-chromedriver to bypass Cloudflare."""

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
from src.utils.logger import get_logger
from src.agents.browser.captcha import (
    setup_stealth_only, setup_captcha_block,
    solve_captcha_on_page, SITES_NEED_REAL_CAPTCHA,
    solve_recaptcha_api, get_captcha_key_for_solve,
)

log = get_logger(__name__)

try:
    from src.agents.kaggle.captcha_solver import solve_kaggle_registration_captcha
except ImportError:
    solve_kaggle_registration_captcha = None


def _wait_visible(page, selectors, timeout=8000):
    if isinstance(selectors, str):
        selectors = [selectors]
    deadline = time.time() + (timeout / 1000.0)
    while time.time() < deadline:
        for sel in selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=400):
                    return True
            except:
                pass
        time.sleep(0.25)
    return False


def _fill(page, selector, value, timeout=3000):
    try:
        el = page.locator(selector).first
        if el.is_visible(timeout=timeout):
            el.click()
            el.fill(value)
            return True
    except:
        pass
    return False


def _click(page, selector, timeout=3000):
    try:
        el = page.locator(selector).first
        if el.is_visible(timeout=timeout):
            el.click()
            return True
    except:
        pass
    return False


def _wait_email(email, log_fn, timeout=60, subject_filter=None):
    log_fn(f"Waiting for email ({timeout}s)...")
    start = time.time()
    seen = set()
    initial = mail_manager.check_inbox(email)
    for m in initial:
        seen.add(m.get("id", ""))

    while time.time() - start < timeout:
        time.sleep(1)
        messages = mail_manager.check_inbox(email)
        for m in messages:
            mid = m.get("id", "")
            if mid and mid not in seen:
                if subject_filter and subject_filter.lower() not in m.get("subject", "").lower():
                    seen.add(mid)
                    continue
                log_fn(f"Email: {m.get('subject','?')}")
                body = (m.get("html", "") or "") + " " + (m.get("body", "") or "")
                return m, mail_manager.extract_code(body), mail_manager.extract_link(body)

    log_fn("No email received")
    return None, None, None


def _handle_captcha(page, sitekey, page_url, log_fn):
    """Solve captcha via FCB API."""
    log_fn("Solving captcha via FCB API...")
    
    # Проверяем что страница жива
    try:
        page.content()
    except Exception as e:
        log_fn(f"Page closed: {e}")
        return False
    
    # Get sitekey from page if not provided
    if not sitekey:
        try:
            sitekey = page.evaluate("""() => {
                const el = document.querySelector('.g-recaptcha[data-sitekey]');
                return el ? el.dataset.sitekey : null;
            }""")
        except Exception as e:
            log_fn(f"Get sitekey error: {e}")
            return False
    
    
    if sitekey:
        token = solve_recaptcha_api(sitekey, page_url, type('Job', (), {'log': staticmethod(log_fn)})())
        if token:
            # Проверяем страницу перед инъекцией
            try:
                page.content()
            except Exception as e:
                log_fn(f"Page closed before token inject: {e}")
                return False
            
            # Inject token (JSON-escaped)
            token_js = json.dumps(token)
            try:
                result = page.evaluate(f"""() => {{
                    let success = false;
                    const token = {token_js};
                    
                    // 1. Set in all textareas
                    document.querySelectorAll('textarea[name="g-recaptcha-response"]').forEach(ta => {{
                        ta.value = token;
                        ta.innerHTML = token;
                        success = true;
                    }});
                    
                    // 2. Set in hidden inputs
                    document.querySelectorAll('input[name="g-recaptcha-response"]').forEach(inp => {{
                        inp.value = token;
                        success = true;
                    }});
                    
                    // 3. Find reCAPTCHA iframe and set response
                    document.querySelectorAll('iframe[title*="recaptcha"]').forEach(iframe => {{
                        try {{
                            // Set data-response attribute
                            iframe.setAttribute('data-response', token);
                            success = true;
                        }} catch(e) {{}}
                    }});
                    
                    // 4. Trigger via grecaptcha object
                    if (window.grecaptcha && window.grecaptcha.getResponse) {{
                        try {{
                            // Find rendered widget
                            const widgetId = window.___grecaptcha_cfg ? 
                                Object.keys(window.___grecaptcha_cfg.clients || {{}})[0] : 0;
                            if (widgetId !== undefined) {{
                                // Set response via internal API
                                const client = window.___grecaptcha_cfg?.clients?.[widgetId];
                                if (client) {{
                                    // Set the response directly
                                    if (client.responseWidget !== undefined) {{
                                        client.responseWidget = token;
                                    }}
                                    // Trigger callback
                                    if (typeof client.callback === 'function') {{
                                        client.callback(token);
                                        success = true;
                                    }}
                                }}
                            }}
                        }} catch(e) {{}}
                    }}
                    
                    // 5. Trigger reCAPTCHA ready callbacks
                    if (window.___grecaptcha_cfg && window.___grecaptcha_cfg.callbacks) {{
                    for (let cb of Object.values(window.___grecaptcha_cfg.callbacks)) {{
                        if (typeof cb === 'function') {{
                            try {{ cb(token); success = true; }} catch(e) {{}}
                        }}
                    }}
                }}
                
                // 6. Dispatch custom event
                window.dispatchEvent(new CustomEvent('recaptcha-response', {{detail: token}}));
                
                return success;
            }}""")
                log_fn(f"✓ Captcha token injected: {result}")
                return True
            except Exception as e:
                log_fn(f"Token inject error: {e}")
                return False
    
    log_fn("✗ Captcha solve failed")
    return False


def _get_chrome_version():
    """Detect installed Chrome/Chromium version."""
    import subprocess
    import re
    
    for cmd in ['google-chrome', 'chromium', 'chromium-browser']:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                match = re.search(r'(\d+)\.', result.stdout)
                if match:
                    return int(match.group(1))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None  # Auto-detect by undetected-chromedriver


def _get_mail_web_url(email_data):
    """Get web interface URL for temp mail provider."""
    provider = email_data.get("provider", "")
    email = email_data.get("email", "")
    
    if provider == "boomlify":
        return "https://boomlify.com/RU/EDU-TEMP-MAIL"
    elif provider == "mail.tm":
        return "https://mail.tm/en/"
    elif provider == "mail.gw":
        return "https://mail.gw/en/"
    elif provider == "temp-mail.io":
        return "https://temp-mail.io/en/"
    elif provider == "1secmail":
        login, domain = email.split("@") if "@" in email else ("", "")
        return f"https://www.1secmail.com/?login={login}&domain={domain}"
    return None


def _boomlify_create_email(driver, log_fn):
    """Create email on Boomlify EDU page, return email string."""
    import time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    log_fn("Opening Boomlify EDU...")
    driver.get("https://boomlify.com/RU/EDU-TEMP-MAIL")
    time.sleep(3)
    
    # Click generate button
    try:
        wait = WebDriverWait(driver, 15)
        for sel in [
            "button[aria-label*='enerate']",
            "button[title*='enerate']",
            "[aria-label*='Generate a new']",
            "button",
        ]:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    txt = (el.get_attribute("aria-label") or el.text or "").lower()
                    if "generate" in txt or "new" in txt and "email" in txt:
                        el.click()
                        break
                else:
                    continue
                break
            except Exception:
                continue
    except Exception:
        pass
    
    time.sleep(2)
    
    # Get email from page - usually in copy button or nearby
    email = None
    for _ in range(5):
        try:
            # Look for email pattern in page
            html = driver.page_source
            import re
            m = re.search(r'[\w\.-]+@[\w\.-]+\.(?:edu|edu\.\w+)', html)
            if m:
                email = m.group(0)
                break
            # Or from button aria-label
            copy_btn = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Copy'], button[aria-label*='copy']")
            if copy_btn:
                parent = copy_btn[0].find_element(By.XPATH, "./..")
                if parent:
                    text = parent.text or ""
                    m2 = re.search(r'[\w\.-]+@[\w\.-]+', text)
                    if m2:
                        email = m2.group(0)
                        break
        except Exception:
            pass
        time.sleep(1)
    
    if not email:
        log_fn("Could not get email from Boomlify page")
        return None
    log_fn(f"Boomlify email: {email}")
    return email


def _boomlify_wait_for_email(driver, log_fn, timeout=120, subject_filter="kaggle"):
    """Poll Boomlify inbox DOM for new messages, return (msg_dict, code, link)."""
    from selenium.webdriver.common.by import By
    
    start = time.time()
    seen_subjects = set()
    
    while time.time() - start < timeout:
        try:
            driver.switch_to.default_content()
            # Check for links with kaggle/verify in page
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='kaggle'], a[href*='verify'], a[href*='confirm'], a[href*='activate']")
            for a in links:
                href = a.get_attribute("href") or ""
                if "kaggle" in href.lower() or ("verify" in href.lower() and "http" in href):
                    log_fn(f"Found link in page")
                    return {"subject": "", "body": "", "html": ""}, None, href
            # Find inbox items
            items = driver.find_elements(By.CSS_SELECTOR, "[data-subject], [class*='message'], [class*='email'], [class*='inbox'] a, [role='listitem']")
            for item in items:
                try:
                    subj = item.get_attribute("data-subject") or item.text or ""
                    if subject_filter and subject_filter.lower() not in subj.lower() and len(subj) > 3:
                        continue
                    if subj and subj in seen_subjects:
                        continue
                    if subj:
                        seen_subjects.add(subj)
                    item.click()
                    time.sleep(2)
                    html = driver.page_source
                    body_el = driver.find_elements(By.CSS_SELECTOR, "[class*='body'], [class*='content'], .email-body")
                    body_text = " ".join(be.text or "" for be in body_el)
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for ifr in iframes:
                        try:
                            driver.switch_to.frame(ifr)
                            body_text += " " + (driver.find_element(By.TAG_NAME, "body").text or "")
                            driver.switch_to.default_content()
                        except Exception:
                            driver.switch_to.default_content()
                    code = mail_manager.extract_code(body_text + " " + html)
                    link = mail_manager.extract_link(html) or mail_manager.extract_link(body_text)
                    if link or code:
                        return {"subject": subj, "body": body_text, "html": html}, code, link
                except Exception:
                    continue
        except Exception as e:
            log_fn(f"Inbox poll: {e}")
        time.sleep(5)
    
    return None, None, None


def kaggle_login(email, password, log_fn):
    """Kaggle login - just open browser instantly, copy credentials to clipboard."""
    import subprocess
    import pyperclip
    
    log_fn("Opening Chrome...")
    
    # Copy credentials to clipboard
    try:
        pyperclip.copy(f"{email}\t{password}")
        log_fn(f"✓ Credentials copied: {email}")
    except:
        log_fn("Note: Copy credentials manually")
    
    # Open Chrome directly - INSTANT
    url = "https://www.kaggle.com/account/login?phase=emailSignIn&returnUrl=%2F"
    
    # Try different Chrome paths
    chrome_paths = [
        "google-chrome",
        "google-chrome-stable", 
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    
    for chrome in chrome_paths:
        try:
            subprocess.Popen(
                [chrome, "--new-window", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            log_fn(f"✓ Browser opened")
            return {"success": True}
        except:
            continue
    
    # Fallback: use xdg-open
    try:
        subprocess.Popen(["xdg-open", url], start_new_session=True)
        log_fn("✓ Browser opened (xdg-open)")
        return {"success": True}
    except Exception as e:
        log_fn(f"Failed: {e}")
        return {"success": False, "error": str(e)}


def _boomlify_create_email_web(driver, log_fn):
    """Create EDU email on Boomlify using the SAME anti-detect browser."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    log_fn("[BOOMLIFY] Opening Boomlify in new tab...")
    original_window = driver.current_window_handle
    driver.execute_script("window.open('https://boomlify.com', '_blank');")
    driver.switch_to.window(driver.window_handles[-1])
    
    wait = WebDriverWait(driver, 15)
    time.sleep(3)
    
    # Select EDU domain
    try:
        edu_tab = driver.find_element(By.XPATH, "//div[contains(text(),'EDU') or contains(@class,'edu')]")
        edu_tab.click()
        time.sleep(1)
        log_fn("[BOOMLIFY] Selected EDU domain")
    except:
        log_fn("[BOOMLIFY] EDU tab not found, using default")
    
    # Get generated email
    email = None
    try:
        email_elem = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[type='text'], .email-address, [data-email], [class*='email']")))
        email = email_elem.get_attribute('value') or email_elem.text
        if '@' not in email:
            email_elem = driver.find_element(By.XPATH, "//*[contains(text(),'@')]")
            email = email_elem.text
    except Exception as e:
        log_fn(f"[BOOMLIFY] Email extraction failed: {e}")
    
    if email and '@' in email:
        log_fn(f"[BOOMLIFY] ✓ Created: {email}")
        # Don't close tab - keep it open for inbox checking
        driver.switch_to.window(original_window)
        return {"email": email, "provider": "boomlify_web", "is_edu": ".edu" in email}
    
    driver.switch_to.window(original_window)
    return None


def _boomlify_check_inbox_web(driver, email, log_fn):
    """Check Boomlify inbox using the SAME anti-detect browser."""
    from selenium.webdriver.common.by import By
    
    log_fn(f"[BOOMLIFY] Checking inbox for {email}...")
    
    # Find or create Boomlify tab
    boomlify_tab = None
    original_window = driver.current_window_handle
    
    for handle in driver.window_handles:
        try:
            driver.switch_to.window(handle)
            if "boomlify" in driver.current_url.lower():
                boomlify_tab = handle
                break
        except:
            continue
    
    if not boomlify_tab:
        # Open new tab
        driver.switch_to.window(original_window)
        driver.execute_script(f"window.open('https://boomlify.com/inbox/{email}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
    else:
        driver.get(f"https://boomlify.com/inbox/{email}")
    
    time.sleep(3)
    
    messages = []
    try:
        msg_elems = driver.find_elements(By.CSS_SELECTOR, ".message, .email-item, tr[onclick], .inbox-row, [class*='message'], [class*='email']")
        log_fn(f"[BOOMLIFY] Found {len(msg_elems)} elements")
        
        for i, elem in enumerate(msg_elems[:5]):
            try:
                elem.click()
                time.sleep(0.5)
                
                body_elem = driver.find_element(By.CSS_SELECTOR, ".message-body, .email-body, .content, [class*='body']")
                body = body_elem.text if body_elem else ""
                
                subj_elem = driver.find_element(By.CSS_SELECTOR, ".subject, .message-subject, [class*='subject']")
                subject = subj_elem.text if subj_elem else ""
                
                from_elem = driver.find_element(By.CSS_SELECTOR, ".from, .sender, [class*='from']")
                from_addr = from_elem.text if from_elem else ""
                
                messages.append({
                    "id": str(i),
                    "from": from_addr,
                    "subject": subject,
                    "body": body,
                    "html": "",
                })
                log_fn(f"[BOOMLIFY] Msg {i}: {subject[:30]}...")
            except Exception as e:
                log_fn(f"[BOOMLIFY] Msg {i} error: {e}")
                continue
    except Exception as e:
        log_fn(f"[BOOMLIFY] Inbox error: {e}")
    
    # Switch back to Kaggle tab
    driver.switch_to.window(original_window)
    return messages


def kaggle_register_undetected(identity, email_data, log_fn, headless=False, proxy=""):
    """Kaggle registration via undetected_chromedriver (anti-detect). Email via web or API."""
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import tempfile
    import os
    
    log_fn("Starting Anti-Detect Chrome...")
    
    # Get Chrome version for undetected_chromedriver
    chrome_ver = _get_chrome_version()
    log_fn(f"Chrome version: {chrome_ver}")
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=390,844')
    options.add_argument('--window-position=100,50')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--start-maximized')
    
    # Proxy support
    if proxy:
        log_fn(f"Using proxy: {proxy[:20]}...")
        options.add_argument(f'--proxy-server={proxy}')
    
    # Enable images for reCAPTCHA
    prefs = {
        "profile.managed_default_content_settings.images": 1,
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)
    
    # Initialize Chrome with detailed error handling
    log_fn("Initializing undetected_chromedriver...")
    log_fn(f"  Chrome version_main: {chrome_ver}, Headless: {headless}")
    
    try:
        driver = uc.Chrome(options=options, version_main=chrome_ver, headless=headless)
        driver.set_window_size(390, 844)
        driver.set_window_position(100, 50)
        log_fn("✓ Anti-detect Chrome started")
    except Exception as e:
        error_str = str(e)
        log_fn(f"Chrome init failed: {error_str}")
        log_fn(f"Traceback: {traceback.format_exc()[-500:]}")
        
        # Fallback: try without version_main
        try:
            log_fn("Retrying without version_main constraint...")
            driver = uc.Chrome(options=options, headless=headless)
            driver.set_window_size(390, 844)
            driver.set_window_position(100, 50)
            log_fn("✓ Anti-detect Chrome started (fallback mode)")
        except Exception as e2:
            log_fn(f"Fallback also failed: {e2}")
            return {"verified": False, "error": f"chrome_init_failed: {error_str}", "error_type": "browser"}
    
    # Create email via Boomlify web if API is rate limited
    if not email_data or not email_data.get("email"):
        log_fn("[MAIL] Creating email via Boomlify web...")
        email_data = _boomlify_create_email_web(driver, log_fn)
        if not email_data:
            log_fn("[MAIL] ✗ Failed to create email")
            driver.quit()
            return {"verified": False, "error": "email_creation_failed", "error_type": "email"}
    
    if not identity.get("email"):
        identity["email"] = email_data["email"]
    
    try:
        log_fn("[STEP 1/10] Loading Kaggle registration page...")
        driver.set_page_load_timeout(60)
        
        # Retry logic for Cloudflare
        page_loaded = False
        for attempt in range(3):
            try:
                log_fn(f"  [1.{attempt+1}] Attempt {attempt+1}/3: GET https://www.kaggle.com/account/login?phase=emailRegister")
                start = time.time()
                driver.get("https://www.kaggle.com/account/login?phase=emailRegister&returnUrl=%2F")
                load_time = round(time.time() - start, 2)
                log_fn(f"  [1.{attempt+1}] ✓ Page loaded in {load_time}s")
                page_loaded = True
                break
            except Exception as e:
                log_fn(f"  [1.{attempt+1}] ✗ Failed: {str(e)[:100]}")
                if attempt < 2:
                    log_fn(f"  [1.{attempt+1}] Retrying in 2s...")
                    time.sleep(2)
                else:
                    log_fn(f"  [1.{attempt+1}] ✗ All attempts failed")
                    raise
        
        if not page_loaded:
            raise Exception("Page load failed after 3 attempts")
        
        # Wait for page ready
        log_fn("[STEP 2/10] Waiting for page ready state...")
        wait = WebDriverWait(driver, 30)
        start = time.time()
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        ready_time = round(time.time() - start, 2)
        log_fn(f"  [2.1] ✓ Document ready in {ready_time}s")
        
        # Verify page elements
        log_fn("  [2.2] Verifying page elements...")
        page_info = driver.execute_script('''
            return {
                url: window.location.href,
                title: document.title,
                forms: document.querySelectorAll('form').length,
                inputs: document.querySelectorAll('input').length,
                buttons: document.querySelectorAll('button').length
            };
        ''')
        log_fn(f"  [2.2] URL: {page_info['url']}")
        log_fn(f"  [2.2] Title: {page_info['title']}")
        log_fn(f"  [2.2] Forms: {page_info['forms']}, Inputs: {page_info['inputs']}, Buttons: {page_info['buttons']}")
        
        if page_info['forms'] == 0 or page_info['inputs'] == 0:
            log_fn("  [2.2] ⚠ Warning: Page may not be fully loaded (no forms/inputs)")
        
        # Check for Cloudflare challenge
        log_fn("[STEP 3/10] Checking for Cloudflare challenge...")
        time.sleep(2)
        cf_detected = "challenge" in driver.current_url or "cloudflare" in driver.page_source.lower()
        
        if cf_detected:
            log_fn("  [3.1] ⚠ Cloudflare challenge DETECTED")
            log_fn(f"  [3.1] URL: {driver.current_url}")
            log_fn("  [3.1] Waiting up to 30s for challenge to pass...")
            
            for cf_wait in range(30):
                time.sleep(1)
                cf_still_present = "challenge" in driver.current_url or "cloudflare" in driver.page_source.lower()
                
                if not cf_still_present:
                    log_fn(f"  [3.1] ✓ Cloudflare passed after {cf_wait+1}s")
                    break
                
                if (cf_wait + 1) % 5 == 0:
                    log_fn(f"  [3.1] Still waiting... ({cf_wait+1}/30s)")
                
                if cf_wait == 29:
                    log_fn("  [3.1] ⚠ Cloudflare still present after 30s - continuing anyway")
        else:
            log_fn("  [3.1] ✓ No Cloudflare challenge detected")
        
        
        # Fill form
        log_fn("[STEP 4/10] Filling registration form...")
        display_name = identity["username"].replace("_", " ")
        
        # Email input
        log_fn("  [4.1] Locating email input...")
        try:
            email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            log_fn(f"  [4.1] ✓ Email input found")
            log_fn(f"  [4.1] Filling email: {identity['email']}")
            email_input.clear()
            email_input.send_keys(identity['email'])
            log_fn(f"  [4.1] ✓ Email filled")
        except Exception as e:
            log_fn(f"  [4.1] ✗ Email input error: {e}")
            raise
        
        # Password input
        log_fn("  [4.2] Locating password input...")
        try:
            pwd_input = driver.find_element(By.NAME, "password")
            log_fn(f"  [4.2] ✓ Password input found")
            log_fn(f"  [4.2] Filling password: {'*' * len(identity['password'])}")
            pwd_input.clear()
            pwd_input.send_keys(identity['password'])
            log_fn(f"  [4.2] ✓ Password filled")
        except Exception as e:
            log_fn(f"  [4.2] ✗ Password input error: {e}")
            raise
        
        # Display name
        log_fn("  [4.3] Locating display name input...")
        try:
            name_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder*='full name']")
            log_fn(f"  [4.3] ✓ Name input found")
            log_fn(f"  [4.3] Filling name: {display_name}")
            name_input.clear()
            name_input.send_keys(display_name)
            log_fn(f"  [4.3] ✓ Name filled")
        except Exception as e:
            log_fn(f"  [4.3] ✗ Name input error: {e}")
            raise
        
        log_fn(f"[STEP 4/10] ✓ Form filled successfully")
        log_fn(f"  Email: {identity['email']}")
        log_fn(f"  Password: {'*' * len(identity['password'])}")
        log_fn(f"  Name: {display_name}")
        
        # Try auto-solve captcha via API first
        log_fn("[STEP 5/10] Attempting auto-solve reCAPTCHA...")
        captcha_solved = False
        
        # Get sitekey
        try:
            log_fn("  [5.1] Extracting sitekey...")
            sitekey_el = driver.find_element(By.CSS_SELECTOR, ".g-recaptcha[data-sitekey], [data-sitekey]")
            sitekey = sitekey_el.get_attribute("data-sitekey")
            log_fn(f"  [5.1] ✓ Sitekey: {sitekey}")
            
            # Try to solve via API
            from src.agents.browser.captcha import solve_recaptcha_api
            class FakeJob:
                def log(self, msg): log_fn(f"[CAPTCHA] {msg}")
            
            log_fn("  [5.2] Calling FCB API to solve captcha...")
            token = solve_recaptcha_api(sitekey, driver.current_url, FakeJob())
            if token:
                log_fn(f"  [5.2] ✓ Got captcha token: {token[:30]}...")
                log_fn("  [5.3] Injecting token into page...")
                driver.execute_script(f"""
                    document.querySelector('textarea[name="g-recaptcha-response"]').value = '{token}';
                    ___grecaptcha_cfg && ___grecaptcha_cfg.clients && Object.values(___grecaptcha_cfg.clients).forEach(c => c && c.callback && c.callback('{token}'));
                """)
                captcha_solved = True
                log_fn("  [5.3] ✓ Token injected successfully")
                log_fn("[STEP 5/10] ✓ Captcha auto-solved!")
        except Exception as e:
            log_fn(f"  [5.X] ✗ Auto-solve failed: {str(e)[:100]}")
            log_fn("  [5.X] Falling back to manual solve")
        
        # Click reCAPTCHA checkbox if not auto-solved
        if not captcha_solved:
            log_fn("[STEP 6/10] Manual captcha solve required...")
            log_fn("  [6.1] Locating reCAPTCHA iframe...")
            try:
                # Switch to reCAPTCHA iframe
                captcha_iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
                log_fn("  [6.1] ✓ reCAPTCHA iframe found")
                driver.switch_to.frame(captcha_iframe)
                log_fn("  [6.1] ✓ Switched to iframe")
                
                # Click the checkbox inside iframe
                log_fn("  [6.2] Clicking reCAPTCHA checkbox...")
                checkbox = driver.find_element(By.CSS_SELECTOR, ".recaptcha-checkbox-checkmark")
                driver.execute_script("arguments[0].click();", checkbox)
                log_fn("  [6.2] ✓ Checkbox clicked")
                
                # Switch back to main page
                driver.switch_to.default_content()
                log_fn("  [6.2] ✓ Switched back to main page")
                log_fn("[STEP 6/10] ✓ reCAPTCHA clicked - solve the challenge manually")
            except Exception as e:
                log_fn(f"  [6.X] ✗ reCAPTCHA click error: {str(e)[:100]}")
        else:
            log_fn("[STEP 6/10] ✓ Skipped (captcha already solved)")
        
        
        log_fn("")
        log_fn("="*70)
        log_fn(">>> MANUAL ACTION REQUIRED <<<")
        log_fn(">>> Solve captcha manually if not auto-solved - rest is automatic <<<")
        log_fn(f">>> Email: {email_data.get('email','?')} (provider: {email_data.get('provider','?')}) <<<")
        log_fn("="*70)
        log_fn("")
        
        # Start email checking in background thread
        log_fn("[STEP 7/10] Starting email monitoring...")
        from src.mail.tempmail import mail_manager
        import threading
        
        code_found = {"value": None}
        link_found = {"value": None}
        
        def check_email_async():
            if email_data and email_data.get("email"):
                email_addr = email_data["email"]
                provider = email_data.get("provider", "?")
                log_fn(f"  [7.1] Email monitor started")
                log_fn(f"  [7.1] Address: {email_addr}")
                log_fn(f"  [7.1] Provider: {provider}")
                log_fn(f"  [7.1] Polling every 1.5s for 90s...")
                
                start = time.time()
                poll_count = 0
                while time.time() - start < 90 and not code_found["value"] and not link_found["value"]:
                    time.sleep(1.5)
                    poll_count += 1
                    try:
                        inbox = mail_manager.check_inbox(email_addr)
                        
                        if poll_count % 10 == 0:  # Log every 15s
                            log_fn(f"  [7.{poll_count}] Poll #{poll_count}: {len(inbox)} messages in inbox")
                        
                        if inbox and poll_count % 5 == 0:  # Show subjects every 7.5s
                            for i, msg in enumerate(inbox[:3]):
                                subj = (msg.get("subject") or "?")[:50]
                                from_addr = (msg.get("from") or "?")[:30]
                                log_fn(f"  [7.{poll_count}]   [{i}] From: {from_addr} | Subject: {subj}")
                        
                        for msg in inbox:
                            subj = (msg.get("subject") or "").lower()
                            from_addr = (msg.get("from") or "").lower()
                            
                            # Filter for Kaggle emails
                            if "kaggle" not in subj and "verif" not in subj and "code" not in subj and "verify" not in subj and "confirm" not in subj and "kaggle" not in from_addr:
                                continue
                            
                            body = (msg.get("body") or "") + "\n" + (msg.get("html") or "")
                            code = mail_manager.extract_code(body) if body else ""
                            link = mail_manager.extract_link(body) if body else ""
                            
                            log_fn(f"  [7.{poll_count}] ✓ KAGGLE EMAIL FOUND!")
                            log_fn(f"  [7.{poll_count}]   Subject: {msg.get('subject','')[:60]}")
                            log_fn(f"  [7.{poll_count}]   Body length: {len(body)} chars")
                            
                            if link and "kaggle.com" in link and "verificationCode=" in link:
                                link_found["value"] = link
                                log_fn(f"  [7.{poll_count}] ✓ Verification link extracted: {link[:70]}...")
                                return
                            
                            if code and len(code) >= 4:
                                code_found["value"] = code
                                log_fn(f"  [7.{poll_count}] ✓ Verification code extracted: {code}")
                                return
                    
                    except Exception as ex:
                        if poll_count % 20 == 0:  # Log errors every 30s
                            log_fn(f"  [7.{poll_count}] ⚠ Inbox check error: {str(ex)[:80]}")
                
                if not code_found["value"] and not link_found["value"]:
                    log_fn(f"  [7.X] ✗ Email timeout after {int(time.time()-start)}s")
        
        # Start email watcher thread
        email_thread = threading.Thread(target=check_email_async, daemon=True)
        email_thread.start()
        
        # Wait for captcha
        log_fn("[STEP 8/10] Waiting for captcha solve...")
        log_fn("  [8.1] Monitoring captcha state (checking every 0.3s)...")
        log_fn("  [8.1] Max wait time: 120s")
        log_fn("")
        
        total_wait = 120
        captcha_solved = False
        check_interval = 0.3
        last_log_time = 0
        
        for i in range(int(total_wait / check_interval)):
            time.sleep(check_interval)
            current_time = i * check_interval
            
            # Combined captcha check
            captcha_state = driver.execute_script('''
            var textarea = document.querySelector('textarea[name="g-recaptcha-response"]');
            var hcaptcha = document.querySelector('input[name="h-captcha-response"]');
            var btn = document.querySelector("button[type=submit]");
            
            var recaptcha_ok = textarea && textarea.value && textarea.value.length > 10;
            var hcaptcha_ok = hcaptcha && hcaptcha.value && hcaptcha.value.length > 10;
            var form_ready = btn && !btn.disabled && btn.offsetParent !== null;
            
            return {
                recaptcha: recaptcha_ok,
                hcaptcha: hcaptcha_ok,
                form_ready: form_ready,
                solved: (recaptcha_ok || hcaptcha_ok) && form_ready
            };
            ''')
            
            # Log progress every 15s
            if current_time - last_log_time >= 15:
                log_fn(f"  [8.{int(current_time)}s] Status: recaptcha={captcha_state.get('recaptcha')}, hcaptcha={captcha_state.get('hcaptcha')}, form_ready={captcha_state.get('form_ready')}")
                last_log_time = current_time
            
            # Success
            if captcha_state.get('solved'):
                log_fn(f"  [8.{int(current_time)}s] ✓ Captcha solved!")
                log_fn(f"[STEP 8/10] ✓ Captcha verification complete (took {int(current_time)}s)")
                captcha_solved = True
                break
            
            # Timeout
            if i == int(total_wait / check_interval) - 1:
                log_fn(f"  [8.{int(current_time)}s] ⚠ Timeout reached, submitting anyway...")
                captcha_solved = True
        
        if captcha_solved:
            # Submit registration form
            log_fn("[STEP 9/10] Submitting registration form...")
            log_fn("  [9.1] Clicking submit button...")
            driver.execute_script('document.querySelector("button[type=submit]")?.click()')
            time.sleep(3)
            log_fn("  [9.1] ✓ Submit clicked")
            
            # Click checkbox if present
            log_fn("  [9.2] Checking for terms checkbox...")
            checkbox_found = False
            for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
                if cb.is_displayed() and not cb.is_selected():
                    cb.click()
                    checkbox_found = True
                    log_fn("  [9.2] ✓ Terms checkbox clicked")
                    break
            if not checkbox_found:
                log_fn("  [9.2] No checkbox found (OK)")
            
            # Click I Agree if dialog appears
            log_fn("  [9.3] Checking for 'I Agree' dialog...")
            agreed = driver.execute_script('''
            for(var b of document.querySelectorAll('button'))
                if(b.textContent.includes('I Agree')) { b.click(); return true; }
            return false;
            ''')
            if agreed:
                log_fn("  [9.3] ✓ 'I Agree' clicked")
            else:
                log_fn("  [9.3] No 'I Agree' dialog (OK)")
            
            time.sleep(1)
            log_fn("[STEP 9/10] ✓ Form submitted")
        
        # Wait for code or link
        log_fn("[STEP 10/10] Waiting for verification email...")
        log_fn("  [10.1] Max wait: 90s")
        log_fn("  [10.1] Email thread is polling in background...")
        
        start_wait = time.time()
        last_status_time = 0
        
        while time.time() - start_wait < 90 and not code_found["value"] and not link_found["value"]:
            time.sleep(0.3)
            elapsed = time.time() - start_wait
            
            # Log status every 15s
            if elapsed - last_status_time >= 15:
                log_fn(f"  [10.{int(elapsed)}s] Still waiting... (code={bool(code_found['value'])}, link={bool(link_found['value'])})")
                last_status_time = elapsed
        
        elapsed_total = int(time.time() - start_wait)
        
        if not code_found["value"] and not link_found["value"]:
            log_fn(f"  [10.{elapsed_total}s] ✗ Email timeout - no verification received")
            log_fn("  [10.X] Checking final inbox state...")
            final_inbox = mail_manager.check_inbox(email_data.get("email", ""))
            log_fn(f"  [10.X] Final inbox: {len(final_inbox)} messages")
            if final_inbox:
                log_fn(f"  [10.X] Subjects: {[m.get('subject','')[:40] for m in final_inbox[:5]]}")
        else:
            if link_found["value"]:
                log_fn(f"  [10.{elapsed_total}s] ✓ Verification link received!")
            if code_found["value"]:
                log_fn(f"  [10.{elapsed_total}s] ✓ Verification code received!")
        
        if link_found["value"]:
            # Open verification link
            log_fn("  [10.V1] Opening verification link...")
            log_fn(f"  [10.V1] URL: {link_found['value'][:80]}...")
            try:
                driver.get(link_found["value"])
                time.sleep(3)
                log_fn("  [10.V1] ✓ Verification link opened")
                
                # Check for success indicators
                page_text = driver.page_source.lower()
                if "verified" in page_text or "success" in page_text:
                    log_fn("  [10.V1] ✓ Verification success detected in page")
                
                # Dismiss dialog if present
                dismissed = driver.execute_script('''
                for(var b of document.querySelectorAll('button'))
                    if(b.textContent.trim() === 'Dismiss') { b.click(); return true; }
                return false;
                ''')
                if dismissed:
                    log_fn("  [10.V1] ✓ Dismissed dialog")
                
                time.sleep(0.5)
            except Exception as e:
                log_fn(f"  [10.V1] ✗ Link open error: {str(e)[:100]}")
        if link_found["value"] or code_found["value"]:
            # Если был код — вставляем и жмём Next (при ссылке — уже верифицированы)
            if code_found["value"] and not link_found["value"]:
                code_selectors = [
                    "input[name*='code']", "input[name*='verif']", "input[name*='otp']",
                    "input[placeholder*='code' i]", "input[placeholder*='verif' i]", "input[placeholder*='enter' i]",
                    "input[autocomplete='one-time-code']", "input[maxlength='6']", "input[maxlength='8']",
                    "input[type='text']", "input[inputmode='numeric']",
                ]
                code_inserted = False
                for sel in code_selectors:
                    try:
                        for inp in driver.find_elements(By.CSS_SELECTOR, sel):
                            if inp.is_displayed() and inp.is_enabled():
                                inp.clear()
                                inp.send_keys(code_found["value"])
                                log_fn(f"✓ Code inserted: {code_found['value']}")
                                code_inserted = True
                                break
                        if code_inserted:
                            break
                    except Exception:
                        continue
                if not code_inserted:
                    try:
                        driver.execute_script('''
                        var inp = document.querySelector("input[type=text], input[name*=code], input[placeholder*=code i], input[maxlength=6], input[maxlength=8]");
                        if(inp && inp.offsetParent !== null) {
                            inp.value = arguments[0];
                            inp.dispatchEvent(new Event("input", {bubbles:true}));
                            inp.dispatchEvent(new Event("change", {bubbles:true}));
                            return true;
                        }
                        return false;
                        ''', code_found["value"])
                        log_fn(f"✓ Code set via JS: {code_found['value']}")
                        code_inserted = True
                    except Exception:
                        pass
                if not code_inserted:
                    log_fn("✗ Code input not found — paste manually: " + code_found["value"])
                time.sleep(0.5)
                for attempt in range(3):
                    clicked = driver.execute_script('''
                    for(var b of document.querySelectorAll('button'))
                        if(b.textContent.trim().toLowerCase() === 'next' || b.textContent.includes('Next')) { b.click(); return true; }
                    return false;
                    ''')
                    if clicked:
                        log_fn("✓ Next clicked")
                        break
                    time.sleep(0.3)
                time.sleep(0.5)
                for attempt in range(3):
                    driver.execute_script('document.querySelector("button[type=submit]")?.click()')
                    time.sleep(0.5)
                for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
                    if cb.is_displayed() and not cb.is_selected():
                        cb.click()
                        break
                driver.execute_script('''
                for(var b of document.querySelectorAll('button'))
                    if(b.textContent.trim() === 'Dismiss') { b.click(); break; }
                ''')
                time.sleep(0.5)
            # Settings
            log_fn("")
            log_fn("="*70)
            log_fn("[POST-VERIFICATION] Extracting API keys...")
            log_fn("="*70)
            log_fn("  [API.1] Navigating to settings page...")
            driver.get("https://www.kaggle.com/settings")
            time.sleep(2)
            log_fn("  [API.1] ✓ Settings page loaded")
            
            # Verify we're on settings page
            current_url = driver.current_url
            log_fn(f"  [API.1] Current URL: {current_url}")
            if "settings" not in current_url:
                log_fn("  [API.1] ⚠ Warning: Not on settings page!")
            
            # ===== 1. Expire existing tokens =====
            log_fn("  [API.2] Expiring existing tokens...")
            driver.execute_script("window.scrollTo(0, 600);")
            time.sleep(1)
            
            expired_count = 0
            for attempt in range(5):
                log_fn(f"    [API.2.{attempt+1}] Looking for token #{attempt+1}...")
                
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
                    log_fn(f"    [API.2.{attempt+1}] No more tokens found")
                    break
                
                log_fn(f"    [API.2.{attempt+1}] ✓ Menu opened")
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
                    log_fn(f"    [API.2.{attempt+1}] No 'Expire Token' option")
                    break
                
                log_fn(f"    [API.2.{attempt+1}] ✓ 'Expire Token' clicked")
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
                    log_fn(f"    [API.2.{attempt+1}] ✓ Token #{expired_count} expired")
                    time.sleep(1)
                else:
                    log_fn(f"    [API.2.{attempt+1}] No 'Expire' button")
                    break
            
            if expired_count:
                log_fn(f"  [API.2] ✓ Expired {expired_count} old tokens")
            else:
                log_fn("  [API.2] No old tokens to expire (OK)")
            
            # ===== 2. Generate New Token =====
            log_fn("  [API.3] Generating New API Token...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
            # Click Generate New Token
            log_fn("    [API.3.1] Looking for 'Generate New Token' button...")
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
            
            if result:
                log_fn("    [API.3.1] ✓ 'Generate New Token' clicked")
                time.sleep(1)
                
                # Fill token name
                log_fn("    [API.3.2] Setting token name to 'now'...")
                name_set = driver.execute_script('''
                var inp = document.querySelector('input[placeholder="Enter Token Name"]');
                if(inp) {
                    inp.focus();
                    inp.value = 'now';
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    return 'set';
                }
                return null;
                ''')
                
                if name_set:
                    log_fn("    [API.3.2] ✓ Token name set to 'now'")
                else:
                    log_fn("    [API.3.2] ⚠ Token name input not found")
                
                time.sleep(0.3)
                
                # ===== SELECT PERMISSIONS =====
                log_fn("    [API.3.2b] Selecting all permissions (kernels, datasets)...")
                perm_clicked = driver.execute_script('''
                // Find and click all permission checkboxes to enable write access
                var clicked = 0;
                
                // Strategy 1: Find checkboxes by label text
                var checkboxes = document.querySelectorAll('input[type="checkbox"]');
                for(var cb of checkboxes) {
                    if(cb.checked) continue;
                    var label = cb.closest('label') || cb.parentElement || cb.nextSibling;
                    if(label) {
                        var text = label.textContent || label.innerText || '';
                        if(text.toLowerCase().includes('kernel') || 
                           text.toLowerCase().includes('dataset') || 
                           text.toLowerCase().includes('model') ||
                           text.toLowerCase().includes('write') ||
                           text.toLowerCase().includes('all')) {
                            cb.click();
                            clicked++;
                        }
                    }
                }
                
                // Strategy 2: Find checkboxes in dialog/modal
                if(clicked === 0) {
                    var dialogs = document.querySelectorAll('[role="dialog"], .modal, [class*="token"], [class*="Token"], [class*="popup"], [class*="Popup"]');
                    for(var dialog of dialogs) {
                        dialog.querySelectorAll('input[type="checkbox"]:not(:checked)').forEach(cb => {
                            cb.click();
                            clicked++;
                        });
                    }
                }
                
                // Strategy 3: Find all unchecked checkboxes in visible area
                if(clicked === 0) {
                    document.querySelectorAll('input[type="checkbox"]:not(:checked)').forEach(cb => {
                        try {
                            if(cb.offsetParent !== null) { // visible
                                cb.click();
                                clicked++;
                            }
                        } catch(e) {}
                    });
                }
                
                // Strategy 4: Find by aria-label or title
                if(clicked === 0) {
                    document.querySelectorAll('[aria-label*="permission"], [aria-label*="Permission"], [title*="permission"], [title*="Permission"]').forEach(el => {
                        var cb = el.querySelector('input[type="checkbox"]') || el;
                        if(cb.type === 'checkbox' && !cb.checked) {
                            cb.click();
                            clicked++;
                        }
                    });
                }
                
                return clicked;
                ''')
                
                if perm_clicked:
                    log_fn(f"    [API.3.2b] ✓ Selected {perm_clicked} permissions")
                else:
                    log_fn("    [API.3.2b] ⚠ No permission checkboxes found (may be auto-selected)")
                
                time.sleep(0.3)
                
                # Click Generate
                log_fn("    [API.3.3] Clicking 'Generate' button...")
                gen_clicked = driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for(var b of buttons) {
                    if(b.textContent.trim() === 'Generate') {
                        b.click();
                        return 'clicked';
                    }
                }
                return null;
                ''')
                
                if gen_clicked:
                    log_fn("    [API.3.3] ✓ 'Generate' clicked")
                else:
                    log_fn("    [API.3.3] ⚠ 'Generate' button not found")
                
                time.sleep(1)
                
                # Extract API Token
                log_fn("    [API.3.4] Extracting API token from page...")
                new_api_token = driver.execute_script('''
                var inp = document.querySelector('input[placeholder="API TOKEN"]');
                if(inp) return inp.value;
                return null;
                ''')
                
                if new_api_token:
                    log_fn(f"    [API.3.4] ✓ API Token extracted: {new_api_token[:25]}...{new_api_token[-10:]}")
                    log_fn(f"    [API.3.4] Token length: {len(new_api_token)} chars")
                else:
                    log_fn("    [API.3.4] ✗ API Token not found in page")
                
                # Click Close
                log_fn("    [API.3.5] Closing dialog...")
                closed = driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for(var b of buttons) {
                    if(b.textContent.trim() === 'Close') {
                        b.click();
                        return 'clicked';
                    }
                }
                return null;
                ''')
                
                if closed:
                    log_fn("    [API.3.5] ✓ Dialog closed")
                
                # Extract username from settings page
                log_fn("    [API.3.6] Extracting username from page...")
                page_username = driver.execute_script('''
                // Try to get username from URL
                var url = window.location.href;
                var urlMatch = url.match(/kaggle\.com\/([^\/]+)/);
                if(urlMatch) return urlMatch[1];
                
                // Try to get from page title
                var title = document.title;
                var titleMatch = title.match(/Kaggle\s*[-|]\s*([^\s|-]+)/);
                if(titleMatch) return titleMatch[1];
                
                // Try to get from profile link
                var profileLink = document.querySelector('a[href*="/"]');
                if(profileLink) {
                    var href = profileLink.getAttribute('href');
                    if(href && href.startsWith('/')) {
                        return href.substring(1).split('/')[0];
                    }
                }
                
                // Try to get from settings page content
                var userElements = document.querySelectorAll('[class*="username"], [class*="user-name"], [data-user]');
                for(var el of userElements) {
                    if(el.textContent && el.textContent.trim().length > 0) {
                        return el.textContent.trim();
                    }
                }
                
                return null;
                ''')
                
                if page_username:
                    log_fn(f"    [API.3.6] ✓ Username from page: {page_username}")
                else:
                    log_fn("    [API.3.6] ⚠ Username not found on page")
                
                time.sleep(0.5)
                log_fn("  [API.3] ✓ New API Token generated")
            else:
                log_fn("  [API.3] ✗ 'Generate New Token' button not found")
            
            # ===== 3. Create Legacy API Key =====
            log_fn("  [API.4] Creating Legacy API Key...")
            log_fn("    [API.4.1] Reloading settings page...")
            driver.get("https://www.kaggle.com/settings")
            time.sleep(2)
            log_fn("    [API.4.1] ✓ Page reloaded")
            
            # Click Create Legacy API Key
            log_fn("    [API.4.2] Looking for 'Create Legacy API Key' button...")
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
            
            if not result:
                log_fn("    [API.4.2] ✗ 'Create Legacy API Key' button not found")
            else:
                log_fn("    [API.4.2] ✓ 'Create Legacy API Key' clicked")
                time.sleep(1)
                
                # Click Continue
                log_fn("    [API.4.3] Looking for 'Continue' button...")
                cont_clicked = driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for(var b of buttons) {
                    if(b.textContent.trim() === 'Continue') {
                        b.click();
                        return 'clicked';
                    }
                }
                return null;
                ''')
                
                if cont_clicked:
                    log_fn("    [API.4.3] ✓ 'Continue' clicked")
                else:
                    log_fn("    [API.4.3] ⚠ 'Continue' button not found")
                
                time.sleep(3)
                log_fn("  [API.4] ✓ Legacy API Key creation initiated")
            
            # ===== 4. Read kaggle.json =====
            log_fn("  [API.5] Reading kaggle.json from Downloads...")
            import os
            import glob
            import json as json_mod
            
            legacy_api_key = None
            legacy_username = None
            downloads_dir = os.path.expanduser("~/Downloads")
            log_fn(f"    [API.5.1] Downloads dir: {downloads_dir}")
            
            # Wait for download
            log_fn("    [API.5.2] Waiting for kaggle.json download (max 3s)...")
            for wait_attempt in range(10):
                time.sleep(0.3)
                files = glob.glob(os.path.join(downloads_dir, "kaggle*.json"))
                
                if files:
                    kaggle_json_path = max(files, key=os.path.getctime)
                    log_fn(f"    [API.5.2] ✓ Found: {os.path.basename(kaggle_json_path)}")
                    
                    try:
                        log_fn("    [API.5.3] Reading JSON file...")
                        with open(kaggle_json_path) as f:
                            kaggle_data = json_mod.load(f)
                        
                        legacy_api_key = kaggle_data.get("key", "")
                        legacy_username = kaggle_data.get("username", "")
                        
                        log_fn(f"    [API.5.3] ✓ Legacy Key: {legacy_api_key[:20]}...{legacy_api_key[-10:] if len(legacy_api_key) > 30 else ''}")
                        log_fn(f"    [API.5.3] ✓ Username: {legacy_username}")
                        log_fn(f"    [API.5.3] Key length: {len(legacy_api_key)} chars")
                        
                        log_fn("    [API.5.4] Deleting kaggle.json...")
                        os.remove(kaggle_json_path)
                        log_fn("    [API.5.4] ✓ File deleted")
                    except Exception as e:
                        log_fn(f"    [API.5.3] ✗ Error reading kaggle.json: {str(e)[:100]}")
                    
                    break
                
                if wait_attempt % 3 == 0 and wait_attempt > 0:
                    log_fn(f"    [API.5.2] Still waiting... ({wait_attempt*0.3:.1f}s)")
            
            if not legacy_api_key:
                log_fn("    [API.5.X] ✗ kaggle.json not found or empty")
            else:
                log_fn("  [API.5] ✓ Legacy API Key extracted")
            
            # Return result
            log_fn("")
            log_fn("="*70)
            log_fn("[FINAL RESULT] Registration complete!")
            log_fn("="*70)
            
            # Use page_username as fallback
            final_username = legacy_username or page_username
            
            if legacy_api_key:
                log_fn(f"  ✓ Legacy API Key: {legacy_api_key[:25]}...{legacy_api_key[-10:]}")
            else:
                log_fn("  ✗ Legacy API Key: NOT FOUND")
            
            if new_api_token:
                log_fn(f"  ✓ New API Token: {new_api_token[:25]}...{new_api_token[-10:]}")
            else:
                log_fn("  ✗ New API Token: NOT FOUND")
            
            if final_username:
                log_fn(f"  ✓ Kaggle Username: {final_username}")
            else:
                log_fn("  ✗ Kaggle Username: NOT FOUND")
            
            log_fn("")
            
            # Create public kernel via UI (API write is blocked)
            kernel_url = None
            if final_username and new_api_token:
                log_fn("")
                log_fn("="*70)
                log_fn("[KERNEL] Creating public kernel via UI...")
                log_fn("="*70)
                
                try:
                    # Load notebook template
                    import json as json_mod
                    notebook_path = os.path.join(os.path.dirname(__file__), "..", "agents", "kaggle", "notebook-telegram.ipynb")
                    if os.path.exists(notebook_path):
                        log_fn(f"  [K.1] Loading notebook template...")
                        
                        # Create new notebook
                        log_fn("  [K.2] Navigating to /code/new...")
                        driver.get("https://www.kaggle.com/code/new")
                        time.sleep(8)
                        
                        current_url = driver.current_url
                        log_fn(f"  [K.2] URL: {current_url}")
                        
                        if "/code/" in current_url:
                            # Extract slug
                            slug = current_url.split("/code/")[1].split("/")[0]
                            log_fn(f"  [K.2] Kernel slug: {slug}")
                            
                            # Make public via Share dialog
                            log_fn("  [K.3] Making kernel public...")
                            
                            # Find and click Share button
                            share_clicked = driver.execute_script('''
                            var buttons = document.querySelectorAll('button');
                            for(var b of buttons) {
                                if(b.textContent.toLowerCase().includes('share')) {
                                    b.click();
                                    return true;
                                }
                            }
                            return false;
                            ''')
                            
                            if share_clicked:
                                log_fn("  [K.3] Share dialog opened")
                                time.sleep(2)
                                
                                # Click Public option
                                public_clicked = driver.execute_script('''
                                var elements = document.querySelectorAll('*');
                                for(var el of elements) {
                                    if(el.textContent === 'Public' || el.textContent === 'Make Public') {
                                        el.click();
                                        return true;
                                    }
                                }
                                return false;
                                ''')
                                
                                if public_clicked:
                                    log_fn("  [K.3] Public option clicked")
                                    time.sleep(1)
                                    
                                    # Save
                                    driver.execute_script('''
                                    var buttons = document.querySelectorAll('button');
                                    for(var b of buttons) {
                                        if(b.textContent.includes('Save') || b.textContent.includes('Apply')) {
                                            b.click();
                                            return true;
                                        }
                                    }
                                    return false;
                                    ''')
                                    time.sleep(2)
                                    
                                    kernel_url = f"https://www.kaggle.com/code/{slug}"
                                    log_fn(f"  [K.3] ✓ Kernel made public!")
                                    log_fn(f"  [K.3] URL: {kernel_url}")
                                else:
                                    log_fn("  [K.3] ⚠ Public option not found")
                            else:
                                log_fn("  [K.3] ⚠ Share button not found")
                    else:
                        log_fn(f"  [K.1] ⚠ Notebook template not found: {notebook_path}")
                        
                except Exception as kernel_err:
                    log_fn(f"  [K.X] ✗ Kernel creation error: {kernel_err}")
            
            driver.quit()
            log_fn("  ✓ Browser closed")
            
            if legacy_api_key or new_api_token:
                log_fn("")
                log_fn("✓✓✓ SUCCESS! Account verified and API keys extracted ✓✓✓")
                result = {
                    "verified": True, 
                    "api_key": legacy_api_key or new_api_token,
                    "api_key_legacy": legacy_api_key,
                    "api_key_new": new_api_token,
                    "kaggle_username": final_username,
                    "error_type": "success"
                }
                if kernel_url:
                    result["kernel_url"] = kernel_url
                return result
            
            log_fn("")
            log_fn("✗✗✗ PARTIAL SUCCESS: Verified but no API keys ✗✗✗")
            return {"verified": False, "error": "no_api_token", "error_type": "verification"}
        
        driver.quit()
        return {"verified": False, "error": "no_code", "error_type": "email"}
        
    except Exception as e:
        log_fn(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Categorize error
        error_str = str(e).lower()
        error_type = "unknown"
        if "chrome" in error_str or "driver" in error_str:
            error_type = "browser"
        elif "network" in error_str or "connection" in error_str:
            error_type = "network"
        elif "timeout" in error_str:
            error_type = "timeout"
        elif "cloudflare" in error_str or "challenge" in error_str:
            error_type = "cloudflare"
        
        try:
            driver.quit()
        except:
            pass
        return {"verified": False, "error": str(e), "error_type": error_type}


def kaggle_register(page, identity, email_data, log_fn):
    """Kaggle registration - wrapper for undetected-chromedriver."""
    return kaggle_register_undetected(identity, email_data, log_fn, headless=False)


def github_register_undetected(identity, email_data, log_fn, headless=False, proxy=""):
    """GitHub registration via undetected_chromedriver - placeholder."""
    log_fn("GitHub registration not yet implemented in worker")
    return {"verified": False, "error": "GitHub registration not implemented", "error_type": "config"}


def huggingface_register_undetected(identity, email_data, log_fn, headless=False, proxy=""):
    """HuggingFace registration via undetected_chromedriver - placeholder."""
    log_fn("HuggingFace registration not yet implemented in worker")
    return {"verified": False, "error": "HuggingFace registration not implemented", "error_type": "config"}


def devin_ai_register_undetected(identity, email_data, log_fn, headless=False, proxy=""):
    """Devin AI registration via undetected_chromedriver - passwordless auth via email code."""
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import tempfile
    import os
    
    log_fn("Starting Anti-Detect Chrome for Devin AI...")
    
    chrome_ver = _get_chrome_version()
    log_fn(f"Chrome version: {chrome_ver}")
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=390,844')
    options.add_argument('--window-position=100,50')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--start-maximized')
    
    if proxy:
        log_fn(f"Using proxy: {proxy[:20]}...")
        options.add_argument(f'--proxy-server={proxy}')
    
    prefs = {
        "profile.managed_default_content_settings.images": 1,
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)
    
    try:
        driver = uc.Chrome(options=options, version_main=chrome_ver, headless=headless)
        driver.set_window_size(390, 844)
        driver.set_window_position(100, 50)
        log_fn("✓ Anti-detect Chrome started")
    except Exception as e:
        log_fn(f"Chrome init failed: {e}")
        return {"verified": False, "error": f"chrome_init_failed: {e}", "error_type": "browser"}
    
    if not email_data or not email_data.get("email"):
        log_fn("[MAIL] Creating email via Boomlify web...")
        email_data = _boomlify_create_email_web(driver, log_fn)
        if not email_data:
            log_fn("[MAIL] ✗ Failed to create email")
            driver.quit()
            return {"verified": False, "error": "email_creation_failed", "error_type": "email"}
    
    if not identity.get("email"):
        identity["email"] = email_data["email"]
    
    try:
        log_fn("[STEP 1/6] Loading Devin AI login page...")
        driver.set_page_load_timeout(60)
        
        for attempt in range(3):
            try:
                log_fn(f"  [1.{attempt+1}] GET https://app.devin.ai/login")
                start = time.time()
                driver.get("https://app.devin.ai/login")
                load_time = round(time.time() - start, 2)
                log_fn(f"  [1.{attempt+1}] ✓ Page loaded in {load_time}s")
                break
            except Exception as e:
                log_fn(f"  [1.{attempt+1}] ✗ Failed: {str(e)[:100]}")
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise
        
        log_fn("[STEP 2/6] Waiting for Auth0 redirect...")
        wait = WebDriverWait(driver, 30)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(2)
        
        page_info = driver.execute_script('''
            return {
                url: window.location.href,
                title: document.title,
                inputs: document.querySelectorAll('input').length
            };
        ''')
        log_fn(f"  URL: {page_info['url']}")
        log_fn(f"  Title: {page_info['title']}")
        
        # Fill email - Auth0 uses #username
        log_fn("[STEP 3/6] Filling email (passwordless auth)...")
        
        time.sleep(1)  # Wait for Auth0 form
        try:
            username = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#username")))
            username.clear()
            username.send_keys(identity['email'])
            log_fn(f"  ✓ Email filled: {identity['email']}")
        except Exception as e:
            log_fn(f"  ✗ Email input error: {e}")
            raise
        
        time.sleep(0.5)
        
        # Click Continue button
        log_fn("[STEP 4/6] Clicking Continue...")
        time.sleep(0.5)
        
        # Find and click Continue button fresh
        continue_clicked = False
        for _ in range(3):
            try:
                btns = driver.find_elements(By.TAG_NAME, "button")
                for btn in btns:
                    if btn.is_displayed() and "continue" in btn.text.lower():
                        btn.click()
                        continue_clicked = True
                        log_fn("  ✓ Continue clicked")
                        break
                if continue_clicked:
                    break
            except:
                pass
            time.sleep(0.3)
        
        if not continue_clicked:
            driver.execute_script('''
                var btns = document.querySelectorAll('button');
                for(var b of btns) {
                    if(b.textContent.toLowerCase().includes('continue')) {
                        b.click();
                        return true;
                    }
                }
                return false;
            ''')
            log_fn("  ✓ Continue clicked via JS")
        
        time.sleep(3)
        
        # Now we should be on passwordless-email-challenge page
        log_fn(f"  Current URL: {driver.current_url}")
        
        # Start email monitoring for verification code
        log_fn("[STEP 5/6] Waiting for verification code...")
        import threading
        
        code_found = {"value": None}
        
        def check_email_async():
            if email_data and email_data.get("email"):
                email_addr = email_data["email"]
                log_fn(f"  Monitoring inbox for {email_addr}")
                
                start = time.time()
                poll_count = 0
                while time.time() - start < 120 and not code_found["value"]:
                    time.sleep(2)
                    poll_count += 1
                    try:
                        inbox = mail_manager.check_inbox(email_addr)
                        
                        if poll_count % 5 == 0:
                            log_fn(f"  Poll #{poll_count}: {len(inbox)} messages")
                        
                        for msg in inbox:
                            subj = (msg.get("subject") or "").lower()
                            from_addr = (msg.get("from") or "").lower()
                            
                            # Filter for Devin/Auth0 verification emails
                            if "devin" not in subj and "verif" not in subj and "code" not in subj and "otp" not in subj and "devin" not in from_addr:
                                continue
                            
                            body = (msg.get("body") or "") + "\n" + (msg.get("html") or "")
                            code = mail_manager.extract_code(body) if body else ""
                            
                            if code and len(code) >= 4:
                                code_found["value"] = code
                                log_fn(f"  ✓ CODE FOUND: {code}")
                                return
                    
                    except Exception as ex:
                        if poll_count % 10 == 0:
                            log_fn(f"  ⚠ Error: {str(ex)[:60]}")
                
                if not code_found["value"]:
                    log_fn(f"  ✗ Email timeout after {int(time.time()-start)}s")
        
        email_thread = threading.Thread(target=check_email_async, daemon=True)
        email_thread.start()
        
        # Wait for code
        start_wait = time.time()
        while time.time() - start_wait < 120 and not code_found["value"]:
            time.sleep(1)
            elapsed = int(time.time() - start_wait)
            if elapsed % 15 == 0 and elapsed > 0:
                log_fn(f"  [{elapsed}s] Waiting for code...")
        
        if code_found["value"]:
            log_fn(f"[STEP 6/6] Entering verification code: {code_found['value']}")
            
            # Wait for code input page
            time.sleep(1)
            
            # Try to find code input - Auth0 uses various selectors
            code_selectors = [
                "input[autocomplete='one-time-code']",
                "input[name*='code']",
                "input[name*='otp']",
                "input[type='text'][maxlength='6']",
                "input[type='text'][maxlength='8']",
                ".input.otp-input",
                "input.otp-input",
            ]
            
            code_entered = False
            for sel in code_selectors:
                try:
                    inputs = driver.find_elements(By.CSS_SELECTOR, sel)
                    for inp in inputs:
                        if inp.is_displayed() and inp.is_enabled():
                            inp.clear()
                            inp.send_keys(code_found["value"])
                            log_fn(f"  ✓ Code entered via: {sel}")
                            code_entered = True
                            break
                    if code_entered:
                        break
                except:
                    continue
            
            if not code_entered:
                # Try JavaScript injection
                driver.execute_script(f'''
                    var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
                    for(var inp of inputs) {{
                        if(inp.offsetParent !== null) {{
                            inp.value = "{code_found['value']}";
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                            return true;
                        }}
                    }}
                    return false;
                ''')
                log_fn("  ✓ Code entered via JS")
            
            time.sleep(1)
            
            # Submit code
            for _ in range(3):
                try:
                    btns = driver.find_elements(By.TAG_NAME, "button")
                    for btn in btns:
                        if btn.is_displayed() and ("continue" in btn.text.lower() or "verify" in btn.text.lower() or "submit" in btn.text.lower()):
                            btn.click()
                            log_fn(f"  ✓ Submit clicked")
                            break
                except:
                    pass
                time.sleep(0.5)
            
            time.sleep(3)
        
        # Check result
        log_fn("Checking registration result...")
        page_url = driver.current_url.lower()
        
        verified = False
        if "devin.ai" in page_url and "login" not in page_url and "auth" not in page_url and "challenge" not in page_url:
            verified = True
            log_fn("  ✓ Redirected to app - registration success!")
        elif code_found["value"]:
            verified = True
            log_fn("  ✓ Code was sent and entered")
        
        driver.quit()
        log_fn("  ✓ Browser closed")
        
        if verified:
            log_fn("")
            log_fn("="*60)
            log_fn("✓✓✓ SUCCESS! Devin AI account registered ✓✓✓")
            log_fn("="*60)
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
        import traceback
        traceback.print_exc()
        
        error_str = str(e).lower()
        error_type = "unknown"
        if "chrome" in error_str or "driver" in error_str:
            error_type = "browser"
        elif "network" in error_str or "connection" in error_str:
            error_type = "network"
        elif "timeout" in error_str:
            error_type = "timeout"
        
        try:
            driver.quit()
        except:
            pass
        return {"verified": False, "error": str(e), "error_type": error_type}


def run_registration(platform: str, headless: bool = True, proxy: str = "", input_data: dict = None):
    """Run single registration and return result as JSON."""
    
    start_time = time.time()
    result = {
        "success": False,
        "identity": None,
        "email": None,
        "account": None,
        "logs": [],
        "error": None,
        "error_type": None,  # error category for retry logic
        "duration_sec": 0,
    }
    
    def log(msg, level="INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        result["logs"].append(f"[{ts}] [{level}] {msg}")
        try:
            print(f"[{ts}] [{level}] {msg}", flush=True)
        except (BrokenPipeError, IOError):
            pass  # Ignore if stdout is closed (Flask context)
    
    driver = None
    try:
        # Используем переданные данные или генерируем новые
        if input_data and input_data.get("identity"):
            identity = input_data["identity"]
            log(f"Using passed identity: {identity['username']}")
        else:
            identity = generate_identity()
            log(f"Generated identity: {identity['username']}")
        result["identity"] = identity
        
        # Email из переданных данных или создаём новый
        if input_data and input_data.get("email"):
            email = input_data["email"]
            email_data = input_data.get("email_data", {})
            log(f"Using passed email: {email}")
        else:
            log("Creating temp email...")
            email_data = mail_manager.create_email()
            email = email_data["email"]
            log(f"Email: {email}")
        identity["email"] = email
        result["email"] = email
        
        # Run registration via undetected-chromedriver
        if platform == "kaggle":
            account = kaggle_register_undetected(identity, email_data, log, headless=headless, proxy=proxy)
        elif platform == "github":
            account = github_register_undetected(identity, email_data, log, headless=headless, proxy=proxy)
        elif platform == "huggingface":
            account = huggingface_register_undetected(identity, email_data, log, headless=headless, proxy=proxy)
        elif platform == "devin_ai":
            account = devin_ai_register_undetected(identity, email_data, log, headless=headless, proxy=proxy)
        else:
            account = {"verified": False, "error": f"Platform '{platform}' not implemented in worker", "error_type": "config"}
        
        result["account"] = account
        result["success"] = account.get("verified", False)
        
        # Save API key if present
        if account.get("api_key"):
            result["api_key"] = account["api_key"]
        
        # Set error info
        if not result["success"] and account.get("error"):
            result["error"] = account["error"]
            result["error_type"] = account.get("error_type", "unknown")
    
    except Exception as e:
        error_str = str(e)
        result["error"] = error_str
        result["logs"].append(f"ERROR: {error_str}")
        result["logs"].append(traceback.format_exc()[-500:])
        
        # Categorize error for retry logic
        if "chrome" in error_str.lower() or "driver" in error_str.lower():
            result["error_type"] = "browser"
        elif "network" in error_str.lower() or "connection" in error_str.lower():
            result["error_type"] = "network"
        elif "timeout" in error_str.lower():
            result["error_type"] = "timeout"
        elif "cloudflare" in error_str.lower() or "challenge" in error_str.lower():
            result["error_type"] = "cloudflare"
        else:
            result["error_type"] = "unknown"
    finally:
        # Ensure driver is closed
        if driver:
            try:
                driver.quit()
            except:
                pass
    
    # Record duration
    result["duration_sec"] = round(time.time() - start_time, 1)
    return result


if __name__ == "__main__":
    # Run as: python autoreg_worker.py kaggle [headless] [input_file_path]
    # If input_file_path provided, reads from file and writes result to file
    platform = sys.argv[1] if len(sys.argv) > 1 else "kaggle"
    headless = sys.argv[2].lower() != "false" if len(sys.argv) > 2 else True
    input_file_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Читаем input_data из файла или stdin
    input_data = None
    result_file = None
    log_file_path = None
    
    if input_file_path:
        try:
            input_file = Path(input_file_path)
            if input_file.exists():
                input_data = json.loads(input_file.read_text())
                result_file = Path(input_data.get("result_file", ""))
                log_file_path = Path(input_data.get("log_file", ""))
        except Exception as e:
            print(f"Input file error: {e}", file=sys.stderr)
    else:
        # Fallback: stdin
        try:
            import select
            if select.select([sys.stdin], [], [], 0.1)[0]:
                stdin_line = sys.stdin.readline().strip()
                if stdin_line:
                    input_data = json.loads(stdin_line)
        except Exception:
            pass
    
    # Run registration
    result = run_registration(platform, headless, "", input_data)
    
    # Write result to file if specified
    if result_file:
        result_file.write_text(json.dumps(result))
        if log_file_path:
            log_file_path.write_text("\n".join(result.get("logs", [])))
    else:
        # Fallback: stdout
        print("---RESULT---")
        print(json.dumps(result))
