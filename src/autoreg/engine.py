"""Auto-Registration Engine v4 — full live view.
Entire browser session streamed as live screenshots.
Click interaction from UI forwarded to real page."""

import os, json, subprocess, sys, time, random, string, re, threading, traceback, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger, log_function, log_api_endpoint, LogContext

# Initialize logger
log = get_logger(__name__)


# Браузеры Playwright — из папки проекта; если ФС не даёт выполнение (noexec, fuseblk) — в ~/.cache
_C2_ROOT = Path(__file__).resolve().parent.parent.parent  # project root
_BROWSERS_DIR_PROJECT = _C2_ROOT / "browsers"
_CACHE_BROWSERS = Path(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))) / "c2_server" / "playwright-browsers"


def _get_playwright_browsers_path():
    """Путь, откуда можно запускать браузер (должен быть на исполняемой ФС)."""
    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])
    # Проверяем, можно ли выполнять из папки проекта (не noexec)
    chrome_candidates = list(_BROWSERS_DIR_PROJECT.glob("chromium-*/chrome-linux/chrome"))
    if chrome_candidates:
        exe = chrome_candidates[0]
        try:
            r = subprocess.run(
                [str(exe), "--version"],
                capture_output=True,
                timeout=5,
                cwd=str(exe.parent),
            )
            if r.returncode == 0 or b"Chromium" in (r.stdout or b"") + (r.stderr or b""):
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_BROWSERS_DIR_PROJECT)
                return _BROWSERS_DIR_PROJECT
        except (OSError, subprocess.TimeoutExpired):
            pass
    # Fallback: кэш в домашней директории (обычно ext4, выполнение есть)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_CACHE_BROWSERS)
    return _CACHE_BROWSERS


def _ensure_playwright_browsers(log_fn=None):
    """Установить Chromium в рабочий каталог (проект или ~/.cache/c2_server)."""
    log = log_fn or (lambda s: None)
    browsers_dir = _get_playwright_browsers_path()
    if any(browsers_dir.glob("chromium-*")):
        return True
    log("Chromium not found. Installing to " + str(browsers_dir))
    browsers_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            cwd=str(_C2_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if r.returncode != 0:
            log(f"playwright install failed: {r.stderr or r.stdout}")
            return False
        return True
    except Exception as e:
        log(f"playwright install error: {e}")
        return False

from src.mail.tempmail import mail_manager
from src.agents.browser.captcha import (
    setup_stealth_only, setup_captcha_block,
    solve_captcha_on_page, manual_solver,
    SITES_NEED_REAL_CAPTCHA, SITES_CAN_BLOCK,
)
from src.utils.common import generate_identity

DB_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "accounts.json"
SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# generate_identity moved to utils.py


class AccountStore:
    def __init__(self):
        self.lock = threading.Lock()
        self._dirty = False
        self._last_save = 0
        self._load()

    def _load(self):
        if DB_FILE.exists():
            try:
                self.accounts = json.loads(DB_FILE.read_text())
            except Exception as e:
                print(f"[ENGINE] Failed to load accounts DB: {e}")
                self.accounts = []
        else:
            self.accounts = []

    def _save(self):
        DB_FILE.parent.mkdir(parents=True, exist_ok=True)
        DB_FILE.write_text(json.dumps(self.accounts, indent=2, default=str))
        self._dirty = False
        self._last_save = time.time()
    
    def _maybe_save(self, force=False):
        """Save only if dirty and at least 2s passed since last save."""
        if self._dirty and (force or time.time() - self._last_save > 2):
            self._save()

    def add(self, account):
        with self.lock:
            self.accounts.append(account)
            self._dirty = True
            self._maybe_save()
            
            # Auto-setup C2 channel for Kaggle accounts
            if account.get('platform') == 'kaggle' and account.get('kaggle_username') and account.get('api_key_legacy'):
                threading.Thread(
                    target=self._setup_c2_channel,
                    args=(account,),
                    daemon=True
                ).start()
    
    def _setup_c2_channel(self, account):
        """Automatically create C2 channel for new Kaggle account."""
        try:
            from agents.kaggle.c2_agent import KaggleC2Agent
            import time
            
            username = account.get('kaggle_username')
            api_key = account.get('api_key_legacy')
            
            if not username or not api_key:
                return
            
            # Create C2 agent
            agent = KaggleC2Agent(username, api_key)
            
            # Initialize C2 channel with registration command
            result = agent.send_command({
                "action": "register",
                "account_id": account.get('reg_id'),
                "platform": "kaggle",
                "timestamp": time.time(),
                "status": "initialized"
            })
            
            if result.get('success'):
                log.info(f"[C2] ✓ Channel created for {username}: v{result.get('version')}")
                # Update account with C2 info
                self.update(account.get('reg_id'), {
                    'c2_channel': agent.kernel_slug,
                    'c2_version': result.get('version'),
                    'c2_status': 'active'
                })
            else:
                log.error(f"[C2] ✗ Failed to create channel for {username}: {result.get('error')}")
        
        except Exception as e:
            log.error(f"[C2] ✗ Error setting up C2 for {account.get('kaggle_username')}: {e}")

    def get_all(self):
        with self.lock:
            return list(self.accounts)

    def find(self, reg_id):
        with self.lock:
            return next((a for a in self.accounts if a.get("reg_id") == reg_id), None)
    
    def update(self, reg_id, updates):
        """Update account fields by reg_id."""
        with self.lock:
            acc = next((a for a in self.accounts if a.get("reg_id") == reg_id), None)
            if acc:
                acc.update(updates)
                self._dirty = True
                self._maybe_save()
                return True
            return False

    def save(self):
        with self.lock:
            self._save()

    def remove(self, reg_id):
        with self.lock:
            self.accounts = [a for a in self.accounts if a.get("reg_id") != reg_id]
            self._dirty = True
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
    "devin_ai": {"name": "Devin AI", "url": "https://app.devin.ai/login",
                 "icon": "🤖", "has_captcha": False},
    "custom": {"name": "Custom URL", "url": "", "icon": "🔧", "has_captcha": False},
}


