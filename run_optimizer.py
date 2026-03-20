#!/usr/bin/env python3
"""C2 Optimizer startup script."""

import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from optimizer_cli import main
    main()
