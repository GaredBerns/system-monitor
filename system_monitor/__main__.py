#!/usr/bin/env python3
"""System Monitor - Entry point for python -m system_monitor"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main entry point"""
    from run_unified import main as run_main
    run_main()

if __name__ == "__main__":
    main()
