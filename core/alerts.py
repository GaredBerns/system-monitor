#!/usr/bin/env python3
"""Alerting system for critical events."""

import time
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Alert:
    """Alert data structure."""
    level: AlertLevel
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: Dict = None
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata or {}
        }

class AlertManager:
    """Manage alerts and notifications."""
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self.handlers: List[Callable] = []
        self.alert_lock = threading.Lock()
        self.max_alerts = 1000
        
        # Alert thresholds
        self.thresholds = {
            "cpu_percent": 90,
            "memory_percent": 90,
            "disk_percent": 85,
            "agent_offline_count": 10,
            "task_failure_rate": 0.5,
            "db_size_mb": 1000
        }
        
        # Cooldown to prevent alert spam
        self.cooldowns: Dict[str, float] = {}
        self.cooldown_seconds = 300  # 5 minutes
    
    def add_handler(self, handler: Callable):
        """Add alert handler (e.g., webhook, email)."""
        self.handlers.append(handler)
    
    def fire_alert(self, alert: Alert):
        """Fire an alert and notify handlers."""
        with self.alert_lock:
            # Check cooldown
            cooldown_key = f"{alert.source}:{alert.title}"
            now = time.time()
            
            if cooldown_key in self.cooldowns:
                if now - self.cooldowns[cooldown_key] < self.cooldown_seconds:
                    return  # Skip duplicate alert
            
            self.cooldowns[cooldown_key] = now
            
            # Add to history
            self.alerts.append(alert)
            if len(self.alerts) > self.max_alerts:
                self.alerts = self.alerts[-self.max_alerts:]
            
            # Notify handlers
            for handler in self.handlers:
                try:
                    threading.Thread(
                        target=handler,
                        args=(alert,),
                        daemon=True
                    ).start()
                except Exception as e:
                    print(f"[Alert] Handler error: {e}")
    
    def get_recent_alerts(self, minutes: int = 60, level: Optional[AlertLevel] = None) -> List[Alert]:
        """Get recent alerts."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        with self.alert_lock:
            alerts = [a for a in self.alerts if a.timestamp > cutoff]
            
            if level:
                alerts = [a for a in alerts if a.level == level]
            
            return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def check_system_health(self, metrics: Dict):
        """Check system metrics and fire alerts if needed."""
        system = metrics.get("system", {})
        
        # CPU alert
        cpu = system.get("cpu_percent", 0)
        if cpu > self.thresholds["cpu_percent"]:
            self.fire_alert(Alert(
                level=AlertLevel.WARNING,
                title="High CPU Usage",
                message=f"CPU usage is {cpu:.1f}% (threshold: {self.thresholds['cpu_percent']}%)",
                timestamp=datetime.now(),
                source="system_monitor",
                metadata={"cpu_percent": cpu}
            ))
        
        # Memory alert
        memory = system.get("memory_percent", 0)
        if memory > self.thresholds["memory_percent"]:
            self.fire_alert(Alert(
                level=AlertLevel.WARNING,
                title="High Memory Usage",
                message=f"Memory usage is {memory:.1f}% (threshold: {self.thresholds['memory_percent']}%)",
                timestamp=datetime.now(),
                source="system_monitor",
                metadata={"memory_percent": memory}
            ))
        
        # Disk alert
        disk = system.get("disk_percent", 0)
        if disk > self.thresholds["disk_percent"]:
            self.fire_alert(Alert(
                level=AlertLevel.ERROR,
                title="High Disk Usage",
                message=f"Disk usage is {disk:.1f}% (threshold: {self.thresholds['disk_percent']}%)",
                timestamp=datetime.now(),
                source="system_monitor",
                metadata={"disk_percent": disk}
            ))
    
    def check_agent_health(self, metrics: Dict):
        """Check agent metrics and fire alerts."""
        agents = metrics.get("agents", {})
        
        # Offline agents alert
        dead = agents.get("dead", 0)
        if dead > self.thresholds["agent_offline_count"]:
            self.fire_alert(Alert(
                level=AlertLevel.WARNING,
                title="Many Offline Agents",
                message=f"{dead} agents are offline (threshold: {self.thresholds['agent_offline_count']})",
                timestamp=datetime.now(),
                source="agent_monitor",
                metadata={"offline_count": dead}
            ))
    
    def check_database_health(self, metrics: Dict):
        """Check database metrics and fire alerts."""
        db = metrics.get("database", {})
        
        # Database size alert
        size_mb = db.get("size_mb", 0)
        if size_mb > self.thresholds["db_size_mb"]:
            self.fire_alert(Alert(
                level=AlertLevel.WARNING,
                title="Large Database Size",
                message=f"Database is {size_mb:.1f}MB (threshold: {self.thresholds['db_size_mb']}MB)",
                timestamp=datetime.now(),
                source="database_monitor",
                metadata={"size_mb": size_mb}
            ))

# Global alert manager instance
alert_manager = AlertManager()

def webhook_alert_handler(alert: Alert):
    """Send alert via webhook."""
    import requests
    
    # This will be configured from server.py
    webhook_url = None  # Set from config
    
    if not webhook_url:
        return
    
    color_map = {
        AlertLevel.INFO: 0x00d4ff,
        AlertLevel.WARNING: 0xffa500,
        AlertLevel.ERROR: 0xff0000,
        AlertLevel.CRITICAL: 0x8b0000
    }
    
    try:
        requests.post(webhook_url, json={
            "embeds": [{
                "title": f"🚨 {alert.title}",
                "description": alert.message,
                "color": color_map.get(alert.level, 0x00d4ff),
                "fields": [
                    {"name": "Level", "value": alert.level.value.upper(), "inline": True},
                    {"name": "Source", "value": alert.source, "inline": True}
                ],
                "footer": {"text": "C2 Alert System"},
                "timestamp": alert.timestamp.isoformat()
            }]
        }, timeout=5)
    except Exception as e:
        print(f"[Alert] Webhook error: {e}")

# Register default handler
alert_manager.add_handler(webhook_alert_handler)
