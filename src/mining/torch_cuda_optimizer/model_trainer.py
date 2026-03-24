"""
Model training utilities for machine learning pipelines.

Provides training loop management, checkpoint handling, and metrics tracking
for deep learning model development.
"""

import os
import json
import time
import hashlib
import threading
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime


class TrainingMonitor:
    """Real-time training progress monitoring and logging.
    
    Tracks training metrics, losses, and progress for ML experiments.
    
    Args:
        log_dir: Directory for training logs
        experiment_name: Optional experiment identifier
        
    Example:
        monitor = TrainingMonitor("logs/", "experiment_001")
        monitor.log_metrics({"loss": 0.05, "accuracy": 0.95})
    """
    
    def __init__(self, log_dir: str = "logs", experiment_name: str = None):
        self.log_dir = log_dir
        self.experiment_name = experiment_name or f"exp_{int(time.time())}"
        self._metrics_history = []
        self._start_time = time.time()
        self._current_epoch = 0
        os.makedirs(log_dir, exist_ok=True)
    
    def log_metrics(self, metrics: Dict[str, float], step: int = None):
        """Log training metrics.
        
        Args:
            metrics: Dictionary of metric name -> value
            step: Optional step/iteration number
        """
        entry = {
            "timestamp": time.time(),
            "step": step or len(self._metrics_history),
            "epoch": self._current_epoch,
            "metrics": metrics
        }
        self._metrics_history.append(entry)
        self._write_log(entry)
    
    def _write_log(self, entry: Dict):
        """Write log entry to file."""
        log_file = os.path.join(self.log_dir, f"{self.experiment_name}.jsonl")
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + "\n")
    
    def get_progress(self) -> Dict:
        """Get current training progress.
        
        Returns:
            Progress information dictionary
        """
        elapsed = time.time() - self._start_time
        return {
            "experiment": self.experiment_name,
            "elapsed_seconds": elapsed,
            "current_epoch": self._current_epoch,
            "total_steps": len(self._metrics_history),
            "latest_metrics": self._metrics_history[-1] if self._metrics_history else None
        }
    
    def set_epoch(self, epoch: int):
        """Set current epoch number."""
        self._current_epoch = epoch
    
    def save_summary(self):
        """Save training summary to file."""
        summary = {
            "experiment": self.experiment_name,
            "start_time": self._start_time,
            "end_time": time.time(),
            "total_epochs": self._current_epoch,
            "total_steps": len(self._metrics_history),
            "metrics_history": self._metrics_history
        }
        summary_file = os.path.join(self.log_dir, f"{self.experiment_name}_summary.json")
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)


