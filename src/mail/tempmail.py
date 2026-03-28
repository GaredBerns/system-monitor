"""Temp Mail — Boomlify EDU (Kaggle принимает только EDU).
Source: https://boomlify.com/RU/EDU-TEMP-MAIL"""

import os
import re
import json
import time
import random
import string
import threading
import requests
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from src.utils.logger import get_logger, log_function, log_api_endpoint, LogContext

# Initialize logger
log = get_logger(__name__)


VERBOSE = os.environ.get("VERBOSE_MAIL", "1") == "1"


def _log(msg: str):
    if VERBOSE:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            print(f"[{ts}] [MAIL] {msg}", flush=True)
        except (BrokenPipeError, IOError):
            pass  # Ignore if stdout is closed (Flask context)

# Multiple Boomlify API keys for rotation (avoid rate limits)
# Load Boomlify API keys from file or env
_boomlify_keys_file = Path(__file__).resolve().parent.parent.parent / "data" / "boomlify_keys.txt"
if _boomlify_keys_file.exists():
    BOOMLIFY_API_KEYS = [
        ln.strip() for ln in _boomlify_keys_file.read_text().splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
else:
    BOOMLIFY_API_KEYS = [
        k for k in os.environ.get("BOOMLIFY_API_KEYS", "").split(",") if k
    ] or [
        "api_50900908bd13d4f960e2d7bf405b4a63dd7f9999192d31e0c8fae53985599949",
        "api_2e4bb3746f9d787d75384b8b9896eb5f9b91d95d86c6f106ffc456ac07faf61f",
    ]
BOOMLIFY_KEY_INDEX = 0

def get_boomlify_key():
    global BOOMLIFY_KEY_INDEX
    key = BOOMLIFY_API_KEYS[BOOMLIFY_KEY_INDEX % len(BOOMLIFY_API_KEYS)]
    BOOMLIFY_KEY_INDEX += 1
    return key

BOOMLIFY_API_KEY = BOOMLIFY_API_KEYS[0]  # Backward compat

TRANSPORT_KEYRING = {
    "aejru": "Jq4nT6zWe5rM8vPaLs71X", "asdfg": "Sm2nL9qTe5rV8pXaZw61M",
    "bchdk": "Ky3pT5nWv7rQ1mLaZx68A", "bpvhs": "Rd3pK9sTe2yN7mQwVb64Z",
    "cltqg": "Wu5sL2nQe8rT1yPaMx93C", "czmop": "De9fR2sXq5tM1nLbVw84P",
    "fyv": "Hv4kM2nBq8sR1tJcLz93F", "gjbjb": "Lf8pC6sWd3vX1qTuMz40S",
    "guyg": "oP6yT1xHaE9qD4KsLi82M", "gyvg": "Nc5wZ1tQe9yH2rLaKs78D",
    "hgjfh": "rk4kA9fQm8v7W4d2TzX1Y", "hgjfhg": "t2PzKd9sQw1Lm3XyVbN6R",
    "hihji": "bV7nL2cMzR6eJ8QaHp39T", "hklop": "Yd3pM6tQw7nR2sLeVk84N",
    "igug": "Za1sX9qWe3rT7yUiPl56K", "kdjsh": "Zt4mP7nQw3rS6xLeVy82H",
    "kqvtd": "Gk1nP8rTe3yL6mQaZw59J", "nmxas": "Rj6mV4qTe8yN1bLcPw53C",
    "ojigh": "mQ3wN8sRcK5tY2VhUe74Z", "pqlmn": "Ep7mV1qRs6tN4xLbYz82D",
    "prxnl": "Bn7qL4tWe2rP9mXsVd61H", "qwert": "Oy6nR5mTe2pL9qXsWa34J",
    "rtuwq": "Uw2nZ7sQa4tK9pLeMr86B", "svyud": "Hp5mN2qTs8yR1lKaVw73U",
    "tjbqw": "Lm6tQ3nWp9rV2sXeYk45I", "vtycx": "Ha9tQ2mWe5rP8nXsLv61F",
    "vy": "Qs7nF3bLk1pV8xTdRm64G", "wmzlk": "Vb8rP4tQe1mS7nKxZa62O",
    "wzufr": "Nk8rS3pTe1yM6wQvZa75G", "ydnfc": "Cf2mH7vQp6tN9sLxRw83Y",
    "yuiop": "Px1vK8tQe4mN7sLaRw53K", "zqplk": "Tx9vK3dRm5nP2sLaQw71E",
}
MAIN_KEY = "7a9b3c8d2e1f4g5h6i9j0k8l2m4n6o8p"


def _decrypt(encrypted_hex: str, key_id: str = ""):
    key = TRANSPORT_KEYRING.get(key_id, MAIN_KEY) if key_id else MAIN_KEY
    kb = key.encode("utf-8")
    hb = bytes.fromhex(encrypted_hex)
    raw = bytearray(hb[i] ^ kb[i % len(kb)] for i in range(len(hb)))
    return json.loads(raw.decode("utf-8"))


def _solve_captcha(sitekey: str, page_url: str) -> str:
    # Load FCB keys from file
    fcb_file = Path(__file__).resolve().parent.parent.parent / "data" / "fcb_keys.txt"
    keys = []
    if fcb_file.exists():
        keys = [ln.strip() for ln in fcb_file.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    
    # Fallback hardcoded keys
    if not keys:
        keys = [
            "fcap-331e8a3a-bc1d-4d8a-9f2e-5c7b8a1d3e9f",
            "fcap-4b2c1d5e-8a7f-4c3b-9d2e-1a5b6c8d0e2f",
        ]
    
    _log(f"Solving CAPTCHA with FCB ({len(keys)} keys)...")
    
    for key in keys:
        try:
            req = Request("https://freecaptchabypass.com/createTask",
                data=json.dumps({"clientKey": key, "task": {"type": "TurnstileTaskProxyLess", "websiteURL": page_url, "websiteKey": sitekey}}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                resp = json.loads(urlopen(req, timeout=30).read())
            except (BrokenPipeError, ConnectionResetError, ConnectionRefusedError) as e:
                _log(f"FCB connection error: {e}, retrying...")
                time.sleep(2)
                continue
            tid = resp.get("taskId")
            if not tid:
                continue
            _log(f"FCB task: {tid[:20]}...")
            for _ in range(40):
                time.sleep(5)
                req2 = Request("https://freecaptchabypass.com/getTaskResult",
                    data=json.dumps({"clientKey": key, "taskId": tid}).encode(),
                    headers={"Content-Type": "application/json"}, method="POST")
                try:
                    resp2 = json.loads(urlopen(req2, timeout=30).read())
                except (BrokenPipeError, ConnectionResetError, ConnectionRefusedError) as e:
                    _log(f"FCB getTaskResult connection error: {e}")
                    continue
                if resp2.get("status") == "ready":
                    _log("✓ CAPTCHA solved!")
                    return resp2.get("solution", {}).get("token", "")
        except Exception as e:
            _log(f"FCB key error: {e}")
            continue
    return ""


def get_domains(edu_only=True) -> list:
    try:
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {BOOMLIFY_API_KEY}", "Content-Type": "application/json"})
        r = s.get("https://v1.boomlify.com/domains/public", timeout=10)
        if r.status_code == 429:
            time.sleep(2)
            r = s.get("https://v1.boomlify.com/domains/public", timeout=10)
        data = r.json() if r.status_code == 200 else {}
        if isinstance(data, dict) and "encrypted" in data:
            data = _decrypt(data["encrypted"], r.headers.get("x-enc-key-id", ""))
        domains = data if isinstance(data, list) else []
        if edu_only:
            return [d for d in domains if d.get("is_edu")]
        return domains
    except Exception:
        pass
    return []


class BoomlifyProvider:
    def __init__(self):
        self._session = None
        self._current_key_idx = 0
        self._key_stats = {}  # key -> {"requests": 0, "limited_at": None}
        self._request_count = 0
        self._max_requests_per_key = 80  # Switch before hitting 100 limit
        # Domain caching
        self._domains_cache = None
        self._domains_cache_time = 0
        self._domains_cache_ttl = 300  # 5 minutes

    def _select_best_key(self):
        """Select key with lowest usage that's not rate limited."""
        now = time.time()
        best_idx = 0
        best_score = float('inf')
        
        for i, key in enumerate(BOOMLIFY_API_KEYS):
            stats = self._key_stats.get(key, {"requests": 0, "limited_at": None})
            
            # Skip if rate limited within last 10 minutes
            if stats.get("limited_at") and now - stats["limited_at"] < 600:
                continue
            
            score = stats.get("requests", 0)
            if score < best_score:
                best_score = score
                best_idx = i
        
        self._current_key_idx = best_idx

    def _get_key(self):
        return BOOMLIFY_API_KEYS[self._current_key_idx % len(BOOMLIFY_API_KEYS)]

    def _rotate_key(self):
        current_key = self._get_key()
        self._key_stats[current_key] = {
            "requests": self._key_stats.get(current_key, {}).get("requests", 0),
            "limited_at": time.time()  # Mark as limited
        }
        self._current_key_idx = (self._current_key_idx + 1) % len(BOOMLIFY_API_KEYS)
        self._session = None
        _log(f"Rotated to API key #{self._current_key_idx}")

    def _track_request(self):
        key = self._get_key()
        stats = self._key_stats.get(key, {"requests": 0, "limited_at": None})
        stats["requests"] = stats.get("requests", 0) + 1
        self._key_stats[key] = stats
        self._request_count += 1
        
        # Auto-rotate before hitting limit
        if stats["requests"] >= self._max_requests_per_key:
            _log(f"Key #{self._current_key_idx} reached {stats['requests']} requests, rotating...")
            self._rotate_key()

    def _session_get(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Authorization": f"Bearer {self._get_key()}",
                "Content-Type": "application/json",
                "Connection": "close",  # Prevent connection reuse issues
            })
            # Retry adapter for connection errors
            adapter = requests.adapters.HTTPAdapter(
                max_retries=3,
                pool_connections=1,
                pool_maxsize=1,
            )
            self._session.mount("https://", adapter)
        return self._session

    def _decrypt_resp(self, r):
        try:
            data = r.json()
            if isinstance(data, dict) and "encrypted" in data:
                return _decrypt(data["encrypted"], r.headers.get("x-enc-key-id", ""))
            return data
        except Exception:
            return {}

    def _get_cached_domains(self):
        """Get domains from cache or fetch new ones."""
        now = time.time()
        if self._domains_cache and (now - self._domains_cache_time) < self._domains_cache_ttl:
            return self._domains_cache
        
        try:
            r = self._session_get().get("https://v1.boomlify.com/domains/public", timeout=10)
        except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, 
                BrokenPipeError, ConnectionResetError) as e:
            _log(f"Boomlify connection error: {e}, retrying...")
            self._session = None
            time.sleep(2)
            r = self._session_get().get("https://v1.boomlify.com/domains/public", timeout=10)
        
        
        domains = self._decrypt_resp(r) if r.status_code == 200 else []
        self._domains_cache = domains
        self._domains_cache_time = now
        return domains
    
    def create_email(self, domain_name=None) -> dict:
        self._track_request()
        domains = self._get_cached_domains()
        edu = [d for d in domains if d.get("is_edu")]
        if not edu:
            # Clear cache and retry once
            self._domains_cache = None
            domains = self._get_cached_domains()
            edu = [d for d in domains if d.get("is_edu")]
            if not edu:
                raise Exception("No EDU domains")
        domain = next((d for d in edu if d["domain"] == domain_name), edu[0]) if domain_name else edu[0]
        login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{login}@{domain['domain']}"
        
        # First attempt without CAPTCHA
        self._track_request()
        last_error = None
        for conn_attempt in range(3):  # Connection retry loop
            try:
                r = self._session_get().post("https://v1.boomlify.com/emails/public/create",
                    json={"email": email, "domainId": domain["id"]}, timeout=15)
                break  # Success, exit retry loop
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError,
                    BrokenPipeError, ConnectionResetError, OSError) as e:
                last_error = e
                _log(f"Boomlify create connection error: {e}, retrying ({conn_attempt+1}/3)...")
                self._session = None  # Force new session
                time.sleep(2)
                if conn_attempt == 2:
                    raise Exception(f"Connection failed after 3 retries: {e}")
        result = self._decrypt_resp(r)
        
        # Check if CAPTCHA required - try solving with retry
        captcha_attempts = 0
        while (result.get("captchaRequired") or result.get("error") == "CAPTCHA_REQUIRED") and captcha_attempts < 3:
            captcha_attempts += 1
            _log(f"CAPTCHA required (attempt {captcha_attempts}), solving...")
            
            # Rotate key if this is not first attempt
            if captcha_attempts > 1:
                _log("Rotating API key...")
                self._rotate_key()
                self._session = None
                # Generate new email with new key
                login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
                email = f"{login}@{domain['domain']}"
                _log(f"New email: {email}")
            
            token = _solve_captcha(result.get("captchaSiteKey", "0x4AAAAAABxNxT9frArMeW8F"),
                "https://boomlify.com/RU/EDU-TEMP-MAIL")
            if token:
                _log(f"CAPTCHA token obtained: {token[:30]}...")
                # Retry with CAPTCHA token
                self._track_request()
                for conn_attempt in range(3):
                    try:
                        r = self._session_get().post("https://v1.boomlify.com/emails/public/create",
                            json={"email": email, "domainId": domain["id"], "captchaToken": token}, timeout=15)
                        break
                    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError,
                            BrokenPipeError, ConnectionResetError, OSError) as e:
                        _log(f"Boomlify create connection error: {e}, retrying ({conn_attempt+1}/3)...")
                        self._session = None
                        time.sleep(2)
                        if conn_attempt == 2:
                            raise Exception(f"Connection failed after 3 retries: {e}")
                result = self._decrypt_resp(r)
                _log(f"Create result after CAPTCHA: {result}")
            else:
                raise Exception("CAPTCHA solve failed")
        
        if result.get("id"):
            _log(f"✓ Boomlify email created: {result['email']}")
            return {"email": result["email"], "email_id": result["id"], "provider": "boomlify", "is_edu": True}
        
        error = result.get("error", "Create failed")
        _log(f"Boomlify create error: {error}")
        raise Exception(error)

    def check_inbox(self, email_data: dict) -> list:
        email = email_data.get("email", "") if isinstance(email_data, dict) else str(email_data)
        if not email:
            _log("check_inbox: empty email")
            return []
        try:
            self._track_request()
            try:
                r = self._session_get().get(f"https://v1.boomlify.com/emails/public/{email}", timeout=10)
            except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError,
                    BrokenPipeError, ConnectionResetError) as e:
                _log(f"Boomlify inbox connection error: {e}, retrying...")
                self._session = None
                time.sleep(2)
                r = self._session_get().get(f"https://v1.boomlify.com/emails/public/{email}", timeout=10)
            _log(f"Boomlify API {email}: status={r.status_code}")
            if r.status_code == 429:
                _log("Boomlify 429 rate limit, rotating key...")
                self._rotate_key()
                self._track_request()
                r = self._session_get().get(f"https://v1.boomlify.com/emails/public/{email}", timeout=10)
                _log(f"Boomlify retry: status={r.status_code}")
            data = self._decrypt_resp(r)
            if isinstance(data, list):
                _log(f"Boomlify inbox: {len(data)} messages")
                out = []
                for m in data:
                    # Boomlify uses body_html, not body
                    body = m.get("body") or m.get("text") or m.get("body_text") or ""
                    html = m.get("html") or m.get("body_html") or ""
                    from_addr = m.get("from") or m.get("from_email") or ""
                    out.append({
                        "id": str(m.get("id", "")),
                        "from": from_addr,
                        "subject": m.get("subject", ""),
                        "body": body,
                        "html": html,
                        "date": m.get("date") or m.get("created_at") or "",
                    })
                return out
            if isinstance(data, dict) and data.get("error"):
                _log(f"Boomlify error: {data.get('error')}")
            else:
                _log(f"Boomlify response type={type(data).__name__}, not list")
        except Exception as e:
            _log(f"Boomlify exception: {e}")
        return []

    def get_message(self, email_data: dict, msg_id: str) -> dict:
        for m in self.check_inbox(email_data):
            if str(m.get("id")) == str(msg_id):
                return m
        return {}


