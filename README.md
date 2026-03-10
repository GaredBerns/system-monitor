# C2 Server — Command & Control Panel

Flask-based C2 panel: multi-platform agents, scheduler, auto-registration, temp mail, webhooks, encrypted agent comms.

## Quick start

```bash
pip install -r requirements.txt
python server.py --port 8443
# Login: admin / admin (change in production)
```

## Features

- **Agents**: Linux, Windows, macOS, Colab, Docker, Cloud VM, Android (Termux), SSH
- **Scheduler**: Recurring tasks (`:start`, `:status`, etc.)
- **Auto-Reg**: Account registration with API key storage
- **Temp Mail**: Disposable inbox (Boomlify)
- **Security**: Agent PSK, XOR encryption, rate limiting, security headers
- **Export**: CSV for agents, logs, tasks

## Options

- `--port` — HTTP port (default 8443)
- `--no-ssl` — run without HTTPS
- `--no-tunnel` — skip Cloudflare tunnel

## Data

Runtime data (DB, certs, uploads) lives in `data/`. Create `data/.secret_key` or let the server generate it on first run.
