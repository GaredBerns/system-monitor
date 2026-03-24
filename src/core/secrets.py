"""Secrets management with encryption."""
import os
import json
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional

class SecretsManager:
    """Manage encrypted secrets."""
    
    def __init__(self, key_file: Path, secrets_file: Path):
        self.key_file = key_file
        self.secrets_file = secrets_file
        self._cipher = None
        self._secrets = {}
        self._load()
    
    def _load(self):
        """Load encryption key and secrets."""
        # Load or generate key
        if self.key_file.exists():
            key = self.key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            self.key_file.parent.mkdir(parents=True, exist_ok=True)
            self.key_file.write_bytes(key)
            os.chmod(self.key_file, 0o600)
        
        self._cipher = Fernet(key)
        
        # Load secrets
        if self.secrets_file.exists():
            try:
                encrypted = self.secrets_file.read_bytes()
                decrypted = self._cipher.decrypt(encrypted)
                self._secrets = json.loads(decrypted)
            except Exception:
                self._secrets = {}
    
    def _save(self):
        """Save encrypted secrets."""
        data = json.dumps(self._secrets).encode()
        encrypted = self._cipher.encrypt(data)
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
        self.secrets_file.write_bytes(encrypted)
        os.chmod(self.secrets_file, 0o600)
    
    def set(self, key: str, value: str):
        """Set secret value."""
        self._secrets[key] = value
        self._save()
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get secret value."""
        return self._secrets.get(key, default)
    
    def delete(self, key: str):
        """Delete secret."""
        if key in self._secrets:
            del self._secrets[key]
            self._save()
    
    def list_keys(self) -> list:
        """List all secret keys."""
        return list(self._secrets.keys())
    
    def encrypt_string(self, data: str) -> str:
        """Encrypt a string."""
        return self._cipher.encrypt(data.encode()).decode()
    
    def decrypt_string(self, data: str) -> str:
        """Decrypt a string."""
        return self._cipher.decrypt(data.encode()).decode()

# Global instance
_secrets_manager = None

def get_secrets_manager(base_dir: Path = None) -> SecretsManager:
    """Get global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        if base_dir is None:
            base_dir = Path(__file__).parent.parent.parent  # project root
        key_file = base_dir / "data" / ".secrets_key"
        secrets_file = base_dir / "data" / ".secrets.enc"
        _secrets_manager = SecretsManager(key_file, secrets_file)
    return _secrets_manager
