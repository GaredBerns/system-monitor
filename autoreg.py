"""Auto-Registration Engine v4 — full live view.
Entire browser session streamed as live screenshots.
Click interaction from UI forwarded to real page."""

import os, json, time, random, string, re, threading, traceback, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from faker import Faker
from tempmail import mail_manager
from captcha_solver import (
    setup_stealth_only, setup_captcha_block,
    solve_captcha_on_page, manual_solver,
    SITES_NEED_REAL_CAPTCHA, SITES_CAN_BLOCK,
)

fake = Faker("en_US")

DB_FILE = Path(__file__).parent / "data" / "accounts.json"
SCREENSHOTS_DIR = Path(__file__).parent / "data" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def _clean_name(s):
    return re.sub(r'[^a-z]', '', s.lower())

def generate_identity() -> dict:
    for _ in range(10):
        first = fake.first_name()
        last = fake.last_name()
        clean_first = _clean_name(first)
        clean_last = _clean_name(last)
        if len(clean_first) >= 2 and len(clean_last) >= 2:
            break

    sep = random.choice(["", "_"])
    base = f"{clean_first}{sep}{clean_last}"
    digits = ''.join(random.choices(string.digits, k=random.randint(4, 6)))
    username = re.sub(r'[^a-z0-9_]', '', (base + digits))[:20]
    if not any(c in username for c in string.digits):
        username = base + ''.join(random.choices(string.digits, k=4))

    pwd = (
        random.choices(string.ascii_lowercase, k=4) +
        random.choices(string.ascii_uppercase, k=3) +
        random.choices(string.digits, k=3) +
        random.choices("!@#$%&", k=2)
    )
    random.shuffle(pwd)
    return {
        "first_name": first, "last_name": last,
        "username": username, "display_name": username.replace("_", " "),
        "password": ''.join(pwd),
        "birth_year": str(random.randint(1985, 2002)),
        "birth_month": str(random.randint(1, 12)).zfill(2),
        "birth_day": str(random.randint(1, 28)).zfill(2),
    }


class AccountStore:
    def __init__(self):
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        if DB_FILE.exists():
            try:
                self.accounts = json.loads(DB_FILE.read_text())
            except:
                self.accounts = []
        else:
            self.accounts = []

    def _save(self):
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        DB_FILE.write_text(json.dumps(self.accounts, indent=2, default=str))

    def add(self, account):
        with self.lock:
            self.accounts.append(account)
            self._save()

    def get_all(self):
        with self.lock:
            return list(self.accounts)

    def find(self, reg_id):
        with self.lock:
            return next((a for a in self.accounts if a.get("reg_id") == reg_id), None)

    def save(self):
        with self.lock:
            self._save()

    def remove(self, reg_id):
        with self.lock:
            self.accounts = [a for a in self.accounts if a.get("reg_id") != reg_id]
            self._save()


account_store = AccountStore()

PLATFORMS = {
    "kaggle": {"name": "Kaggle", "url": "https://www.kaggle.com/account/login?phase=emailRegister&returnUrl=%2F",
               "icon": "🏆", "has_captcha": True},
    "github": {"name": "GitHub", "url": "https://github.com/signup",
               "icon": "🐙", "has_captcha": True},
    "huggingface": {"name": "HuggingFace", "url": "https://huggingface.co/join",
                    "icon": "🤗", "has_captcha": False},
    "replit": {"name": "Replit", "url": "https://replit.com/signup",
               "icon": "💻", "has_captcha": True},
    "paperspace": {"name": "Paperspace", "url": "https://console.paperspace.com/signup",
                   "icon": "🖥️", "has_captcha": True},
    "lightning_ai": {"name": "Lightning AI", "url": "https://lightning.ai/sign-up",
                     "icon": "⚡", "has_captcha": True},
    "custom": {"name": "Custom URL", "url": "", "icon": "🔧", "has_captcha": False},
}


