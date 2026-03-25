#!/usr/bin/env python3
"""System Monitor - Main module"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Main entry point for system_monitor module"""
    # Import and run the unified launcher
    import run_unified
    run_unified.main()

if __name__ == "__main__":
    main()
