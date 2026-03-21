import socket
import sys

# Тест подключения к пулу
pools = [
    ("gulf.moneroocean.stream", 10128),
    ("gulf.moneroocean.stream", 20128),
    ("gulf.moneroocean.stream", 443),
    ("pool.supportxmr.com", 3333),
    ("pool.supportxmr.com", 5555),
    ("xmr.pool.minergate.com", 45700),
]

print("=== ТЕСТ ПОДКЛЮЧЕНИЯ К ПУЛАМ ===\n")

for host, port in pools:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✓ {host}:{port} - ДОСТУПЕН")
        else:
            print(f"✗ {host}:{port} - НЕДОСТУПЕН (код {result})")
    except Exception as e:
        print(f"✗ {host}:{port} - ОШИБКА: {e}")

print("\n=== ВЫВОД ===")
print("Если все пулы недоступны с этой машины,")
print("но Kaggle может иметь другие правила firewall.")
print("\nНужно проверить логи kernel в браузере!")
