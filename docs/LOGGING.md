# 📋 ENHANCED LOGGING SYSTEM - Documentation

## ✅ УЛУЧШЕННОЕ ЛОГИРОВАНИЕ ДОБАВЛЕНО

**Дата:** 2026-03-22  
**Статус:** АКТИВНО

---

## 🎯 ЧТО УЛУЧШЕНО

### 1. Расширенный Logger (core/logger.py)
- ✅ Цветное логирование в консоль
- ✅ Множественные файлы логов (основной, JSON, ошибки)
- ✅ Структурированные JSON логи
- ✅ Статистика логов
- ✅ Специализированные методы (API, задачи, агенты, безопасность)
- ✅ Декораторы для автоматического логирования
- ✅ Context manager для блоков кода

### 2. Файлы Логов
```
logs/
├── {name}.log              # Основной лог (все уровни)
├── {name}_json.log         # Структурированный JSON
└── {name}_errors.log       # Только ошибки
```

### 3. Добавлено в Файлы
✅ core/server.py
✅ autoreg/engine.py
✅ autoreg/worker.py
✅ kaggle/deploy_agents.py
✅ kaggle/datasets.py
✅ browser/firefox.py
✅ browser/captcha.py
✅ mail/tempmail.py

---

## 📚 КАК ИСПОЛЬЗОВАТЬ

### Базовое Использование

```python
from core.logger import get_logger

# Получить логгер
log = get_logger(__name__)

# Базовые уровни
log.debug("Debug message")
log.info("Info message")
log.warning("Warning message")
log.error("Error message")
log.critical("Critical message")

# Специальные методы
log.success("Operation completed")
log.fail("Operation failed")
```

### Структурированное Логирование

```python
# API вызовы
log.log_api_call(
    method="POST",
    endpoint="/api/task/create",
    status=200,
    duration=0.123,
    user_id="user123"
)

# Задачи
log.log_task(
    task_id="task-123",
    task_type="shell",
    status="completed",
    result="success"
)

# Агенты
log.log_agent(
    agent_id="agent-456",
    action="register",
    hostname="server1",
    os="Linux"
)

# Безопасность
log.log_security(
    event="failed_login",
    severity="high",
    details={"ip": "1.2.3.4", "attempts": 5}
)

# Производительность
log.log_performance(
    operation="database_query",
    duration=0.045,
    rows=100
)
```

### Декораторы

```python
from core.logger import log_function, log_api_endpoint, log_task_execution

# Автоматическое логирование функций
@log_function()
def process_data(data):
    # Автоматически логирует вызов, результат, ошибки
    return data.upper()

# Логирование API endpoints (Flask)
@app.route('/api/test')
@log_api_endpoint()
def test_endpoint():
    return {"status": "ok"}

# Логирование выполнения задач
@log_task_execution()
def execute_task(task_id, task_type, payload):
    # Автоматически логирует начало, завершение, ошибки
    return {"result": "done"}
```

### Context Manager

```python
from core.logger import LogContext

# Логирование блока кода
with LogContext("myapp", "data_processing", records=1000):
    # Код обработки
    process_records()
    # Автоматически логирует время выполнения
```

### Форматированный Вывод

```python
# Секции
log.section("STARTING SERVER")

# Подсекции
log.subsection("Loading Configuration")

# Прогресс
for i in range(1, 101):
    log.progress(i, 100, f"Processing {i}/100")

# Таблицы
log.table(
    ["Name", "Status", "Count"],
    [
        ["Server", "Running", "1"],
        ["Agents", "Active", "5"],
        ["Tasks", "Pending", "10"]
    ]
)

# JSON
log.json_pretty(
    {"server": "running", "agents": 5},
    title="System Status"
)
```

---

## 🔍 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### Пример 1: API Endpoint

```python
from flask import Flask, request
from core.logger import get_logger, log_api_endpoint
import time

app = Flask(__name__)
log = get_logger("api")

@app.route('/api/task/create', methods=['POST'])
@log_api_endpoint()
def create_task():
    data = request.get_json()
    
    log.info(f"Creating task: {data.get('type')}")
    
    try:
        # Создание задачи
        task_id = create_task_in_db(data)
        
        log.log_task(
            task_id=task_id,
            task_type=data.get('type'),
            status="created"
        )
        
        return {"task_id": task_id}, 201
    except Exception as e:
        log.error(f"Failed to create task: {e}")
        return {"error": str(e)}, 500
```

### Пример 2: Обработка Задач

```python
from core.logger import get_logger, LogContext

log = get_logger("tasks")

def process_task(task_id, task_type, payload):
    with LogContext("tasks", f"process_{task_type}", task_id=task_id):
        log.info(f"Processing task {task_id}")
        
        try:
            # Выполнение
            result = execute_command(payload)
            
            log.log_task(
                task_id=task_id,
                task_type=task_type,
                status="completed",
                result=result[:100]
            )
            
            return result
        except Exception as e:
            log.log_task(
                task_id=task_id,
                task_type=task_type,
                status="failed",
                error=str(e)
            )
            raise
```

### Пример 3: Регистрация Агента

```python
from core.logger import get_logger

log = get_logger("agents")

def register_agent(agent_data):
    agent_id = agent_data.get('id')
    
    log.log_agent(
        agent_id=agent_id,
        action="register",
        hostname=agent_data.get('hostname'),
        os=agent_data.get('os'),
        ip=agent_data.get('ip_external')
    )
    
    # Сохранение в БД
    save_to_db(agent_data)
    
    log.success(f"Agent {agent_id[:8]} registered successfully")
```

