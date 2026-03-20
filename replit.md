# C2 Server — Command & Control Panel

## Overview
A full-featured Command & Control (C2) framework with a Flask web dashboard for managing multi-platform agents, automated account registrations, and GPU-optimized machine learning tasks.

## Tech Stack
- **Backend**: Python 3.12, Flask, Flask-SocketIO, Flask-Bcrypt
- **Database**: SQLite (`data/c2.db`)
- **Templating**: Jinja2 (server-side rendered)
- **Frontend**: Custom HTML/CSS/JS in `templates/` and `static/`
- **Real-time**: WebSocket via Flask-SocketIO

## Project Structure
- `server.py` — Main Flask application (4000+ lines), all routes and business logic
- `run_server.py` — Entry point / startup script
- `autoreg.py` / `autoreg_worker.py` — Auto-registration engine for platform account creation
- `tempmail.py` — Temporary email service integration
- `captcha_solver.py` — CAPTCHA solving utilities
- `agents/` — Platform-specific agent implementations (Linux, macOS, Windows, Colab, Kaggle)
- `optimizer/` — PyTorch GPU workload optimizer
- `kaggle_c2_transport.py` — Kaggle-specific C2 transport layer
- `templates/` — Jinja2 HTML templates for the dashboard
- `static/` — CSS, JS, and other static assets
- `data/` — SQLite database, uploads, and secret key storage

## Running the App
The app runs via:
```
python3 run_server.py --port 5000 --no-ssl --no-tunnel --host 0.0.0.0
```

Default login: **admin / admin**

## Configuration
- Copy `.env.example` to `.env` and fill in API keys for CAPTCHA services, email services, etc.
- The secret key is auto-generated and stored in `data/.secret_key`
- SQLite DB is auto-initialized at `data/c2.db`

## Workflow
- **Start application**: Runs the server on port 5000 (webview)

## Deployment
- Configured as VM deployment (needed for WebSocket/SocketIO support)
- Run command: `python3 run_server.py --port 5000 --no-ssl --no-tunnel --host 0.0.0.0`
