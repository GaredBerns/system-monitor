# C2 Server - Чистая документация

## 📋 Структура проекта

### `/src/c2/` - Основной сервер
- `server.py` - Flask приложение с API endpoints
- `orchestrator.py` - Объединённые модули (Scanner, CounterSurveillance, Exploits)
- `models.py` - Модели данных (User, Agent, Task и т.д.)
- `config.py` - Конфигурация приложения

### `/src/agents/` - Агенты
- `browser/` - Браузер автоматизация (Firefox, Captcha solver)
- `kaggle/` - Kaggle агенты для деплоя
- `universal.py` - Универсальный агент для разных ОС

### `/src/autoreg/` - Автоматическая регистрация
Модули для авторегистрации аккаунтов на различных платформах

### `/src/mail/` - Email менеджер
- `tempmail.py` - Работа с временными email адресами

### `/src/mining/` - Майнинг
Модули для криптовалютного майнинга (XMRig и т.д.)

### `/src/utils/` - Утилиты
- `logger.py` - Логирование с разными уровнями и форматами
- `proxy.py` - Управление прокси
- `rate_limit.py` - Rate limiting
- `validation.py` - Валидация данных
- `common.py` - Общие утилиты

### `/src/core/` - Core конфигурация
- `validation.py` - Валидация для API
- `secrets.py` - Управление секретами
- `config.py` - Конфигурация

## 🚀 Запуск

### Основной сервер
```bash
python3 run_unified.py --host 0.0.0.0 --port 5000 --debug
```

### С параметрами
```bash
# Своё имя хоста и порт
python3 run_unified.py --host 192.168.1.100 --port 8443

# Production (без debug)
python3 run_unified.py --host 0.0.0.0 --port 5000
```

## 📊 API Endpoints

### Authentication
- `POST /api/auth/login` - Вход
- `POST /api/auth/logout` - Выход
- `GET /api/auth/session` - Проверка сессии

### Agents
- `GET /api/agents` - Список агентов
- `POST /api/agents/register` - Регистрация агента
- `GET /api/agents/<id>` - Информация об агенте
- `DELETE /api/agents/<id>` - Удаление агента

### Tasks
- `POST /api/tasks` - Создание задачи
- `GET /api/tasks/<id>` - Статус задачи
- `GET /api/tasks/agent/<agent_id>` - Задачи агента

## 🔧 Конфигурация

Основные переменные окружения в `src/core/config.py`:

```python
# Database
DATABASE_URL = "sqlite:///data/c2.db"

# Flask
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 8443
FLASK_DEBUG = False

# Security
SESSION_LIFETIME_HOURS = 12
AGENT_TIMEOUT_SECONDS = 30

# Rate limiting
RATE_LIMIT_ENABLED = True
RATE_LIMIT_DEFAULT = "60 per minute"
```

## 📝 Логирование

Логи находятся в `/logs/` директории. Каждый модуль имеет:
- `.log` - основной лог
- `_errors.log` - только ошибки
- `_json.log` - JSON формат для парсинга

Использование логгера:
```python
from src.utils.logger import get_logger

log = get_logger('my_module')
log.info("Info сообщение")
log.warning("Предупреждение")
log.error("Ошибка")
```

## 🛡️ Безопасность

- Все пароли хэшируются с bcrypt
- Коммуникация может быть зашифрована
- Rate limiting защищает от brute-force
- CSRF защита на всех формах
- SQL injection prevention через ORM

## 🐳 Docker (опционально)

```bash
docker-compose up -d
```

## ❓ Troubleshooting

### Проблема: "ModuleNotFoundError"
**Решение**: Убедитесь что вы находитесь в корне проекта и добавили его в PYTHONPATH
```bash
export PYTHONPATH="${PYTHONPATH}:/mnt/F/C2_server-main"
```

### Проблема: Порт уже занят
**Решение**: Используйте другой порт
```bash
python3 run_unified.py --port 8888
```

### Проблема: ошибка базы данных
**Решение**: Удалите старую БД и запустите заново
```bash
rm data/c2.db
python3 run_unified.py
```

## 📞 Support

Для отчётов об ошибках и предложений создавайте issues в репозитории.

