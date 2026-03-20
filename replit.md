# C2 Server — Command & Control Panel

## Обзор
Полнофункциональный C2-фреймворк с веб-дашбордом на Flask для управления агентами, автоматической регистрации аккаунтов и GPU-оптимизации.

## Технологии
- **Backend**: Python 3.12, Flask, Flask-SocketIO, Flask-Bcrypt
- **База данных**: SQLite (`data/c2.db`)
- **Шаблоны**: Jinja2 (server-side rendering)
- **Стили**: кастомный CSS с CSS custom properties
- **Real-time**: WebSocket через Flask-SocketIO

## Структура файлов

```
/
├── server.py               # Основное Flask-приложение (все роуты и логика)
├── run_server.py           # Точка входа (запуск сервера)
├── autoreg.py              # Движок авто-регистрации аккаунтов
├── autoreg_worker.py       # Воркер авто-регистрации
├── tempmail.py             # Сервис временной почты
├── captcha_solver.py       # Решение CAPTCHA
├── kaggle_c2_transport.py  # C2-транспорт через Kaggle
├── agents/                 # Агенты для разных платформ
│   ├── agent_linux.py
│   ├── agent_macos.py
│   ├── agent_colab.py
│   ├── agent_windows.ps1
│   └── kaggle_agent.py
├── optimizer/              # PyTorch GPU-оптимизатор
├── templates/              # Jinja2 HTML-шаблоны
│   ├── base.html           # Базовый шаблон (сайдбар, топбар)
│   ├── login.html          # Страница входа
│   ├── dashboard.html      # Главный дашборд
│   ├── devices.html        # Управление устройствами
│   ├── console.html        # Консоль команд
│   ├── payloads.html       # Генератор пейлоадов
│   ├── scheduler.html      # Планировщик задач
│   ├── autoreg.html        # Авто-регистрация
│   ├── laboratory.html     # Лаборатория
│   ├── tempmail.html       # Временная почта
│   ├── logs.html           # Системные логи
│   └── settings.html       # Настройки
├── static/
│   ├── css/
│   │   └── style.css       # Единый CSS (без дубликатов, переменные + компоненты)
│   └── js/
│       ├── socket.js       # SocketIO-соединение и статус подключения
│       └── ui.js           # Уведомления, command palette, клавиатурные шорткаты
└── data/                   # БД, загрузки, ключи
```

## Запуск
```bash
python3 run_server.py --port 5000 --no-ssl --no-tunnel --host 0.0.0.0
```
Логин по умолчанию: **admin / admin**

## Workflow
- **Start application** → порт 5000, webview

## Деплой
- Тип: VM (нужен для WebSocket/SocketIO)
- Команда: `python3 run_server.py --port 5000 --no-ssl --no-tunnel --host 0.0.0.0`
