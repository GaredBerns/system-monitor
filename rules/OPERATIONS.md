# OPERATIONS — Операционные Протоколы

## C2 OPERATIONS

### ПРОТОКОЛЫ
HTTP/HTTPS: GET requests (URL params), POST requests (body), Headers (custom), Cookies (session), URI paths (encoded commands), Beaconing (periodic check-in)
DNS: A record (IP encoding), TXT record (data exfil), CNAME (domain encoding), DNS tunneling (full channel), Subdomain encoding
ICMP: Echo request/reply (data in payload), ICMP tunneling, Ping exfil
WebSocket: Full duplex, Encrypted (WSS), Persistent, Custom protocol
Domain Fronting: CDN abuse (Cloudflare, AWS CloudFront, Google Cloud CDN, Azure CDN)
Social Media: Twitter (Posts/DMs), Telegram (Channels/Groups), Reddit (Posts/Comments), GitHub (Repos/Gists), Gmail (Drafts/Emails)

### АРХИТЕКТУРА
Centralized: Single server, Multiple ports, Load balancing, Failover
Decentralized: Mesh network (P2P), Multiple servers, Peer-to-peer, Blockchain
Redundancy: Multiple domains, Multiple IPs, Multiple protocols, Geographic distribution
Resilience: Fast flux, Double flux, DGA (Domain Generation Algorithm), IP rotation

### IMPLANT КОММУНИКАЦИЯ
Beaconing: Interval, Jitter, Sleep time, Working hours
Staging: Staged (download then execute), Stageless (single executable), Shellcode, Reflective (memory loading)
Encryption: AES, RSA, XOR, Custom
Encoding: Base64, Hex, Custom, Multi-layer

### ФРЕЙМВОРКИ
Open Source: Metasploit (msfconsole, msfvenom), Covenant (.NET), Sliver (Go), Empire (PowerShell), PoshC2, Mythic (Multi-agent)
Commercial: Cobalt Strike, Core Impact, Canvas, Brute Ratel
Custom: Python (Flask/Django), Go (Gin/Echo), Node.js (Express), C# (ASP.NET), Rust (Actix/Rocket)

### OPSEC
Инфраструктура: Bulletproof hosting, VPS rotation, Domain privacy, SSL certificates, Geographic distribution
Сетевая защита: Firewall rules, IP whitelisting, Rate limiting, Geo-blocking, VPN/Proxy
Обнаружение: IDS/IPS evasion, AV evasion, EDR evasion, Sandbox evasion, Analysis evasion
Реагирование: Burn server, Rotate infrastructure, Change protocol, Go dark, Clean up

### ИНСТРУМЕНТЫ
Фреймворки: msfconsole, Covenant (Web UI), Sliver (CLI/GUI), Empire (CLI), Mythic (Web UI)
Генераторы: msfvenom, Donut (shellcode), sRDI (reflective DLL), SharpGen (.NET)
Туннелирование: dnscat2 (DNS), iodine (DNS), icmpsh (ICMP), Chisel (TCP/UDP)
Domain Fronting: DomainFronting, CDNBypass, Custom scripts

---

## PERSISTENCE

### WINDOWS (15+ методов)
Registry: HKCU\Software\Microsoft\Windows\CurrentVersion\Run, HKLM\Software\Microsoft\Windows\CurrentVersion\Run, Winlogon Helper, Service, LSA Authentication Packages, Time Providers, AppInit_DLLs, Image File Execution Options
Scheduled Tasks: schtasks /create, WMI event subscription, PowerShell Empire persistence
Services: sc create, Service creation, Service hijacking, DLL search order hijacking
WMI: __EventFilter, __EventConsumer, __FilterToConsumerBinding, WMI event subscription
File System: Startup folder, DLL search order hijacking, DLL side-loading, COM hijacking
Boot: Bootkit, UEFI/BIOS implants, VBR hijacking
Other: PowerShell profiles, Office macros, Browser extensions, LNK files, Shortcut hijacking

