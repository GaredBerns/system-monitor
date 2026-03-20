# C2 Server — Command & Control Panel

Flask-based C2 panel: multi-platform agents, scheduler, auto-registration, temp mail, webhooks, encrypted agent comms.

## Quick start

```bash
pip install -r requirements.txt
playwright install chromium   # for Auto-Reg
./run_autoreg.sh             # или: python3 server.py --port 8443 --no-tunnel
# Login: admin / admin
```

Проверка: `python3 verify.py`

## Features

- **Agents**: Linux, Windows, macOS, Colab, Docker, Cloud VM, Android (Termux), SSH
- **Scheduler**: Recurring tasks (`:start`, `:status`, etc.)
- **Auto-Reg**: Kaggle, GitHub, HuggingFace, etc. — Playwright + CAPTCHA (2captcha/FCB)
- **Temp Mail**: Disposable inbox (Boomlify, mail.tm, temp-mail.io)
- **Security**: Agent PSK, XOR encryption, rate limiting, security headers
- **Export**: CSV for agents, logs, tasks

## Options

- `--port` — HTTP port (default 8443)
- `--no-ssl` — run without HTTPS
- `--no-tunnel` — skip Cloudflare tunnel

## CAPTCHA (Auto-Reg)

Set `CAPTCHA_API_KEY` and optionally `CAPTCHA_SERVICE` (default: 2captcha). For Kaggle with 2captcha:
```bash
export CAPTCHA_API_KEY=your_2captcha_key
export CAPTCHA_SERVICE=2captcha
```

See `docs/kaggle_captcha_analysis.md` for Kaggle CAPTCHA details.

## Data

Runtime data (DB, certs, uploads) lives in `data/`. Create `data/.secret_key` or let the server generate it on first run.
