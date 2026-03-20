# Kaggle → C2: почему машины не появляются в Devices

## Возможные причины

### 1. Kaggle блокирует trycloudflare.com
Cloudflare quick tunnel может быть недоступен из сети Kaggle.

**Решение:** используй прямой URL (DDNS/VPN):
1. Запусти C2: `./start.sh` (порт 18443, без SSL)
2. В Settings → **Kaggle C2 URL** укажи: `http://kaggle2.ddns.net:18443`
3. Убедись, что VPN и port forwarding работают
4. Запусти: `python3 run_batch_join.py --quick`

### 2. Аккаунт Kaggle не подтверждён по телефону
Для доступа в интернет из kernel нужна мобильная верификация.

**Проверка:** зайди на kaggle.com → Account → Phone verification.

### 3. Internet выключен в kernel
В настройках kernel должен быть включён Internet (Settings → Internet: ON).

Мы ставим `enable_internet: True` в metadata при push — это должно работать.

---

## Тест доступа из Kaggle

Создай новый notebook на Kaggle и выполни в ячейке:

```python
import requests
print(requests.get("https://httpbin.org/ip", timeout=10).json())
```

Если ошибка — интернет в kernel недоступен (верификация или настройки).

---

## Текущий URL для агентов

- **Public URL:** `public_url` из Settings (Cloudflare tunnel)
- **Kaggle override:** `public_url_kaggle` — если задан, используется для deploy вместо Public URL
