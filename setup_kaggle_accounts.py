#!/usr/bin/env python3
"""
Массовая настройка Kaggle аккаунтов для C2.
- Удаляет все kernels и datasets
- Создаёт 1 dataset с commands.json
- Создаёт 5 kernels подключённых к dataset
"""

import json
import subprocess
import time
import tempfile
from pathlib import Path

ACCOUNTS_FILE = "/mnt/F/C2_server/data/accounts.json"
KERNELS_PER_ACCOUNT = 5

def run_cmd(cmd, timeout=60):
    """Run shell command."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr
    except:
        return 1, "", "timeout"

def setup_account(username, api_key, index):
    """Setup single account."""
    print(f"\n[ACCOUNT {index}] {username}")
    
    # Set credentials
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    (kaggle_dir / "kaggle.json").write_text(json.dumps({"username": username, "key": api_key}))
    (kaggle_dir / "kaggle.json").chmod(0o600)
    
    # Delete existing kernels
    ret, out, err = run_cmd("kaggle kernels list --mine --csv 2>/dev/null | grep -v 'Private Notebook' | head -20")
    if out:
        for line in out.strip().split('\n')[1:]:
            parts = line.split(',')
            if len(parts) > 0 and parts[0]:
                kernel_ref = parts[0].strip().strip('"')
                if kernel_ref and '/' in kernel_ref:
                    print(f"  [DELETE KERNEL] {kernel_ref}")
                    run_cmd(f"kaggle kernels delete {kernel_ref} -y 2>/dev/null", timeout=30)
    
    # Delete existing datasets
    ret, out, err = run_cmd("kaggle datasets list --mine --csv 2>/dev/null | head -10")
    if out:
        for line in out.strip().split('\n')[1:]:
            parts = line.split(',')
            if len(parts) > 0 and parts[0]:
                ds_ref = parts[0].strip().strip('"')
                if ds_ref and '/' in ds_ref:
                    print(f"  [DELETE DATASET] {ds_ref}")
                    run_cmd(f"kaggle datasets delete {ds_ref} -y 2>/dev/null", timeout=30)
    
    time.sleep(2)
    
    # Create dataset
    ds_name = f"c2-commands-{username}"
    ds_slug = f"{username}/{ds_name}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Dataset metadata
        metadata = {
            "title": ds_name,
            "id": ds_slug,
            "licenses": [{"name": "CC0-1.0"}]
        }
        (tmpdir_path / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2))
        
        # Initial commands
        commands = {
            "version": int(time.time()),
            "commands": [{"id": "init", "type": "info", "payload": ""}]
        }
        (tmpdir_path / "commands.json").write_text(json.dumps(commands, indent=2))
        
        print(f"  [CREATE DATASET] {ds_slug}")
        ret, out, err = run_cmd(f"cd {tmpdir} && kaggle datasets create -p . --public 2>&1", timeout=120)
        
        if ret != 0 and "already exists" not in err and "403" not in err and "Permission" not in err:
            print(f"  [DATASET ERROR] {err[:100]}")
            # Try to use existing dataset
            ret, out, err = run_cmd(f"kaggle datasets version -p {tmpdir} -m v{int(time.time())} 2>&1", timeout=120)
            if ret != 0:
                print(f"  [DATASET VERSION ERROR] {err[:100]}")
                return None
    
    time.sleep(2)
    
    # Create 5 kernels
    kernel_slugs = []
    for i in range(1, KERNELS_PER_ACCOUNT + 1):
        kernel_name = f"c2-agent-{i}"
        kernel_slug = f"{username}/{kernel_name}"
        kernel_slugs.append(kernel_slug)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Kernel metadata
            metadata = {
                "id": kernel_slug,
                "title": f"C2 Agent {i}",
                "code_file": "notebook.ipynb",
                "language": "python",
                "kernel_type": "notebook",
                "is_private": "true",
                "enable_gpu": "false",
                "enable_internet": "false",
                "dataset_sources": [ds_slug]
            }
            (tmpdir_path / "kernel-metadata.json").write_text(json.dumps(metadata, indent=2))
            
            # Agent notebook
            notebook = {
                "cells": [{
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": [
                        "import json, subprocess, socket, platform\n",
                        "from pathlib import Path\n",
                        "\n",
                        "AGENT = socket.gethostname()[:10]\n",
                        "print(f'[AGENT-{AGENT}] Ready', flush=True)\n",
                        "\n",
                        "cf = next(Path('/kaggle/input').rglob('commands.json'), None)\n",
                        "if not cf: raise SystemExit(1)\n",
                        "\n",
                        "cmds = json.loads(cf.read_text()).get('commands', [])\n",
                        "results = []\n",
                        "for c in cmds:\n",
                        "    r = {'id': c.get('id'), 'status': 'error', 'output': ''}\n",
                        "    try:\n",
                        "        if c.get('type') == 'shell':\n",
                        "            out = subprocess.check_output(c.get('payload',''), shell=True, stderr=subprocess.STDOUT, timeout=60)\n",
                        "            r['status'], r['output'] = 'ok', out.decode(errors='replace')[:5000]\n",
                        "        elif c.get('type') == 'info':\n",
                        "            r['status'], r['output'] = 'ok', json.dumps({'host': socket.gethostname(), 'os': platform.system()})\n",
                        "    except Exception as e: r['output'] = str(e)\n",
                        "    results.append(r)\n",
                        "\n",
                        "Path('/kaggle/working/results.json').write_text(json.dumps({'agent': AGENT, 'results': results}))\n",
                        "print('[DONE]', flush=True)\n"
                    ]
                }],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 4
            }
            (tmpdir_path / "notebook.ipynb").write_text(json.dumps(notebook))
            
            print(f"  [CREATE KERNEL {i}] {kernel_slug}")
            ret, out, err = run_cmd(f"cd {tmpdir} && kaggle kernels push -p . 2>&1", timeout=120)
            if ret != 0:
                print(f"    [ERROR] {err[:80]}")
        
        time.sleep(1)
    
    return {"dataset_slug": ds_slug, "kernels": kernel_slugs}

def main():
    # Load accounts
    accounts = json.loads(Path(ACCOUNTS_FILE).read_text())
    print(f"[TOTAL] {len(accounts)} accounts")
    
    results = {}
    
    # Process ALL accounts
    for i, acc in enumerate(accounts):  # ALL accounts
        # Use kaggle_username (real Kaggle username) if available, else username
        username = acc.get("kaggle_username") or acc.get("username")
        api_key = acc.get("api_key")
        
        if not username or not api_key:
            continue
        
        result = setup_account(username, api_key, i+1)
        if result:
            results[username] = result
        
        time.sleep(3)  # Rate limiting
    
    # Save results
    output = {"accounts": {}}
    for username, data in results.items():
        output["accounts"][username] = {
            "dataset_slug": data["dataset_slug"],
            "kernels": data["kernels"]
        }
    
    Path("/mnt/F/C2_server/data/kaggle_setup.json").write_text(json.dumps(output, indent=2))
    print(f"\n[DONE] Setup {len(results)} accounts")
    print(f"[OUTPUT] /mnt/F/C2_server/data/kaggle_setup.json")

if __name__ == "__main__":
    main()
