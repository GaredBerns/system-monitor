#!/usr/bin/env python3
"""
Kaggle C2 Communication Example

This example demonstrates how to use Kaggle kernels as C2 workers
that communicate via file-based beaconing.

Usage:
    python3 kaggle_c2_example.py
"""

import sys
import os
import time
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agents.kaggle import (
    create_dataset_with_machines,
    get_kernel_output,
    get_kernel_status,
    push_kernel_json,
)


# Kaggle credentials
KAGGLE_USERNAME = "josebarnett970364"
KAGGLE_API_KEY = "704aa6bdd9e1f227ed6e4abe79a39c4b"


def create_c2_worker():
    """Create a C2 worker kernel on Kaggle."""
    
    # Worker notebook code
    notebook = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "cells": [{
            "cell_type": "code",
            "execution_count": None,
            "metadata": {"id": "cell1"},
            "outputs": [],
            "source": [
                'print("C2 Worker started")\n',
                'import os, json, time, socket, platform, uuid\n',
                '\n',
                'AGENT_ID = str(uuid.uuid4())[:8]\n',
                'os.makedirs("/kaggle/working", exist_ok=True)\n',
                '\n',
                '# Register\n',
                'status = {\n',
                '    "agent_id": AGENT_ID,\n',
                '    "hostname": socket.gethostname(),\n',
                '    "platform": platform.system(),\n',
                '    "cpu_count": os.cpu_count(),\n',
                '    "timestamp": time.time(),\n',
                '    "status": "registered"\n',
                '}\n',
                'with open("/kaggle/working/status.json", "w") as f:\n',
                '    json.dump(status, f)\n',
                'print(f"Registered: {AGENT_ID}")\n',
                '\n',
                '# Heartbeat loop (100 iterations x 10 sec = ~17 min)\n',
                'for i in range(100):\n',
                '    time.sleep(10)\n',
                '    status["iteration"] = i\n',
                '    status["timestamp"] = time.time()\n',
                '    status["status"] = "active"\n',
                '    with open("/kaggle/working/status.json", "w") as f:\n',
                '        json.dump(status, f)\n',
                '    print(f"Heartbeat {i}")\n',
                'print("Done")\n'
            ]
        }]
    }
    
    # Push kernel with auto-run
    result = push_kernel_json(
        username=KAGGLE_USERNAME,
        api_key=KAGGLE_API_KEY,
        notebook_content=json.dumps(notebook),
        kernel_slug=f"{KAGGLE_USERNAME}/c2-worker-{int(time.time())}",
        title=f"C2 Worker {int(time.time())}",
        enable_internet=True,
        is_private=True,
        log_fn=print,
    )
    
    return result


def check_worker_status(kernel_slug):
    """Check worker status and get output."""
    
    # Get kernel status
    status = get_kernel_status(
        username=KAGGLE_USERNAME,
        api_key=KAGGLE_API_KEY,
        kernel_slug=kernel_slug,
    )
    print(f"Kernel status: {status}")
    
    # Get kernel output
    output = get_kernel_output(
        username=KAGGLE_USERNAME,
        api_key=KAGGLE_API_KEY,
        kernel_slug=kernel_slug,
        log_fn=print,
    )
    
    if output["success"] and output["status"]:
        print(f"\nWorker beacon data:")
        print(json.dumps(output["status"], indent=2))
    
    return output


def main():
    """Main example."""
    
    print("=" * 60)
    print("Kaggle C2 Communication Example")
    print("=" * 60)
    
    # Option 1: Create new worker
    # result = create_c2_worker()
    # kernel_slug = result.get("url", "").split("/")[-1]
    
    # Option 2: Check existing worker
    kernel_slug = "josebarnett970364/c2-worker-1"
    
    print(f"\nChecking worker: {kernel_slug}")
    output = check_worker_status(kernel_slug)
    
    if output["success"]:
        print("\n✓ C2 communication working!")
        print(f"  Files: {output['files']}")
        if output["status"]:
            print(f"  Agent ID: {output['status'].get('agent_id')}")
            print(f"  Hostname: {output['status'].get('hostname')}")
            print(f"  Platform: {output['status'].get('platform')}")
            print(f"  Status: {output['status'].get('status')}")
            print(f"  Iteration: {output['status'].get('iteration')}")
    else:
        print(f"\n✗ Failed: {output.get('error')}")


if __name__ == "__main__":
    main()
