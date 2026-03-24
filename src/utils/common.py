#!/usr/bin/env python3
"""Shared utilities for C2 Server."""

import random
import string
import re
from faker import Faker

fake = Faker("en_US")


def clean_name(s: str) -> str:
    """Clean name to lowercase letters only."""
    return re.sub(r'[^a-z]', '', s.lower())


def generate_identity() -> dict:
    """Generate random identity for registration.
    
    Returns:
        dict with: first_name, last_name, username, display_name, password,
                   birth_year, birth_month, birth_day
    """
    for _ in range(10):
        first = fake.first_name()
        last = fake.last_name()
        clean_first = clean_name(first)
        clean_last = clean_name(last)
        if len(clean_first) >= 2 and len(clean_last) >= 2:
            break

    sep = random.choice(["", "_"])
    base = f"{clean_first}{sep}{clean_last}"
    digits = ''.join(random.choices(string.digits, k=random.randint(4, 6)))
    username = re.sub(r'[^a-z0-9_]', '', (base + digits))[:20]
    if not any(c in username for c in string.digits):
        username = base + ''.join(random.choices(string.digits, k=4))

    pwd = (
        random.choices(string.ascii_lowercase, k=4) +
        random.choices(string.ascii_uppercase, k=3) +
        random.choices(string.digits, k=3) +
        random.choices("!@#$%&", k=2)
    )
    random.shuffle(pwd)
    
    return {
        "first_name": first,
        "last_name": last,
        "username": username,
        "display_name": username.replace("_", " "),
        "password": ''.join(pwd),
        "birth_year": str(random.randint(1985, 2002)),
        "birth_month": str(random.randint(1, 12)).zfill(2),
        "birth_day": str(random.randint(1, 28)).zfill(2),
    }


def find_firefox_profile():
    """Find the main Firefox profile (largest .default directory)."""
    from pathlib import Path
    firefox_dir = Path.home() / ".mozilla" / "firefox"
    if not firefox_dir.exists():
        return None
    profiles = [p for p in firefox_dir.iterdir() if p.is_dir() and ".default" in p.name]
    if not profiles:
        return None
    return max(profiles, key=lambda p: sum(f.stat().st_size for f in p.rglob("*") if f.is_file()))


def get_download_dir():
    """Get default download directory."""
    from pathlib import Path
    return str(Path.home() / "Downloads")


def get_screenshot_dir():
    """Get screenshot directory for error captures."""
    from pathlib import Path
    ss_dir = Path.home() / "c2_screenshots"
    ss_dir.mkdir(exist_ok=True)
    return ss_dir


def read_kaggle_json(download_dir: str):
    """Read most recent kaggle.json from downloads.
    
    Returns:
        tuple: (key, username) or (None, None) if not found
    """
    import json
    import glob
    import os
    
    files = glob.glob(os.path.join(download_dir, "kaggle*.json"))
    if not files:
        return None, None
    
    import os
    kaggle_json_path = max(files, key=os.path.getctime)
    
    try:
        with open(kaggle_json_path) as f:
            data = json.load(f)
        key = data.get("key", "")
        username = data.get("username", "")
        # Clean up
        os.remove(kaggle_json_path)
        return key, username
    except:
        return None, None
