#!/usr/bin/env python3
"""C2 Server — entry point."""

import sys
from pathlib import Path

# Ensure project root is in Python path
sys.path.insert(0, str(Path(__file__).parent))

# Gevent monkey-patch must happen before any other imports
try:
    from gevent import monkey
    monkey.patch_all()
except ImportError:
    try:
        import eventlet
        eventlet.monkey_patch()
    except ImportError:
        pass

if __name__ == "__main__":
    from core.server import main
    main()
