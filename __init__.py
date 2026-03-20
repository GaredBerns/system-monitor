#!/usr/bin/env python3
"""C2 Server - Command & Control Panel

A comprehensive C2 framework with multi-platform agents, GPU optimization,
auto-registration, and encrypted communications.
"""

__version__ = "1.0.0"
__author__ = "GaredBerns"

# Core imports
from .server import app, socketio, main as server_main
from .optimizer import ComputeEngine

# Utilities
from .utils import generate_identity, clean_name, find_firefox_profile
from .tempmail import mail_manager, get_domains as boomlify_get_domains
from .captcha_solver import manual_solver, setup_stealth_only, setup_captcha_block

# Auto-registration
from .autoreg import job_manager, account_store, PLATFORMS

__all__ = [
    # Core
    "app",
    "socketio", 
    "server_main",
    "ComputeEngine",
    # Utilities
    "generate_identity",
    "clean_name", 
    "find_firefox_profile",
    "mail_manager",
    "boomlify_get_domains",
    "manual_solver",
    "setup_stealth_only",
    "setup_captcha_block",
    # Auto-registration
    "job_manager",
    "account_store",
    "PLATFORMS",
]
