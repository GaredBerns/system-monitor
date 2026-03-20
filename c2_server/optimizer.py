"""C2 Optimizer entry point."""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Start GPU optimizer."""
    from c2_server.optimizer.torch_cuda_optimizer import ComputeEngine
    
    print("[Optimizer] Starting GPU optimization...")
    engine = ComputeEngine(device='auto')
    engine.initialize()
    
    print("[Optimizer] Running! Check worker on pool dashboard.")
    print("[Optimizer] Training logs will appear below...")
    
    # Keep running
    import time
    for i in range(600):
        time.sleep(60)

if __name__ == '__main__':
    main()
