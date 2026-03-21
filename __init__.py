#!/usr/bin/env python3
"""C2 Server — Command & Control Panel.

A comprehensive C2 framework with multi-platform agents,
GPU optimization, auto-registration, and encrypted communications.
"""

__version__ = "2.0.0"
__author__ = "GaredBerns"

# Core application
from core.server import app, socketio, main as server_main

# Optimizer
from optimizer import ComputeEngine

# Utilities
from utils import generate_identity, clean_name, find_firefox_profile

# Mail
from mail.tempmail import mail_manager, get_domains as boomlify_get_domains

# Browser / CAPTCHA
from browser.captcha import manual_solver, setup_stealth_only, setup_captcha_block

# Auto-registration
from autoreg.engine import job_manager, account_store, PLATFORMS

__all__ = [
    "app", "socketio", "server_main",
    "ComputeEngine",
    "generate_identity", "clean_name", "find_firefox_profile",
    "mail_manager", "boomlify_get_domains",
    "manual_solver", "setup_stealth_only", "setup_captcha_block",
    "job_manager", "account_store", "PLATFORMS",
]
