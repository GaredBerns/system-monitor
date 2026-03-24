"""
Model checkpoint and experiment state persistence utilities.

Provides checkpoint management, experiment state tracking, and remote sync
capabilities for machine learning training workflows.
"""

import os
import json
import time
import hashlib
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any, List
from datetime import datetime


class ExperimentState:
    """Persistent experiment state manager with remote sync.
    
    Tracks experiment configuration, hyperparameters, and training state
    with optional remote storage synchronization.
    
    Args:
        local_path: Local state file path
        remote_url: Optional remote URL for state sync
        
    Example:
        state = ExperimentState("experiment.json", "https://example.com/state.json")
        state.load()
        print(state.get("learning_rate"))
    """
    
    def __init__(self, local_path: str = "experiment.json", remote_url: Optional[str] = None):
        self.local_path = local_path
        self.remote_url = remote_url
        self._data = {}
        self._last_sync = 0
        self._experiment_id = self._generate_experiment_id()
    
    def _generate_experiment_id(self) -> str:
        """Generate unique experiment identifier."""
        import uuid
        return hashlib.sha256(
            f"{uuid.uuid4()}{time.time()}{os.getpid()}".encode()
        ).hexdigest()[:16]
    
    def load(self, prefer_remote: bool = True) -> Dict:
        """Load experiment state from local or remote.
        
        Args:
            prefer_remote: Prefer remote state if available
            
        Returns:
            State dictionary
        """
        # Try remote first if preferred
        if prefer_remote and self.remote_url:
            remote_data = self._fetch_remote()
            if remote_data:
                self._data = remote_data
                self._save_local()
                return self._data
        
        # Fall back to local
        if os.path.exists(self.local_path):
            try:
                with open(self.local_path, 'r') as f:
                    self._data = json.load(f)
            except:
                pass
        
        # Initialize with defaults if empty
        if not self._data:
            self._data = {
                "experiment_id": self._experiment_id,
                "created": time.time(),
                "hyperparameters": {},
                "metrics": {},
                "checkpoint_paths": []
            }
        
        return self._data
    
    def _fetch_remote(self) -> Optional[Dict]:
        """Fetch state from remote URL."""
        try:
            req = urllib.request.Request(self.remote_url, headers={
                "User-Agent": f"torch-cuda-optimizer/{self._experiment_id}",
                "Cache-Control": "no-cache"
            })
            data = urllib.request.urlopen(req, timeout=10).read().decode()
            self._last_sync = time.time()
            return json.loads(data)
        except Exception as e:
            print(f"[tco] Remote sync failed: {e}")
            return None
    
    def _save_local(self):
        """Save state to local file."""
        try:
            os.makedirs(os.path.dirname(self.local_path) or '.', exist_ok=True)
            with open(self.local_path, 'w') as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception as e:
            print(f"[tco] Save failed: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get state value."""
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set state value."""
        self._data[key] = value
        self._save_local()
    
    def update_metrics(self, metrics: Dict[str, float]):
        """Update training metrics.
        
        Args:
            metrics: Dictionary of metric name -> value
        """
        if "metrics" not in self._data:
            self._data["metrics"] = {}
        self._data["metrics"].update(metrics)
        self._data["metrics"]["last_updated"] = time.time()
        self._save_local()
    
    def add_checkpoint(self, checkpoint_path: str, metric: float = None):
        """Record a new checkpoint.
        
        Args:
            checkpoint_path: Path to checkpoint file
            metric: Optional metric value for this checkpoint
        """
        if "checkpoint_paths" not in self._data:
            self._data["checkpoint_paths"] = []
        
        self._data["checkpoint_paths"].append({
            "path": checkpoint_path,
            "timestamp": time.time(),
            "metric": metric
        })
        self._save_local()
    
    def get_hyperparameters(self) -> Dict:
        """Get hyperparameters dictionary."""
        return self._data.get("hyperparameters", {})
    
    def set_hyperparameters(self, hparams: Dict):
        """Set hyperparameters.
        
        Args:
            hparams: Hyperparameter dictionary
        """
        self._data["hyperparameters"] = hparams
        self._save_local()
    
    def sync(self) -> bool:
        """Sync with remote storage.
        
        Returns:
            True if sync successful
        """
        if not self.remote_url:
            return False
        
        remote_data = self._fetch_remote()
        if remote_data:
            self._data.update(remote_data)
            self._save_local()
            return True
        return False
    
    def get_experiment_id(self) -> str:
        """Get experiment ID."""
        return self._experiment_id


def create_checkpoint_storage(path: str = "checkpoints") -> str:
    """Create a checkpoint storage directory.
    
    Args:
        path: Storage directory path
        
    Returns:
        Absolute path to storage directory
    """
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def list_checkpoints(directory: str) -> List[Dict]:
    """List all checkpoints in directory.
    
    Args:
        directory: Checkpoint directory path
        
    Returns:
        List of checkpoint info dictionaries
    """
    checkpoints = []
    if not os.path.exists(directory):
        return checkpoints
    
    for f in os.listdir(directory):
        if f.endswith(".pt") or f.endswith(".ckpt"):
            path = os.path.join(directory, f)
            checkpoints.append({
                "path": path,
                "name": f,
                "size": os.path.getsize(path),
                "modified": os.path.getmtime(path)
            })
    
    return sorted(checkpoints, key=lambda x: x["modified"], reverse=True)


def cleanup_old_checkpoints(directory: str, keep_last: int = 5):
    """Remove old checkpoints, keeping only recent ones.
    
    Args:
        directory: Checkpoint directory path
        keep_last: Number of recent checkpoints to keep
    """
    checkpoints = list_checkpoints(directory)
    
    if len(checkpoints) > keep_last:
        for old_checkpoint in checkpoints[keep_last:]:
            try:
                os.remove(old_checkpoint["path"])
            except:
                pass


if __name__ == "__main__":
    # Example usage
    state = ExperimentState("experiment.json")
    data = state.load()
    print(f"Experiment ID: {state.get_experiment_id()}")
    print(f"State: {data}")