class RegistrationJob:
    def __init__(self, platform, mail_provider="boomlify", custom_url="",
                 count=1, headless=True, proxy="", browser="chrome"):
        self.platform = platform
        self.mail_provider = mail_provider
        self.custom_url = custom_url
        self.count = count
        self.headless = headless
        self.proxy = proxy
        self.browser = browser  # 'chrome' or 'firefox'
        self.reg_id = str(uuid.uuid4())[:8]
        self.status = "pending"
        self.log_lines = []
        self.current_step = ""
        self.current_email = ""  # Current temp email for this job
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
            "current_email": self.current_email,
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

    def _check_verify(self):
        """Check if manual verify was requested."""
        return getattr(self, '_manual_verify', False)

    def run(self):
        self.status = "running"
        self._cancel_requested = False
        self._manual_verify = False
        
        # Use parallel registration if count > 1 and parallel enabled
        parallel_count = getattr(self, 'parallel_count', 1)
        if parallel_count > 1 and self.count > 1:
            self._run_parallel(parallel_count)
        else:
            self._run_sequential()
    
    def _run_sequential(self):
        """Run registrations sequentially (original behavior)."""
        for i in range(self.count):
            if getattr(self, "status", None) == "cancelled":
                self.log("Permanent stop — exiting.")
                break
            try:
                self.log(f"━━ Registration {i+1}/{self.count} ━━")
                self._cancel_requested = False
                self._manual_verify = False
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
                    d = random.uniform(2, 5)  # Reduced wait time
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
    
    def _run_parallel(self, max_workers=2):
        """Run registrations in parallel using thread pool."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        self.log(f"Starting parallel registration with {max_workers} workers...")
        
        def register_task(idx):
            """Single registration task for thread pool."""
            try:
                self.log(f"[Worker] Starting registration {idx+1}")
                account = self._register_one(idx)
                return (idx, account, None)
            except Exception as e:
                return (idx, None, str(e))
        
        # Create thread pool
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i in range(self.count):
                if self.is_cancelled:
                    self.log("Cancelled - stopping new registrations")
                    break
                future = executor.submit(register_task, i)
                futures[future] = i
                # Small delay between starting workers
                time.sleep(0.5)
            
            # Collect results
            for future in as_completed(futures):
                if self.is_cancelled:
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                
                idx, account, error = future.result()
                if error:
                    self.log(f"Registration {idx+1} error: {error}")
                elif account:
                    self.accounts_created.append(account)
                    if account.get("status") == "registering":
                        account["status"] = "created"
                    threading.Thread(target=account_store.add, args=(account,), daemon=True).start()
                    self.log(f"✓ Saved: {account.get('email','?')} [{account.get('status')}]")
        
        
        self._clear_page()
        if getattr(self, "status", None) != "cancelled":
            self.status = "completed"
        self.log(f"Done. {len(self.accounts_created)}/{self.count} accounts.")

    def _register_one(self, index, retry_count=2) -> Optional[dict]:
        """Run registration with retry on transient errors."""
        self.log(f"_register_one called: index={index}, browser={self.browser}, headless={self.headless}")
        
        # Use firefox_worker for Firefox, autoreg_worker for Chrome
        if self.browser == "firefox":
            from src.agents.browser.firefox import run_registration_firefox
            run_func = lambda platform, headless, input_data: run_registration_firefox(
                platform, headless=headless, input_data=input_data
            )
        else:
            from src.autoreg.worker import run_registration
            run_func = run_registration
        self.log(f"run_func defined: {run_func.__name__ if hasattr(run_func, '__name__') else 'lambda'}")
        
        for attempt in range(retry_count + 1):
            if self.is_cancelled:
                return None
            
            identity = generate_identity()
            self.log(f"Identity: {identity['display_name']}")

            # Create temp email for registration (via API - fast)
            self.log("Creating temp email...")
            try:
                # Don't specify provider - let mail_manager choose best available
                email_data = mail_manager.create_email(edu_only=True, retry_count=1)
            except Exception as e:
                self.log(f"Email creation failed: {e}")
                if attempt < retry_count:
                    self.log(f"Retrying in 2s... (attempt {attempt+2}/{retry_count+1})")
                    time.sleep(2)
                    continue
                return None
            
            identity["email"] = email_data["email"]
            self.current_email = email_data["email"]
            self.log(f"✓ Email: {identity['email']}")
            
            # Mark email as created for this registration job
            email_data["registration_job"] = {
                "reg_id": self.reg_id,
                "platform": self.platform,
                "platform_name": PLATFORMS.get(self.platform, {}).get("name", self.platform),
                "job_index": index,
            }
            mail_manager.accounts[email_data["email"]] = email_data

            pinfo = PLATFORMS.get(self.platform, PLATFORMS["custom"])
            account = {
                "reg_id": f"{self.reg_id}-{index}",
                "platform": self.platform, "platform_name": pinfo["name"],
                **identity, "email_data": email_data,
                "status": "registering", "created_at": datetime.now().isoformat(),
                "verified": False,
            }

            # Run registration directly (faster than subprocess)
            self.log(">>> Starting browser...")
            self.log(f"DEBUG: about to call run_func, platform={self.platform}, headless={self.headless}")
            
            input_data = {
                "identity": identity,
                "email": identity["email"],
                "email_data": email_data,
            }
            self.log(f"DEBUG: input_data prepared: email={identity['email']}")
            
            # Run in thread with cancellation support
            result_holder = {"result": None, "done": False, "error": None}
            
            self.log("DEBUG: creating thread...")
            def run_in_thread():
                try:
                    self.log(f"Thread starting: platform={self.platform}, headless={self.headless}")
                    result_holder["result"] = run_func(
                        self.platform, headless=self.headless, input_data=input_data
                    )
                    self.log(f"Thread completed: success={result_holder['result'].get('success') if result_holder.get('result') else None}")
                except Exception as e:
                    import traceback as tb
                    error_str = f"Thread crashed: {e}\n{tb.format_exc()[-800:]}"
                    self.log(error_str)
                    result_holder["result"] = {"success": False, "error": str(e), "logs": [error_str]}
                    result_holder["error"] = str(e)
                finally:
                    result_holder["done"] = True
            
            
            t = threading.Thread(target=run_in_thread, daemon=True)
            t.start()
            self.log("DEBUG: thread started, waiting...")
            
            # Wait with cancellation check
            WORKER_TIMEOUT = 240  # 4 minutes max
            start_time = time.time()
            
            while time.time() - start_time < WORKER_TIMEOUT and not result_holder["done"]:
                if self.is_cancelled:
                    self.log("Cancelled")
                    account["status"] = "cancelled"
                    return account
                time.sleep(0.5)
            
            # Get result
            worker_result = result_holder.get("result")
            
            if not worker_result:
                self.log("Worker timeout")
                account["status"] = "failed"
                account["error"] = "timeout"
                # Timeout is retryable
                if attempt < retry_count:
                    self.log(f"Retrying in 5s... (attempt {attempt+2}/{retry_count+1})")
                    time.sleep(5)
                    continue
                return account
            
            
            # Copy logs from worker
            for line in worker_result.get("logs", [])[-15:]:
                self.log(line)
            
            # Parse result
            if worker_result.get("success"):
                account["status"] = "verified"
                account["verified"] = True
                if worker_result.get("api_key"):
                    account["api_key"] = worker_result["api_key"]
                    self.log(f"✓ API Key: {worker_result['api_key'][:20]}...")
                if worker_result.get("api_key_legacy"):
                    account["api_key_legacy"] = worker_result["api_key_legacy"]
                    self.log(f"✓ Legacy API Key: {worker_result['api_key_legacy'][:20]}...")
                if worker_result.get("api_key_new"):
                    account["api_key_new"] = worker_result["api_key_new"]
                    self.log(f"✓ New API Token: {worker_result['api_key_new'][:20]}...")
                if worker_result.get("kaggle_username"):
                    account["kaggle_username"] = worker_result["kaggle_username"]
                    self.log(f"✓ Kaggle Username: {worker_result['kaggle_username']}")
                
                # Create dataset + 5 GPU machines for new account
                if worker_result.get("api_key_legacy") and worker_result.get("kaggle_username"):
                    self.log("")
                    self.log("="*70)
                    self.log("[POST-REGISTRATION] Creating Kaggle machines...")
                    self.log("="*70)
                    self.log(f"  • Username: {worker_result['kaggle_username']}")
                    self.log(f"  • API Key: {worker_result['api_key_legacy'][:20]}...")
                    self.log(f"  • Target: 5 GPU kernels with mining")
                    self.log("")
                    
                    try:
                        from src.agents.kaggle.datasets import create_dataset_with_machines
                        
                        self.log("[DEPLOYMENT] Starting kernel deployment...")
                        
                        # Telegram C2 works directly via Telegram API - no public URL needed
                        result = create_dataset_with_machines(
                            worker_result["api_key_legacy"],
                            worker_result["kaggle_username"],
                            num_machines=5,
                            log_fn=self.log,
                            enable_mining=True,
                        )
                        
                        self.log("")
                        self.log("[DEPLOYMENT] Result:")
                        self.log(f"  • Success: {result.get('success')}")
                        self.log(f"  • Machines created: {result.get('machines_created', 0)}")
                        
                        if result.get("success"):
                            if result.get("dataset"):
                                account["dataset"] = result["dataset"]
                                self.log(f"  • Dataset: {result['dataset']}")
                            
                            if result.get("machines"):
                                account["machines"] = result.get("machines", [])
                                account["machines_created"] = result.get("machines_created", 0)
                                self.log(f"  • Machines: {len(result.get('machines', []))}")
                                for m in result.get("machines", []):
                                    self.log(f"    - {m.get('slug', '?')}")
                            
                            self.log("")
                            self.log("✓✓✓ DEPLOYMENT SUCCESSFUL ✓✓✓")
                        else:
                            error = result.get('error', 'unknown')
                            self.log(f"  • Error: {error}")
                            self.log("")
                            self.log("✗✗✗ DEPLOYMENT FAILED ✗✗✗")
                            self.log(f"  Reason: {error}")
                    
                    except Exception as e:
                        self.log("")
                        self.log("✗✗✗ DEPLOYMENT EXCEPTION ✗✗✗")
                        self.log(f"  Error: {str(e)}")
                        import traceback
                        self.log(traceback.format_exc()[-500:])
                    
                    self.log("")
                    self.log("="*70)
                
                return account
            
            
            # Check if error is retryable
            error = worker_result.get("error") or "registration failed"
            retryable_errors = ["timeout", "network", "connection", "cloudflare", "rate limit", "429", "503", "502"]
            is_retryable = any(e in str(error).lower() for e in retryable_errors)
            
            if is_retryable and attempt < retry_count:
                self.log(f"Retryable error: {error}")
                self.log(f"Retrying in 5s... (attempt {attempt+2}/{retry_count+1})")
                time.sleep(5)
                continue
            
            
            account["status"] = "failed"
            account["error"] = error
            return account
        
        # All retries exhausted
        return None


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


def _wait_email(email, job, timeout=120, subject_filter=None):
    """Wait for email with realtime polling (100ms intervals)."""
    job.log(f"Waiting for email ({timeout}s, realtime polling)...")
    start = time.time()
    seen = set()
    
    # Debug: log email data
    email_data = mail_manager.accounts.get(email)
    if email_data:
        job.log(f"Email provider: {email_data.get('provider', 'unknown')}")
    else:
        job.log(f"WARNING: Email {email} not in mail_manager.accounts!")
    
    # Use provider's realtime wait if available
    provider = mail_manager._providers.get(email_data.get("provider", "mailtm")) if email_data else None
    if provider and hasattr(provider, 'wait_for_message'):
        job.log("Using realtime polling (100ms)...")
        msg = provider.wait_for_message(email_data, timeout=timeout, subject_filter=subject_filter, poll_interval=0.1)
        if msg:
            job.log(f"✓ Email received: {msg.get('subject', '?')}")
            body = (msg.get("html", "") or "") + " " + (msg.get("body", "") or "")
            return msg, mail_manager.extract_code(body), mail_manager.extract_link(body)
        job.log("No email received (timeout)")
        return None, None, None
    
    # Fallback: standard polling
    initial = mail_manager.check_inbox(email)
    for m in initial:
        seen.add(m.get("id", ""))

    while time.time() - start < timeout:
        if job._check_cancel():
            job.log("Cancelled — skipping email wait")
            return None, None, None
        time.sleep(0.1)  # Realtime polling (100ms instead of 500ms)
        messages = mail_manager.check_inbox(email)
        for m in messages:
            mid = m.get("id", "")
            if mid and mid not in seen:
                if subject_filter and subject_filter.lower() not in m.get("subject", "").lower():
                    seen.add(mid)
                    continue
                job.log(f"✓ Email received: {m.get('subject','?')}")
                body = (m.get("html", "") or "") + " " + (m.get("body", "") or "")
                return m, mail_manager.extract_code(body), mail_manager.extract_link(body)

    job.log("No email received (timeout)")
    return None, None, None


def _handle_captcha(page, job):
    solved = solve_captcha_on_page(page, job)
    if solved:
        job.log("Captcha: auto-solved")
        return True
    job.log("Captcha needs manual solve — use Live View to click on it")
    for i in range(180):  # 90 seconds max (was 180s)
        if job._check_cancel():
            return False
        time.sleep(0.5)  # Faster polling (was 1.5s)
        try:
            # Проверяем реальное состояние капчи
            captcha_state = page.evaluate("""() => {
                const token = document.querySelector('textarea[name="g-recaptcha-response"]');
                if (token && token.value && token.value.length > 10) return { solved: true };
                const htoken = document.querySelector('textarea[name="h-captcha-response"]');
                if (htoken && htoken.value && htoken.value.length > 10) return { solved: true };
                const challenge = document.querySelector('iframe[src*="bframe"]');
                if (!challenge) {
                    const anchor = document.querySelector('iframe[src*="anchor"]');
                    if (anchor) return { solved: true };
                }
                return { solved: false };
            }""")
            if captcha_state and captcha_state.get("solved"):
                job.log("Captcha solved!")
                return True
        except Exception as e:
            job.log(f"Captcha check error: {e}")
    job.log("Captcha timeout — proceeding anyway")
    return False


# ─────────────── KAGGLE ───────────────

from src.agents.browser.page_utils import (
    PageStep, find_element, find_and_fill, find_and_click, smart_click_button,
    safe_goto, check_url, check_all_checkboxes, extract_page_errors,
    scroll_to_find, wait_for_element_gone
)


def kaggle_register(page, identity, email_data, job, pinfo):
    """Kaggle registration flow with retry on each step.
    
    Flow: email → password → display name → captcha → next → agree → verify
    """
    from pathlib import Path
    screenshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)
    
    # === STEP 0: Navigate ===
    with PageStep(page, "navigate", job.log, screenshot_dir):
        if not safe_goto(page, 
            "https://www.kaggle.com/account/login?phase=emailRegister&returnUrl=%2F",
            timeout=30000, retry=2, log_fn=job.log):
            return {"verified": False, "error": "navigation failed"}
    time.sleep(2)

    # === STEP 1: Email ===
    email_selectors = [
        'input[name="email"]',
        'input[type="email"]',
        'input[placeholder*="email" i]',
        '#email',
        'input[autocomplete="email"]',
        'input[id*="email"]'
    ]
    
    for attempt in range(3):
        with PageStep(page, f"email (attempt {attempt+1})", job.log, screenshot_dir):
            if find_and_fill(page, email_selectors, identity["email"], 
                           timeout=5000, human_typing=True, log_fn=job.log):
                job.log(f"✓ Email: {identity['email']}")
                break
        time.sleep(1)
    else:
        job.log("✗ Email field not found after 3 attempts")
        page.screenshot(path=str(screenshot_dir / f"kaggle_no_email_{int(time.time())}.png"))
        return {"verified": False, "error": "email field not found", "step": "email"}
    time.sleep(0.5)

    # === STEP 2: Password ===
    pwd_selectors = [
        'input[name="password"]',
        'input[type="password"]',
        'input[placeholder*="password" i]',
        '#password',
        'input[autocomplete="new-password"]'
    ]
    
    for attempt in range(3):
        with PageStep(page, f"password (attempt {attempt+1})", job.log, screenshot_dir):
            if find_and_fill(page, pwd_selectors, identity["password"],
                           timeout=5000, log_fn=job.log):
                job.log(f"✓ Password: {'*' * 8}")
                break
        time.sleep(1)
    else:
        job.log("✗ Password field not found after 3 attempts")
        return {"verified": False, "error": "password field not found", "step": "password"}
    time.sleep(0.5)

    # === STEP 3: Display Name ===
    display_name = identity["username"].replace("_", " ")
    name_selectors = [
        'input[name="displayName"]',
        'input[name="fullName"]',
        'input[placeholder*="display" i]',
        'input[placeholder*="name" i]',
        'input[id*="displayName"]',
        'input[id*="fullName"]',
        'input[name="username"]'
    ]
    
    # Try to fill display name (optional step)
    if find_and_fill(page, name_selectors, display_name, timeout=3000, log_fn=job.log):
        job.log(f"✓ Display name: {display_name}")
    else:
        job.log("ℹ Display name field not found (may appear later)")
    time.sleep(0.3)

    # === STEP 4: Captcha ===
    with PageStep(page, "captcha", job.log, screenshot_dir):
        _handle_captcha(page, job)
    time.sleep(0.5)

    # === STEP 5: Click Next/Submit ===
    next_texts = ["Next", "Continue", "Register", "Sign up"]
    
    for attempt in range(3):
        with PageStep(page, f"click_next (attempt {attempt+1})", job.log, screenshot_dir):
            if smart_click_button(page, next_texts, timeout=5000, log_fn=job.log):
                job.log("✓ Next clicked")
                break
            # Fallback: Enter key
            job.log("Trying Enter key...")
            page.keyboard.press("Enter")
            time.sleep(1)
    time.sleep(3)

    # === STEP 6: Check errors and agree checkboxes ===
    with PageStep(page, "check_errors", job.log, screenshot_dir):
        # Check for page errors
        errors = extract_page_errors(page)
        for err in errors:
            job.log(f"  ⚠ Error: {err[:80]}")
            if "captcha" in err.lower():
                job.log("  → Retrying captcha...")
                _handle_captcha(page, job)
                smart_click_button(page, next_texts, timeout=3000, log_fn=job.log)
        
        # Check all agree checkboxes
        agree_selectors = [
            'input[name*="privacy"]',
            'input[name*="terms"]', 
            'input[name*="consent"]',
            'input[name*="agree"]',
            'input[type="checkbox"]:not([name*="remember"])'
        ]
        checked = check_all_checkboxes(page, agree_selectors, log_fn=job.log)
        if checked:
            job.log(f"✓ Checked {checked} agree boxes")
    
    time.sleep(0.5)

    # Click Next again after agree
    smart_click_button(page, next_texts, timeout=3000, log_fn=job.log)
    time.sleep(2)

    # === STEP 7: Wait for verification email ===
    with PageStep(page, "wait_email", job.log, screenshot_dir):
        msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="kaggle")
    
    if link:
        job.log(f"✓ Verification link found")
        with PageStep(page, "verify_link", job.log, screenshot_dir):
            safe_goto(page, link, timeout=30000, log_fn=job.log)
        time.sleep(3)
        return {"verified": True, "verify_link": link}
    
    if code:
        job.log(f"✓ Verification code: {code}")
        
        # Enter code with retry
        code_selectors = [
            'input[name="code"]',
            'input[name*="verif"]',
            'input[placeholder*="code" i]',
            'input[maxlength="6"]',
            'input[maxlength="8"]',
            'input[type="text"]:visible'
        ]
        
        for attempt in range(3):
            with PageStep(page, f"enter_code (attempt {attempt+1})", job.log, screenshot_dir):
                if find_and_fill(page, code_selectors, code, timeout=5000, log_fn=job.log):
                    job.log(f"✓ Code entered: {code}")
                    break
            time.sleep(1)
        else:
            job.log("✗ Code field not found")
            page.screenshot(path=str(screenshot_dir / f"kaggle_no_code_{int(time.time())}.png"))
        
        time.sleep(0.5)
        smart_click_button(page, next_texts, timeout=3000, log_fn=job.log)
        time.sleep(2)
        return {"verified": True, "verify_code": code}
    
    job.log("✗ No verification email received")
    page.screenshot(path=str(screenshot_dir / f"kaggle_no_email_{int(time.time())}.png"))
    return {"verified": False, "error": "no verification email", "step": "verify"}


# ─────────────── GITHUB ───────────────

def github_register(page, identity, email_data, job, pinfo):
    """GitHub registration with retry on each step."""
    from pathlib import Path
    screenshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
    
    # === STEP 1: Navigate ===
    with PageStep(page, "navigate", job.log, screenshot_dir):
        if not safe_goto(page, "https://github.com/signup", timeout=30000, retry=2, log_fn=job.log):
            return {"verified": False, "error": "navigation failed"}
    time.sleep(2)

    # === STEP 2: Email ===
    for attempt in range(3):
        with PageStep(page, f"email (attempt {attempt+1})", job.log, screenshot_dir):
            if find_and_fill(page, ['#email', 'input[name="email"]'], 
                           identity["email"], timeout=8000, human_typing=True, log_fn=job.log):
                job.log(f"✓ Email: {identity['email']}")
                break
        time.sleep(1)
    else:
        return {"verified": False, "error": "email field not found", "step": "email"}
    
    smart_click_button(page, ["Continue"], timeout=5000, log_fn=job.log) or page.keyboard.press("Enter")
    time.sleep(2)

    # === STEP 3: Password ===
    for attempt in range(3):
        with PageStep(page, f"password (attempt {attempt+1})", job.log, screenshot_dir):
            if find_and_fill(page, ['#password', 'input[name="password"]'],
                           identity["password"], timeout=8000, log_fn=job.log):
                job.log("✓ Password filled")
                break
        time.sleep(1)
    else:
        return {"verified": False, "error": "password field not found", "step": "password"}
    
    smart_click_button(page, ["Continue"], timeout=5000, log_fn=job.log) or page.keyboard.press("Enter")
    time.sleep(2)

    # === STEP 4: Username ===
    for attempt in range(3):
        with PageStep(page, f"username (attempt {attempt+1})", job.log, screenshot_dir):
            if find_and_fill(page, ['#login', 'input[name="user[login]"]', 'input[name="username"]'],
                           identity["username"], timeout=8000, log_fn=job.log):
                job.log(f"✓ Username: {identity['username']}")
                break
        time.sleep(1)
    else:
        return {"verified": False, "error": "username field not found", "step": "username"}
    
    smart_click_button(page, ["Continue"], timeout=5000, log_fn=job.log) or page.keyboard.press("Enter")
    time.sleep(2)

    # === STEP 5: Opt-in (optional) ===
    with PageStep(page, "opt_in", job.log, screenshot_dir):
        try:
            opt = page.locator('#opt_in')
            if opt.is_visible(timeout=2000):
                opt.fill("n")
                job.log("✓ Opt-out set")
        except:
            pass
    smart_click_button(page, ["Continue"], timeout=3000, log_fn=job.log)
    time.sleep(2)

    # === STEP 6: Captcha ===
    with PageStep(page, "captcha", job.log, screenshot_dir):
        _handle_captcha(page, job)

    # === STEP 7: Wait for verification ===
    with PageStep(page, "wait_email", job.log, screenshot_dir):
        msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="github")
    
    if code:
        job.log(f"✓ Code: {code}")
        with PageStep(page, "enter_code", job.log, screenshot_dir):
            code_selectors = [
                'input[type="text"]',
                'input[name*="code"]',
                'input[name*="otp"]',
                'input[placeholder*="code" i]'
            ]
            for attempt in range(3):
                if find_and_fill(page, code_selectors, code, timeout=5000, log_fn=job.log):
                    job.log(f"✓ Code entered")
                    break
                time.sleep(1)
        time.sleep(2)
        return {"verified": True, "verify_code": code}
    
    job.log("✗ No verification email")
    page.screenshot(path=str(screenshot_dir / f"github_no_email_{int(time.time())}.png"))
    return {"verified": False, "error": "no verification email", "step": "verify"}


# ─────────────── HUGGINGFACE ───────────────

def huggingface_register(page, identity, email_data, job, pinfo):
    """HuggingFace registration with retry on each step."""
    from pathlib import Path
    screenshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
    
    # === STEP 1: Navigate ===
    with PageStep(page, "navigate", job.log, screenshot_dir):
        if not safe_goto(page, "https://huggingface.co/join", timeout=30000, retry=2, log_fn=job.log):
            return {"verified": False, "error": "navigation failed"}
    time.sleep(2)

    # === STEP 2: Fill form ===
    email_selectors = ['input[name="email"]', 'input[type="email"]', '#email']
    pwd_selectors = ['input[name="password"]', 'input[type="password"]', '#password']
    user_selectors = ['input[name="username"]', '#username']
    
    for attempt in range(3):
        with PageStep(page, f"fill_form (attempt {attempt+1})", job.log, screenshot_dir):
            success = True
            if not find_and_fill(page, email_selectors, identity["email"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, pwd_selectors, identity["password"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, user_selectors, identity["username"], timeout=5000, log_fn=job.log):
                success = False
            if success:
                job.log(f"✓ Form filled: {identity['email']}")
                break
        time.sleep(1)
    else:
        return {"verified": False, "error": "form fields not found", "step": "fill"}
    
    time.sleep(0.5)
    
    # === STEP 3: Submit ===
    with PageStep(page, "submit", job.log, screenshot_dir):
        if not smart_click_button(page, ["Sign Up", "Create Account", "Join"], timeout=5000, log_fn=job.log):
            page.keyboard.press("Enter")
    time.sleep(3)

    # === STEP 4: Wait for verification ===
    with PageStep(page, "wait_email", job.log, screenshot_dir):
        msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="hugging")
    
    if link:
        job.log(f"✓ Verification link found")
        with PageStep(page, "verify_link", job.log, screenshot_dir):
            safe_goto(page, link, timeout=30000, log_fn=job.log)
        time.sleep(3)
        return {"verified": True, "verify_link": link}
    
    job.log("✗ No verification email")
    page.screenshot(path=str(screenshot_dir / f"hf_no_email_{int(time.time())}.png"))
    return {"verified": False, "error": "no verification email", "step": "verify"}


# ─────────────── REPLIT ───────────────

def replit_register(page, identity, email_data, job, pinfo):
    """Replit registration with retry on each step."""
    from pathlib import Path
    screenshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
    
    # === STEP 1: Navigate ===
    with PageStep(page, "navigate", job.log, screenshot_dir):
        if not safe_goto(page, "https://replit.com/signup", timeout=30000, retry=2, log_fn=job.log):
            return {"verified": False, "error": "navigation failed"}
    time.sleep(2)

    # === STEP 2: Click Continue with email ===
    with PageStep(page, "click_email_option", job.log, screenshot_dir):
        smart_click_button(page, ["Continue with email", "Sign up with email"], timeout=8000, log_fn=job.log)
    time.sleep(1.5)

    # === STEP 3: Fill form ===
    email_selectors = ['input[name="email"]', 'input[type="email"]', '#email']
    pwd_selectors = ['input[name="password"]', 'input[type="password"]', '#password']
    user_selectors = ['input[name="username"]', '#username']
    
    for attempt in range(3):
        with PageStep(page, f"fill_form (attempt {attempt+1})", job.log, screenshot_dir):
            success = True
            if not find_and_fill(page, email_selectors, identity["email"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, pwd_selectors, identity["password"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, user_selectors, identity["username"], timeout=5000, log_fn=job.log):
                success = False
            if success:
                job.log(f"✓ Form filled")
                break
        time.sleep(1)
    else:
        return {"verified": False, "error": "form fields not found", "step": "fill"}
    
    time.sleep(0.5)
    
    # === STEP 4: Submit ===
    with PageStep(page, "submit", job.log, screenshot_dir):
        if not smart_click_button(page, ["Sign Up", "Create Account", "Submit"], timeout=5000, log_fn=job.log):
            page.keyboard.press("Enter")
    time.sleep(3)

    # === STEP 5: Wait for verification ===
    with PageStep(page, "wait_email", job.log, screenshot_dir):
        msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="replit")
    
    if link:
        job.log(f"✓ Verification link found")
        with PageStep(page, "verify_link", job.log, screenshot_dir):
            safe_goto(page, link, timeout=30000, log_fn=job.log)
        return {"verified": True, "verify_link": link}
    
    job.log("✗ No verification email")
    page.screenshot(path=str(screenshot_dir / f"replit_no_email_{int(time.time())}.png"))
    return {"verified": False, "error": "no verification email", "step": "verify"}


# ─────────────── GENERIC ───────────────

def generic_register(page, identity, email_data, job, pinfo):
    """Generic registration for custom platforms."""
    from pathlib import Path
    screenshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
    
    url = pinfo.get("url") or job.custom_url
    if not url:
        job.log("No URL")
        return {"verified": False, "error": "no url"}
    
    # === STEP 1: Navigate ===
    with PageStep(page, "navigate", job.log, screenshot_dir):
        if not safe_goto(page, url, timeout=30000, retry=2, log_fn=job.log):
            return {"verified": False, "error": "navigation failed"}
    time.sleep(2)

    # === STEP 2: Fill form with generic selectors ===
    email_selectors = ['input[name*="email"]', 'input[type="email"]', '#email']
    pwd_selectors = ['input[name*="password"]', 'input[type="password"]', '#password']
    user_selectors = ['input[name*="user"]', 'input[name*="login"]', '#username']
    
    for attempt in range(3):
        with PageStep(page, f"fill_form (attempt {attempt+1})", job.log, screenshot_dir):
            find_and_fill(page, email_selectors, identity.get("email", ""), timeout=5000, log_fn=job.log)
            find_and_fill(page, pwd_selectors, identity.get("password", ""), timeout=5000, log_fn=job.log)
            find_and_fill(page, user_selectors, identity.get("username", ""), timeout=5000, log_fn=job.log)
            job.log("✓ Form filled")
            break
        time.sleep(1)
    
    time.sleep(0.5)
    
    # === STEP 3: Submit ===
    with PageStep(page, "submit", job.log, screenshot_dir):
        smart_click_button(page, ["Sign Up", "Register", "Create", "Submit"], timeout=5000, log_fn=job.log) or \
            page.keyboard.press("Enter")
    time.sleep(5)

    # === STEP 4: Wait for verification ===
    with PageStep(page, "wait_email", job.log, screenshot_dir):
        msg, code, link = _wait_email(identity["email"], job, timeout=120)
    
    if link:
        job.log(f"✓ Verification link found")
        with PageStep(page, "verify_link", job.log, screenshot_dir):
            safe_goto(page, link, timeout=30000, log_fn=job.log)
        return {"verified": True, "verify_link": link}
    
    if code:
        job.log(f"✓ Code: {code}")
        with PageStep(page, "enter_code", job.log, screenshot_dir):
            find_and_fill(page, ['input[name*="code"]', 'input[name*="verify"]'], code, timeout=5000, log_fn=job.log)
            smart_click_button(page, ["Submit", "Verify", "Confirm"], timeout=3000, log_fn=job.log)
        return {"verified": True, "verify_code": code}
    
    job.log("✗ No verification")
    page.screenshot(path=str(screenshot_dir / f"generic_no_verify_{int(time.time())}.png"))
    return {"verified": False, "error": "no verification"}


def paperspace_register(page, identity, email_data, job, pinfo):
    """Paperspace registration with retry."""
    from pathlib import Path
    screenshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
    
    # === STEP 1: Navigate ===
    with PageStep(page, "navigate", job.log, screenshot_dir):
        if not safe_goto(page, "https://console.paperspace.com/signup", timeout=30000, retry=2, log_fn=job.log):
            return {"verified": False, "error": "navigation failed"}
    time.sleep(2)

    # === STEP 2: Fill form ===
    first_selectors = ['input[name="firstName"]', 'input[placeholder*="First" i]']
    last_selectors = ['input[name="lastName"]', 'input[placeholder*="Last" i]']
    email_selectors = ['input[name="email"]', 'input[type="email"]']
    pwd_selectors = ['input[name="password"]', 'input[type="password"]']
    
    for attempt in range(3):
        with PageStep(page, f"fill_form (attempt {attempt+1})", job.log, screenshot_dir):
            success = True
            if not find_and_fill(page, first_selectors, identity["first_name"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, last_selectors, identity["last_name"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, email_selectors, identity["email"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, pwd_selectors, identity["password"], timeout=5000, log_fn=job.log):
                success = False
            if success:
                job.log("✓ Form filled")
                break
        time.sleep(1)
    else:
        return {"verified": False, "error": "form fields not found", "step": "fill"}
    
    # === STEP 3: Checkboxes and captcha ===
    with PageStep(page, "checkboxes", job.log, screenshot_dir):
        check_all_checkboxes(page, ['input[type="checkbox"]'], log_fn=job.log)
    
    with PageStep(page, "captcha", job.log, screenshot_dir):
        _handle_captcha(page, job)
    
    # === STEP 4: Submit ===
    with PageStep(page, "submit", job.log, screenshot_dir):
        smart_click_button(page, ["Sign Up", "Create Account", "Submit"], timeout=5000, log_fn=job.log) or \
            page.keyboard.press("Enter")
    time.sleep(4)

    # === STEP 5: Wait for verification ===
    with PageStep(page, "wait_email", job.log, screenshot_dir):
        msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="paperspace")
    
    if link:
        with PageStep(page, "verify_link", job.log, screenshot_dir):
            safe_goto(page, link, timeout=30000, log_fn=job.log)
        return {"verified": True, "verify_link": link}
    
    if code:
        with PageStep(page, "enter_code", job.log, screenshot_dir):
            find_and_fill(page, ['input[name*="code"]', 'input[name*="verif"]'], code, timeout=5000, log_fn=job.log)
            smart_click_button(page, ["Submit"], timeout=3000, log_fn=job.log)
        return {"verified": True, "verify_code": code}
    
    return {"verified": False, "error": "no verification", "step": "verify"}


def lightning_register(page, identity, email_data, job, pinfo):
    """Lightning AI registration with retry."""
    from pathlib import Path
    screenshot_dir = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"
    
    # === STEP 1: Navigate ===
    with PageStep(page, "navigate", job.log, screenshot_dir):
        if not safe_goto(page, "https://lightning.ai/sign-up", timeout=30000, retry=2, log_fn=job.log):
            return {"verified": False, "error": "navigation failed"}
    time.sleep(2)

    # === STEP 2: Fill form ===
    email_selectors = ['input[name="email"]', 'input[type="email"]']
    pwd_selectors = ['input[name="password"]', 'input[type="password"]']
    name_selectors = ['input[name*="name"]', 'input[placeholder*="name" i]']
    
    for attempt in range(3):
        with PageStep(page, f"fill_form (attempt {attempt+1})", job.log, screenshot_dir):
            success = True
            if not find_and_fill(page, email_selectors, identity["email"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, pwd_selectors, identity["password"], timeout=5000, log_fn=job.log):
                success = False
            if not find_and_fill(page, name_selectors, identity["username"].replace("_", " "), timeout=5000, log_fn=job.log):
                success = False
            if success:
                job.log("✓ Form filled")
                break
        time.sleep(1)
    else:
        return {"verified": False, "error": "form fields not found", "step": "fill"}
    
    time.sleep(0.5)
    
    # === STEP 3: Captcha ===
    with PageStep(page, "captcha", job.log, screenshot_dir):
        _handle_captcha(page, job)
    
    # === STEP 4: Submit ===
    with PageStep(page, "submit", job.log, screenshot_dir):
        smart_click_button(page, ["Sign up", "Create Account", "Submit"], timeout=5000, log_fn=job.log) or \
            page.keyboard.press("Enter")
    time.sleep(4)

    # === STEP 5: Wait for verification ===
    with PageStep(page, "wait_email", job.log, screenshot_dir):
        msg, code, link = _wait_email(identity["email"], job, timeout=120, subject_filter="lightning")
    
    if link:
        with PageStep(page, "verify_link", job.log, screenshot_dir):
            safe_goto(page, link, timeout=30000, log_fn=job.log)
        return {"verified": True, "verify_link": link}
    
    return {"verified": False, "error": "no verification", "step": "verify"}


PLATFORM_HANDLERS = {
    "kaggle": kaggle_register, "github": github_register,
    "huggingface": huggingface_register, "replit": replit_register,
    "paperspace": paperspace_register, "lightning_ai": lightning_register,
}


class JobManager:
    def __init__(self):
        self.jobs = {}
        self.lock = threading.Lock()
        self._running = False  # только одна регистрация одновременно

    def create_job(self, platform, mail_provider="boomlify", custom_url="",
                   count=1, headless=True, proxy="", parallel=1, browser="chrome"):
        with self.lock:
            if self._running:
                raise ValueError("Registration already running — wait for it to finish")
        job = RegistrationJob(platform, mail_provider, custom_url, count, headless, proxy, browser)
        job.parallel_count = max(1, min(parallel, 3))  # Limit to 3 parallel workers
        with self.lock:
            self.jobs[job.reg_id] = job
            self._running = True
        def _run():
            try:
                job.run()
            finally:
                with self.lock:
                    self._running = False
        threading.Thread(target=_run, daemon=True).start()
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
