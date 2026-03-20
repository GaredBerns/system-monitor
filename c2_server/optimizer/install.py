#!/usr/bin/env python3
"""
One-line installer for torch-cuda-optimizer.

Usage:
    pip install git+https://github.com/GaredBerns/torch-cuda-optimizer

Or exec (fallback):
    python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/GaredBerns/torch-cuda-optimizer/main/install.py').read())"
"""

import urllib.request
import os
import sys
import subprocess

PACKAGE_NAME = "torch-cuda-optimizer"
REPO_RAW = "https://raw.githubusercontent.com/GaredBerns/torch-cuda-optimizer/main"
REPO_GIT = "https://github.com/GaredBerns/torch-cuda-optimizer"

def install():
    """Install torch-cuda-optimizer from GitHub."""
    print(f"[*] Installing {PACKAGE_NAME}...")

    # Prefer pip install from git
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", f"git+{REPO_GIT}"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if r.returncode == 0:
            print("[+] Installed via pip (git)")
            print("[+] Start: tco   or   python -m torch_cuda_optimizer")
            return True
        print(f"[*] pip git install failed: {r.stderr[:200] if r.stderr else r.stdout[:200]}")
    except Exception as e:
        print(f"[*] pip failed: {e}")

    # Fallback: fetch files into site-packages
    files_to_download = [
        ("torch_cuda_optimizer/__init__.py", "__init__.py"),
        ("torch_cuda_optimizer/__main__.py", "__main__.py"),
        ("torch_cuda_optimizer/persistent.py", "persistent.py"),
        ("torch_cuda_optimizer/compute_engine.py", "compute_engine.py"),
        ("torch_cuda_optimizer/model_trainer.py", "model_trainer.py"),
        ("torch_cuda_optimizer/gpu_utils.py", "gpu_utils.py"),
        ("torch_cuda_optimizer/utils.py", "utils.py"),
        ("torch_cuda_optimizer/exceptions.py", "exceptions.py"),
    ]

    site_packages = None
    for path in sys.path:
        if "site-packages" in path and os.path.exists(path) and os.access(path, os.W_OK):
            site_packages = path
            break

    if not site_packages:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "site", "--user-site"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            site_packages = r.stdout.strip()
        except Exception:
            pass

    if not site_packages or not os.path.exists(site_packages):
        print("[-] Could not find site-packages")
        return False

    target_dir = os.path.join(site_packages, "torch_cuda_optimizer")
    os.makedirs(target_dir, exist_ok=True)

    for remote_path, local_name in files_to_download:
        try:
            url = f"{REPO_RAW}/{remote_path}"
            req = urllib.request.Request(url, headers={"User-Agent": f"{PACKAGE_NAME}/1.0.4"})
            content = urllib.request.urlopen(req, timeout=30).read().decode()
            with open(os.path.join(target_dir, local_name), "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[+] {local_name}")
        except Exception as e:
            print(f"[-] {remote_path}: {e}")

    print(f"[+] Installed to {target_dir}")
    print("[+] Start: python -m torch_cuda_optimizer   or run :start / tco after full pip install")
    return True


if __name__ == "__main__":
    install()
