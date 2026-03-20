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

# Add parent to path
_C2_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_C2_ROOT))

from faker import Faker
from tempmail import mail_manager
from captcha_solver import (
    setup_stealth_only, setup_captcha_block,
    solve_captcha_on_page, SITES_NEED_REAL_CAPTCHA,
    solve_recaptcha_api, get_captcha_key_for_solve,
)
from utils import generate_identity
try:
    from kaggle_captcha_solver import solve_kaggle_registration_captcha
except ImportError:
    solve_kaggle_registration_captcha = None

fake = Faker("en_US")


# generate_identity moved to utils.py


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
    
    try:
        driver = uc.Chrome(options=options, version_main=chrome_ver, headless=headless)
        driver.set_window_size(390, 844)
        driver.set_window_position(100, 50)
        log_fn("✓ Anti-detect Chrome started")
    except Exception as e:
        log_fn(f"Chrome init failed: {e}")
        return {"verified": False, "error": f"chrome_init_failed: {e}", "error_type": "browser"}
    
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
        log_fn("Loading Kaggle...")
        driver.set_page_load_timeout(60)  # Increased from 15 to 60
        
        # Retry logic for Cloudflare
        for attempt in range(3):
            try:
                driver.get("https://www.kaggle.com/account/login?phase=emailRegister&returnUrl=%2F")
                break
            except Exception as e:
                if attempt < 2:
                    log_fn(f"Page load attempt {attempt+1} failed, retrying...")
                    time.sleep(2)
                else:
                    raise
        
        # Wait for page ready
        wait = WebDriverWait(driver, 30)  # Increased from 15
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        log_fn("✓ Page loaded")
        
        # Check for Cloudflare challenge
        time.sleep(2)
        if "challenge" in driver.current_url or "cloudflare" in driver.page_source.lower():
            log_fn("⚠ Cloudflare challenge detected - waiting...")
            for cf_wait in range(30):  # Wait up to 30s for CF to pass
                time.sleep(1)
                if "challenge" not in driver.current_url and "cloudflare" not in driver.page_source.lower():
                    log_fn("✓ Cloudflare passed")
                    break
                if cf_wait == 29:
                    log_fn("⚠ Cloudflare still present - continuing anyway")
        
        
        # Fill form - registration page has type='email' for email input!
        display_name = identity["username"].replace("_", " ")
        
        # Email input (type='email' on registration page)
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_input.send_keys(identity['email'])
        
        # Password input
        pwd_input = driver.find_element(By.NAME, "password")
        pwd_input.send_keys(identity['password'])
        
        # Display name - find by placeholder
        name_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder*='full name']")
        name_input.send_keys(display_name)
        
        log_fn(f"✓ Form filled: {identity['email']}")
        
        # Try auto-solve captcha via API first
        log_fn("Attempting auto-solve reCAPTCHA...")
        captcha_solved = False
        
        # Get sitekey
        try:
            sitekey_el = driver.find_element(By.CSS_SELECTOR, ".g-recaptcha[data-sitekey], [data-sitekey]")
            sitekey = sitekey_el.get_attribute("data-sitekey")
            log_fn(f"Sitekey: {sitekey}")
            
            # Try to solve via API
            from captcha_solver import solve_recaptcha_api
            class FakeJob:
                def log(self, msg): log_fn(f"[CAPTCHA] {msg}")
            
            token = solve_recaptcha_api(sitekey, driver.current_url, FakeJob())
            if token:
                log_fn("✓ Got captcha token, injecting...")
                driver.execute_script(f"""
                    document.querySelector('textarea[name="g-recaptcha-response"]').value = '{token}';
                    ___grecaptcha_cfg && ___grecaptcha_cfg.clients && Object.values(___grecaptcha_cfg.clients).forEach(c => c && c.callback && c.callback('{token}'));
                """)
                captcha_solved = True
                log_fn("✓ Captcha auto-solved!")
        except Exception as e:
            log_fn(f"Auto-solve failed: {e} - falling back to manual")
        
        # Click reCAPTCHA checkbox if not auto-solved
        if not captcha_solved:
            log_fn("Clicking reCAPTCHA checkbox...")
            try:
                # Switch to reCAPTCHA iframe
                captcha_iframe = driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
                driver.switch_to.frame(captcha_iframe)
                
                # Click the checkbox inside iframe
                checkbox = driver.find_element(By.CSS_SELECTOR, ".recaptcha-checkbox-checkmark")
                driver.execute_script("arguments[0].click();", checkbox)
                
                # Switch back to main page
                driver.switch_to.default_content()
                log_fn("✓ reCAPTCHA clicked - solve the challenge")
            except Exception as e:
                log_fn(f"reCAPTCHA click error: {e}")
        
        
        log_fn(">>> Solve captcha manually if not auto-solved - rest is automatic <<<")
        log_fn(f"[MAIL] Email: {email_data.get('email','?')} provider={email_data.get('provider','?')}")
        
        # Start email checking in background thread (API - no browser switching)
        from tempmail import mail_manager
        import threading
        
        code_found = {"value": None}
        link_found = {"value": None}
        
        def check_email_async():
            if email_data and email_data.get("email"):
                email_addr = email_data["email"]
                provider = email_data.get("provider", "?")
                log_fn(f"[MAIL] Polling {email_addr} (provider={provider})")
                start = time.time()
                poll_count = 0
                while time.time() - start < 90 and not code_found["value"] and not link_found["value"]:
                    time.sleep(1.5)  # Faster polling (was 3s)
                    poll_count += 1
                    try:
                        # Use API (no browser switching issues)
                        inbox = mail_manager.check_inbox(email_addr)
                        log_fn(f"[MAIL] Poll #{poll_count}: inbox={len(inbox)} msgs")
                        if inbox:
                            for i, msg in enumerate(inbox[:5]):
                                subj = (msg.get("subject") or "?")[:60]
                                from_addr = (msg.get("from") or "?")[:40]
                                body_preview = ((msg.get("body") or "")[:80] + "..") if (msg.get("body") or "") else ""
                                log_fn(f"[MAIL]   msg[{i}]: subj={subj!r} from={from_addr!r}")
                                if body_preview:
                                    log_fn(f"[MAIL]     body_preview: {body_preview!r}")
                        for msg in inbox:
                            subj = (msg.get("subject") or "").lower()
                            from_addr = (msg.get("from") or "").lower()
                            if "kaggle" not in subj and "verif" not in subj and "code" not in subj and "verify" not in subj and "confirm" not in subj and "kaggle" not in from_addr:
                                log_fn(f"[MAIL]   Skip (no kaggle/verif): subj={subj[:50]!r}")
                                continue
                            body = (msg.get("body") or "") + "\n" + (msg.get("html") or "")
                            code = mail_manager.extract_code(body) if body else ""
                            link = mail_manager.extract_link(body) if body else ""
                            log_fn(f"[MAIL] Match! subj={msg.get('subject','')[:50]!r} body_len={len(body)} code={code!r} link={link[:60]!r}..." if link else f"[MAIL] Match! subj={msg.get('subject','')[:50]!r} body_len={len(body)} code={code!r}")
                            if link and "kaggle.com" in link and "verificationCode=" in link:
                                link_found["value"] = link
                                log_fn(f"✓ Link: {link[:80]}...")
                                return
                            if code and len(code) >= 4:
                                code_found["value"] = code
                                log_fn(f"✓ Code: {code}")
                                return
                    except Exception as ex:
                        log_fn(f"[MAIL] Inbox error: {ex}")
                        import traceback
                        log_fn(traceback.format_exc()[-300:])
        
        # Start email watcher thread
        email_thread = threading.Thread(target=check_email_async, daemon=True)
        email_thread.start()
        
        # Wait for captcha - Kaggle may show MULTIPLE captchas in sequence
        log_fn(">>> Solve ALL captchas manually - rest is automatic <<<")
        
        # Wait for ALL captchas to be solved (Kaggle shows multiple)
        total_wait = 120  # 2 minutes max (reduced from 3)
        captcha_solved = False
        check_interval = 0.3  # Check every 0.3s for faster response
        
        for i in range(int(total_wait / check_interval)):
            time.sleep(check_interval)
            
            # Combined captcha check in one JS call (faster)
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
            if i % int(15 / check_interval) == 0:
                log_fn(f"[CAPTCHA] {int(i*check_interval)}s: solved={captcha_state.get('solved')} form={captcha_state.get('form_ready')}")
            
            # Success: form is ready to submit
            if captcha_state.get('solved'):
                log_fn(f"[CAPTCHA] ✓ Captcha solved at {int(i*check_interval)}s")
                captcha_solved = True
                break
            
            # Timeout
            if i == int(total_wait / check_interval) - 1:
                log_fn("[CAPTCHA] Timeout, submitting anyway...")
                captcha_solved = True
        
        if captcha_solved:
            # Submit registration form
            log_fn("[FORM] Submitting...")
            driver.execute_script('document.querySelector("button[type=submit]")?.click()')
            time.sleep(3)
            
            # Click checkbox if present (terms of service)
            for cb in driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
                if cb.is_displayed() and not cb.is_selected():
                    cb.click()
                    break
            
            # Click I Agree if dialog appears
            driver.execute_script('''
            for(var b of document.querySelectorAll('button'))
                if(b.textContent.includes('I Agree')) { b.click(); break; }
            ''')
            time.sleep(1)
        
        # Wait for code or link (Boomlify EDU — доставка может занять 1-2 мин)
        start_wait = time.time()
        while time.time() - start_wait < 90 and not code_found["value"] and not link_found["value"]:
            time.sleep(0.3)  # Faster polling
        
        if not code_found["value"] and not link_found["value"]:
            log_fn("✗ Code timeout - email not received")
            final_inbox = mail_manager.check_inbox(email_data.get("email", ""))
            log_fn(f"[MAIL] Final inbox: {len(final_inbox)} msgs, subjects={[m.get('subject','')[:30] for m in final_inbox[:5]]}")
        
        if link_found["value"]:
            # Kaggle: переход по ссылке верификации (вместо ввода кода)
            log_fn(f"[VERIFY] Opening link: {link_found['value'][:70]}...")
            try:
                driver.get(link_found["value"])
                time.sleep(3)
                log_fn("✓ Verification link opened")
                # Dismiss если есть
                driver.execute_script('''
                for(var b of document.querySelectorAll('button'))
                    if(b.textContent.trim() === 'Dismiss') { b.click(); break; }
                ''')
                time.sleep(0.5)
            except Exception as e:
                log_fn(f"Link open error: {e}")
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
            # Settings (общий путь для link и code)
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
            
            if result:
                log_fn("✓ Clicked Generate New Token")
                time.sleep(1)
                
                # Fill token name "now"
                driver.execute_script('''
                var inp = document.querySelector('input[placeholder="Enter Token Name"]');
                if(inp) {
                    inp.focus();
                    inp.value = 'now';
                    inp.dispatchEvent(new Event('input', {bubbles: true}));
                    return 'found';
                }
                return null;
                ''')
                log_fn("✓ Set token name to 'now'")
                time.sleep(0.3)
                
                # Click Generate
                driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for(var b of buttons) {
                    if(b.textContent.trim() === 'Generate') {
                        b.click();
                        return 'clicked';
                    }
                }
                return null;
                ''')
                log_fn("✓ Clicked Generate")
                time.sleep(1)
                
                # Extract API Token
                new_api_token = driver.execute_script('''
                var inp = document.querySelector('input[placeholder="API TOKEN"]');
                if(inp) return inp.value;
                return null;
                ''')
                
                if new_api_token:
                    log_fn(f"✓ API Token: {new_api_token[:20]}...")
                
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
                time.sleep(0.5)
            
            # ===== 3. Create Legacy API Key =====
            log_fn("Creating Legacy API Key...")
            driver.get("https://www.kaggle.com/settings")
            time.sleep(2)
            
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
            
            if not result:
                log_fn("✗ Create Legacy API Key button not found")
            else:
                log_fn("✓ Clicked Create Legacy API Key")
                time.sleep(1)
                
                # Click Continue
                driver.execute_script('''
                var buttons = document.querySelectorAll('button');
                for(var b of buttons) {
                    if(b.textContent.trim() === 'Continue') {
                        b.click();
                        return 'clicked';
                    }
                }
                return null;
                ''')
                log_fn("✓ Clicked Continue")
                time.sleep(3)
            
            # ===== 4. Read kaggle.json =====
            import os
            import glob
            import json as json_mod
            
            legacy_api_key = None
            legacy_username = None
            downloads_dir = os.path.expanduser("~/Downloads")
            
            # Wait for download
            for _ in range(10):
                time.sleep(0.3)
                files = glob.glob(os.path.join(downloads_dir, "kaggle*.json"))
                if files:
                    kaggle_json_path = max(files, key=os.path.getctime)
                    try:
                        with open(kaggle_json_path) as f:
                            kaggle_data = json_mod.load(f)
                        legacy_api_key = kaggle_data.get("key", "")
                        legacy_username = kaggle_data.get("username", "")
                        log_fn(f"✓ Legacy Key: {legacy_api_key[:20]}...")
                        log_fn(f"✓ Username: {legacy_username}")
                        os.remove(kaggle_json_path)
                    except Exception as e:
                        log_fn(f"Error reading kaggle.json: {e}")
                    break
            
            # Return result
            driver.quit()
            
            if legacy_api_key or new_api_token:
                return {
                    "verified": True, 
                    "api_key": legacy_api_key or new_api_token,
                    "api_key_legacy": legacy_api_key,
                    "api_key_new": new_api_token,
                    "kaggle_username": legacy_username,
                    "error_type": "success"
                }
            
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
        print(f"[{ts}] [{level}] {msg}", flush=True)
    
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
