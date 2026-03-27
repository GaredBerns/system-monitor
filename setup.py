#!/usr/bin/env python3
"""Setup script for System Monitor."""

from setuptools import setup, find_packages

setup(
    name="system-monitor",
    version="3.0.0",
    author="GaredBerns",
    description="System monitoring toolkit",
    package_dir={"": "."},
    packages=find_packages(where="."),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "startcon=src.agents.universal:main",
        ],
    },
)
