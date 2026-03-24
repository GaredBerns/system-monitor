# Project Structure

## Directory Organization

```
C2_server-main/
├── src/                      # Core application source code
│   ├── c2/                   # C2 server core
│   ├── agents/               # Platform-specific agents
│   ├── autoreg/              # Auto-registration system
│   ├── mail/                 # Email services
│   ├── mining/               # GPU mining/compute
│   ├── core/                 # Configuration & validation
│   └── utils/                # Shared utilities
├── templates/                # HTML templates for web UI
├── static/                   # CSS/JS assets
├── data/                     # Database and runtime data
├── logs/                     # Application logs
├── docs/                     # Documentation
├── scripts/                  # Utility scripts
├── tests/                    # Test suite
├── config/                   # Configuration files
├── deploy/                   # Deployment configs
└── rules/                    # Project rules/guidelines
```

## Core Components

### 1. C2 Server Core (`src/c2/`)
**Purpose**: Main command & control server implementation

- `server.py` - Flask application with web dashboard, API endpoints, WebSocket support
- `orchestrator.py` - Unified module orchestration (scanner, exploits, counter-surveillance)
- `master_orchestrator.py` - High-level coordination of all subsystems
- `autonomous_miner.py` - Automated mining operations
- `task_queue.py` - Task distribution and queue management
- `models.py` - Database models for agents, tasks, logs

**Key Responsibilities**:
- Agent registration and management
- Task creation and distribution
- Real-time dashboard updates via WebSocket
- API endpoints for agent communication
- Authentication and session management

### 2. Agents (`src/agents/`)
**Purpose**: Platform-specific agent implementations

- `universal.py` - Cross-platform Python agent
- `base.py` - Base agent class with common functionality
- `windows.ps1` - PowerShell agent for Windows
- `browser/` - Browser automation agents (captcha solving, Firefox control)
- `kaggle/` - Kaggle-specific agents and deployment

**Agent Capabilities**:
- Command execution
- File upload/download
- System information gathering
- Periodic check-in with C2 server
- Task result reporting

### 3. Auto-Registration (`src/autoreg/`)
**Purpose**: Automated account creation and management

- `engine.py` - Registration orchestration engine
- `worker.py` - Worker processes for parallel registration

**Features**:
- Multi-threaded account creation
- Browser automation for registration flows
- Captcha solving integration
- Account credential storage

### 4. Email Services (`src/mail/`)
**Purpose**: Temporary email management

- `tempmail.py` - Temporary email API integration
- Email verification handling
- Account activation automation

### 5. Mining/Compute (`src/mining/`)
**Purpose**: GPU-optimized compute operations

- `cli.py` - Command-line interface for mining operations
- `torch_cuda_optimizer/` - PyTorch CUDA optimization modules
- XMRig integration for cryptocurrency mining

### 6. Core Infrastructure (`src/core/`)
**Purpose**: Configuration, validation, and system health

- `config.py` - Configuration management and environment variables
- `validation.py` - Input validation and sanitization
- `secrets.py` - Secret key management
- `health.py` - Health check endpoints
- `metrics.py` - Metrics collection and reporting

### 7. Utilities (`src/utils/`)
**Purpose**: Shared utility functions

- `logger.py` - Structured logging with JSON output
- `proxy.py` - Proxy management and rotation
- `rate_limit.py` - Rate limiting for API endpoints
- `validation.py` - Common validation functions
- `common.py` - Shared helper functions

## Architectural Patterns

### 1. Modular Architecture
- Clear separation of concerns with dedicated modules
- Each module has single responsibility
- Loose coupling through well-defined interfaces

### 2. Integration Layer
- `orchestrator.py` provides unified API for all modules
- Centralized coordination of scanner, exploits, alerts
- Event-driven architecture with callbacks

### 3. Agent-Server Pattern
- Agents poll server for tasks (pull model)
- Server maintains agent registry
- Queue-based task distribution
- Asynchronous result reporting

### 4. Web Dashboard Architecture
- Flask backend with Jinja2 templates
- WebSocket for real-time updates (Flask-SocketIO)
- RESTful API for agent communication
- Session-based authentication

### 5. Data Layer
- SQLite database for persistence (`data/c2.db`)
- JSON files for configuration (`accounts.json`, `email_accounts.json`)
- File-based storage for uploads and screenshots

## Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Dashboard                          │
│                    (Flask + SocketIO)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   C2 Server Core                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Orchestrator │  │  Task Queue  │  │   Models     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌────▼─────┐ ┌─────▼──────┐
│   Agents     │ │ AutoReg  │ │   Mining   │
│ (Universal,  │ │ (Engine, │ │ (Optimizer,│
│  Kaggle,     │ │  Worker) │ │   XMRig)   │
│  Browser)    │ └──────────┘ └────────────┘
└──────────────┘
        │
┌───────▼──────────────────────────────────────┐
│         Utilities & Core Services            │
│  (Logger, Proxy, Config, Validation)         │
└──────────────────────────────────────────────┘
```

## Data Flow

1. **Agent Registration**: Agent → `/api/agent/register` → Database
2. **Task Creation**: Dashboard → Task Queue → Database
3. **Task Retrieval**: Agent → `/api/agent/tasks` → Task Queue
4. **Result Submission**: Agent → `/api/agent/result` → Database → WebSocket → Dashboard
5. **Real-time Updates**: Server Event → WebSocket → Dashboard

## Configuration Files

- `.env` - Environment variables (secrets, API keys)
- `config/settings.yaml` - Application settings
- `config/logging.yaml` - Logging configuration
- `gunicorn.conf.py` - Production server configuration
- `docker-compose.yml` - Docker deployment
- `prometheus.yml` - Metrics collection

## Entry Points

- `run_unified.py` - Main application launcher
- `wsgi.py` - WSGI entry point for production
- `setup.py` - Package installation
- `manage.sh` - Server management script
