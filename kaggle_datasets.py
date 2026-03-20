"""
Kaggle Dataset & Machine creation via CLI.
Creates 5 machines (kernels) per account WITHOUT dataset (to avoid Permission denied).
"""

import os
import json
import time
import subprocess
import tempfile
from pathlib import Path

def setup_kaggle_credentials(api_key: str, username: str):
    """Setup kaggle.json for CLI authentication."""
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    kaggle_json = kaggle_dir / "kaggle.json"
    
    kaggle_json.write_text(json.dumps({
        "username": username,
        "key": api_key
    }))
    
    os.chmod(kaggle_json, 0o600)
    return True


def delete_existing_kernels(api_key: str, username: str, log_fn=print):
    """Delete existing c2-agent kernels for this account."""
    try:
        setup_kaggle_credentials(api_key, username)
        
        result = subprocess.run(
            ["kaggle", "kernels", "list", "--mine", "--csv"],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                if 'c2-agent' in line:
                    parts = line.split(',')
                    if len(parts) >= 1:
                        kernel_ref = parts[0].strip()
                        if kernel_ref and '/' in kernel_ref:
                            log_fn(f"[DELETE] {kernel_ref}")
                            subprocess.run(
                                ["kaggle", "kernels", "delete", kernel_ref],
                                capture_output=True, text=True, timeout=30
                            )
                            time.sleep(0.3)
    except Exception as e:
        log_fn(f"[DELETE] Error: {e}")


def get_existing_kernels(api_key: str, username: str, log_fn=print):
    """Get list of existing c2-agent kernels for this account."""
    existing = set()
    try:
        setup_kaggle_credentials(api_key, username)
        
        result = subprocess.run(
            ["kaggle", "kernels", "list", "--mine", "--csv"],
            capture_output=True, text=True, timeout=30
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n')[1:]:
                if 'c2-agent' in line:
                    parts = line.split(',')
                    if len(parts) >= 1:
                        kernel_ref = parts[0].strip()
                        if kernel_ref and '/' in kernel_ref:
                            # Extract kernel number: c2-agent-1 -> 1
                            kernel_name = kernel_ref.split('/')[-1]
                            if kernel_name.startswith('c2-agent-'):
                                num = kernel_name.replace('c2-agent-', '')
                                if num.isdigit():
                                    existing.add(int(num))
    except Exception as e:
        log_fn(f"[CHECK] Error: {e}")
    
    return existing


def create_kernel(api_key: str, username: str, kernel_name: str, log_fn=print):
    """Create a kernel/notebook WITHOUT dataset dependency.
    
    Returns: dict with kernel_slug or error
    """
    try:
        setup_kaggle_credentials(api_key, username)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create kernel-metadata.json (NO dataset, GPU enabled)
            metadata = {
                "id": f"{username}/{kernel_name}",
                "title": f"C2 Agent {kernel_name.split('-')[-1]}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True
            }
            (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Create C2 agent notebook
            notebook = {
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "import json, subprocess, socket, platform, os, sys, time\n",
                            "AGENT_ID = socket.gethostname()[:10]\n",
                            "print(f'[AGENT-{AGENT_ID}] C2 Machine Ready', flush=True)\n",
                            "print(f'Platform: {platform.system()} {platform.release()}', flush=True)\n",
                            "print(f'Python: {sys.version.split()[0]}', flush=True)\n"
                        ]
                    }
                ],
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3"
                    },
                    "language_info": {"name": "python", "version": "3.10.0"}
                },
                "nbformat": 4,
                "nbformat_minor": 4
            }
            (tmpdir_path / "notebook.ipynb").write_text(json.dumps(notebook, indent=2))
            
            log_fn(f"[Kernel] Creating {username}/{kernel_name}...")
            
            result = subprocess.run(
                ["kaggle", "kernels", "push", "-p", tmpdir],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0 or "successfully" in result.stdout.lower():
                log_fn(f"[Kernel] ✓ Created: {username}/{kernel_name}")
                return {
                    "success": True,
                    "slug": f"{username}/{kernel_name}",
                    "url": f"https://www.kaggle.com/code/{username}/{kernel_name}"
                }
            else:
                log_fn(f"[Kernel] ✗ Error: {result.stderr[:100]}")
                return {"success": False, "error": result.stderr[:100]}
                
    except subprocess.TimeoutExpired:
        log_fn("[Kernel] ✗ Timeout")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        log_fn(f"[Kernel] ✗ Exception: {e}")
        return {"success": False, "error": str(e)}


def create_dataset_with_machines(api_key: str, username: str, num_machines=5, log_fn=print):
    """Create N machines (kernels) for an account WITHOUT dataset.
    
    Kernels are named: c2-agent-1, c2-agent-2, ..., c2-agent-N
    
    Handles existing kernels:
    - If all N kernels exist, skip and return success
    - If some exist, create only missing ones
    
    Returns: dict with machines info
    """
    result = {
        "dataset": None,
        "machines": [],
        "success": False,
        "skipped": False
    }
    
    # Check existing kernels first
    log_fn(f"[Setup] Checking existing kernels for {username}...")
    existing = get_existing_kernels(api_key, username, log_fn)
    
    if len(existing) >= num_machines:
        log_fn(f"[Setup] ✓ All {num_machines} kernels already exist, skipping")
        result["success"] = True
        result["skipped"] = True
        result["machines_created"] = num_machines
        result["dataset"] = {"slug": f"{username}/no-dataset-needed", "success": True}
        for i in range(1, num_machines + 1):
            result["machines"].append({
                "success": True,
                "slug": f"{username}/c2-agent-{i}",
                "existing": True
            })
        return result
    
    if existing:
        log_fn(f"[Setup] Found {len(existing)} existing kernels: {sorted(existing)}")
    
    # Determine which kernels to create
    to_create = [i for i in range(1, num_machines + 1) if i not in existing]
    log_fn(f"[Setup] Need to create {len(to_create)} kernels: {to_create}")
    
    # Create missing machines
    for i in to_create:
        kernel_name = f"c2-agent-{i}"
        kernel = create_kernel(api_key, username, kernel_name, log_fn)
        result["machines"].append(kernel)
        time.sleep(0.5)
    
    # Add existing kernels to result
    for i in existing:
        result["machines"].append({
            "success": True,
            "slug": f"{username}/c2-agent-{i}",
            "existing": True
        })
    
    # Check success
    successful_machines = sum(1 for m in result["machines"] if m.get("success"))
    result["success"] = successful_machines == num_machines
    result["machines_created"] = successful_machines
    
    if result["success"]:
        result["dataset"] = {"slug": f"{username}/no-dataset-needed", "success": True}
    
    return result


def check_kaggle_cli_installed():
    """Check if kaggle CLI is installed."""
    try:
        result = subprocess.run(
            ["kaggle", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False


if __name__ == "__main__":
    print("Testing Kaggle CLI...")
    if check_kaggle_cli_installed():
        print("✓ Kaggle CLI installed")
    else:
        print("✗ Kaggle CLI not installed. Run: pip install kaggle")
