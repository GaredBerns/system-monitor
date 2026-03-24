# SKILLS — Навыки и Инструменты

## ЯЗЫКИ ПРОГРАММИРОВАНИЯ
Python: Automation, exploits, tools | JavaScript/Node.js: Web, APIs, automation | C/C++: System programming, shellcode, malware | Go: Tools, cross-platform binaries | Rust: High-performance tools | PowerShell: Windows automation, post-exploitation | Bash: Linux automation, scripting | PHP: Web exploitation, shells | Ruby: Metasploit modules, tools | Java: Enterprise exploitation, deserialization

## SHELLCODE DEVELOPMENT
x86 Assembly: 32-bit shellcode | x64 Assembly: 64-bit shellcode | ARM Assembly: Mobile/IoT shellcode | Position-Independent Code | Null-byte free shellcode | Alphanumeric shellcode | Encoded shellcode | Staged vs Stageless

## MALWARE TECHNIQUES
Process Injection: DLL, Process Hollowing, APC, Early Bird | Memory Manipulation: ReadProcessMemory, WriteProcessMemory | Hooking: IAT, Inline, VTable | Reflective Loading: Self-loading DLL/EXE | Unhooking: Restore clean ntdll | AMSI Bypass: Patching, Reflection | ETW Bypass: Patching | Direct Syscalls: Assembly stubs

## OBFUSCATION
Code: Control flow flattening, dead code | String: Encryption, encoding | Binary: Packing, encryption | PowerShell: Encoding, chaining | JavaScript: Minification, encoding | Anti-Debugging: IsDebuggerPresent, timing checks | Anti-VM: Registry, MAC, processes, files | Anti-Sandbox: Timing, resources, user activity

## WEB DEVELOPMENT (for understanding targets)
Frontend: HTML, CSS, JavaScript frameworks | Backend: Node.js, Python, PHP, Java, .NET | Databases: MySQL, PostgreSQL, MongoDB, Redis | APIs: REST, GraphQL, WebSocket | Authentication: JWT, OAuth, SAML | Cloud: AWS, Azure, GCP

## CRYPTOGRAPHY
Symmetric: AES, DES, ChaCha20 | Asymmetric: RSA, ECC, DSA | Hashing: SHA, MD5, bcrypt | Key Exchange: DH, ECDH | Digital Signatures: RSA, ECDSA | PKI: Certificates, chains | Attacks: Padding oracle, Timing, Downgrade

## BYPASS TECHNIQUES

### CLOUDFLARE BYPASS
Origin IP Discovery: DNS History (SecurityTrails, ViewDNS.info), SSL Certificate Logs (crt.sh, Censys, Shodan), Subdomain Enumeration (subfinder, amass, httpx), MX/NS/TXT Records, Email Headers, JS Files, Wayback Machine
WAF Bypass: SQLi (/**/, %0a, /*!OR*/, BETWEEN, LIKE, case variation), XSS (img/svg/body events, no spaces, no alert, no parentheses), LFI (Double encoding, Unicode, PHP wrappers), RCE (${IFS}, %09, base64, variable concatenation)
Tools: cloudscraper, CloudFlair, HatCloud, sqlmap tamper scripts, ffuf, httpx

### SANDBOX BYPASS
Detection: Hardware (RAM<4GB, CPU<2, Disk<60GB), System (Uptime<10min, Processes<50), VM (MAC prefixes, Registry keys, Processes, Files), Debugger (IsDebuggerPresent, NtGlobalFlag, Hardware breakpoints), Analysis Tools (Process names), Time (Sleep acceleration), User Activity (Recent files, idle time, mouse movement)
Evasion: Time-Based (Long sleep, Wait for user interaction), Environment (Username/computer name checks), Process Injection, Direct Syscalls, AMSI Bypass, ETW Bypass, Unhooking, LoLBins (certutil, bitsadmin, mshta, regsvr32, msbuild)

### AV/EDR BYPASS
Windows Defender: Add-MpPreference (exclusions), Set-MpPreference -DisableRealtimeMonitoring, Tamper Protection bypass (Registry modification)
CrowdStrike/Carbon Black: Direct syscalls, Kernel callbacks bypass, Living off the land binaries, Process injection into trusted processes

### BROWSER SANDBOX BYPASS
Chrome: Mojo IPC vulnerabilities, GPU process escape, Network service escape, Site isolation bypass
Firefox: IPC message manipulation, Parent process compromise, Extension vulnerabilities

### CONTAINER ESCAPE
Docker: Privileged containers, Docker socket exposure, Kernel vulnerabilities, Namespace breakout
Kubernetes: Pod security policies bypass, Service account token abuse, Node escalation

## HARDWARE ATTACKS

### DMA ATTACKS
Tools: PCILeech, Inception, PCIe exploitation, Thunderbolt
Techniques: Memory read/write, Kernel manipulation, Credential extraction, Screen unlocking

### JTAG/DEBUG
Firmware extraction, Debug interface exploitation, Boundary scan, UART access, SWD debugging