### LINUX (12+ методов)
Cron: /etc/crontab, /etc/cron.d/, /etc/cron.daily/, /var/spool/cron/, User crontab
Systemd: /etc/systemd/system/, ~/.config/systemd/user/, systemd service creation
Init: /etc/init.d/, /etc/rc.local, init.d scripts
Shell: ~/.bashrc, ~/.bash_profile, ~/.profile, /etc/profile
SSH: ~/.ssh/authorized_keys, SSH key persistence
Other: At jobs, Incron, Web shells, Rootkits, Kernel modules, LKM rootkits

### macOS (10+ методов)
Launch Agents: ~/Library/LaunchAgents/, /Library/LaunchAgents/
Launch Daemons: /Library/LaunchDaemons/
Login Items: System Preferences → Users & Groups → Login Items
Cron: /usr/lib/cron/tabs/
Other: Startup Items, Kernel extensions (kext), Spotlight plugins, QuickLook plugins, Login hooks, At jobs

### FIRMWARE
UEFI: UEFI implants, NVRAM variables, DXE drivers, SMM modules
BIOS: BIOS implants, Option ROMs
Bootkit: MBR bootkit, VBR bootkit, Boot sector
Hardware: Hardware implants, Modified chips, Malicious cables

---

## SURVEILLANCE

### ЦИФРОВОЕ НАБЛЮДЕНИЕ
Компьютер: Keylogging (Hardware/Software), Screen capture, Clipboard monitoring, File monitoring, Process monitoring, Browser monitoring
Сеть: Traffic capture (Wireshark, tcpdump), DNS monitoring, SSL interception (MITM proxy), Email monitoring, Chat monitoring
Мобильный: GPS tracking, Call logging, SMS capture, App monitoring, Camera access, Microphone access
Соцсети: Profile monitoring, Friend mapping, Location tracking, Content analysis, Metadata extraction
Облако: Cloud storage access, Email account access, Photo library, Contact sync, Calendar access

### ФИЗИЧЕСКОЕ НАБЛЮДЕНИЕ
Слежка: Foot surveillance, Vehicle surveillance, Static observation, Multiple teams, Aerial (drone)
Техсредства: Hidden cameras, Audio bugs, GPS trackers, RFID tracking, Night vision
Точки: Safe houses, Vehicles, Public spaces, Online
Документирование: Photography, Video recording, Notes, Timestamps

### OSINT / OSUR
Разведка: Name search, Address history, Phone numbers, Email addresses, Social media, Public records
Инструменты: Maltego, Shodan, Censys, theHarvester, recon-ng, SpiderFoot, Social-Analyzer
Источники: Public records, Social media, People search, Data brokers, Breach databases, Dark web
Анализ: Network mapping, Timeline construction, Geolocation, Financial, Digital footprint

### COUNTER-SURVEILLANCE
Обнаружение: Physical detection, Technical detection (bug sweeping), Digital detection, Behavioral
Противодействие: Evasion techniques, Misdirection, Technical countermeasures, Digital hygiene
OPSEC: Cover identity, Blending in, Communication security, Evidence handling
Инструменты: RF detectors, Non-linear junction detectors, Thermal cameras, Spectrum analyzers

---

## ANTI-FORENSICS

### УНИЧТОЖЕНИЕ ДАННЫХ
Файлы: Secure deletion (DoD 5220.22-M, Gutmann), File wiping, Free space wiping, Slack space wiping, MFT cleaning
Диски: Full disk encryption (BitLocker, LUKS, VeraCrypt), Secure erase (ATA), Physical destruction (shredding, degaussing), Partition wiping
SSD: TRIM exploitation, Secure Erase, Encryption, Physical destruction
Мобильные: Factory reset, Encryption reset, Secure folder, Remote wipe
Облако: Account deletion, Data purging, Backup deletion, Metadata removal

### МАНИПУЛЯЦИЯ ВРЕМЕНЕМ
Timestamps: File creation time ($MFT), Modification time (mtime), Access time (atime), Entry modified (NTFS $STANDARD_INFORMATION), MAC times
Tools: Timestomp, Set-MacAttribute (PowerShell), touch (Linux), Metasploit timestamp module
Event logs: Log clearing, Log injection, Log modification, Log disabling
Timeline: System time, NTP manipulation, Timezone changes, Application timestamps