class RegistrationJob:
    def __init__(self, platform, mail_provider="boomlify", custom_url="",
                 count=1, headless=True, proxy=""):
        self.platform = platform
        self.mail_provider = mail_provider
        self.custom_url = custom_url
        self.count = count
        self.headless = headless
        self.proxy = proxy
        self.reg_id = str(uuid.uuid4())[:8]
        self.status = "pending"
        self.log_lines = []
        self.current_step = ""
        self.accounts_created = []
        self._page = None
        self._page_lock = threading.Lock()
        self._live_file = str(SCREENSHOTS_DIR / f"live_{self.reg_id}.jpg")
        self._streamer = None
        self._frame_seq = 0
        self._socketio = None

    def set_socketio(self, sio):
        self._socketio = sio

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_lines.append(f"[{ts}] {msg}")
        if len(self.log_lines) > 120:
            self.log_lines = self.log_lines[-100:]
        self.current_step = msg

    def _set_page(self, page):
        with self._page_lock:
            self._page = page
        if page and not self._streamer:
            self._streamer = threading.Thread(target=self._stream_loop, daemon=True)
            self._streamer.start()

    def _clear_page(self):
        with self._page_lock:
            self._page = None

    def _stream_loop(self):
        while self.status == "running":
            with self._page_lock:
                pg = self._page
            if pg:
                try:
                    pg.screenshot(path=self._live_file, type="jpeg", quality=55)
                    self._frame_seq += 1
                    if self._socketio:
                        self._socketio.emit("live_frame", {
                            "reg_id": self.reg_id, "seq": self._frame_seq
                        })
                except:
                    pass
            time.sleep(0.4)

    def get_live_screenshot_path(self):
        return self._live_file

    def click_at(self, x, y):
        with self._page_lock:
            pg = self._page
        if not pg:
            return False
        try:
            pg.mouse.click(x, y)
            time.sleep(0.15)
            pg.screenshot(path=self._live_file, type="jpeg", quality=55)
            self._frame_seq += 1
            return True
        except:
            return False

    def type_text(self, text):
        with self._page_lock:
            pg = self._page
        if not pg:
            return False
        try:
            pg.keyboard.type(text, delay=40)
            time.sleep(0.1)
            pg.screenshot(path=self._live_file, type="jpeg", quality=55)
            self._frame_seq += 1
            return True
        except:
            return False

    def press_key(self, key):
        with self._page_lock:
            pg = self._page
        if not pg:
            return False
        try:
            pg.keyboard.press(key)
            time.sleep(0.1)
            pg.screenshot(path=self._live_file, type="jpeg", quality=55)
            self._frame_seq += 1
            return True
        except:
            return False

    def to_dict(self):
        return {
            "reg_id": self.reg_id, "platform": self.platform,
            "platform_name": PLATFORMS.get(self.platform, {}).get("name", self.platform),
            "status": self.status, "current_step": self.current_step,
            "count": self.count, "created": len(self.accounts_created),
            "log": self.log_lines[-60:], "accounts": self.accounts_created,
            "has_live_view": self._page is not None,
        }

    def cancel(self):
        self._cancel_requested = True
        self.log("Cancel requested — saving current account and moving on...")

    @property
    def is_cancelled(self):
        return getattr(self, '_cancel_requested', False)

    def _check_cancel(self):
        """Check if cancel was requested. Returns True if should abort current registration."""
        return getattr(self, '_cancel_requested', False)

    def run(self):
        self.status = "running"
        self._cancel_requested = False
        for i in range(self.count):
            if getattr(self, "status", None) == "cancelled":
                self.log("Permanent stop — exiting.")
                break
            try:
                self.log(f"━━ Registration {i+1}/{self.count} ━━")
                self._cancel_requested = False
                account = self._register_one(i)
                if getattr(self, "status", None) == "cancelled":
                    break
                if account:
                    self.accounts_created.append(account)
                    if account.get("status") == "registering":
                        account["status"] = "created"
                    threading.Thread(target=account_store.add, args=(account,), daemon=True).start()
                    self.log(f"✓ Saved: {account.get('email','?')} [{account.get('status')}]")
                if i < self.count - 1:
                    d = random.uniform(3, 8)
                    self.log(f"Waiting {d:.0f}s...")
                    deadline = time.time() + d
                    while time.time() < deadline:
                        if getattr(self, "status", None) == "cancelled":
                            break
                        time.sleep(0.5)
            except Exception as e:
                self.log(f"ERROR: {e}")
                self.log(traceback.format_exc()[-300:])
        self._clear_page()
        if getattr(self, "status", None) != "cancelled":
            self.status = "completed"
        self.log(f"Done. {len(self.accounts_created)}/{self.count} accounts.")

    def _register_one(self, index) -> Optional[dict]:
        from playwright.sync_api import sync_playwright

        identity = generate_identity()
        self.log(f"Identity: {identity['display_name']} / {identity['username']}")

        self.log("Creating temp email...")
        email_data = mail_manager.create_email()
        identity["email"] = email_data["email"]
        self.log(f"Email: {identity['email']}")

        pinfo = PLATFORMS.get(self.platform, PLATFORMS["custom"])
        account = {
            "reg_id": f"{self.reg_id}-{index}",
            "platform": self.platform, "platform_name": pinfo["name"],
            **identity, "email_data": email_data,
            "status": "registering", "created_at": datetime.now().isoformat(),
            "verified": False,
        }

        with sync_playwright() as p:
            args = ["--no-sandbox", "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage"]
            opts = dict(headless=self.headless, args=args)
            if self.proxy:
                opts["proxy"] = {"server": self.proxy}

            browser = p.chromium.launch(**opts)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-US",
            )

            if self.platform in SITES_NEED_REAL_CAPTCHA:
                setup_stealth_only(context)
                self.log("Mode: stealth (captcha visible)")
            else:
                tmp = context.new_page()
                setup_captcha_block(context, tmp, self)
                tmp.close()
                self.log("Mode: block (captcha blocked)")

            page = context.new_page()
            self._set_page(page)

            try:
                handler = PLATFORM_HANDLERS.get(self.platform, generic_register)
                result = handler(page, identity, email_data, self, pinfo)
                if self._check_cancel():
                    self.log("Cancelled — saving account as created")
                    account["status"] = "created"
                elif result:
                    account.update(result)
                    if result.get("verified"):
                        account["status"] = "verified"
                    elif result.get("error"):
                        account["status"] = "failed"
                        account["error"] = result.get("error", "")
                    elif account["status"] == "registering":
                        account["status"] = "created"
                else:
                    account["status"] = "created"
            except Exception as e:
                self.log(f"Browser error: {e}")
                account["error"] = str(e)
                account["status"] = "created"
            finally:
                self._clear_page()
                try:
                    browser.close()
                except Exception:
                    pass

        return account


