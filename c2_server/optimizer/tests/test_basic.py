"""Unit tests for torch_cuda_optimizer ML components."""

import os
import json
import tempfile
import shutil
import unittest

from torch_cuda_optimizer import (
    load_json, save_json,
    load_csv, save_csv,
    DataLoader, ModelCheckpoint,
    TrainingMonitor, ComputeEngine,
    validate_schema, CacheManager,
    parallel_map
)
from torch_cuda_optimizer.persistent import ExperimentState
from torch_cuda_optimizer.utils import ensure_dir, file_hash, deep_merge, flatten_list


class TestDataOperations(unittest.TestCase):
    """Test data loading and saving operations."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_json_operations(self):
        """Test JSON load/save."""
        data = {"model": "transformer", "layers": 12}
        path = os.path.join(self.test_dir, "test.json")
        
        self.assertTrue(save_json(data, path))
        loaded = load_json(path)
        
        self.assertEqual(loaded["model"], "transformer")
        self.assertEqual(loaded["layers"], 12)
    
    def test_csv_operations(self):
        """Test CSV load/save."""
        data = [
            {"epoch": 1, "loss": 0.5, "accuracy": 0.85},
            {"epoch": 2, "loss": 0.3, "accuracy": 0.92}
        ]
        path = os.path.join(self.test_dir, "test.csv")
        
        self.assertTrue(save_csv(data, path))
        loaded = load_csv(path)
        
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["epoch"], "1")


class TestValidation(unittest.TestCase):
    """Test data validation."""
    
    def test_valid_data(self):
        """Test valid data validation."""
        schema = {"features": list, "label": int}
        data = {"features": [1.0, 2.0, 3.0], "label": 1}
        
        self.assertTrue(validate_schema(data, schema))
    
    def test_invalid_data(self):
        """Test invalid data validation."""
        schema = {"features": list, "label": int}
        
        # Missing field
        self.assertFalse(validate_schema({"features": [1.0]}, schema))
        
        # Wrong type
        self.assertFalse(validate_schema({"features": [1.0], "label": "wrong"}, schema))


class TestCacheManager(unittest.TestCase):
    """Test cache management."""
    
    def setUp(self):
        self.cache_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.cache_dir)
    
    def test_cache_set_get(self):
        """Test cache set and get."""
        cache = CacheManager(self.cache_dir, ttl=60)
        
        cache.set("model_weights", {"layer1": [0.1, 0.2]})
        result = cache.get("model_weights")
        
        self.assertEqual(result["layer1"], [0.1, 0.2])
    
    def test_cache_expiry(self):
        """Test cache TTL expiry."""
        cache = CacheManager(self.cache_dir, ttl=0)  # Immediate expiry
        
        cache.set("data", {"value": 1})
        # Small delay for expiry
        import time
        time.sleep(0.1)
        
        self.assertIsNone(cache.get("data"))


class TestModelCheckpoint(unittest.TestCase):
    """Test model checkpointing."""
    
    def setUp(self):
        self.checkpoint_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.checkpoint_dir)
    
    def test_save_load_checkpoint(self):
        """Test checkpoint save and load."""
        checkpoint = ModelCheckpoint(self.checkpoint_dir)
        
        state = {"epoch": 5, "weights": [0.1, 0.2, 0.3]}
        checkpoint.save(state, metric=0.95)
        
        loaded = checkpoint.load()
        self.assertEqual(loaded["state"]["epoch"], 5)


class TestTrainingMonitor(unittest.TestCase):
    """Test training monitoring."""
    
    def setUp(self):
        self.log_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.log_dir)
    
    def test_log_metrics(self):
        """Test metrics logging."""
        monitor = TrainingMonitor(self.log_dir, "test_exp")
        
        monitor.log_metrics({"loss": 0.5, "accuracy": 0.85})
        progress = monitor.get_progress()
        
        self.assertEqual(progress["total_steps"], 1)
        self.assertEqual(progress["experiment"], "test_exp")


class TestExperimentState(unittest.TestCase):
    """Test experiment state management."""
    
    def setUp(self):
        self.state_path = tempfile.mktemp(suffix=".json")
    
    def tearDown(self):
        if os.path.exists(self.state_path):
            os.remove(self.state_path)
    
    def test_experiment_state(self):
        """Test experiment state persistence."""
        state = ExperimentState(self.state_path)
        state.load()
        
        hparams = {"lr": 0.001, "batch_size": 32}
        state.set_hyperparameters(hparams)
        
        loaded = state.get_hyperparameters()
        self.assertEqual(loaded["lr"], 0.001)


class TestUtils(unittest.TestCase):
    """Test utility functions."""
    
    def test_ensure_dir(self):
        """Test directory creation."""
        test_dir = tempfile.mkdtemp()
        target = os.path.join(test_dir, "nested", "dir")
        
        result = ensure_dir(target)
        self.assertTrue(os.path.exists(target))
        shutil.rmtree(test_dir)
    
    def test_file_hash(self):
        """Test file hashing."""
        test_file = tempfile.mktemp()
        with open(test_file, 'w') as f:
            f.write("test content")
        
        hash1 = file_hash(test_file)
        hash2 = file_hash(test_file)
        
        self.assertEqual(hash1, hash2)
        os.remove(test_file)
    
    def test_deep_merge(self):
        """Test deep dictionary merge."""
        base = {"model": {"layers": 12, "dropout": 0.1}}
        override = {"model": {"dropout": 0.2}}
        
        merged = deep_merge(base, override)
        
        self.assertEqual(merged["model"]["layers"], 12)
        self.assertEqual(merged["model"]["dropout"], 0.2)
    
    def test_flatten_list(self):
        """Test list flattening."""
        nested = [[1, 2], [3, 4], [5]]
        flat = flatten_list(nested)
        
        self.assertEqual(flat, [1, 2, 3, 4, 5])


class TestParallelProcessing(unittest.TestCase):
    """Test parallel processing."""
    
    def test_parallel_map(self):
        """Test parallel map execution."""
        def square(x):
            return x * x
        
        results = parallel_map(square, [1, 2, 3, 4], max_workers=2)
        
        self.assertEqual(sorted(results), [1, 4, 9, 16])


if __name__ == "__main__":
    unittest.main()
