#!/usr/bin/env python3
"""Setup script for C2 Server."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text(encoding="utf-8").strip().split("\n")
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith("#")]

setup(
    name="c2-server",
    version="2.0.0",
    author="GaredBerns",
    author_email="",
    description="A comprehensive C2 framework with multi-platform agents, GPU optimization, and auto-registration",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/GaredBerns/C2_server",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "server": [
            "flask>=2.0.0",
            "flask-socketio>=5.0.0",
            "flask-bcrypt>=1.0.0",
        ],
        "optimizer": [
            "torch>=2.0.0",
            "torchvision>=0.15.0",
            "numpy>=1.21.0",
        ],
        "agents": [
            "playwright>=1.40.0",
            "selenium>=4.0.0",
            "undetected-chromedriver>=3.5.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "c2-server=core.server:main",
            "c2-optimizer=optimizer.cli:main",
            "c2-agent=src.agents.universal:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["templates/*", "static/*", "data/*"],
    },
)
