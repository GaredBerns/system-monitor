#!/usr/bin/env python3
"""Setup script for System Monitor Pro - Enterprise System Health Monitoring."""

from setuptools import setup, find_packages

setup(
    name="sysmon-pro",
    version="3.0.1",
    author="DevOpsTools",
    description="Enterprise system health monitoring and resource optimization toolkit",
    long_description="""System Monitor Pro - Enterprise-grade system health monitoring.

Features:
- Real-time system health monitoring
- Resource optimization and cleanup
- Performance telemetry and analytics
- Automated maintenance scheduling
- Cross-platform support (Linux, macOS, Windows)

Ideal for DevOps teams and system administrators.""",
    package_dir={"": "."},
    packages=find_packages(where="."),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "sysmon-agent=src.agents.universal:main",
            "syscheck=src.agents.universal:main",
            "healthmon=src.agents.universal:main",
        ],
    },
)