# ─────────────── HELPERS ───────────────

def _wait_visible(page, selectors, timeout=8000):
    """Wait until one of the selectors is visible. timeout in milliseconds."""
    if isinstance(selectors, str):
        selectors = [selectors]
    deadline = time.time() + (timeout / 1000.0)
    while time.time() < deadline:
        for sel in selectors:
            try:
                if page.locator(sel).first.is_visible(timeout=400):
                    return True
            except Exception:
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
    except Exception:
        pass
    return False


def _click(page, selector, timeout=3000):
    try:
        el = page.locator(selector).first
        if el.is_visible(timeout=timeout):
            el.click()
            return True
    except Exception:
        pass
    return False


def _fill_step(page, job, selectors, value, step_name, timeout=8000):
    """Wait for element(s), fill, log only on success. Returns True only if filled."""
    if isinstance(selectors, str):
        selectors = [selectors]
    if not _wait_visible(page, selectors, timeout):
        job.log(f"Step skipped: {step_name} (element not found)")
        return False
    time.sleep(0.4)
    for sel in selectors:
        if _fill(page, sel, value, timeout=2000):
            job.log(step_name)
            return True
    return False


def _click_step(page, job, selectors, step_name, timeout=8000):
    """Wait for element(s), click, log only on success. Returns True only if clicked."""
    if isinstance(selectors, str):
        selectors = [selectors]
    if not _wait_visible(page, selectors, timeout):
        job.log(f"Step skipped: {step_name} (button not found)")
        return False
    time.sleep(0.3)
    for sel in selectors:
        if _click(page, sel, timeout=2000):
            job.log(step_name)
            return True
    return False