### SIDE-CHANNEL
Timing: Cryptographic timing, Response time analysis, Cache timing
Power: SPA (Simple Power Analysis), DPA (Differential Power Analysis)
EM: Electromagnetic radiation analysis, TEMPEST attacks
Acoustic: CPU whine, Keyboard sounds, Fan noise analysis
Optical: Screen reflection, LED indicators, Power LED analysis

### FAULT INJECTION
Voltage Glitching: Power supply manipulation, Bypass checks, Cause undefined behavior
Clock Glitching: Speed up/slow down clock, Skip instructions, Race condition injection
EM Fault: Strong EM pulse, Bit flips, Rowhammer-like effects
Laser Fault: Target specific transistors, Precise bit manipulation

### RFID/NFC
Cloning: Proxmark, RFID cloner, HID emulator
Relay attacks: Distance bounding bypass, Time delay exploitation
Downgrade: Force older protocol, Weak encryption exploitation

## CLOUD SECURITY

### AWS
Enumeration: S3 enumeration, IAM enumeration, Lambda enumeration
Exploitation: S3 bucket access, IAM privilege escalation, Lambda injection, EC2 metadata (169.254.169.254)
Tools: Pacu, AWS CLI, CloudGoat

### AZURE
Enumeration: Blob enumeration, Runbook enumeration, Logic apps enumeration
Exploitation: Blob access, Runbook exploitation, Logic apps exploitation, VM metadata
Tools: MicroBurst, Azure CLI, Stormspotter

### GCP
Enumeration: Storage enumeration, Cloud functions enumeration, IAM enumeration
Exploitation: Storage access, Cloud functions exploitation, IAM privilege escalation, Compute metadata
Tools: GCPwn, gcloud CLI

### CONTAINER SECURITY
Docker: Docker escape (privileged containers, socket exposure), Container enumeration, Image exploitation
Kubernetes: K8s exploitation (service account token, RBAC bypass), Pod breakout, Node escalation
Tools: cdk, kube-hunter, checkov

## MOBILE SECURITY

### ANDROID
APK decompilation: apktool, jadx, dex2jar
Intent injection: Intent redirection, Intent spoofing
Root detection bypass: Magisk, SafetyNet bypass
Malware: Payload delivery, Persistence, Data theft
Tools: Drozer, Frida, Objection, MobSF

### iOS
IPA analysis: Class-dump, Hopper, Ghidra
Jailbreak detection bypass: Liberty, unc0ver
Keychain extraction: Keychain-dumper
Malware: Payload delivery, Persistence, Data theft
Tools: Frida, Objection, Clutch, MobSF

## SOCIAL ENGINEERING

### PHISHING
Clone sites: HTTrack, wget, Manual clone
Typosquatting: Domain registration, Similar domains
Homograph: Unicode lookalikes, IDN homograph attacks
Email spoofing: SPF/DKIM/DMARC bypass
Tools: Gophish, SET (Social Engineering Toolkit), Evilginx2

### DEEPFAKES
Video: DeepFaceLab, FaceSwap, First Order Motion Model
Voice: Real-Time Voice Cloning, Tacotron, SV2TTS
Real-time: DeepFaceLab real-time, Avatarify
Detection bypass: High-quality generation, Consistent artifacts

### OSINT
Data harvesting: theHarvester, SpiderFoot, Maltego
Profile building: Social-Analyzer, Sherlock, Maigret
Target reconnaissance: recon-ng, Amass, Subfinder
Tools: Maltego, Shodan, Censys, SpiderFoot, theHarvester

## TOOLS & AUTOMATION

### RECONNAISSANCE
Subdomain enumeration: subfinder, amass, httpx, Sublist3r
Port scanning: nmap, masscan, rustscan
Directory enumeration: ffuf, gobuster, dirsearch, feroxbuster
Vulnerability scanning: nuclei, nikto, wpscan
Cloud enumeration: CloudEnum, S3Scanner, GCPBucketBrute

### EXPLOITATION
Web: sqlmap, XSStrike, tplmap, XXEinjector, NoSQLMap
Network:Responder, Impacket, mitm6, bettercap
Binary: GDB, pwntools, ROPgadget, one_gadget
Frameworks: Metasploit, ExploitDB, Searchsploit

### POST-EXPLOITATION
Privilege escalation: LinPEAS, WinPEAS, Linux Exploit Suggester, Windows Exploit Suggester
Persistence: Empire, Covenant, Sliver, Metasploit
Lateral movement: CrackMapExec, Impacket, Evil-WinRM, SSHuttle
Data exfil: DNS exfil, ICMP exfil, HTTP exfil, Steganography

### DEVELOPMENT
Languages: Python, Go, Rust, C/C++, JavaScript, PowerShell
Frameworks: Flask, FastAPI, Gin, Express, ASP.NET
Build tools: Make, CMake, Cargo, pip, npm
Version control: Git, GitHub, GitLab

### ANALYSIS
Reverse engineering: Ghidra, IDA Pro, Binary Ninja, radare2
Forensics: Autopsy, Volatility, FTK, EnCase
Network: Wireshark, tcpdump, Zeek, Suricata
Debugging: GDB, x64dbg, OllyDbg, WinDbg
