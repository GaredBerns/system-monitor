# C2 Server — Command & Control Panel

## Overview
Full-featured C2 framework with a Flask web dashboard for managing agents across multiple platforms, auto-registering accounts, and GPU compute optimization.

**Default login:** `admin / admin`  
**Start command:** `python3 run_server.py --port 5000 --no-ssl --no-tunnel --host 0.0.0.0`

---

## Tech Stack
- **Backend:** Python 3.12, Flask, Flask-SocketIO, Flask-Bcrypt
- **Database:** SQLite (`data/c2.db`, WAL mode)
- **Templates:** Jinja2 (server-side rendering)
- **Styles:** Custom CSS with CSS custom properties
- **Real-time:** WebSocket via Flask-SocketIO

---

## Project Structure

```
/
├── run_server.py           # Server entry point
├── run_optimizer.py        # GPU optimizer entry point
├── utils.py                # Shared utilities (generate_identity, clean_name)
├── setup.py                # Package config (c2-server, c2-optimizer console scripts)
├── requirements.txt        # Python dependencies
│
├── core/
│   ├── __init__.py
│   └── server.py           # All Flask routes, SocketIO handlers, DB logic (~4100 lines)
│
├── agents/                 # Agent scripts (served at /agents/<filename>)
│   ├── agent_linux.py      # Linux/Unix agent (Python 3, stdlib only)
│   ├── agent_macos.py      # macOS agent with LaunchAgent persistence
│   ├── agent_windows.ps1   # Windows PowerShell agent
│   ├── agent_colab.py      # Google Colab / Jupyter agent
│   ├── agent_universal.py  # Auto-detect platform universal agent
│   └── kaggle_agent.py     # Kaggle kernel agent (DoH DNS bypass)
│
├── autoreg/                # Auto-registration engine
│   ├── engine.py           # Job manager, account store, PLATFORMS registry
│   └── worker.py           # Playwright/undetected-chromedriver worker
│
├── browser/                # Browser automation
│   ├── captcha.py          # CAPTCHA bypass (manual, 2captcha, stealth)
│   ├── firefox.py          # Selenium Firefox worker
│   └── page_utils.py       # Page helper utilities
│
├── kaggle/                 # Kaggle C2 transport
│   ├── transport.py        # C2 via Kaggle kernels/datasets
│   ├── datasets.py         # Dataset management
│   ├── gpu.py              # GPU activator
│   ├── quick_save.py       # State snapshots
│   ├── batch_join.py       # Mass agent joining
│   └── setup_accounts.py   # Account setup helpers
│
├── mail/
│   └── tempmail.py         # Temp email (Boomlify + providers)
│
├── network/
│   └── relay.py            # Webhook relay server
│
├── optimizer/
│   ├── cli.py              # CLI entry point
│   └── torch_cuda_optimizer.py  # PyTorch GPU optimization engine
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Base layout (sidebar, topbar)
│   ├── login.html          # Login page
│   ├── dashboard.html      # Main dashboard
│   ├── devices.html        # Agent list & management
│   ├── payloads.html       # Payload generator (all platforms)
│   ├── agent_console.html  # Per-agent shell console
│   ├── autoreg.html        # Auto-registration control
│   ├── tempmail.html       # Temp email manager
│   ├── laboratory.html     # GPU optimizer UI
│   ├── settings.html       # Server settings
│   ├── scheduler.html      # Task scheduler
│   └── logs.html           # Event log viewer
│
├── static/
│   ├── css/style.css       # Unified CSS (CSS custom properties)
│   └── js/
│       ├── ui.js           # Notifications, command palette, shortcuts
│       └── socket.js       # SocketIO connection (depends on ui.js)
│
└── data/                   # Persistent storage (gitignored)
    ├── c2.db               # SQLite database
    ├── uploads/            # File uploads from agents
    ├── accounts.json       # Registered accounts
    └── .secret_key         # Flask secret key
```

---

## Agent System

### How Agents Work
1. Agent starts → calls `POST /api/agent/register` with sysinfo
2. Agent loops → calls `POST /api/agent/beacon` every N seconds
3. Server responds with pending tasks
4. Agent executes tasks → calls `POST /api/agent/result`
5. Results appear in real-time in the agent console (WebSocket)

### Agent URL Injection
All agents use `http://CHANGE_ME:443` as a placeholder. When served via `GET /agents/<filename>`, the server automatically injects:
- Correct public/tunnel URL
- Auth token (if configured in Settings)
- Encryption key (if configured in Settings)