def _wait_email(email, job, timeout=60, subject_filter=None):
    job.log(f"Waiting for email ({timeout}s)...")
    start = time.time()
    seen = set()
    initial = mail_manager.check_inbox(email)
    for m in initial:
        seen.add(m.get("id", ""))

    while time.time() - start < timeout:
        if job._check_cancel():
            job.log("Cancelled — skipping email wait")
            return None, None, None
        time.sleep(1)
        messages = mail_manager.check_inbox(email)
        for m in messages:
            mid = m.get("id", "")
            if mid and mid not in seen:
                if subject_filter and subject_filter.lower() not in m.get("subject", "").lower():
                    seen.add(mid)
                    continue
                job.log(f"Email: {m.get('subject','?')}")
                body = (m.get("html", "") or "") + " " + (m.get("body", "") or "")
                return m, mail_manager.extract_code(body), mail_manager.extract_link(body)

    job.log("No email received")
    return None, None, None


def _handle_captcha(page, job):
    solved = solve_captcha_on_page(page, job)
    if solved:
        job.log("Captcha: auto-solved")
        return True
    job.log("Captcha needs manual solve — use Live View to click on it")
    for i in range(120):
        if job._check_cancel():
            return False
        time.sleep(1.5)
        try:
            still_visible = page.evaluate("""() => {
                return document.querySelectorAll(
                    'iframe[src*="recaptcha"], iframe[src*="hcaptcha"], .g-recaptcha, [data-sitekey]'
                ).length > 0;
            }""")
            if not still_visible:
                job.log("Captcha disappeared — solved via live view!")
                return True
        except:
            pass
    job.log("Captcha timeout — proceeding anyway")
    return False


# ─────────────── KAGGLE ───────────────

