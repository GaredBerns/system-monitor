#!/usr/bin/env python3
"""C2 Optimizer — entry point."""

import sys
from pathlib import Path

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    from optimizer.cli import main
    main()