### Supported Platforms
| File | Platform | Persistence |
|------|----------|-------------|
| `agent_linux.py` | Linux / Unix | crontab, systemd |
| `agent_macos.py` | macOS | LaunchAgents plist |
| `agent_windows.ps1` | Windows 7+ | Scheduled Task, Registry Run |
| `agent_colab.py` | Google Colab / Jupyter | daemon thread |
| `agent_universal.py` | All of the above | auto-detects |
| `kaggle_agent.py` | Kaggle kernels | daemon thread + DoH DNS |

### Supported Task Types
| Task Type | Description |
|-----------|-------------|
| `cmd` | Execute shell command |
| `python` | Execute Python code |
| `sysinfo` | Full system information JSON |
| `env` | List all environment variables |
| `ls [path]` | List directory contents |
| `ps` | Running process list |
| `net` | Network interfaces and routes |
| `clipboard` | Read clipboard contents |
| `download <path>` | Download file (returned as base64) |
| `upload <path>\|<b64>` | Upload file to agent |
| `screenshot` | Capture screen (requires `pip install mss`) |
| `persist` | Install platform-appropriate persistence |
| `persist_systemd` | Install systemd service (Linux) |
| `kill` | Terminate agent and remove persistence |

### Console Shortcuts (Beacon Dynamic Sleep)
Beacon response now returns `sleep` and `jitter` from DB per-agent — agents auto-update their interval without restart.

Type these in any agent console (cmd type, or click buttons in Shortcuts sidebar):

**GPU Optimizer:**
- `:start` — установить и запустить GPU optimizer
- `:status` — статус optimizer
- `:log` — лог optimizer (последние 50 строк)
- `:persist` — запуск + добавить в crontab
- `:stop` — остановить optimizer
- `:cleanup` — удалить все следы

**Сбор информации:**
- `:sysinfo` — полная информация о системе
- `:id` — whoami + hostname
- `:ps` — список процессов по CPU
- `:net` — сетевые интерфейсы + маршруты
- `:ports` — открытые порты
- `:env` — переменные окружения
- `:gpu` — информация о GPU
- `:cwd` — текущая директория + ls
- `:history` — история bash
- `:cron` — crontab
- `:ssh` — SSH ключи / known_hosts
- `:uptime` — uptime + кто залогинен

---

## Payload Generator (`/payloads`)
The payloads page provides ready-to-use one-liners for every platform. The server URL is auto-injected on page load from `/api/server/public_url`. You can also paste any custom URL and click **Apply**.

---

## Settings & Configuration

### Key Config Values (Settings page)
| Key | Description |
|-----|-------------|
| `public_url` | Public URL для туннелей/внешнего доступа |
| `agent_token` | Auth токен — агенты должны отправлять в X-Auth-Token |
| `encryption_key` | XOR ключ шифрования agent ↔ server трафика |
| `cloudflare_tunnel_token` | Cloudflare named tunnel token |
| `captcha_api_key` | CapMonster/Anti-Captcha API ключ (для авторегистрации) |
| `boomlify_api_keys` | Boomlify API ключи (по строке) — для temp mail |
| `fcb_api_keys` | FCaptcha API ключи (по строке) |
| `webhook_discord` | Discord webhook URL для нотификаций |
| `webhook_telegram` | Telegram bot URL для нотификаций |

Ключи captcha/mail автоматически синхронизируются в env vars и `data/*.txt` при сохранении и при запуске сервера.

### Environment Variables (`.env`)
```bash
SECRET_KEY=your-flask-secret-key
DEBUG=False
VERBOSE_MAIL=0
```

---

## Architecture Notes

- `core/server.py` uses `BASE_DIR = Path(__file__).resolve().parent.parent` for project root
- All `data/` paths: `Path(__file__).resolve().parent.parent / "data" / ...`
- JS load order: SocketIO CDN → `ui.js` → `socket.js` (socket.js depends on `showNotification` from ui.js)
- Lazy imports inside routes: `from kaggle.transport import ...`, `from mail.tempmail import ...`
- SQLite WAL mode enabled for concurrent reads during SocketIO events

---

## Deployment
- **Type:** VM (required for WebSocket / SocketIO)
- **Command:** `python3 run_server.py --port 5000 --no-ssl --no-tunnel --host 0.0.0.0`
- **Port mapping:** 5000 → 80 (external)
- **Public URL:** Configure in Settings or use Cloudflare tunnel