class BoomlifyWebProvider:
    """Boomlify через веб-интерфейс Selenium (обходит API rate limits)"""
    def __init__(self):
        self._driver = None
        self._emails = {}  # email -> {password, created}

    def _get_driver(self):
        if self._driver is None:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            options = Options()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            # Don't use headless for CAPTCHA solving
            self._driver = webdriver.Chrome(options=options)
        return self._driver

    def create_email(self, domain_name=None) -> dict:
        import re
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
        
        try:
            driver = self._get_driver()
            driver.get("https://boomlify.com/RU/EDU-TEMP-MAIL")
            time.sleep(3)
            
            # Close modal dialogs
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            time.sleep(1)
            
            # Click New Email button
            wait = WebDriverWait(driver, 10)
            try:
                new_btn = driver.find_element(By.XPATH, "//button[contains(., 'New Email')]")
                driver.execute_script("arguments[0].scrollIntoView(true);", new_btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", new_btn)
                _log("Clicked New Email button")
            except Exception as e:
                _log(f"Button click error: {e}")
                raise
            
            # Wait for email generation (may need CAPTCHA)
            email = None
            for attempt in range(30):
                time.sleep(2)
                
                # Check for email in page source
                page_source = driver.page_source
                emails = re.findall(r'([a-zA-Z0-9]{6,}@(?:bscse|bseee|okcx|priyo)[^@]*\.edu\.[a-z]{2,})', page_source)
                if emails:
                    email = emails[0]
                    break
                
                # Check input elements
                for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email']"):
                    val = inp.get_attribute('value')
                    if val and '@' in val and '.edu' in val:
                        email = val
                        break
                
                if email:
                    break
                    
                # Check for error messages
                try:
                    error = driver.find_element(By.XPATH, "//*[contains(text(), 'error') or contains(text(), 'Error')]")
                    if error.text.strip():
                        _log(f"Page error: {error.text}")
                except:
                    pass
                
                _log(f"Waiting for email... attempt {attempt+1}")
            
            if not email or '@' not in email:
                raise Exception("No email generated")
            
            _log(f"✓ BoomlifyWeb created: {email}")
            self._emails[email] = {"created": time.time()}
            return {"email": email, "provider": "boomlify_web", "is_edu": ".edu" in email}
            
        except Exception as e:
            _log(f"BoomlifyWeb create error: {e}")
            raise

    def check_inbox(self, email_data: dict) -> list:
        email = email_data.get("email", "") if isinstance(email_data, dict) else str(email_data)
        if not email:
            return []
        try:
            driver = self._get_driver()
            # Navigate to inbox
            driver.get(f"https://boomlify.com/inbox/{email}")
            time.sleep(3)
            
            from selenium.webdriver.common.by import By
            messages = []
            
            # Find message elements
            msg_elems = driver.find_elements(By.CSS_SELECTOR, ".message, .email-item, tr[onclick], .inbox-row")
            
            for elem in msg_elems[:10]:
                try:
                    elem.click()
                    time.sleep(0.5)
                    
                    # Get message content
                    body_elem = driver.find_element(By.CSS_SELECTOR, ".message-body, .email-body, .content")
                    body = body_elem.text if body_elem else ""
                    
                    subj_elem = driver.find_element(By.CSS_SELECTOR, ".subject, .message-subject")
                    subject = subj_elem.text if subj_elem else ""
                    
                    from_elem = driver.find_element(By.CSS_SELECTOR, ".from, .sender")
                    from_addr = from_elem.text if from_elem else ""
                    
                    messages.append({
                        "id": str(len(messages)),
                        "from": from_addr,
                        "subject": subject,
                        "body": body,
                        "html": "",
                        "date": "",
                    })
                except:
                    continue
            
            _log(f"BoomlifyWeb inbox: {len(messages)} messages")
            return messages
        except Exception as e:
            _log(f"BoomlifyWeb inbox error: {e}")
            return []

    def get_message(self, email_data: dict, msg_id: str) -> dict:
        for m in self.check_inbox(email_data):
            if m.get("id") == msg_id:
                return m
        return {}


class MailGwProvider:
    """mail.gw — бесплатный API, 8 QPS. Не EDU — для тестов."""
    BASE = "https://api.mail.gw"

    def create_email(self, domain_name=None) -> dict:
        try:
            r = requests.get(f"{self.BASE}/domains", timeout=10)
            if r.status_code != 200:
                raise Exception(f"domains {r.status_code}")
            data = r.json()
            members = data.get("hydra:member", [])
            if not members:
                raise Exception("No domains")
            domain = members[0].get("domain", "mail.gw")
            login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            email = f"{login}@{domain}"
            pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            r2 = requests.post(f"{self.BASE}/accounts", json={"address": email, "password": pwd}, timeout=10)
            if r2.status_code not in (200, 201):
                raise Exception(f"create {r2.status_code}: {r2.text[:200]}")
            acc = r2.json()
            r3 = requests.post(f"{self.BASE}/token", json={"address": email, "password": pwd}, timeout=10)
            if r3.status_code != 200:
                raise Exception(f"token {r3.status_code}")
            token = r3.json().get("token", "")
            return {"provider": "mailgw", "email": email, "token": token, "password": pwd, "account_id": acc.get("id", "")}
        except Exception as e:
            _log(f"mailgw create: {e}")
            raise

    def check_inbox(self, email_data: dict) -> list:
        token = email_data.get("token", "")
        if not token:
            _log("mailgw: no token")
            return []
        try:
            r = requests.get(f"{self.BASE}/messages", headers={"Authorization": f"Bearer {token}"}, timeout=10)
            if r.status_code != 200:
                _log(f"mailgw messages: {r.status_code}")
                return []
            data = r.json()
            members = data.get("hydra:member", [])
            _log(f"mailgw: {len(members)} messages")
            out = []
            for m in members:
                mid = m.get("id", "")
                r2 = requests.get(f"{self.BASE}/messages/{mid}", headers={"Authorization": f"Bearer {token}"}, timeout=10)
                full = r2.json() if r2.status_code == 200 else m
                from_addr = full.get("from", {})
                if isinstance(from_addr, dict):
                    from_addr = from_addr.get("address", str(from_addr))
                body = full.get("text", "") or full.get("intro", "")
                html = "".join(full.get("html", [])) if isinstance(full.get("html"), list) else (full.get("html") or "")
                out.append({
                    "id": str(mid),
                    "from": from_addr,
                    "subject": full.get("subject", ""),
                    "body": body,
                    "html": html,
                    "date": full.get("createdAt", ""),
                })
            return out
        except Exception as e:
            _log(f"mailgw exception: {e}")
            return []

    def get_message(self, email_data: dict, msg_id: str) -> dict:
        for m in self.check_inbox(email_data):
            if str(m.get("id")) == str(msg_id):
                return m
        return {}


class TempMailIoProvider:
    """TempMail.io style - generate EDU email without API dependency."""
    EDU_DOMAINS = [
        "student.edu.tempmail.io",
        "university.edu.tempmail.io", 
        "academy.edu.tempmail.io",
        "college.edu.tempmail.io",
    ]
    
    def create_email(self, domain_name=None) -> dict:
        # Generate email directly without API call
        domain = domain_name or random.choice(self.EDU_DOMAINS)
        login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{login}@{domain}"
        
        return {
            "provider": "tempmail_io",
            "email": email,
            "login": login,
            "domain": domain,
            "is_edu": True  # Always EDU
        }

    def check_inbox(self, email_data: dict) -> list:
        # TempMail.io style emails don't have real inbox - return empty
        # These are generated emails, not real ones
        return []

    def get_message(self, email_data: dict, msg_id: str) -> dict:
        for m in self.check_inbox(email_data):
            if str(m.get("id")) == str(msg_id):
                return m
        return {}


class EduEmailProvider:
    """Агрегатор EDU почты - пробует несколько источников."""
    
    def __init__(self):
        self._edu_domains_cache = []
        self._cache_time = 0
    
    def _get_edu_domains(self) -> list:
        """Get EDU domains from multiple sources."""
        now = time.time()
        if self._edu_domains_cache and now - self._cache_time < 3600:
            return self._edu_domains_cache
        
        domains = []
        
        # Try Boomlify
        try:
            boomlify_domains = get_domains(edu_only=True)
            domains.extend([d.get("domain") for d in boomlify_domains if d.get("domain")])
        except:
            pass
        
        # Add known EDU temp mail domains
        domains.extend([
            # TempMail.io style
            "student.edu.tempmail.io",
            "university.edu.tempmail.io",
            "academy.edu.tempmail.io",
            # EduMail.su / EduMail.to domains
            "kalia.edu.pl",
            "edu.pl",
            "student.edu.pl",
            # Edu temp domains
            "edumail.edu.pl",
            "email.edu.pl",
            # Priyo EDU (Bangladesh student portal)
            "usa.priyo.edu.pl",
            "uk.priyo.edu.pl",
            # Serbian EDU domains (Boomlify uses these)
            "bscse.okcx.edu.rs",
            "bseee.okcx.edu.rs",
            "it.okcx.edu.rs",
            # More EDU domains
            "student.university.edu",
            "campus.edu.temp",
            "academic.edu.net",
        ])
        
        self._edu_domains_cache = list(set(domains))
        self._cache_time = now
        return self._edu_domains_cache
    
    def create_email(self, domain_name=None) -> dict:
        domains = self._get_edu_domains()
        if not domains:
            raise Exception("No EDU domains available")
        
        domain = domain_name or random.choice(domains)
        login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{login}@{domain}"
        
        return {
            "provider": "edu_aggregator",
            "email": email,
            "login": login,
            "domain": domain,
            "is_edu": True
        }
    
    def check_inbox(self, email_data: dict) -> list:
        # Delegate to appropriate provider based on domain
        domain = email_data.get("domain", "")
        if "boomlify" in domain or email_data.get("provider") == "boomlify":
            return BoomlifyProvider().check_inbox(email_data)
        elif "tempmail.io" in domain:
            return TempMailIoProvider().check_inbox(email_data)
        else:
            # Try 1secmail as fallback
            return OneSecMailProvider().check_inbox(email_data)
    
    def get_message(self, email_data: dict, msg_id: str) -> dict:
        for m in self.check_inbox(email_data):
            if str(m.get("id")) == str(msg_id):
                return m
        return {}


class MailTmProvider:
    """Mail.tm temporary email provider - reliable and free."""
    
    def create_email(self, domain_name=None) -> dict:
        import random
        import string
        
        # Get available domains from mail.tm API
        domains = ["sharebot.net", "mail.tm", "tm.mail.tm"]
        try:
            req = Request("https://api.mail.tm/domains", headers={"User-Agent": "Mozilla/5.0"})
            resp = urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            if isinstance(data, dict):
                items = data.get("hydra:member", data.get("items", []))
                domains = [d.get("domain") for d in items if d.get("isActive")]
        except:
            pass
        
        domain = domain_name or random.choice(domains)
        login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{login}@{domain}"
        
        # Create account via API
        try:
            import requests
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            r = requests.post("https://api.mail.tm/accounts", json={
                "address": email,
                "password": password
            }, timeout=10)
            if r.status_code == 201:
                # Get token
                r2 = requests.post("https://api.mail.tm/token", json={
                    "address": email,
                    "password": password
                }, timeout=10)
                if r2.status_code == 200:
                    token = r2.json().get("token")
                    return {
                        "provider": "mailtm",
                        "email": email,
                        "login": login,
                        "domain": domain,
                        "password": password,
                        "token": token
                    }
        except Exception as e:
            _log(f"MailTm create error: {e}")
        
        # Fallback without account creation
        return {
            "provider": "mailtm",
            "email": email,
            "login": login,
            "domain": domain
        }
    
    def check_inbox(self, email_data: dict) -> list:
        token = email_data.get("token", "")
        if not token:
            _log("mailtm: no token")
            return []
        
        try:
            import requests
            r = requests.get("https://api.mail.tm/messages", 
                headers={"Authorization": f"Bearer {token}"},
                timeout=5  # Faster timeout for realtime
            )
            if r.status_code != 200:
                _log(f"mailtm: status {r.status_code}")
                return []
            
            messages = r.json().get("hydra:member", [])
            out = []
            for m in messages:
                # Get full message
                msg_id = m.get("id")
                try:
                    r2 = requests.get(f"https://api.mail.tm/messages/{msg_id}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=5  # Faster timeout
                    )
                    full = r2.json() if r2.status_code == 200 else m
                except:
                    full = m
                
                out.append({
                    "id": str(full.get("id", "")),
                    "from": full.get("from", {}).get("address", "") if isinstance(full.get("from"), dict) else full.get("from", ""),
                    "subject": full.get("subject", ""),
                    "body": full.get("text", ""),
                    "html": full.get("html", []),
                    "date": full.get("createdAt", "")
                })
            _log(f"mailtm: {len(out)} messages")
            return out
        except Exception as e:
            _log(f"mailtm error: {e}")
            return []
    
    def wait_for_message(self, email_data: dict, timeout=120, subject_filter=None, poll_interval=0.1):
        """Realtime wait for new message with instant polling."""
        seen = set()
        start = time.time()
        
        # Get initial messages
        for m in self.check_inbox(email_data):
            seen.add(m.get("id", ""))
        
        _log(f"mailtm: waiting for new message (timeout={timeout}s, poll={poll_interval}s)")
        
        while time.time() - start < timeout:
            messages = self.check_inbox(email_data)
            for m in messages:
                mid = m.get("id", "")
                if mid and mid not in seen:
                    if subject_filter and subject_filter.lower() not in m.get("subject", "").lower():
                        seen.add(mid)
                        continue
                    _log(f"mailtm: NEW MESSAGE: {m.get('subject', '?')}")
                    return m
            time.sleep(poll_interval)  # Realtime polling (default 100ms)
        
        _log("mailtm: timeout waiting for message")
        return None
    
    def get_message(self, email_data: dict, msg_id: str) -> dict:
        for m in self.check_inbox(email_data):
            if str(m.get("id")) == str(msg_id):
                return m
        return {}


class OneSecMailProvider:
    """1secmail — для Kaggle (Boomlify EDU часто блокируют)."""
    def create_email(self, domain_name=None) -> dict:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
            req = Request("https://www.1secmail.com/api/v1/?action=getDomainList",
                         headers=headers)
            try:
                resp = urlopen(req, timeout=10)
                domains = json.loads(resp.read().decode())
            except (BrokenPipeError, ConnectionResetError, ConnectionRefusedError) as e:
                _log(f"1secmail connection error: {e}")
                domains = ["1secmail.com", "1secmail.org", "1secmail.net"]
        except Exception:
            domains = ["1secmail.com", "1secmail.org", "1secmail.net"]
        domain = domain_name or random.choice(domains)
        login = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{login}@{domain}"
        return {"provider": "1secmail", "email": email, "login": login, "domain": domain}

    def check_inbox(self, email_data: dict) -> list:
        email = email_data.get("email", "")
        if "@" not in email:
            _log("1secmail: invalid email")
            return []
        login, domain = email.split("@", 1)
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
            req = Request(f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}",
                         headers=headers)
            try:
                resp = urlopen(req, timeout=10)
                messages = json.loads(resp.read().decode())
            except (BrokenPipeError, ConnectionResetError, ConnectionRefusedError) as e:
                _log(f"1secmail connection error: {e}")
                return []
            _log(f"1secmail {email}: {len(messages)} messages")
        except Exception as e:
            _log(f"1secmail exception: {e}")
            return []
        out = []
        for m in messages:
            try:
                req2 = Request(f"https://www.1secmail.com/api/v1/?action=readMessage&login={login}&domain={domain}&id={m['id']}",
                              headers=headers)
                try:
                    full = json.loads(urlopen(req2, timeout=10).read().decode())
                except (BrokenPipeError, ConnectionResetError, ConnectionRefusedError):
                    full = m
            except Exception:
                full = m
            out.append({
                "id": str(m.get("id", "")),
                "from": full.get("from", ""),
                "subject": full.get("subject", ""),
                "body": full.get("body", full.get("text", "")),
                "html": full.get("html", ""),
                "date": full.get("date", ""),
            })
        return out

    def get_message(self, email_data: dict, msg_id: str) -> dict:
        for m in self.check_inbox(email_data):
            if str(m.get("id")) == str(msg_id):
                return m
        return {}


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode entities for text extraction."""
    if not html:
        return ""
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", html, flags=re.I)
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text, flags=re.I)
    text = re.sub(r"&amp;", "&", text, flags=re.I)
    text = re.sub(r"&lt;", "<", text, flags=re.I)
    text = re.sub(r"&gt;", ">", text, flags=re.I)
    text = re.sub(r"&quot;", '"', text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_code(text: str) -> str:
    """Extract verification code from email body (plain or HTML).
    Kaggle: 6-digit code from /account/verify?code=XXX link."""
    if not text:
        return ""
    raw = text if len(text) < 8000 else text[:8000]
    
    # First try to extract from Kaggle verification link
    kaggle_code = re.search(r'kaggle\.com/account/verify\?code=([A-Za-z0-9]+)', raw, re.I)
    if kaggle_code:
        code = kaggle_code.group(1)
        _log(f"extract_code: found in Kaggle link -> {code!r}")
        return code
    
    plain = _strip_html(raw) if "<" in raw else raw
    combined = plain + " " + raw[:4000]
    skip = {"kaggle", "verify", "click", "here", "email", "address", "ignore", "request", "your", "this", "code", "public", "private", "https", "http", "www", "com", "action", "button", "link", "having", "with", "from", "about", "please", "thank", "thanks", "dear", "hello", "welcome", "confirm", "account", "security", "protect", "team"}
    
    # Auth0/Devin AI: Look for 6-digit numeric code specifically (priority)
    # First try to find code in specific Auth0 email format
    auth0_patterns = [
        # Auth0 specific: code in styled box/strong tag
        r'(?:verification|verify|confirm|your|one-time|otp)\s*(?:code|pin)[^<]*<[^>]*>(\d{6})<',
        r'<td[^>]*>(\d{6})</td>',
        r'<span[^>]*>(\d{6})</span>',
        r'<strong[^>]*>(\d{6})</strong>',
        r'<div[^>]*style="[^"]*font-size[^"]*"[^>]*>(\d{6})</div>',
        # Code after specific keywords
        r"(?:verification|verify|confirm|your|one-time|otp)\s*(?:code|pin)[:\s]*(\d{6})",
        # Standalone 6-digit in HTML context
        r">\s*(\d{6})\s*<",
    ]
    for i, p in enumerate(auth0_patterns):
        for m in re.findall(p, combined, re.IGNORECASE):
            code = (m if isinstance(m, str) else m[0]).strip()
            if code and code.isdigit() and len(code) == 6:
                _log(f"extract_code: Auth0 pattern#{i} matched -> {code!r}")
                return code
    
    # Fallback: find all 6-digit numbers and pick the most likely one
    all_6digit = re.findall(r'\b(\d{6})\b', combined)
    if all_6digit:
        # Filter out obvious non-codes (years, dates, etc)
        for code in all_6digit:
            # Skip years (1900-2099)
            if code.startswith(('19', '20')) and len(code) == 4:
                continue
            # Skip if it looks like a date
            if code[:2] in ('01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12') and code[2:4] in ('19', '20', '21', '22', '23', '24', '25', '26'):
                continue
            _log(f"extract_code: fallback 6-digit -> {code!r}")
            return code
    
    patterns = [
        r"verificationCode=([a-fA-F0-9\-]{30,50})",
        r"verification_code[=:\s]+([a-fA-F0-9\-]{30,50})",
        r"code[=:\s]+([a-fA-F0-9\-]{30,50})",
        r"(?:verification|verify|confirmation|your)\s+code[:\s]+([A-Za-z0-9]{6})",
        r"code[:\s]+([A-Za-z0-9]{6})",
        r"(?:enter|use)\s+(?:the\s+)?(?:following\s+)?code[:\s]+([A-Za-z0-9]{6})",
        r"[>\s]([A-Z][A-Za-z0-9]{5})\s*[<\s]",
        r"\b([A-Za-z0-9]{6})\s*(?:is your|to verify|verification)",
        r"<strong>([A-Za-z0-9]{6})</strong>",
    ]
    for i, p in enumerate(patterns):
        for m in re.findall(p, combined, re.IGNORECASE):
            code = (m if isinstance(m, str) else m[0]).strip()
            if code and code.lower() not in skip and len(code) >= 4:
                _log(f"extract_code: pattern#{i} matched -> {code!r}")
                return code
    if len(combined) > 50:
        _log(f"extract_code: no match in {len(combined)} chars")
    return ""


def extract_link(text: str) -> str:
    """Extract verification link (Kaggle: kaggle.com/account/verify?code=)."""
    if not text:
        return ""
    raw = text if len(text) < 10000 else text[:10000]
    # Decode HTML entities
    raw = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    patterns = [
        r'(https?://[^\s<>"\']*kaggle\.com/account/verify[^\s<>"\']*)',
        r'(https?://[^\s<>"\']*kaggle\.com[^\s<>"\']*verificationCode=[^\s<>"\']+)',
        r'(https?://[^\s<>"\']+(?:verify|confirm|activate|validate|token|code|register|signup)[^\s<>"\']*)',
    ]
    for p in patterns:
        m = re.search(p, raw, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


class TempMailManager:
    def __init__(self):
        self.accounts = {}
        self.lock = threading.Lock()
        self._providers = {
            "mailtm": MailTmProvider(),  # Primary - most reliable
            "boomlify": BoomlifyProvider(),
            "boomlify_web": BoomlifyWebProvider(),
            "tempmail_io": TempMailIoProvider(),
            "edu_aggregator": EduEmailProvider(),
            "1secmail": OneSecMailProvider(),
            "mailgw": MailGwProvider(),
        }
        self._api_rate_limited = False
        self._inbox_cache = {}  # email -> (timestamp, messages)
        self._inbox_cache_ttl = 5  # seconds
        self.load_accounts()

    def get_domains(self, edu_only=True) -> list:
        return get_domains(edu_only)

    def create_email(self, domain_name=None, provider_name=None, edu_only=True, retry_count=3, **kwargs) -> dict:
        """Create email with intelligent provider selection and retry logic."""
        with self.lock:
            provider_name = (provider_name or "").lower()
            last_error = None
            
            # Provider priority based on reliability and EDU support
            if provider_name and provider_name in self._providers:
                providers_to_try = [provider_name]
            else:
                if edu_only:
                    # mailtm is most reliable, then boomlify for EDU
                    providers_to_try = ["mailtm", "boomlify", "1secmail", "mailgw"]
                else:
                    providers_to_try = ["mailtm", "boomlify", "1secmail", "mailgw", "tempmail_io"]
            
            for prov_name in providers_to_try:
                prov = self._providers.get(prov_name)
                if not prov:
                    continue
                
                # Skip boomlify_web if no display (headless)
                if prov_name == "boomlify_web" and kwargs.get("headless"):
                    continue
                    
                for attempt in range(retry_count):
                    try:
                        start_time = time.time()
                        _log(f"Trying {prov_name} (attempt {attempt+1}/{retry_count})...")
                        
                        email_data = prov.create_email(domain_name)
                        email_data["provider"] = prov_name
                        email_data["created_at"] = time.time()
                        
                        # Check if EDU was required and obtained
                        if edu_only and not email_data.get("is_edu"):
                            _log(f"{prov_name}: not EDU, skipping...")
                            continue
                        
                        elapsed = time.time() - start_time
                        self.accounts[email_data["email"]] = email_data
                        self._save_accounts()
                        _log(f"✓ Email created via {prov_name} in {elapsed:.1f}s: {email_data['email']}")
                        return email_data
                        
                    except TimeoutError as e:
                        last_error = e
                        _log(f"{prov_name} timeout")
                        break  # Try next provider
                        
                    except Exception as e:
                        last_error = e
                        err_str = str(e).lower()
                        _log(f"{prov_name} error: {e}")
                        
                        # Permanent errors - no retry
                        if "no edu" in err_str or "not found" in err_str or "captcha" in err_str:
                            break
                        
                        # Rate limit - try next provider immediately
                        if "rate" in err_str or "limit" in err_str or "429" in err_str:
                            if prov_name == "boomlify" and hasattr(prov, '_rotate_key'):
                                prov._rotate_key()
                            break
                        
                        # Connection errors - quick retry
                        if attempt < retry_count - 1:
                            time.sleep(0.5)  # Quick retry, no backoff
                        else:
                            break
            
            # All providers failed
            err_msg = f"All email providers failed. Last error: {last_error}"
            _log(err_msg)
            raise Exception(err_msg)

    def _save_accounts(self):
        p = Path(__file__).resolve().parent.parent.parent / "data" / "email_accounts.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        to_save = {}
        for email, data in self.accounts.items():
            save_data = {}
            for k, v in data.items():
                if hasattr(v, 'isoformat'):
                    save_data[k] = v.isoformat()
                elif not str(k).startswith('_'):
                    save_data[k] = v
            to_save[email] = save_data
        p.write_text(json.dumps(to_save, indent=2, ensure_ascii=False))

    def load_accounts(self):
        p = Path(__file__).resolve().parent.parent.parent / "data" / "email_accounts.json"
        if p.exists():
            try:
                with self.lock:
                    self.accounts.update(json.loads(p.read_text()))
            except Exception:
                pass

    def check_inbox(self, email: str, use_cache=True) -> list:
        """Check inbox with caching and retry logic."""
        # Check cache first
        if use_cache:
            cached = self._inbox_cache.get(email)
            if cached:
                ts, msgs = cached
                if time.time() - ts < self._inbox_cache_ttl:
                    return msgs
        
        with self.lock:
            email_data = self.accounts.get(email, {"email": email})
        provider = email_data.get("provider", "1secmail")
        
        # Try provider with retry
        for attempt in range(2):
            prov = self._providers.get(provider)
            if not prov:
                prov = self._providers["1secmail"]
            
            try:
                _log(f"check_inbox {email} provider={provider} attempt={attempt+1}")
                result = prov.check_inbox(email_data)
                
                # Update cache
                self._inbox_cache[email] = (time.time(), result)
                _log(f"check_inbox result: {len(result)} msgs")
                return result
                
            except Exception as e:
                _log(f"check_inbox error: {e}")
                # Try fallback provider
                if provider != "1secmail":
                    provider = "1secmail"
                    continue
                # If already using fallback, return empty
                return []
        
        return []

    def get_message(self, email: str, msg_id: str) -> dict:
        with self.lock:
            email_data = self.accounts.get(email, {"email": email})
        prov = self._providers.get(email_data.get("provider", "boomlify"), self._providers["boomlify"])
        return prov.get_message(email_data, msg_id)

    def wait_for_email(self, email: str, timeout=120, poll_interval=1, subject_filter=None) -> dict:
        start = time.time()
        seen = set()
        for m in self.check_inbox(email):
            seen.add(m.get("id"))
        while time.time() - start < timeout:
            time.sleep(poll_interval)
            for m in self.check_inbox(email):
                mid = m.get("id")
                if mid and mid not in seen:
                    seen.add(mid)
                    if subject_filter and subject_filter.lower() not in (m.get("subject") or "").lower():
                        continue
                    return m
        return {}

    def extract_code(self, text: str) -> str:
        return extract_code(text)

    def extract_link(self, text: str) -> str:
        return extract_link(text)

    def list_accounts(self) -> list:
        with self.lock:
            return list(self.accounts.values())

    def remove_account(self, email: str):
        with self.lock:
            self.accounts.pop(email, None)
            self._save_accounts()


mail_manager = TempMailManager()
