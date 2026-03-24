"""Database models using SQLAlchemy."""
from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, scoped_session
from datetime import datetime
import json

Base = declarative_base()

class User(Base):
    """User model."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    role = Column(String(32), default='operator')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Agent(Base):
    """Agent model."""
    __tablename__ = 'agents'
    
    id = Column(String(64), primary_key=True)
    hostname = Column(String(255))
    username = Column(String(255))
    os = Column(String(255))
    arch = Column(String(64))
    ip_external = Column(String(64))
    ip_internal = Column(String(64))
    platform_type = Column(String(64), default='unknown')
    tags = Column(Text, default='[]')
    group_name = Column(String(64), default='default', index=True)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_alive = Column(Boolean, default=True, index=True)
    sleep_interval = Column(Integer, default=5)
    jitter = Column(Integer, default=0)
    note = Column(Text, default='')
    
    tasks = relationship('Task', back_populates='agent', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'hostname': self.hostname,
            'username': self.username,
            'os': self.os,
            'arch': self.arch,
            'ip_external': self.ip_external,
            'ip_internal': self.ip_internal,
            'platform_type': self.platform_type,
            'tags': json.loads(self.tags) if self.tags else [],
            'group_name': self.group_name,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'is_alive': self.is_alive,
            'sleep_interval': self.sleep_interval,
            'jitter': self.jitter,
            'note': self.note
        }

class Task(Base):
    """Task model."""
    __tablename__ = 'tasks'
    
    id = Column(String(64), primary_key=True)
    agent_id = Column(String(64), ForeignKey('agents.id'), nullable=False, index=True)
    task_type = Column(String(64), nullable=False)
    payload = Column(Text, nullable=False)
    status = Column(String(32), default='pending', index=True)
    result = Column(Text, default='')
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    agent = relationship('Agent', back_populates='tasks')
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'task_type': self.task_type,
            'payload': self.payload,
            'status': self.status,
            'result': self.result,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class Log(Base):
    """Log model."""
    __tablename__ = 'logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event = Column(String(255), nullable=False, index=True)
    details = Column(Text)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'event': self.event,
            'details': self.details,
            'ts': self.ts.isoformat() if self.ts else None
        }

class Listener(Base):
    """Listener model."""
    __tablename__ = 'listeners'
    
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    protocol = Column(String(32), default='http')
    host = Column(String(255), default='0.0.0.0')
    port = Column(Integer, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'protocol': self.protocol,
            'host': self.host,
            'port': self.port,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Config(Base):
    """Config model."""
    __tablename__ = 'config'
    
    key = Column(String(255), primary_key=True)
    value = Column(Text, default='')
    
    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value
        }

class ScheduledTask(Base):
    """Scheduled task model."""
    __tablename__ = 'scheduled_tasks'
    
    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    task_type = Column(String(64), default='cmd')
    payload = Column(Text, nullable=False)
    target = Column(String(64), default='all')
    interval_sec = Column(Integer, default=3600)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'task_type': self.task_type,
            'payload': self.payload,
            'target': self.target,
            'interval_sec': self.interval_sec,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# Database session management
_engine = None
_session_factory = None

def init_db(database_url: str):
    """Initialize database."""
    global _engine, _session_factory
    
    _engine = create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600
    )
    
    # Create tables
    Base.metadata.create_all(_engine)
    
    # Create session factory
    _session_factory = scoped_session(sessionmaker(bind=_engine))
    
    return _engine

def get_session():
    """Get database session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _session_factory()

def close_session():
    """Close database session."""
    if _session_factory:
        _session_factory.remove()