def kaggle_register(page, identity, email_data, job, pinfo):
    job.log("Opening Kaggle (email register)...")
    page.goto("https://www.kaggle.com/account/login?phase=emailRegister&returnUrl=%2F", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)

    # Step 1: only when email field is visible — fill email
    if not _fill_step(page, job,
                      ['input[name="email"]', 'input[type="email"]'],
                      identity["email"], "Email filled", timeout=10000):
        job.log("Abort: email field not found")
        return {"verified": False, "error": "email field not found"}
    time.sleep(0.6)

    # Step 2: wait for password field then fill (do not fill until it's there)
    if not _fill_step(page, job,
                      ['input[name="password"]', 'input[type="password"]'],
                      identity["password"], "Password filled", timeout=8000):
        job.log("Abort: password field not found")
        return {"verified": False, "error": "password field not found"}
    time.sleep(0.6)

    # Step 3: if there is a Next/Continue for step 1, click it and wait for step 2
    next_sel = ['button:has-text("Next")', 'button:has-text("Continue")', 'button[type="submit"]']
    if _wait_visible(page, next_sel, timeout=3000):
        _click_step(page, job, next_sel, "Next (to step 2)", timeout=2000)
        time.sleep(2)
        # wait for step 2 fields (name input or any text input)
        _wait_visible(page, [
            'input[placeholder*="name" i]', 'input[placeholder*="full" i]',
            'input[name="displayName"]', 'input[name="fullName"]',
        ], timeout=10000)
        time.sleep(0.3)

    # Step 4: fill visible name/full-name field — use username (with digits) as display name
    uname = identity["username"]
    name_for_field = uname.replace("_", " ")
    name_filled = _fill_step(page, job,
               ['input[placeholder*="full name" i]', 'input[placeholder*="name" i]',
                'input[name="displayName"]', 'input[name="fullName"]',
                'input[id*="displayName"]', 'input[id*="fullName"]'],
               name_for_field, f"Name: {name_for_field}", timeout=8000)
    if not name_filled:
        job.log("Warning: name field not found")
    time.sleep(0.3)

    # Step 5: fill username — try visible field first, then set hidden input via JS
    uname = identity["username"]
    uname_filled = _fill_step(page, job,
               ['input[name="userName"]:not([type="hidden"])', 'input[name="username"]:not([type="hidden"])',
                'input[id*="userName"]', 'input[id*="username"]',
                'input[placeholder*="user" i]', 'input[autocomplete="username"]'],
               uname, f"Username: {uname}", timeout=4000)
    if not uname_filled:
        try:
            page.evaluate(f'document.querySelector("input[name=\\"userName\\"]") && (document.querySelector("input[name=\\"userName\\"]").value = "{uname}")')
            job.log(f"Username set (hidden): {uname}")
        except Exception:
            job.log(f"Warning: username field not available")
    time.sleep(0.3)

    # Step 6: checkboxes (privacy/terms/consent or plain checkbox)
    for sel in ['input[name*="privacy"]', 'input[name*="terms"]', 'input[name*="consent"]', 'input[type="checkbox"]']:
        try:
            cb = page.locator(sel).first
            if cb.is_visible(timeout=600) and not cb.is_checked():
                cb.click()
                time.sleep(0.2)
                job.log("Checkbox checked")
        except Exception:
            pass

    _handle_captcha(page, job)

    # Step 7: submit only when submit/Next button is visible (final step)
    job.log("Submitting...")
    submit_sel = ['button:has-text("Next")', 'button[type="submit"]', 'button:has-text("Register")',
                  'button:has-text("Sign up")', 'button:has-text("Create Account")', 'button:has-text("Create account")']
    if not _click_step(page, job, submit_sel, "Submit clicked", timeout=8000):
        page.keyboard.press("Enter")
    time.sleep(4)

    try:
        err = page.locator('.form-error, .error-message, [role="alert"]').first.text_content(timeout=2000)
        if err and len(err.strip()) > 0:
            job.log(f"Error: {err.strip()[:100]}")
    except Exception:
        pass

    msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="kaggle")
    if link:
        job.log("Verification link found")
        page.goto(link, timeout=30000)
        time.sleep(3)
        return {"verified": True, "verify_link": link}
    if code:
        job.log(f"Code: {code}")
        if _wait_visible(page, ['input[name="code"]', 'input[name*="verif"]', 'input[placeholder*="code" i]'], timeout=5000):
            _fill(page, 'input[name="code"], input[name*="verif"], input[placeholder*="code" i]', code, 2000)
            _click_step(page, job, 'button[type="submit"]', "Verify submitted", 3000)
        time.sleep(3)
        return {"verified": True, "verify_code": code}
    return {"verified": False}


# ─────────────── GITHUB ───────────────

def github_register(page, identity, email_data, job, pinfo):
    job.log("Opening GitHub...")
    page.goto("https://github.com/signup", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)

    if not _fill_step(page, job, '#email', identity["email"], "Email", timeout=10000):
        return {"verified": False, "error": "email field not found"}
    if not _click_step(page, job, 'button:has-text("Continue")', "Continue (email)", timeout=6000):
        page.keyboard.press("Enter")
    time.sleep(2)
    _wait_visible(page, '#password', timeout=8000)
    time.sleep(0.4)

    if not _fill_step(page, job, '#password', identity["password"], "Password", timeout=8000):
        return {"verified": False, "error": "password field not found"}
    if not _click_step(page, job, 'button:has-text("Continue")', "Continue (password)", timeout=6000):
        page.keyboard.press("Enter")
    time.sleep(2)
    _wait_visible(page, '#login', timeout=8000)
    time.sleep(0.4)

    if not _fill_step(page, job, '#login', identity["username"], f"Username: {identity['username']}", timeout=8000):
        return {"verified": False, "error": "username field not found"}
    if not _click_step(page, job, 'button:has-text("Continue")', "Continue (username)", timeout=6000):
        page.keyboard.press("Enter")
    time.sleep(2)
    try:
        o = page.locator('#opt_in')
        if o.is_visible(timeout=2000):
            o.fill("n")
    except Exception:
        pass
    _click_step(page, job, 'button:has-text("Continue")', "Continue (opt-in)", 4000)
    time.sleep(2)

    _handle_captcha(page, job)

    msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="github")
    if code:
        job.log(f"Code: {code}")
        try:
            inp = page.locator('input[type="text"], input[name*="code"], input[name*="otp"]')
            if inp.count() >= 1:
                inp.first.fill(code)
                time.sleep(2)
        except:
            pass
        return {"verified": True, "verify_code": code}
    return {"verified": False}


