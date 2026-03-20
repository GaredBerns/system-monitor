# C2 Panel — постоянный домен (локально + сеть)

## Локальный домен c2panel.rog (твоя машина + LAN)

На этой машине один раз выполни (нужен sudo):
  cd /mnt/F/tools/C2_server
  sudo ./setup_domain.sh

Скрипт:
  - добавляет в /etc/hosts запись 127.0.0.1 c2panel.rog
  - генерирует SSL-сертификат для c2panel.rog
  - выведет IP в LAN и инструкцию для других устройств

После этого:
  - на этой машине: https://c2panel.rog:8443
  - на других ПК в той же сети: добавить в их hosts строку <IP_этой_машины> c2panel.rog, затем открывать https://c2panel.rog:8443

Перезапусти сервер после первого запуска setup: sudo systemctl restart c2server

## Локальный доступ без домена
Всегда: https://<IP-машины>:8443  или  https://localhost:8443

## Публичный доступ (интернет)

### Вариант 1: Быстрый туннель (без аккаунта)
При старте сервера автоматически поднимается cloudflared quick tunnel.
URL вида https://xxx.trycloudflare.com сохраняется в настройках и подставляется в payloads.
После перезапуска сервера URL может измениться — зайди в Payloads и обнови поле «Public URL» или в Settings → Domain & Tunnel посмотри актуальный.

### Вариант 2: Свой постоянный домен (Cloudflare Named Tunnel)
1. Зарегистрируйся на https://dash.cloudflare.com
2. Zero Trust → Networks → Tunnels → Create tunnel → Cloudflared → Укажи имя (например c2)
3. В настройках туннеля добавь Public Hostname: твой домен или поддомен (например c2.mydomain.com), Service: http://localhost:8443
4. Скопируй команду «Run the tunnel» или токен (cloudflared tunnel run --token ...)
5. В панели C2: Settings → Domain & Tunnel:
   - Public URL: https://c2.mydomain.com (тот же hostname, что в Cloudflare)
   - Cloudflare Tunnel Token: вставь токен из шага 4
6. Сохрани и перезапусти сервер: sudo systemctl restart c2server

Дальше панель всегда доступна по https://c2.mydomain.com и по локальному https://<IP>:8443.