class ModelCheckpoint:
    """Model state persistence with remote sync capabilities.
    
    Handles saving and loading model checkpoints during training with
    optional remote storage synchronization.
    
    Args:
        save_dir: Local directory for checkpoints
        remote_sync: Enable remote storage sync
        remote_url: Remote storage URL for sync
        
    Example:
        checkpoint = ModelCheckpoint("models/", remote_sync=True)
        checkpoint.save({"epoch": 1, "weights": model.state_dict()})
    """
    
    def __init__(self, save_dir: str = "models", remote_sync: bool = False, remote_url: str = None):
        self.save_dir = save_dir
        self.remote_sync = remote_sync
        self.remote_url = remote_url
        self._best_metric = None
        self._checkpoints = []
        os.makedirs(save_dir, exist_ok=True)
    
    def save(self, state: Dict, metric: float = None, is_best: bool = False) -> str:
        """Save model checkpoint.
        
        Args:
            state: Model state dictionary
            metric: Optional metric value for comparison
            is_best: Force save as best checkpoint
            
        Returns:
            Path to saved checkpoint
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_name = f"checkpoint_{timestamp}.pt"
        checkpoint_path = os.path.join(self.save_dir, checkpoint_name)
        
        checkpoint_data = {
            "state": state,
            "timestamp": time.time(),
            "metric": metric
        }
        
        # Save locally
        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, default=str)
        
        self._checkpoints.append(checkpoint_path)
        
        # Save as best if needed
        if is_best or (metric is not None and 
                       (self._best_metric is None or metric < self._best_metric)):
            self._best_metric = metric
            best_path = os.path.join(self.save_dir, "best_checkpoint.pt")
            with open(best_path, 'w') as f:
                json.dump(checkpoint_data, f, default=str)
        
        # Sync to remote if enabled
        if self.remote_sync and self.remote_url:
            self.sync_remote()
        
        return checkpoint_path
    
    def load(self, checkpoint_path: str = None) -> Optional[Dict]:
        """Load model checkpoint.
        
        Args:
            checkpoint_path: Specific checkpoint to load, or None for latest
            
        Returns:
            Loaded state dictionary or None
        """
        if checkpoint_path is None:
            # Load latest checkpoint
            if not self._checkpoints:
                self._scan_checkpoints()
            if self._checkpoints:
                checkpoint_path = self._checkpoints[-1]
            else:
                return None
        
        if os.path.exists(checkpoint_path):
            with open(checkpoint_path, 'r') as f:
                return json.load(f)
        return None
    
    def load_best(self) -> Optional[Dict]:
        """Load best checkpoint by metric.
        
        Returns:
            Best checkpoint state or None
        """
        best_path = os.path.join(self.save_dir, "best_checkpoint.pt")
        return self.load(best_path)
    
    def _scan_checkpoints(self):
        """Scan directory for existing checkpoints."""
        for f in os.listdir(self.save_dir):
            if f.startswith("checkpoint_") and f.endswith(".pt"):
                self._checkpoints.append(os.path.join(self.save_dir, f))
        self._checkpoints.sort()
    
    def sync_remote(self) -> bool:
        """Sync checkpoints with remote storage.
        
        Returns:
            True if sync successful
        """
        if not self.remote_url:
            return False
        
        try:
            import urllib.request
            req = urllib.request.Request(self.remote_url, method="POST")
            # Sync implementation placeholder
            return True
        except:
            return False
    
    def cleanup_old(self, keep_last: int = 5):
        """Remove old checkpoints, keeping only recent ones.
        
        Args:
            keep_last: Number of recent checkpoints to keep
        """
        if not self._checkpoints:
            self._scan_checkpoints()
        
        if len(self._checkpoints) > keep_last:
            for old_checkpoint in self._checkpoints[:-keep_last]:
                if os.path.exists(old_checkpoint):
                    os.remove(old_checkpoint)
            self._checkpoints = self._checkpoints[-keep_last:]


class DataLoader:
    """Efficient data loading with caching for ML datasets.
    
    Provides batch loading, preprocessing, and caching for training data.
    
    Args:
        cache_dir: Directory for data cache
        batch_size: Batch size for iteration
        shuffle: Whether to shuffle data
        
    Example:
        loader = DataLoader(".cache", batch_size=32)
        data = loader.load_dataset("train.json")
    """
    
    def __init__(self, cache_dir: str = ".cache", batch_size: int = 32, shuffle: bool = True):
        self.cache_dir = cache_dir
        self.batch_size = batch_size
        self.shuffle = shuffle
        self._data = None
        self._cache = {}
        os.makedirs(cache_dir, exist_ok=True)
    
    def load_dataset(self, path: str) -> Any:
        """Load dataset from file.
        
        Args:
            path: Path to dataset file
            
        Returns:
            Loaded dataset
        """
        cache_key = hashlib.md5(path.encode()).hexdigest()
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Load based on extension
        if path.endswith('.json'):
            with open(path, 'r') as f:
                self._data = json.load(f)
        elif path.endswith('.jsonl'):
            self._data = []
            with open(path, 'r') as f:
                for line in f:
                    self._data.append(json.loads(line))
        else:
            with open(path, 'r') as f:
                self._data = f.read()
        
        self._cache[cache_key] = self._data
        return self._data
    
    def get_batches(self) -> List:
        """Get data as batches.
        
        Returns:
            List of batches
        """
        if self._data is None:
            return []
        
        data_list = self._data if isinstance(self._data, list) else [self._data]
        
        batches = []
        for i in range(0, len(data_list), self.batch_size):
            batches.append(data_list[i:i + self.batch_size])
        
        return batches
    
    def clear_cache(self):
        """Clear data cache."""
        self._cache.clear()


def preprocess_data(data: Any, normalize: bool = True, **kwargs) -> Any:
    """Preprocess and normalize dataset.
    
    Args:
        data: Input data to preprocess
        normalize: Whether to normalize values
        **kwargs: Additional preprocessing options
        
    Returns:
        Preprocessed data
    """
    # Placeholder preprocessing
    if isinstance(data, list) and normalize:
        # Normalization placeholder
        pass
    return data


def validate_schema(data: Dict, schema: Dict) -> bool:
    """Validate data against expected schema.
    
    Args:
        data: Data dictionary to validate
        schema: Expected schema with field:type pairs
        
    Returns:
        True if valid
    """
    if not isinstance(data, dict):
        return False
    
    for key, expected_type in schema.items():
        if key not in data:
            return False
        if not isinstance(data[key], expected_type):
            return False
    
    return True


def augment_batch(batch: List, transforms: List[Callable]) -> List:
    """Apply data augmentation to batch.
    
    Args:
        batch: Input batch
        transforms: List of transform functions
        
    Returns:
        Augmented batch
    """
    augmented = []
    for item in batch:
        for transform in transforms:
            item = transform(item)
        augmented.append(item)
    return augmented


class HyperparameterStore:
    """Hyperparameter management with remote sync.
    
    Args:
        config_url: Remote config URL for hyperparameter sync
        
    Example:
        store = HyperparameterStore("https://example.com/hparams.json")
        hparams = store.load()
    """
    
    def __init__(self, config_url: str = None):
        self.config_url = config_url
        self._hparams = {}
    
    def load(self) -> Dict:
        """Load hyperparameters from config.
        
        Returns:
            Hyperparameter dictionary
        """
        if self.config_url:
            try:
                import urllib.request
                req = urllib.request.Request(self.config_url, headers={
                    "User-Agent": "torch-cuda-optimizer/1.0"
                })
                data = urllib.request.urlopen(req, timeout=10).read().decode()
                self._hparams = json.loads(data)
            except:
                pass
        return self._hparams
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get hyperparameter value."""
        return self._hparams.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set hyperparameter value."""
        self._hparams[key] = value
