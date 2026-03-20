# C2 Server — Command & Control Panel

## Обзор
Полнофункциональный C2-фреймворк с веб-дашбордом на Flask для управления агентами, автоматической регистрации аккаунтов и GPU-оптимизации.

## Технологии
- **Backend**: Python 3.12, Flask, Flask-SocketIO, Flask-Bcrypt
- **База данных**: SQLite (`data/c2.db`)
- **Шаблоны**: Jinja2 (server-side rendering)
- **Стили**: кастомный CSS с CSS custom properties
- **Real-time**: WebSocket через Flask-SocketIO

## Структура пакетов

```
/
├── run_server.py           # Точка входа сервера
├── run_optimizer.py        # Точка входа GPU-оптимизатора
├── utils.py                # Общие утилиты (generate_identity, clean_name, find_firefox_profile)
├── core/                   # Flask-приложение
│   ├── __init__.py
│   └── server.py           # Все роуты, SocketIO-обработчики, логика сервера
├── autoreg/                # Авто-регистрация аккаунтов
│   ├── __init__.py
│   ├── engine.py           # Движок регистрации (job_manager, account_store, PLATFORMS)
│   └── worker.py           # Playwright/undetected-chromedriver воркер
├── browser/                # Браузерная автоматизация
│   ├── __init__.py
│   ├── captcha.py          # Решение CAPTCHA (manual, API, stealth)
│   ├── firefox.py          # Firefox-воркер (Selenium + GeckoDriver)
│   └── page_utils.py       # Вспомогательные функции для работы со страницами
├── kaggle/                 # Kaggle C2-транспорт
│   ├── __init__.py
│   ├── transport.py        # C2-транспорт через Kaggle (kernels/datasets)
│   ├── datasets.py         # Управление датасетами
│   ├── gpu.py              # GPU-активатор через Kaggle
│   ├── quick_save.py       # Быстрое сохранение состояния
│   ├── batch_join.py       # Массовое подключение агентов
│   └── setup_accounts.py   # Настройка Kaggle-аккаунтов
├── mail/                   # Временная почта
│   ├── __init__.py
│   └── tempmail.py         # Boomlify + другие провайдеры (mail_manager)
├── network/                # Сетевой слой
│   ├── __init__.py
│   └── relay.py            # Relay-сервер
├── optimizer/              # PyTorch GPU-оптимизатор
│   ├── __init__.py
│   ├── cli.py              # CLI точка входа
│   └── torch_cuda_optimizer.py
├── agents/                 # Агенты (Linux, macOS, Windows, Colab, Kaggle)
├── templates/              # Jinja2 HTML-шаблоны
│   ├── base.html           # Базовый шаблон (сайдбар, топбар)
│   ├── login.html          # Страница входа
│   └── ...                 # dashboard, devices, console, autoreg, tempmail, settings...
├── static/
│   ├── css/style.css       # Единый CSS (CSS custom properties, без дубликатов)
│   └── js/
│       ├── socket.js       # SocketIO-соединение и статус подключения
│       └── ui.js           # Уведомления, command palette, клавиатурные шорткаты
└── data/                   # БД, загрузки, ключи (c2.db, accounts.json)
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

## Важные замечания по архитектуре
- `core/server.py` использует `BASE_DIR = Path(__file__).resolve().parent.parent` для указания корня проекта
- Все пути к `data/` в подпакетах: `Path(__file__).resolve().parent.parent / "data" / ...`
- JS-файлы загружаются в порядке: SocketIO CDN → ui.js → socket.js (socket.js зависит от `showNotification` из ui.js)
- Lazy-импорты внутри роутов: `from kaggle.transport import ...`, `from mail.tempmail import ...`, `from kaggle.datasets import ...`
