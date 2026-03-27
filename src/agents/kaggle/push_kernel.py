#!/usr/bin/env python3
"""Push kernel to Kaggle - Reads credentials from config.json."""
import sys, json, time, random, os, pathlib
sys.path.insert(0, '/mnt/F/C2_server-main')
from src.agents.kaggle.datasets import push_kernel_json

# ═══════════════════════════════════════════════════════════════════════════
# AUTO-CONFIG: Load from config.json
# ═══════════════════════════════════════════════════════════════════════════

# Default credentials (override in config.json)
USERNAME = 'YOUR_KAGGLE_USERNAME'
API_KEY = 'YOUR_KAGGLE_API_KEY'

# Load from config.json if exists
config_path = pathlib.Path(__file__).parent.parent.parent.parent / "config.json"
if config_path.exists():
    try:
        with open(config_path) as f:
            cfg = json.load(f)
            if cfg.get("kaggle_username"):
                USERNAME = cfg["kaggle_username"]
            if cfg.get("kaggle_api_key"):
                API_KEY = cfg["kaggle_api_key"]
            print(f"[CONFIG] Loaded credentials for: {USERNAME}")
    except Exception as e:
        print(f"[CONFIG] Error loading config: {e}")

# Check if credentials are set
if USERNAME == 'YOUR_KAGGLE_USERNAME' or API_KEY == 'YOUR_KAGGLE_API_KEY':
    print("="*60)
    print("ERROR: Credentials not configured!")
    print("="*60)
    print("1. Edit config.json and set:")
    print("   - kaggle_username: 'your_username'")
    print("   - kaggle_api_key: 'your_api_key'")
    print("")
    print("2. Or use C2 UI: /api/config/kaggle")
    print("="*60)
    sys.exit(1)

# Unique slug with random suffix to avoid 409 conflict
slug = f'{USERNAME}/perf-analyzer-{int(time.time())}-{random.randint(1000,9999)}'

# Load notebook from same directory (stealth version)
notebook_path = os.path.join(os.path.dirname(__file__), "notebook-stealth.ipynb")
with open(notebook_path, "r") as f:
    notebook = json.load(f)

result = push_kernel_json(
    username=USERNAME,
    api_key=API_KEY,
    notebook_content=json.dumps(notebook),
    kernel_slug=slug,
    title='Performance Analyzer',
    enable_internet=True,
    dataset_sources=[f'{USERNAME}/perf-analyzer'],
    log_fn=print
)

print('='*60)
print('RESULT')
print('='*60)
print(f'Success: {result.get("success")}')
print(f'Kernel: {slug}')
print(f'URL: {result.get("url", "N/A")}')
print(f'Error: {result.get("error", "None")}')
print('='*60)
