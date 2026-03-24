"""Input validation using Pydantic."""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import re

class AgentRegister(BaseModel):
    """Agent registration data."""
    id: Optional[str] = None
    hostname: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    os: str = Field(..., min_length=1, max_length=255)
    arch: str = Field(..., min_length=1, max_length=64)
    ip_internal: Optional[str] = None
    platform_type: str = Field(default="machine", max_length=64)
    
    @validator('id')
    def validate_id(cls, v):
        if v and (len(v) > 64 or not re.match(r'^[a-zA-Z0-9\-_]+$', v)):
            raise ValueError('Invalid agent ID format')
        return v

class TaskCreate(BaseModel):
    """Task creation data."""
    agent_id: str = Field(..., min_length=1, max_length=64)
    type: str = Field(..., min_length=1, max_length=64)
    payload: str = Field(..., min_length=1, max_length=65535)
    
    @validator('agent_id')
    def validate_agent_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9\-_]+$', v):
            raise ValueError('Invalid agent_id format')
        return v
    
    @validator('type')
    def validate_type(cls, v):
        allowed = ['cmd', 'shell', 'upload', 'download', 'kill', 'sleep', 'exec']
        if v not in allowed:
            raise ValueError(f'Invalid task type. Allowed: {allowed}')
        return v

class TaskBroadcast(BaseModel):
    """Broadcast task data."""
    type: str = Field(..., min_length=1, max_length=64)
    payload: str = Field(..., min_length=1, max_length=65535)
    target: str = Field(default="all", max_length=64)
    
    @validator('type')
    def validate_type(cls, v):
        allowed = ['cmd', 'shell', 'upload', 'download', 'kill', 'sleep', 'exec']
        if v not in allowed:
            raise ValueError(f'Invalid task type. Allowed: {allowed}')
        return v

class UserCreate(BaseModel):
    """User creation data."""
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    role: str = Field(default="operator", max_length=32)
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('Username must be alphanumeric')
        return v
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['admin', 'operator', 'viewer']:
            raise ValueError('Invalid role')
        return v

class ConfigUpdate(BaseModel):
    """Config update data."""
    webhook_discord: Optional[str] = Field(None, max_length=512)
    webhook_telegram: Optional[str] = Field(None, max_length=512)
    encryption_key: Optional[str] = Field(None, max_length=128)
    agent_token: Optional[str] = Field(None, max_length=128)
    public_url: Optional[str] = Field(None, max_length=512)
    
    @validator('public_url')
    def validate_url(cls, v):
        if v and not re.match(r'^https?://.+', v):
            raise ValueError('Invalid URL format')
        return v

class ScheduledTaskCreate(BaseModel):
    """Scheduled task creation."""
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(default="cmd", max_length=64)
    payload: str = Field(..., min_length=1, max_length=65535)
    target: str = Field(default="all", max_length=64)
    interval: int = Field(default=3600, ge=60, le=86400)

def validate_request(model_class: type[BaseModel], data: dict):
    """Validate request data against Pydantic model.
    
    Returns:
        tuple: (is_valid: bool, result: dict or model)
    """
    try:
        validated = model_class(**data)
        return True, validated.dict()
    except Exception as e:
        return False, {"error": str(e)}