# ─────────────── HUGGINGFACE ───────────────

def huggingface_register(page, identity, email_data, job, pinfo):
    job.log("Opening HuggingFace...")
    page.goto("https://huggingface.co/join", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)
    if not _wait_visible(page, ['input[name="email"]', 'input[type="email"]'], timeout=8000):
        return {"verified": False}
    _fill_step(page, job, ['input[name="email"]', 'input[type="email"]'], identity["email"], "Email", 4000)
    _fill_step(page, job, 'input[name="password"], input[type="password"]', identity["password"], "Password", 4000)
    _fill_step(page, job, 'input[name="username"]', identity["username"], "Username", 4000)
    time.sleep(0.5)
    _click_step(page, job, 'button[type="submit"]', "Submit", 4000) or page.keyboard.press("Enter")
    time.sleep(3)
    msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="hugging")
    if link:
        page.goto(link, timeout=30000)
        time.sleep(3)
        return {"verified": True, "verify_link": link}
    return {"verified": False}


# ─────────────── REPLIT ───────────────

def replit_register(page, identity, email_data, job, pinfo):
    job.log("Opening Replit...")
    page.goto("https://replit.com/signup", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)
    _click_step(page, job, 'text=Continue with email', "Continue with email", 8000)
    time.sleep(1.5)
    if not _wait_visible(page, ['input[name="email"]', 'input[type="email"]'], timeout=8000):
        return {"verified": False}
    _fill_step(page, job, ['input[name="email"]', 'input[type="email"]'], identity["email"], "Email", 4000)
    _fill_step(page, job, 'input[name="password"], input[type="password"]', identity["password"], "Password", 4000)
    _fill_step(page, job, 'input[name="username"]', identity["username"], "Username", 4000)
    time.sleep(0.5)
    _click_step(page, job, 'button[type="submit"]', "Submit", 4000) or page.keyboard.press("Enter")
    time.sleep(3)
    msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="replit")
    if link:
        page.goto(link, timeout=30000)
        return {"verified": True, "verify_link": link}
    return {"verified": False}


# ─────────────── GENERIC ───────────────

def generic_register(page, identity, email_data, job, pinfo):
    url = pinfo.get("url") or job.custom_url
    if not url:
        job.log("No URL")
        return {"verified": False}
    job.log(f"Opening {url}...")
    page.goto(url, timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)
    if not _wait_visible(page, ['input[name*="email"]', 'input[type="email"]'], timeout=8000):
        return {"verified": False}
    _fill_step(page, job, ['input[name*="email"]', 'input[type="email"]'], identity.get("email", ""), "Email", 5000)
    _fill_step(page, job, ['input[name*="password"]', 'input[type="password"]'], identity.get("password", ""), "Password", 5000)
    _fill_step(page, job, ['input[name*="user"]', 'input[name*="login"]'], identity.get("username", ""), "Username", 5000)
    time.sleep(0.5)
    _click_step(page, job, ['button[type="submit"]', 'button:has-text("Sign Up")', 'button:has-text("Register")', 'button:has-text("Create")'], "Submit", 5000)
    time.sleep(5)
    msg, code, link = _wait_email(identity["email"], job, timeout=120)
    if link:
        page.goto(link, timeout=30000)
        return {"verified": True, "verify_link": link}
    if code:
        for s in ['input[name*="code"]', 'input[name*="verify"]']:
            if _fill(page, s, code, 2000):
                _click(page, 'button[type="submit"]')
                break
        return {"verified": True, "verify_code": code}
    return {"verified": False}


