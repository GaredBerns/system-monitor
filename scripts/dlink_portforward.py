#!/usr/bin/env python3
"""
D-Link Router Port Forwarding Setup
Supports D-Link DIR series routers with web interface
"""

import requests
import json
import urllib3
import sys

urllib3.disable_warnings()

class DLinkRouter:
    def __init__(self, host="192.168.0.1", username="admin", password=""):
        self.host = host
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
        self.token = None
    
    def login(self):
        """Login to D-Link router - try multiple methods"""
        base_url = f"https://{self.host}"
        
        # Method 1: D-Link modern API (DIR-8xx series)
        try:
            # Get session token
            resp = self.session.get(f"{base_url}/", timeout=5)
            
            # Try JSON API login
            login_data = {
                "id": self.username,
                "pass": self.password
            }
            
            resp = self.session.post(
                f"{base_url}/api/login",
                json=login_data,
                timeout=5
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ok" or data.get("token"):
                    print(f"[+] Login successful via JSON API")
                    self.token = data.get("token")
                    return True
        except Exception as e:
            print(f"[-] JSON API login failed: {e}")
        
        # Method 2: Form-based login
        try:
            login_data = {
                "name": self.username,
                "pswd": self.password,
                "action": "login"
            }
            
            resp = self.session.post(
                f"{base_url}/",
                data=login_data,
                timeout=5
            )
            
            if resp.status_code == 200 and "error" not in resp.text.lower():
                print(f"[+] Login successful via form POST")
                return True
        except Exception as e:
            print(f"[-] Form login failed: {e}")
        
        # Method 3: D-Link DWR/DAP style
        try:
            resp = self.session.post(
                f"{base_url}/login.cgi",
                data={
                    "username": self.username,
                    "password": self.password
                },
                timeout=5
            )
            
            if resp.status_code in [200, 302]:
                print(f"[+] Login successful via login.cgi")
                return True
        except Exception as e:
            print(f"[-] login.cgi failed: {e}")
        
        # Method 4: Basic Auth
        try:
            resp = self.session.get(
                f"{base_url}/",
                auth=(self.username, self.password),
                timeout=5
            )
            
            if resp.status_code == 200:
                print(f"[+] Login successful via Basic Auth")
                return True
        except Exception as e:
            print(f"[-] Basic Auth failed: {e}")
        
        return False
    
    def get_device_info(self):
        """Get router model and info"""
        base_url = f"https://{self.host}"
        
        endpoints = [
            "/api/device",
            "/api/status",
            "/DevInfo.txt",
            "/device.htm",
            "/info.htm"
        ]
        
        for endpoint in endpoints:
            try:
                resp = self.session.get(f"{base_url}{endpoint}", timeout=5)
                if resp.status_code == 200 and len(resp.text) > 50:
                    print(f"[+] Device info from {endpoint}:")
                    print(resp.text[:500])
                    return resp.text
            except:
                pass
        
        return None
    
    def add_port_forward(self, name, internal_ip, internal_port, external_port=None, protocol="tcp"):
        """Add port forwarding rule"""
        base_url = f"https://{self.host}"
        external_port = external_port or internal_port
        
        # D-Link virtual server / port forwarding API variations
        
        # Method 1: Modern D-Link API
        try:
            rule = {
                "name": name,
                "protocol": protocol.upper(),
                "publicPort": str(external_port),
                "privatePort": str(internal_port),
                "localIp": internal_ip,
                "enabled": "true"
            }
            
            resp = self.session.post(
                f"{base_url}/api/virtualserver/add",
                json=rule,
                timeout=5
            )
            
            if resp.status_code == 200:
                result = resp.json()
                if result.get("status") == "ok" or result.get("result") == "success":
                    print(f"[+] Port forward added via API: {external_port} -> {internal_ip}:{internal_port}")
                    return True
        except Exception as e:
            print(f"[-] API method failed: {e}")
        
        # Method 2: Form-based
        try:
            data = {
                "action": "add",
                "name": name,
                "protocol": protocol,
                "public_port": str(external_port),
                "private_port": str(internal_port),
                "local_ip": internal_ip,
                "enabled": "1"
            }
            
            resp = self.session.post(
                f"{base_url}/virtual_server.cgi",
                data=data,
                timeout=5
            )
            
            if resp.status_code in [200, 302]:
                print(f"[+] Port forward added via CGI: {external_port} -> {internal_ip}:{internal_port}")
                return True
        except Exception as e:
            print(f"[-] CGI method failed: {e}")
        
        # Method 3: D-Link DIR-8xx style
        try:
            rule = {
                "enabled": True,
                "description": name,
                "protocol": protocol,
                "publicPort": external_port,
                "privatePort": internal_port,
                "localIp": internal_ip
            }
            
            config = {"virtualServerList": [rule]}
            
            resp = self.session.post(
                f"{base_url}/api/config",
                json={"virtualserver": config},
                timeout=5
            )
            
            if resp.status_code == 200:
                print(f"[+] Port forward added via config API")
                return True
        except Exception as e:
            print(f"[-] Config API failed: {e}")
        
        return False
    
    def list_port_forwards(self):
        """List existing port forwarding rules"""
        base_url = f"https://{self.host}"
        
        endpoints = [
            "/api/virtualserver/list",
            "/api/virtualserver",
            "/virtual_server.htm",
            "/api/config/virtualserver"
        ]
        
        for endpoint in endpoints:
            try:
                resp = self.session.get(f"{base_url}{endpoint}", timeout=5)
                if resp.status_code == 200:
                    print(f"[+] Port forwards from {endpoint}:")
                    print(resp.text[:1000])
                    return resp.text
            except:
                pass
        
        return None
    
    def save_config(self):
        """Save configuration changes"""
        base_url = f"https://{self.host}"
        
        try:
            resp = self.session.post(f"{base_url}/api/config/save", timeout=5)
            if resp.status_code == 200:
                print("[+] Configuration saved")
                return True
        except:
            pass
        
        try:
            resp = self.session.get(f"{base_url}/save.cgi", timeout=5)
            if resp.status_code == 200:
                print("[+] Configuration saved via CGI")
                return True
        except:
            pass
        
        return False


def main():
    if len(sys.argv) < 4:
        print("Usage: python dlink_portforward.py <router_ip> <username> <password> [internal_ip] [port]")
        print("Example: python dlink_portforward.py 192.168.0.1 admin password 192.168.0.172 5000")
        sys.exit(1)
    
    router_ip = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]
    internal_ip = sys.argv[4] if len(sys.argv) > 4 else "192.168.0.172"
    port = int(sys.argv[5]) if len(sys.argv) > 5 else 5000
    
    print(f"[*] Connecting to D-Link router at {router_ip}")
    print(f"[*] Username: {username}")
    
    router = DLinkRouter(host=router_ip, username=username, password=password)
    
    # Login
    if not router.login():
        print("[-] Failed to login to router!")
        sys.exit(1)
    
    # Get device info
    print("\n[*] Getting device info...")
    router.get_device_info()
    
    # List existing rules
    print("\n[*] Checking existing port forwards...")
    router.list_port_forwards()
    
    # Add port forward
    print(f"\n[*] Adding port forward: {port} -> {internal_ip}:{port}")
    if router.add_port_forward(
        name="C2Server",
        internal_ip=internal_ip,
        internal_port=port,
        external_port=port,
        protocol="tcp"
    ):
        print("[+] Port forward added successfully!")
        
        # Save config
        router.save_config()
    else:
        print("[-] Failed to add port forward")
        print("[*] You may need to add it manually via router web interface")


if __name__ == "__main__":
    main()