### Пример 4: Безопасность

```python
from core.logger import get_logger

log = get_logger("security")

def check_login(username, password, ip):
    if failed_attempts[ip] > 5:
        log.log_security(
            event="brute_force_detected",
            severity="critical",
            details={
                "ip": ip,
                "username": username,
                "attempts": failed_attempts[ip]
            }
        )
        return False
    
    if not verify_password(username, password):
        failed_attempts[ip] += 1
        
        log.log_security(
            event="failed_login",
            severity="high",
            details={
                "ip": ip,
                "username": username,
                "attempts": failed_attempts[ip]
            }
        )
        return False
    
    log.log_security(
        event="successful_login",
        severity="info",
        details={"ip": ip, "username": username}
    )
    return True
```

---

## 📊 СТАТИСТИКА ЛОГОВ

```python
from core.logger import get_logger

log = get_logger("myapp")

# Получить статистику
stats = log.get_stats()
print(stats)
# {'debug': 100, 'info': 50, 'warning': 10, 'error': 2, 'critical': 0}

# Сбросить статистику
log.reset_stats()
```

---

## 🎨 ЦВЕТОВОЕ КОДИРОВАНИЕ

### Консоль
- 🔵 **DEBUG** - Cyan
- 🟢 **INFO** - Green
- 🟡 **WARNING** - Yellow
- 🔴 **ERROR** - Red
- ⚫ **CRITICAL** - Red background

### Специальные
- ✅ **SUCCESS** - Bright Green
- ❌ **FAIL** - Bright Red
- 📊 **SECTION** - Bold Cyan
- 📝 **SUBSECTION** - Bold Blue

---

## 📁 СТРУКТУРА ЛОГОВ

### Основной Лог (app.log)
```
2026-03-22 06:30:15 | api | INFO | create_task:45 | Creating task: shell
2026-03-22 06:30:15 | api | INFO | create_task:52 | Task created: task-123
2026-03-22 06:30:16 | agents | INFO | register_agent:78 | Agent registered: agent-456
```

### JSON Лог (app_json.log)
```json
{"timestamp": "2026-03-22T06:30:15", "logger": "api", "event_type": "api_call", "data": {"method": "POST", "endpoint": "/api/task/create", "status": 201, "duration_ms": 45.2}}
{"timestamp": "2026-03-22T06:30:16", "logger": "agents", "event_type": "agent", "data": {"agent_id": "agent-456", "action": "register", "hostname": "server1"}}
```

### Лог Ошибок (app_errors.log)
```
2026-03-22 06:30:20 | api | ERROR | create_task:58 | Failed to create task: Database connection error
Traceback (most recent call last):
  File "api.py", line 56, in create_task
    task_id = create_task_in_db(data)
...
```

---

## 🔧 НАСТРОЙКА

### Уровни Логирования

```python
from core.logger import EnhancedLogger
import logging

# Создать логгер с кастомными уровнями
log = EnhancedLogger(
    name="myapp",
    log_dir="logs",
    console_level=logging.INFO,    # Консоль: INFO и выше
    file_level=logging.DEBUG       # Файл: все уровни
)
```

### Отключение Цветов

```python
# Для production без цветов
import logging

log = logging.getLogger("myapp")
handler = logging.FileHandler("app.log")
handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
))
log.addHandler(handler)
```

---

## 📈 МОНИТОРИНГ

### Анализ JSON Логов

```bash
# Подсчёт событий
cat logs/api_json.log | jq -r '.event_type' | sort | uniq -c

# API вызовы с ошибками
cat logs/api_json.log | jq 'select(.data.status >= 400)'

# Медленные операции
cat logs/api_json.log | jq 'select(.data.duration_ms > 1000)'

# События безопасности
cat logs/security_json.log | jq 'select(.data.severity == "critical")'
```

### Статистика

```bash
# Количество ошибок
grep "ERROR" logs/api.log | wc -l

# Топ endpoints
cat logs/api_json.log | jq -r '.data.endpoint' | sort | uniq -c | sort -rn | head -10

# Средняя длительность
cat logs/api_json.log | jq '.data.duration_ms' | awk '{sum+=$1; count++} END {print sum/count}'
```

---

## ✅ CHECKLIST

- [x] Улучшенный логгер создан
- [x] Множественные файлы логов
- [x] JSON логирование
- [x] Декораторы добавлены
- [x] Context manager создан
- [x] Логирование добавлено в 8 файлов
- [x] Документация создана
- [x] Примеры использования

---

## 🚀 БЫСТРЫЙ СТАРТ

```python
# 1. Импорт
from core.logger import get_logger

# 2. Создание логгера
log = get_logger(__name__)

# 3. Использование
log.info("Server started")
log.success("Operation completed")
log.error("Something went wrong")

# 4. Структурированное логирование
log.log_api_call("POST", "/api/test", 200, 0.123)
log.log_task("task-1", "shell", "completed")
log.log_agent("agent-1", "register")
```

---

**Статус:** ✅ ГОТОВО К ИСПОЛЬЗОВАНИЮ  
**Версия:** 2.1 (Enhanced Logging)  
**Дата:** 2026-03-22
