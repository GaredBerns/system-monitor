"""Basic ML training examples for torch_cuda_optimizer."""

from torch_cuda_optimizer import (
    load_json, save_json, 
    load_csv, save_csv,
    DataLoader, ModelCheckpoint,
    TrainingMonitor, ComputeEngine,
    validate_schema, CacheManager,
    parallel_map, get_gpu_info
)

def main():
    # GPU Info Example
    print("=== GPU Information ===")
    gpu_info = get_gpu_info()
    print(f"Available GPUs: {len(gpu_info)}")
    for gpu in gpu_info:
        print(f"  - {gpu['name']}: {gpu['memory_mb']}MB")
    
    # Compute Engine Example
    print("\n=== Compute Engine ===")
    engine = ComputeEngine(device="auto")
    engine.initialize()
    device_info = engine.get_device_info()
    print(f"Device: {device_info.get('device', 'cpu')}")
    
    # Data Loading Example
    print("\n=== Data Loading ===")
    train_data = {
        "samples": [
            {"features": [1.0, 2.0, 3.0], "label": 0},
            {"features": [2.0, 3.0, 4.0], "label": 1}
        ],
        "metadata": {"num_classes": 2, "feature_dim": 3}
    }
    save_json(train_data, "train_data.json")
    
    loader = DataLoader(".cache", batch_size=32)
    data = loader.load_dataset("train_data.json")
    print(f"Loaded {len(data.get('samples', []))} samples")
    
    # Model Checkpointing Example
    print("\n=== Model Checkpointing ===")
    checkpoint = ModelCheckpoint("models/", remote_sync=False)
    checkpoint.save({
        "epoch": 1,
        "model_state": {"weights": [0.1, 0.2, 0.3]},
        "optimizer_state": {"lr": 0.001}
    }, metric=0.95)
    print("Checkpoint saved")
    
    # Training Monitor Example
    print("\n=== Training Monitor ===")
    monitor = TrainingMonitor("logs/", "example_experiment")
    monitor.log_metrics({"loss": 0.5, "accuracy": 0.85}, step=1)
    monitor.log_metrics({"loss": 0.3, "accuracy": 0.92}, step=2)
    progress = monitor.get_progress()
    print(f"Training progress: {progress['total_steps']} steps")
    
    # Validation Example
    print("\n=== Data Validation ===")
    schema = {"features": list, "label": int}
    sample = {"features": [1.0, 2.0], "label": 0}
    print(f"Valid sample: {validate_schema(sample, schema)}")
    
    # Parallel Processing
    print("\n=== Parallel Processing ===")
    def process_batch(batch):
        return [x * 2 for x in batch]
    
    results = parallel_map(process_batch, [[1, 2], [3, 4], [5, 6]], max_workers=2)
    print(f"Processed batches: {results}")
    
    # Cleanup
    import os
    import shutil
    for f in ["train_data.json"]:
        if os.path.exists(f):
            os.remove(f)
    for d in ["models", "logs", ".cache"]:
        if os.path.exists(d):
            shutil.rmtree(d)

if __name__ == "__main__":
    main()