def paperspace_register(page, identity, email_data, job, pinfo):
    job.log("Opening Paperspace...")
    page.goto("https://console.paperspace.com/signup", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)
    if not _wait_visible(page, ['input[name="email"]', 'input[type="email"]', 'input[name="firstName"]'], timeout=8000):
        return {"verified": False}
    _fill_step(page, job, ['input[name="firstName"]', 'input[placeholder*="First" i]'], identity["first_name"], "First name", 4000)
    _fill_step(page, job, ['input[name="lastName"]', 'input[placeholder*="Last" i]'], identity["last_name"], "Last name", 4000)
    _fill_step(page, job, ['input[name="email"]', 'input[type="email"]'], identity["email"], "Email", 4000)
    _fill_step(page, job, 'input[name="password"], input[type="password"]', identity["password"], "Password", 4000)
    time.sleep(0.5)
    for sel in ['input[type="checkbox"]']:
        try:
            cb = page.locator(sel).first
            if cb.is_visible(timeout=1000) and not cb.is_checked():
                cb.click()
        except:
            pass
    _handle_captcha(page, job)
    _click(page, 'button[type="submit"]') or _click(page, 'button:has-text("Sign Up")') or page.keyboard.press("Enter")
    time.sleep(4)
    msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="paperspace")
    if link:
        page.goto(link, timeout=30000)
        return {"verified": True, "verify_link": link}
    if code:
        _fill(page, 'input[name*="code"], input[name*="verif"]', code)
        _click(page, 'button[type="submit"]')
        return {"verified": True, "verify_code": code}
    return {"verified": False}


def lightning_register(page, identity, email_data, job, pinfo):
    job.log("Opening Lightning AI...")
    page.goto("https://lightning.ai/sign-up", timeout=30000)
    page.wait_for_load_state("domcontentloaded")
    time.sleep(2)
    if not _wait_visible(page, ['input[name="email"]', 'input[type="email"]'], timeout=8000):
        return {"verified": False}
    _fill_step(page, job, ['input[name="email"]', 'input[type="email"]'], identity["email"], "Email", 4000)
    _fill_step(page, job, 'input[name="password"], input[type="password"]', identity["password"], "Password", 4000)
    _fill_step(page, job, ['input[name*="name"]', 'input[placeholder*="name" i]'], identity["username"].replace("_", " "), "Name", 4000)
    time.sleep(0.5)
    _handle_captcha(page, job)
    _click_step(page, job, ['button[type="submit"]', 'button:has-text("Sign up")'], "Submit", 4000) or page.keyboard.press("Enter")
    time.sleep(4)
    msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="lightning")
    if link:
        page.goto(link, timeout=30000)
        return {"verified": True, "verify_link": link}
    return {"verified": False}


PLATFORM_HANDLERS = {
    "kaggle": kaggle_register, "github": github_register,
    "huggingface": huggingface_register, "replit": replit_register,
    "paperspace": paperspace_register, "lightning_ai": lightning_register,
}


class JobManager:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()

    def create_job(self, platform, mail_provider="boomlify", custom_url="",
                   count=1, headless=True, proxy=""):
        job = RegistrationJob(platform, mail_provider, custom_url, count, headless, proxy)
        with self.lock:
            self.jobs[job.reg_id] = job
        threading.Thread(target=job.run, daemon=True).start()
        return job

    def get_job(self, reg_id):
        with self.lock:
            return self.jobs.get(reg_id)

    def get_all_jobs(self):
        with self.lock:
            return [j.to_dict() for j in self.jobs.values()]

    def remove_job(self, reg_id):
        with self.lock:
            self.jobs.pop(reg_id, None)


job_manager = JobManager()
