"""CAPTCHA Bypass Engine v3 — adaptive per-platform strategy.

Two modes:
 - STEALTH: block captcha scripts, fake token, good for sites without server-side validation
 - SOLVE:   let captcha load, solve via API (2captcha/capsolver) or manual live view
"""

import os, json, time, re, threading, random, string
from urllib.request import Request, urlopen
from pathlib import Path

SCREENSHOTS_DIR = Path(__file__).resolve().parent / "data" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Load keys: CAPTCHA_API_KEY (single) or CAPTCHA_API_KEYS (comma-sep, rotation)
_captcha_keys_raw = os.environ.get("CAPTCHA_API_KEYS", "").strip() or os.environ.get("CAPTCHA_API_KEY", "")
CAPTCHA_API_KEYS_LIST = [k.strip() for k in _captcha_keys_raw.split(",") if k.strip()] if _captcha_keys_raw else []
CAPTCHA_API_KEY = CAPTCHA_API_KEYS_LIST[0] if CAPTCHA_API_KEYS_LIST else os.environ.get("CAPTCHA_API_KEY", "")
_captcha_key_index = 0

# FCB keys: env FCB_API_KEYS (comma-sep) или data/fcb_keys.txt (по одному на строку)
_data_dir = Path(__file__).resolve().parent / "data"
_fcb_keys_env = os.environ.get("FCB_API_KEYS", "").strip()
if _fcb_keys_env:
    FCB_API_KEYS = [k.strip() for k in _fcb_keys_env.split(",") if k.strip()]
