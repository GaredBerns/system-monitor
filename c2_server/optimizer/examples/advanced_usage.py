"""Advanced ML training examples for torch_cuda_optimizer."""

from torch_cuda_optimizer import (
    ComputeEngine, DistributedTrainer,
    ModelCheckpoint, TrainingMonitor,
    DataLoader, HyperparameterStore,
    parallel_map, retry_on_error
)
from torch_cuda_optimizer.persistent import (
    ExperimentState, create_checkpoint_storage,
    list_checkpoints, cleanup_old_checkpoints
)
from torch_cuda_optimizer.utils import ensure_dir, file_hash, deep_merge, flatten_list
import time

def main():
    # Distributed Training Example
    print("=== Distributed Training ===")
    trainer = DistributedTrainer(num_workers=4, backend="nccl")
    trainer.setup()
    print("Distributed trainer initialized")
    
    # Compute Engine with GPU
    print("\n=== GPU Compute Engine ===")
    engine = ComputeEngine(device="auto", memory_fraction=0.8)
    engine.initialize()
    device_info = engine.get_device_info()
    print(f"Device info: {device_info}")
    
    # Experiment State Management
    print("\n=== Experiment State ===")
    state = ExperimentState("experiment.json")
    state.load()
    print(f"Experiment ID: {state.get_experiment_id()}")
    
    # Set hyperparameters
    hparams = {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100,
        "optimizer": "adam"
    }
    state.set_hyperparameters(hparams)
    print(f"Hyperparameters: {state.get_hyperparameters()}")
    
    # Model Checkpointing with Remote Sync
    print("\n=== Model Checkpointing ===")
    checkpoint_dir = create_checkpoint_storage("checkpoints")
    checkpoint = ModelCheckpoint(checkpoint_dir, remote_sync=False)
    
    # Save multiple checkpoints
    for epoch in range(1, 4):
        checkpoint.save({
            "epoch": epoch,
            "model_state": {"weights": [0.1 * epoch, 0.2 * epoch]},
            "metrics": {"loss": 1.0 / epoch, "accuracy": 0.8 + 0.05 * epoch}
        }, metric=1.0 / epoch)
        state.add_checkpoint(f"checkpoint_{epoch}.pt", metric=1.0 / epoch)
    
    # List checkpoints
    checkpoints = list_checkpoints(checkpoint_dir)
    print(f"Saved {len(checkpoints)} checkpoints")
    
    # Cleanup old checkpoints
    cleanup_old_checkpoints(checkpoint_dir, keep_last=2)
    print(f"Cleaned up old checkpoints")
    
    # Training Monitor with Metrics
    print("\n=== Training Monitor ===")
    monitor = TrainingMonitor("logs/", "advanced_experiment")
    monitor.set_epoch(0)
    
    # Simulate training loop
    for epoch in range(3):
        monitor.set_epoch(epoch)
        for step in range(5):
            metrics = {
                "loss": 1.0 / (epoch + 1) - step * 0.01,
                "accuracy": 0.8 + epoch * 0.05 + step * 0.01,
                "learning_rate": 0.001 * (0.95 ** epoch)
            }
            monitor.log_metrics(metrics, step=epoch * 5 + step)
    
    progress = monitor.get_progress()
    print(f"Training progress: {progress['total_steps']} steps, {progress['current_epoch']} epochs")
    monitor.save_summary()
    
    # Hyperparameter Store
    print("\n=== Hyperparameter Store ===")
    hparam_store = HyperparameterStore()
    hparam_store.set("model_type", "transformer")
    hparam_store.set("hidden_size", 768)
    hparam_store.set("num_heads", 12)
    print(f"Stored hyperparameters: model_type={hparam_store.get('model_type')}")
    
    # Deep Merge for Config
    print("\n=== Config Deep Merge ===")
    base_config = {
        "model": {"layers": 12, "hidden_size": 768, "dropout": 0.1},
        "training": {"lr": 0.001, "warmup_steps": 1000},
        "data": {"batch_size": 32, "shuffle": True}
    }
    override_config = {
        "model": {"dropout": 0.2},
        "training": {"lr": 0.0001, "max_steps": 10000}
    }
    merged = deep_merge(base_config, override_config)
    print(f"Merged config: {merged}")
    
    # Retry Decorator for Training
    print("\n=== Retry Decorator ===")
    @retry_on_error(max_retries=3, delay=0.1)
    def unstable_training_step(step):
        import random
        if random.random() < 0.5:
            raise RuntimeError(f"Training step {step} failed")
        return f"Step {step} completed"
    
    try:
        result = unstable_training_step(1)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Failed: {e}")
    
    # Parallel Data Processing
    print("\n=== Parallel Data Processing ===")
    def preprocess_batch(batch_idx):
        time.sleep(0.05)
        return {"batch": batch_idx, "processed": True}
    
    results = parallel_map(preprocess_batch, list(range(8)), max_workers=4)
    print(f"Processed {len(results)} batches in parallel")
    
    # Cleanup
    import os
    import shutil
    for f in ["experiment.json"]:
        if os.path.exists(f):
            os.remove(f)
    for d in ["checkpoints", "logs"]:
        if os.path.exists(d):
            shutil.rmtree(d)
    engine.shutdown()

if __name__ == "__main__":
    main()
