#!/bin/bash
# 🔄 Миграция архитектуры - перемещение файлов в новую структуру

set -e

echo "🔄 Начало миграции архитектуры..."
echo ""

# Проверка, что мы в правильной директории
if [ ! -f "setup.py" ]; then
    echo "❌ Ошибка: Запустите скрипт из корня проекта"
    exit 1
fi

# Функция для безопасного перемещения
move_file() {
    local src=$1
    local dst=$2

    if [ -f "$src" ]; then
        echo "  📄 $src → $dst"
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
    else
        echo "  ⊘ Пропущено: $src (не найден)"
    fi
}

# Функция для перемещения папки
move_dir() {
    local src=$1
    local dst=$2

    if [ -d "$src" ]; then
        echo "  📁 $src → $dst"
        mkdir -p "$dst"
        cp -r "$src"/* "$dst/" 2>/dev/null || true
    else
        echo "  ⊘ Пропущено: $src (не найдена)"
    fi
}

# ============================================================================
# ФАЗА 1: Перемещение утилит
# ============================================================================
echo "📝 Фаза 1: Перемещение утилит..."

mkdir -p src/utils
move_file "core/logger.py" "src/utils/logger.py"
move_file "core/proxy.py" "src/utils/proxy.py"
move_file "core/rate_limit.py" "src/utils/rate_limit.py"
move_file "core/validation.py" "src/utils/validation.py"
move_file "core/cache.py" "src/utils/cache.py"
move_file "utils.py" "src/utils/common.py"

# ============================================================================
# ФАЗА 2: Перемещение основного сервера
# ============================================================================
echo ""
echo "🎯 Фаза 2: Перемещение основного сервера..."

mkdir -p src/c2
move_file "core/server.py" "src/c2/server.py"
move_file "core/models.py" "src/c2/models.py"
move_file "core/unified.py" "src/c2/orchestrator.py"
move_file "core/task_queue.py" "src/c2/task_queue.py"
move_file "core/autonomous_miner.py" "src/c2/autonomous_miner.py"
move_file "core/master_orchestrator.py" "src/c2/master_orchestrator.py"

# ============================================================================
# ФАЗА 3: Перемещение агентов
# ============================================================================
echo ""
echo "🤖 Фаза 3: Перемещение агентов..."

mkdir -p src/agents/{browser,kaggle}
move_file "agents/agent_universal.py" "src/agents/universal.py"
move_file "agents/agent_windows.ps1" "src/agents/windows.ps1"
move_file "agents/kaggle_agent.py" "src/agents/kaggle/agent.py"

# Browser
move_file "browser/firefox.py" "src/agents/browser/firefox.py"
move_file "browser/captcha.py" "src/agents/browser/captcha.py"
move_file "browser/page_utils.py" "src/agents/browser/utils.py"

# Kaggle
move_file "kaggle/deploy_unified.py" "src/agents/kaggle/deploy.py"
move_file "kaggle/auto_manager.py" "src/agents/kaggle/manager.py"
move_file "kaggle/datasets.py" "src/agents/kaggle/datasets.py"
move_file "kaggle/transport.py" "src/agents/kaggle/transport.py"

# ============================================================================
# ФАЗА 4: Перемещение других модулей
# ============================================================================
echo ""
echo "📦 Фаза 4: Перемещение других модулей..."

# Авторегистрация
mkdir -p src/autoreg
move_dir "autoreg" "src/autoreg"

# Майнинг (если есть)
mkdir -p src/mining
if [ -d "optimizer" ]; then
    move_dir "optimizer" "src/mining"
fi

# Email
mkdir -p src/mail
move_dir "mail" "src/mail"

# Ядро системы
mkdir -p src/core
move_file "core/config.py" "src/core/config.py"
move_file "core/secrets.py" "src/core/secrets.py"
move_file "core/validation.py" "src/core/validation.py"

# ============================================================================
# ФАЗА 5: Перемещение конфигурации
# ============================================================================
echo ""
echo "⚙️  Фаза 5: Перемещение конфигурации..."

# settings.py и секреты уже созданы выше
# Просто подтверждение
if [ -f "config/settings.py" ]; then
    echo "  ✅ config/settings.py уже существует"
fi

# ============================================================================
# ФАЗА 6: Резервная копия старых файлов
# ============================================================================
echo ""
echo "💾 Фаза 6: Создание резервных копий..."

# Архивируем старые папки
if [ -d "core" ] && [ ! -d "core.backup" ]; then
    cp -r core core.backup
    echo "  💾 core → core.backup"
fi

if [ -d "agents" ] && [ ! -d "agents.backup" ]; then
    cp -r agents agents.backup
    echo "  💾 agents → agents.backup"
fi

if [ -d "browser" ] && [ ! -d "browser.backup" ]; then
    cp -r browser browser.backup
    echo "  💾 browser → browser.backup"
fi

if [ -d "kaggle" ] && [ ! -d "kaggle.backup" ]; then
    cp -r kaggle kaggle.backup
    echo "  💾 kaggle → kaggle.backup"
fi

# ============================================================================
# ФАЗА 7: Проверка результатов
# ============================================================================
echo ""
echo "✅ Фаза 7: Проверка результатов..."

declare -a files=(
    "src/c2/server.py"
    "src/c2/models.py"
    "src/agents/universal.py"
    "src/agents/browser/firefox.py"
    "src/agents/kaggle/deploy.py"
    "src/autoreg/engine.py"
    "src/utils/logger.py"
    "config/settings.py"
)

failed=0
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (ОТСУТСТВУЕТ)"
        ((failed++))
    fi
done

echo ""
if [ $failed -eq 0 ]; then
    echo "🎉 Миграция завершена успешно!"
    echo ""
    echo "📝 Следующие шаги:"
    echo "  1. Обновите импорты в коде (см. MIGRATION.md)"
    echo "  2. Запустите: python3 -m py_compile src/**/*.py"
    echo "  3. Запустите тесты: pytest tests/"
    echo "  4. При успехе удалите backup папки: rm -rf *.backup"
else
    echo "⚠️  Миграция завершена с $failed ошибками"
    echo "📝 Проверьте файлы, которые отмечены как ОТСУТСТВУЮТ"
    exit 1
fi

