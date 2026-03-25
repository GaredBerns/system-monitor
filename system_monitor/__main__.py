#!/usr/bin/env python3
"""System Monitor - Entry point for python -m system_monitor"""

def main():
    """Main entry point"""
    from .main import main as package_main
    package_main()

if __name__ == "__main__":
    main()
