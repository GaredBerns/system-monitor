"""Unit tests for core functionality."""
import pytest
import json
from pathlib import Path
import sys

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.validation import TaskCreate, AgentRegister, validate_request
from src.core.secrets import SecretsManager
from src.utils.rate_limit import RateLimiter

# ==================== VALIDATION TESTS ====================

def test_task_create_valid():
    """Test valid task creation."""
    data = {
        "agent_id": "test-agent-123",
        "type": "cmd",
        "payload": "whoami"
    }
    is_valid, result = validate_request(TaskCreate, data)
    assert is_valid
    assert result["agent_id"] == "test-agent-123"
    assert result["type"] == "cmd"

def test_task_create_invalid_type():
    """Test invalid task type."""
    data = {
        "agent_id": "test-agent",
        "type": "invalid_type",
        "payload": "test"
    }
    is_valid, result = validate_request(TaskCreate, data)
    assert not is_valid
    assert "error" in result

def test_task_create_invalid_agent_id():
    """Test invalid agent ID format."""
    data = {
        "agent_id": "test agent with spaces",
        "type": "cmd",
        "payload": "test"
    }
    is_valid, result = validate_request(TaskCreate, data)
    assert not is_valid

def test_agent_register_valid():
    """Test valid agent registration."""
    data = {
        "hostname": "test-host",
        "username": "test-user",
        "os": "Linux",
        "arch": "x86_64"
    }
    is_valid, result = validate_request(AgentRegister, data)
    assert is_valid
    assert result["hostname"] == "test-host"

def test_agent_register_invalid_id():
    """Test invalid agent ID."""
    data = {
        "id": "invalid id with spaces!",
        "hostname": "test",
        "username": "test",
        "os": "Linux",
        "arch": "x86_64"
    }
    is_valid, result = validate_request(AgentRegister, data)
    assert not is_valid

# ==================== SECRETS TESTS ====================

def test_secrets_manager_set_get(tmp_path):
    """Test secrets set and get."""
    key_file = tmp_path / "key"
    secrets_file = tmp_path / "secrets"
    
    sm = SecretsManager(key_file, secrets_file)
    sm.set("test_key", "test_value")
    
    assert sm.get("test_key") == "test_value"
    assert sm.get("nonexistent", "default") == "default"

def test_secrets_manager_persistence(tmp_path):
    """Test secrets persistence."""
    key_file = tmp_path / "key"
    secrets_file = tmp_path / "secrets"
    
    # Create and save
    sm1 = SecretsManager(key_file, secrets_file)
    sm1.set("key1", "value1")
    sm1.set("key2", "value2")
    
    # Load in new instance
    sm2 = SecretsManager(key_file, secrets_file)
    assert sm2.get("key1") == "value1"
    assert sm2.get("key2") == "value2"

def test_secrets_manager_delete(tmp_path):
    """Test secrets deletion."""
    key_file = tmp_path / "key"
    secrets_file = tmp_path / "secrets"
    
    sm = SecretsManager(key_file, secrets_file)
    sm.set("test", "value")
    assert sm.get("test") == "value"
    
    sm.delete("test")
    assert sm.get("test") is None

def test_secrets_manager_encrypt_decrypt(tmp_path):
    """Test string encryption/decryption."""
    key_file = tmp_path / "key"
    secrets_file = tmp_path / "secrets"
    
    sm = SecretsManager(key_file, secrets_file)
    
    original = "sensitive data"
    encrypted = sm.encrypt_string(original)
    decrypted = sm.decrypt_string(encrypted)
    
    assert encrypted != original
    assert decrypted == original

# ==================== RATE LIMIT TESTS ====================

def test_rate_limiter_allow():
    """Test rate limiter allows requests within limit."""
    limiter = RateLimiter()
    
    # First request should be allowed
    allowed, info = limiter.is_allowed("test_key", limit=5, window=60)
    assert allowed
    assert info["remaining"] == 4

def test_rate_limiter_block():
    """Test rate limiter blocks requests over limit."""
    limiter = RateLimiter()
    
    # Make requests up to limit
    for i in range(5):
        allowed, _ = limiter.is_allowed("test_key", limit=5, window=60)
        assert allowed
    
    # Next request should be blocked
    allowed, info = limiter.is_allowed("test_key", limit=5, window=60)
    assert not allowed
    assert info["remaining"] == 0
    assert "retry_after" in info

def test_rate_limiter_reset():
    """Test rate limiter reset."""
    limiter = RateLimiter()
    
    # Fill up limit
    for i in range(5):
        limiter.is_allowed("test_key", limit=5, window=60)
    
    # Should be blocked
    allowed, _ = limiter.is_allowed("test_key", limit=5, window=60)
    assert not allowed
    
    # Reset
    limiter.reset("test_key")
    
    # Should be allowed again
    allowed, _ = limiter.is_allowed("test_key", limit=5, window=60)
    assert allowed

def test_rate_limiter_window_expiry():
    """Test rate limiter window expiry."""
    import time
    limiter = RateLimiter()
    
    # Make request
    allowed, _ = limiter.is_allowed("test_key", limit=2, window=1)
    assert allowed
    
    # Fill limit
    allowed, _ = limiter.is_allowed("test_key", limit=2, window=1)
    assert allowed
    
    # Should be blocked
    allowed, _ = limiter.is_allowed("test_key", limit=2, window=1)
    assert not allowed
    
    # Wait for window to expire
    time.sleep(1.1)
    
    # Should be allowed again
    allowed, _ = limiter.is_allowed("test_key", limit=2, window=1)
    assert allowed

# ==================== RUN TESTS ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
