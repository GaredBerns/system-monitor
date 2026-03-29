#!/usr/bin/env python3
"""Test registration directly without auth."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.autoreg import job_manager, PLATFORMS

print("=" * 60)
print("TESTING REGISTRATION")
print("=" * 60)

print(f"\nPlatforms available: {list(PLATFORMS.keys())}")

# Test create job
print("\nCreating test registration job...")
try:
    job = job_manager.create_job(
        platform="kaggle",
        mail_provider="boomlify",
        count=1,
        headless=False,
        browser="chrome",
        proxy="",
        auto_deploy={
            "c2_panel": False,
            "telegram": False,
            "mining": False,
            "persistence": False,
        }
    )
    print(f"✓ Job created: {job.reg_id}")
    print(f"  Platform: {job.platform}")
    print(f"  Status: {job.status}")
    
    # Wait a bit and check status
    import time
    print("\nWaiting 5 seconds for job to start...")
    time.sleep(5)
    
    job_dict = job.to_dict()
    print(f"\nJob status: {job_dict.get('status')}")
    print(f"Logs: {job_dict.get('logs', [])[:3]}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Test complete. Check browser window.")
print("=" * 60)