### ЛОЖНЫЕ СЛЕДЫ
Файловые: Fake files, Wrong timestamps, Wrong ownership, Wrong locations, Encrypted decoys
Сетевые: Fake IP (proxy/VPN), Fake user-agent, Fake location (GPS spoofing), Fake device (HW ID spoofing), Traffic obfuscation
Логические: Fake logins, Fake activity, Fake timestamps, Fake locations
Поведенческие: Normal activity, Scheduled activity, Multiple identities, Misdirection

### LOG MANIPULATION
Windows: wevtutil, Security log (4624, 4634, 4688), System log, Application log, PowerShell log, Prefetch
Linux: /var/log/*, journalctl, auth.log, syslog, apache/nginx logs, auditd
macOS: system.log, security.log, install.log, unified logging
Cloud: AWS CloudTrail, Azure Activity Log, GCP Audit Logs, Application logs, Database logs

### ANTI-MEMORY FORENSICS
Memory: Process hollowing, Memory obfuscation, Heap spraying, Stack manipulation
Anti-dumping: Anti-debugging, Process protection, Memory encryption, Hook protection
Cleaning: Secure memory allocation (mlock), Memory zeroing, Key material deletion, Cache clearing

### ИНСТРУМЕНТЫ
Wiping: DBAN, shred, srm, Eraser, BleachBit
Timestamp: Timestomp, Set-MacAttribute, touch, Metasploit timestamp
Log: wevtutil, logrotate, auditctl, Clear-EventLog
Encryption: VeraCrypt, BitLocker, LUKS, FileVault

---

## FINANCIAL OPERATIONS

### КРИПТОВАЛЮТЫ
Анонимные: Monero (XMR - Ring signatures, Stealth addresses), Zcash (ZEC - zk-SNARKs), Dash (PrivateSend, CoinJoin), Bitcoin mixing (CoinJoin, CoinSwap, Atomic swaps)
Миксеры: Centralized (ChipMixer, Blender.io), Decentralized (Tornado Cash, Wasabi Wallet), Chain hopping, Layer 2 (Lightning Network)
Cold storage: Hardware wallets (Ledger, Trezor), Paper wallets, Air-gapped systems, Multi-sig
Private key extraction: Memory extraction, Clipboard monitoring, Browser extraction, Hardware extraction, Seed phrase recovery
DeFi exploitation: Flash loans (Aave, dYdX, Uniswap), Oracle manipulation, Reentrancy, Governance attacks, Bridge exploitation

### ТРАДИЦИОННЫЕ ФИНАНСЫ
Банки: Account takeover, Wire fraud (BEC), Credit card fraud, Loan fraud, Insider trading
Кардинг: CVV dumps, Fullz, BIN lookup, Carding shops, Cashout methods (money mules, crypto)
Money laundering: Structuring (smurfing), Layering (shell companies), Integration (real estate), Trade-based, Casino/Gambling
Tax evasion: Offshore accounts, Shell companies, Transfer pricing, Crypto non-declaration

### АНОНИМНОСТЬ И OPSEC
Кошельки: HD wallets, Multi-signature, Watch-only, Hardware
Транзакции: CoinJoin, CoinSwap, Chain hopping, Lightning Network
Инфраструктура: VPN chaining, Tor, I2P, Proxy chains
Identity: Fake identities, Mix real/fake, Jurisdiction shopping, Compartmentalization

### ИНСТРУМЕНТЫ
Крипто: Electrum, Wasabi, Samourai, Monero GUI, Ledger/Trezor, MetaMask
Миксеры: Tornado Cash, Wasabi Wallet, Samourai Whirlpool, Unstoppable Swaps
Анализ: Etherscan, Blockstream, CipherTrace, Elliptic, OSINT
DeFi: Uniswap, Aave, Compound, Yearn, Curve
