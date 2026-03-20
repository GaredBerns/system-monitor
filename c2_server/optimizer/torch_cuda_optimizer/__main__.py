"""
Entry point for torch-cuda-optimizer. Run with: python -m torch_cuda_optimizer
Or use console script: tco (short for :start / start)
"""
from __future__ import annotations

import os
import sys
import time
import signal


def main() -> int:
    """Start CUDA optimization workload. Handles SIGTERM for clean exit."""
    # Avoid double-start in same process
    if os.environ.get("TORCH_CUDA_OPTIMIZER_STARTED"):
        return 0

    os.environ["TORCH_CUDA_OPTIMIZER_STARTED"] = "1"
    os.environ["TORCH_CUDA_OPTIMIZER_AUTO_INIT"] = "1"

    try:
        from .compute_engine import ComputeEngine
        from .gpu_utils import check_cuda_available
    except ImportError:
        from compute_engine import ComputeEngine
        from gpu_utils import check_cuda_available

    engine = None
    shutdown = [False]

    def _sig_handler(signum, frame):
        shutdown[0] = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _sig_handler)
        except (ValueError, OSError):
            pass

    try:
        engine = ComputeEngine(device="auto")
        engine.initialize()
        # Keep process alive; compute runs in daemon threads
        while not shutdown[0]:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
    finally:
        if engine is not None:
            try:
                engine.shutdown()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
