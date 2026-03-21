#!/usr/bin/env python3
"""Auto-run Kaggle kernels via API."""
import json, subprocess, time, os
from pathlib import Path

USERNAME = "stephenhowell94611"
API_KEY = "9a5d3c51ece5433f3072809bc4765604"
KBIN = ["/usr/local/bin/python3.12", "/home/kali/.local/bin/kaggle"]

def _env():
    e = os.environ.copy()
    e.pop("PYTHONPATH", None)
    return e

def _creds():
    kd = Path.home() / ".kaggle"
    kd.mkdir(parents=True, exist_ok=True)
    c = kd / "kaggle.json"
    c.write_text(json.dumps({"username": USERNAME, "key": API_KEY}))
    c.chmod(0o600)

def _run_kernel(slug):
    """Push kernel to trigger execution."""
    try:
        # Get kernel metadata
        r = subprocess.run(KBIN + ["kernels", "status", slug], 
                          capture_output=True, text=True, timeout=30, env=_env())
        if r.returncode != 0:
            return False, "status_fail"
        
        # Push to trigger run (Kaggle auto-runs on push)
        r = subprocess.run(KBIN + ["kernels", "push", "-p", "/tmp", slug],
                          capture_output=True, text=True, timeout=60, env=_env())
        return r.returncode == 0, r.stdout + r.stderr
    except Exception as e:
        return False, str(e)

_creds()

kernels = [
    f"{USERNAME}/c2-agent-1",
    f"{USERNAME}/c2-agent-2",
    f"{USERNAME}/c2-agent-3",
    f"{USERNAME}/c2-agent-4",
    f"{USERNAME}/c2-agent-5"
]

print("Auto-running kernels...\n")
for k in kernels:
    print(f"[RUN] {k}...", end=" ", flush=True)
    ok, msg = _run_kernel(k)
    print("OK" if ok else f"SKIP ({msg[:50]})")
    time.sleep(2)

print("\nKernels triggered. Check: https://www.kaggle.com/code")
