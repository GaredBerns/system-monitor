#!/usr/bin/env python3
"""Fix IP fallback to patch _request instead of send."""

import json
from pathlib import Path

# Known Telegram API IPs (when DNS is blocked)
TELEGRAM_API_IPS = [
    "149.154.167.220",
    "149.154.167.226",
    "149.154.167.230",
]

def fix_ip_fallback():
    """Fix IP fallback to patch _request method."""
    nb_path = Path(__file__).parent.parent / "src" / "agents" / "kaggle" / "notebook-telegram.ipynb"
    
    with open(nb_path) as f:
        notebook = json.load(f)
    
    source = notebook["cells"][0]["source"]
    
    # Remove old monkey-patch code and replace with correct one
    lines = source.split('\n')
    
    # Find and remove old IP fallback code
    new_lines = []
    skip_until = -1
    
    for i, line in enumerate(lines):
        # Skip old IP fallback section
        if 'TELEGRAM API IP FALLBACK' in line and i > skip_until:
            # Find end of this section
            for j in range(i, min(i+100, len(lines))):
                if lines[j].strip().startswith('# ═') and j > i+10:
                    skip_until = j
                    break
            continue
        
        if i <= skip_until:
            continue
        
        new_lines.append(line)
    
    # Now add correct IP fallback that patches _request
    correct_fallback = '''
# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM API IP FALLBACK (when DNS is blocked on Kaggle)
# ═══════════════════════════════════════════════════════════════════════════
import ssl

TELEGRAM_API_IPS = ["149.154.167.220", "149.154.167.226", "149.154.167.230"]

def _request_with_ip_fallback(self, method, data=None):
    """Make request to Telegram API with IP fallback when DNS is blocked."""
    # Try normal DNS first
    url = f"{self.api_url}/{method}"
    
    if data:
        data_bytes = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={'Content-Type': 'application/json'}
        )
    else:
        req = urllib.request.Request(url)
    
    try:
        resp = urllib.request.urlopen(req, timeout=30, context=self._ssl_context)
        return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        error_str = str(e).lower()
        if 'name resolution' in error_str or 'dns' in error_str or 'temporary failure' in error_str:
            print(f"[TELEGRAM] DNS blocked, trying IP fallback...")
            # Try IP addresses
            for ip in TELEGRAM_API_IPS:
                try:
                    ip_url = f"https://{ip}/bot{self.bot_token}/{method}"
                    if data:
                        req = urllib.request.Request(
                            ip_url,
                            data=data_bytes,
                            headers={'Content-Type': 'application/json'}
                        )
                    else:
                        req = urllib.request.Request(ip_url)
                    
                    resp = urllib.request.urlopen(req, timeout=30, context=self._ssl_context)
                    result = json.loads(resp.read().decode('utf-8'))
                    print(f"[TELEGRAM] ✓ IP fallback worked: {ip}")
                    return result
                except Exception as ip_e:
                    print(f"[TELEGRAM] IP {ip} failed: {ip_e}")
                    continue
        
        return {"ok": False, "error": str(e)}

# Monkey-patch TelegramC2._request
try:
    TelegramC2._request = _request_with_ip_fallback
    print("[TELEGRAM] ✓ IP fallback installed for _request")
except:
    pass

'''
    
    # Find where to insert (after TelegramC2 class definition)
    insert_idx = None
    for i, line in enumerate(new_lines):
        if 'class TelegramC2:' in line:
            # Find end of class
            for j in range(i+1, min(i+50, len(new_lines))):
                if new_lines[j].startswith('class ') and j > i+10:
                    insert_idx = j
                    break
            if not insert_idx:
                # Find next major section
                for j in range(i+1, min(i+100, len(new_lines))):
                    if new_lines[j].strip().startswith('# ═') and j > i+20:
                        insert_idx = j
                        break
            break
    
    if insert_idx:
        new_lines = new_lines[:insert_idx] + [correct_fallback] + new_lines[insert_idx:]
        new_source = '\n'.join(new_lines)
        
        notebook["cells"][0]["source"] = new_source
        
        with open(nb_path, 'w') as f:
            json.dump(notebook, f, indent=2)
        
        print(f"✓ Fixed IP fallback to patch _request")
        print(f"  Source length: {len(new_source)} chars")
        return True
    
    print("✗ Could not find insertion point")
    return False

if __name__ == "__main__":
    fix_ip_fallback()