else:
    _fcb_file = _data_dir / "fcb_keys.txt"
    if _fcb_file.exists():
        FCB_API_KEYS = [ln.strip() for ln in _fcb_file.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    else:
        FCB_API_KEYS = []  # Нет ключей по умолчанию — добавьте в data/fcb_keys.txt
_fcb_key_index = 0

# Если есть FCB ключи и нет 2captcha — используем FCB
_has_2captcha = bool(CAPTCHA_API_KEYS_LIST or CAPTCHA_API_KEY)
CAPTCHA_SERVICE = os.environ.get("CAPTCHA_SERVICE", "fcb" if FCB_API_KEYS and not _has_2captcha else "2captcha")

SITES_NEED_REAL_CAPTCHA = {"kaggle", "github", "google_colab", "paperspace"}
SITES_CAN_BLOCK = {"huggingface", "replit", "lightning_ai", "custom"}


def setup_stealth_only(context):
    """Minimal stealth: anti-detection only, no captcha blocking.
    Use for sites that validate captcha server-side."""
    context.add_init_script("""() => {
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
        if (window.chrome === undefined) {
            window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}};
        }
        const origQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (params) =>
            params.name === 'notifications'
                ? Promise.resolve({state: Notification.permission})
                : origQuery(params);
    }""")


def setup_captcha_block(context, page, job):
    """Full block mode: prevent captcha scripts from loading, inject fake tokens.
    Use for sites without server-side captcha validation."""
    context.add_init_script("""() => {
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});

        const _fakeToken = '03AFcWeA5_' + Array.from({length:160}, () =>
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
            [Math.floor(Math.random()*64)]).join('');

        window.grecaptcha = {
            ready: cb => cb && setTimeout(cb,0), render: () => 0, reset: () => {},
            getResponse: () => _fakeToken, execute: () => Promise.resolve(_fakeToken),
            enterprise: { ready: cb => cb && setTimeout(cb,0), render: () => 0,
                          getResponse: () => _fakeToken, execute: () => Promise.resolve(_fakeToken) },
        };
        Object.defineProperty(window, 'grecaptcha', {get:()=>window.grecaptcha, set:()=>true, configurable:true});

        window.hcaptcha = { render:()=>0, getResponse:()=>_fakeToken,
            execute:()=>Promise.resolve({response:_fakeToken}) };

        const obs = new MutationObserver(() => {
            document.querySelectorAll('textarea[name="g-recaptcha-response"]').forEach(t => {
                if (!t.value) t.value = _fakeToken;
            });
            document.querySelectorAll('.g-recaptcha,.h-captcha,[data-sitekey]').forEach(el => el.style.display='none');
        });
        if (document.documentElement) obs.observe(document.documentElement, {childList:true,subtree:true});
        window.__BYPASS_TOKEN = _fakeToken;
    }""")

    def block_captcha(route):
        url = route.request.url
        for d in ["recaptcha", "hcaptcha", "captcha"]:
            if d in url:
                job.log(f"BLOCKED: {url[:60]}")
                route.fulfill(status=200, content_type="application/javascript", body="/* blocked */")
                return
        route.continue_()

    page.route("**/*recaptcha*", block_captcha)
    page.route("**/*hcaptcha*", block_captcha)
    job.log("Block mode: captcha scripts will be blocked")


# ─────────────── SOLVE MODE: API services ───────────────

def _api_request(url, data=None):
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
    return json.loads(urlopen(req, timeout=30).read())


def _get_next_fcb_key() -> str:
    """Get next FCB key in rotation."""
    global _fcb_key_index
    key = FCB_API_KEYS[_fcb_key_index % len(FCB_API_KEYS)]
    _fcb_key_index += 1
    return key


def _get_next_2captcha_key() -> str:
    """Rotate through 2captcha keys."""
    global _captcha_key_index
    if not CAPTCHA_API_KEYS_LIST:
        return CAPTCHA_API_KEY
    key = CAPTCHA_API_KEYS_LIST[_captcha_key_index % len(CAPTCHA_API_KEYS_LIST)]
    _captcha_key_index += 1
    return key


def get_captcha_key_for_solve() -> str:
    """Get next key for external solvers (kaggle_captcha_solver)."""
    return _get_next_2captcha_key() if CAPTCHA_SERVICE == "2captcha" else CAPTCHA_API_KEY


def solve_recaptcha_api(sitekey, page_url, job, is_enterprise=False, enterprise_payload=None) -> str:
    """Solve reCAPTCHA v2 via paid service. Returns token or empty string."""
    key = _get_next_2captcha_key() if CAPTCHA_SERVICE == "2captcha" else CAPTCHA_API_KEY
    svc = CAPTCHA_SERVICE
    
    # Auto-detect FCB if no key set but FCB keys available
    if not key and FCB_API_KEYS:
        key = _get_next_fcb_key()
        svc = "fcb"
        job.log(f"Using FCB key rotation (key #{_fcb_key_index})")
    
    # 2captcha without key — try FCB as fallback
    if not key and svc == "2captcha" and FCB_API_KEYS:
        key = _get_next_fcb_key()
        svc = "fcb"
        job.log("No 2captcha key — using FCB fallback")
    
    if not key:
        job.log("No CAPTCHA API key. Add keys to data/captcha_keys.txt or set CAPTCHA_API_KEYS env")
        return ""

    job.log(f"Sending captcha to {svc} API...")
    if is_enterprise:
        job.log("Using Enterprise reCAPTCHA type")

    try:
        if svc == "2captcha":
            r = _api_request(f"https://2captcha.com/in.php?key={key}&method=userrecaptcha&googlekey={sitekey}&pageurl={page_url}&json=1")
            if r.get("status") != 1:
                return ""
            tid = r["request"]
            for i in range(60):
                time.sleep(5)
                r2 = _api_request(f"https://2captcha.com/res.php?key={key}&action=get&id={tid}&json=1")
                if r2.get("status") == 1:
                    job.log("Captcha solved by API!")
                    return r2["request"]
                if "UNSOLVABLE" in str(r2.get("request", "")):
                    return ""
        elif svc == "fcb":
            # FCB API (Free CAPTCHA Bypass) - capsolver-compatible format
            # Detect captcha type by sitekey format or explicit enterprise flag
            if is_enterprise:
                task_type = "ReCaptchaV2EnterpriseTaskProxyLess"
            elif sitekey.startswith("0x"):  # Cloudflare Turnstile
                task_type = "TurnstileTaskProxyLess"
            else:
                task_type = "ReCaptchaV2TaskProxyLess"
            
            task = {
                "type": task_type,
                "websiteURL": page_url,
                "websiteKey": sitekey
            }
            
            # Add enterprise payload if provided
            if is_enterprise and enterprise_payload:
                task["enterprisePayload"] = enterprise_payload
            
            r = _api_request("https://freecaptchabypass.com/createTask", {
                "clientKey": key,
                "task": task
            })
            tid = r.get("taskId")
            if not tid:
                job.log(f"FCB createTask error: {r}")
                return ""
            job.log(f"FCB taskId: {tid}")
            for i in range(60):
                time.sleep(5)
                r2 = _api_request("https://freecaptchabypass.com/getTaskResult", {
                    "clientKey": key,
                    "taskId": tid
                })
                if r2.get("status") == "ready":
                    job.log("Captcha solved by FCB API!")
                    sol = r2.get("solution", {}) or {}
                    return sol.get("gRecaptchaResponse") or sol.get("token") or sol.get("response") or ""
                if r2.get("errorId", 0) > 0:
                    job.log(f"FCB error: {r2}")
                    return ""
                if (i + 1) % 6 == 0:
                    job.log(f"FCB still processing... ({i+1}*5s)")
        elif svc in ("capsolver", "anticaptcha"):
            base = {"capsolver": "https://api.capsolver.com", "anticaptcha": "https://api.anti-captcha.com"}[svc]
            r = _api_request(f"{base}/createTask", {"clientKey": key, "task": {
                "type": "RecaptchaV2TaskProxyless", "websiteURL": page_url, "websiteKey": sitekey}})
            tid = r.get("taskId")
            if not tid:
                return ""
            for i in range(60):
                time.sleep(5)
                r2 = _api_request(f"{base}/getTaskResult", {"clientKey": key, "taskId": tid})
                if r2.get("status") == "ready":
                    job.log("Captcha solved by API!")
                    return r2.get("solution", {}).get("gRecaptchaResponse", "")
                if r2.get("errorId", 0) > 0:
                    return ""
    except Exception as e:
        job.log(f"API captcha error: {e}")
    return ""


def extract_sitekey(page) -> str:
    try:
        return page.evaluate("""() => {
            let el = document.querySelector('[data-sitekey]');
            if (el) return el.getAttribute('data-sitekey');
            let iframe = document.querySelector('iframe[src*="recaptcha"]');
            if (iframe) { let m = iframe.src.match(/[?&]k=([^&]+)/); if (m) return m[1]; }
            return '';
        }""") or ""
    except:
        return ""


def inject_token(page, token, job) -> bool:
    """Inject a solved token into page DOM and fire callbacks."""
    try:
        result = page.evaluate("""(token) => {
            let filled = 0;
            document.querySelectorAll('textarea[name="g-recaptcha-response"]').forEach(t => {
                t.style.display = 'block'; t.value = token; filled++;
            });
            // Fire reCAPTCHA internal callback
            try {
                if (typeof ___grecaptcha_cfg !== 'undefined') {
                    Object.keys(___grecaptcha_cfg.clients).forEach(key => {
                        const c = ___grecaptcha_cfg.clients[key];
                        function walk(o, d) {
                            if (!o || d > 10) return;
                            for (let k of Object.keys(o)) {
                                if (typeof o[k] === 'function') { try { o[k](token); filled++; } catch(e){} }
                                else if (typeof o[k] === 'object' && o[k] !== null) walk(o[k], d+1);
                            }
                        }
                        walk(c, 0);
                    });
                }
            } catch(e){}
            // Also try grecaptcha callback
            try {
                if (typeof grecaptcha !== 'undefined' && grecaptcha.getResponse) {
                    // nothing extra needed, token already in textarea
                }
            } catch(e){}
            // Enable disabled buttons
            document.querySelectorAll('button[disabled], input[type="submit"][disabled]').forEach(b => {
                b.disabled = false; b.removeAttribute('disabled');
            });
            return filled;
        }""", token)
        if result:
            job.log(f"Token injected into {result} element(s)")
        return result > 0
    except Exception as e:
        job.log(f"Token inject error: {e}")
        return False


def solve_captcha_on_page(page, job) -> bool:
    """Full solve pipeline for sites with server-side validation.
    1) Check if already solved (invisible captcha may auto-solve)
    2) Try API if key set
    3) Try checkbox click (might pass without challenge)
    4) Fall back to manual live view
    """

    # Сначала проверяем - может капча уже решена (invisible v3)
    try:
        already_solved = page.evaluate("""() => {
        const token = document.querySelector('textarea[name="g-recaptcha-response"]');
        if (token && token.value && token.value.length > 10) return true;
        // Проверяем grecaptcha объект
        if (typeof grecaptcha !== 'undefined' && grecaptcha.getResponse) {
            try { return grecaptcha.getResponse() && grecaptcha.getResponse().length > 10; } catch(e) {}
        }
        return false;
    }""")
        if already_solved:
            job.log("Captcha already solved (invisible/v3)")
            return True
    except:
        pass

    has_captcha = False
    try:
        has_captcha = page.evaluate("""() => {
            return document.querySelectorAll('iframe[src*="recaptcha"], .g-recaptcha, [data-sitekey]').length > 0;
        }""")
    except:
        pass

    if not has_captcha:
        job.log("No captcha elements found on page")
        return True

    job.log("Captcha detected — attempting solve...")

    sitekey = extract_sitekey(page)

    # Method 1: API solve
    if sitekey and CAPTCHA_API_KEY:
        token = solve_recaptcha_api(sitekey, page.url, job)
        if token:
            inject_token(page, token, job)
            time.sleep(1)
            return True

    # Method 2: checkbox click (sometimes passes without challenge)
    # ВАЖНО: кликаем только один раз, повторный клик сбросит токен!
    try:
        anchor = page.frame_locator("iframe[src*='recaptcha'][src*='anchor']")
        cb = anchor.locator("#recaptcha-anchor")
        if cb.is_visible(timeout=3000):
            # Проверяем состояние чекбокса - если уже checked, не кликаем
            cb_class = cb.get_attribute("class") or ""
            if "recaptcha-checkbox-checked" in cb_class:
                job.log("Captcha checkbox already checked")
                return True
            
            cb.click()
            job.log("Clicked captcha checkbox (once)")
            time.sleep(4)

            try:
                has_challenge = page.frame_locator(
                    "iframe[src*='recaptcha'][src*='bframe']"
                ).locator(".rc-imageselect-challenge, .rc-audiochallenge-play-button").is_visible(timeout=2000)
            except:
                has_challenge = False

            if not has_challenge:
                job.log("Checkbox click passed — no challenge!")
                return True
            else:
                job.log("Image/audio challenge appeared — needs manual solve")
    except Exception as e:
        job.log(f"Checkbox click: {e}")

    # Method 3: manual via live view
    job.log("Auto-solve failed — requesting manual solve in live view...")
    return False


# ─────────────── MANUAL LIVE VIEW ───────────────

class ManualCaptchaSolver:
    _pending = {}
    _lock = threading.Lock()

    @classmethod
    def request_solve(cls, job_id, page, job) -> bool:
        event = threading.Event()
        ss = str(SCREENSHOTS_DIR / f"captcha_live_{job_id}.png")
        try:
            page.screenshot(path=ss)
        except:
            pass

        with cls._lock:
            cls._pending[job_id] = {
                "event": event, "screenshot": ss,
                "page": page, "solved": False,
                "requested_at": time.time(),
            }
        job.log("CAPTCHA needs manual solving — open Live View on Auto-Reg page")
        solved = event.wait(timeout=180)
        with cls._lock:
            entry = cls._pending.pop(job_id, {})
        return entry.get("solved", False)

    @classmethod
    def mark_solved(cls, job_id):
        with cls._lock:
            e = cls._pending.get(job_id)
            if e:
                e["solved"] = True
                e["event"].set()
                return True
        return False

    @classmethod
    def refresh_screenshot(cls, job_id):
        with cls._lock:
            e = cls._pending.get(job_id)
            if e and e.get("page"):
                try:
                    ss = str(SCREENSHOTS_DIR / f"captcha_live_{job_id}.png")
                    e["page"].screenshot(path=ss)
                    return ss
                except:
                    pass
        return ""

    @classmethod
    def get_pending(cls):
        with cls._lock:
            return [{"job_id": k, "screenshot": v["screenshot"],
                     "age": int(time.time() - v["requested_at"])} for k, v in cls._pending.items()]

    @classmethod
    def click_at(cls, job_id, x, y):
        with cls._lock:
            e = cls._pending.get(job_id)
            if e and e.get("page"):
                try:
                    e["page"].mouse.click(x, y)
                    time.sleep(0.5)
                    ss = str(SCREENSHOTS_DIR / f"captcha_live_{job_id}.png")
                    e["page"].screenshot(path=ss)
                    e["screenshot"] = ss
                    return True
                except:
                    pass
        return False


manual_solver = ManualCaptchaSolver
