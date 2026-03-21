#!/usr/bin/env python3
"""Metrics collection and Prometheus export."""

import time
import sqlite3
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta

class MetricsCollector:
    """Collect and expose metrics in Prometheus format."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.start_time = time.time()
    
    def get_agent_metrics(self) -> Dict:
        """Get agent-related metrics."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            cursor = conn.cursor()
            
            # Total agents
            total = cursor.execute("SELECT COUNT(*) FROM agents").fetchone()[0]
            
            # Alive agents
            alive = cursor.execute("SELECT COUNT(*) FROM agents WHERE is_alive=1").fetchone()[0]
            
            # Agents by platform
            platforms = {}
            for row in cursor.execute("SELECT platform_type, COUNT(*) FROM agents GROUP BY platform_type"):
                platforms[row[0] or 'unknown'] = row[1]
            
            # Agents by OS
            os_types = {}
            for row in cursor.execute("SELECT os, COUNT(*) FROM agents GROUP BY os"):
                os_name = (row[0] or 'unknown').split()[0].lower()
                os_types[os_name] = os_types.get(os_name, 0) + row[1]
            
            conn.close()
            
            return {
                "total": total,
                "alive": alive,
                "dead": total - alive,
                "platforms": platforms,
                "os_types": os_types
            }
        except Exception as e:
            print(f"[Metrics] Agent metrics error: {e}")
            return {"total": 0, "alive": 0, "dead": 0, "platforms": {}, "os_types": {}}
    
    def get_task_metrics(self) -> Dict:
        """Get task-related metrics."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            cursor = conn.cursor()
            
            # Total tasks
            total = cursor.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            
            # Tasks by status
            statuses = {}
            for row in cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status"):
                statuses[row[0]] = row[1]
            
            # Tasks today
            today = datetime.now().strftime("%Y-%m-%d")
            today_count = cursor.execute(
                "SELECT COUNT(*) FROM tasks WHERE created_at LIKE ?",
                (f"{today}%",)
            ).fetchone()[0]
            
            # Average completion time (last 100 completed tasks)
            avg_time = cursor.execute("""
                SELECT AVG(
                    (julianday(completed_at) - julianday(created_at)) * 86400
                ) FROM (
                    SELECT created_at, completed_at 
                    FROM tasks 
                    WHERE status='completed' AND completed_at IS NOT NULL
                    ORDER BY completed_at DESC 
                    LIMIT 100
                )
            """).fetchone()[0]
            
            conn.close()
            
            return {
                "total": total,
                "statuses": statuses,
                "today": today_count,
                "avg_completion_seconds": round(avg_time or 0, 2)
            }
        except Exception as e:
            print(f"[Metrics] Task metrics error: {e}")
            return {"total": 0, "statuses": {}, "today": 0, "avg_completion_seconds": 0}
    
    def get_system_metrics(self) -> Dict:
        """Get system metrics."""
        try:
            import psutil
            
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_used_mb": psutil.virtual_memory().used / 1024 / 1024,
                "disk_percent": psutil.disk_usage('/').percent,
                "uptime_seconds": time.time() - self.start_time
            }
        except Exception as e:
            print(f"[Metrics] System metrics error: {e}")
            return {
                "cpu_percent": 0,
                "memory_percent": 0,
                "memory_used_mb": 0,
                "disk_percent": 0,
                "uptime_seconds": 0
            }
    
    def get_database_metrics(self) -> Dict:
        """Get database metrics."""
        try:
            db_size = Path(self.db_path).stat().st_size
            
            conn = sqlite3.connect(str(self.db_path), timeout=5)
            cursor = conn.cursor()
            
            # Table sizes
            tables = {}
            for table in ['agents', 'tasks', 'logs', 'users']:
                count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                tables[table] = count
            
            conn.close()
            
            return {
                "size_mb": round(db_size / 1024 / 1024, 2),
                "tables": tables
            }
        except Exception as e:
            print(f"[Metrics] Database metrics error: {e}")
            return {"size_mb": 0, "tables": {}}
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Agent metrics
        agent_metrics = self.get_agent_metrics()
        lines.append("# HELP c2_agents_total Total number of agents")
        lines.append("# TYPE c2_agents_total gauge")
        lines.append(f"c2_agents_total {agent_metrics['total']}")
        
        lines.append("# HELP c2_agents_alive Number of alive agents")
        lines.append("# TYPE c2_agents_alive gauge")
        lines.append(f"c2_agents_alive {agent_metrics['alive']}")
        
        lines.append("# HELP c2_agents_by_platform Agents by platform")
        lines.append("# TYPE c2_agents_by_platform gauge")
        for platform, count in agent_metrics['platforms'].items():
            lines.append(f'c2_agents_by_platform{{platform="{platform}"}} {count}')
        
        # Task metrics
        task_metrics = self.get_task_metrics()
        lines.append("# HELP c2_tasks_total Total number of tasks")
        lines.append("# TYPE c2_tasks_total counter")
        lines.append(f"c2_tasks_total {task_metrics['total']}")
        
        lines.append("# HELP c2_tasks_by_status Tasks by status")
        lines.append("# TYPE c2_tasks_by_status gauge")
        for status, count in task_metrics['statuses'].items():
            lines.append(f'c2_tasks_by_status{{status="{status}"}} {count}')
        
        lines.append("# HELP c2_tasks_avg_completion_seconds Average task completion time")
        lines.append("# TYPE c2_tasks_avg_completion_seconds gauge")
        lines.append(f"c2_tasks_avg_completion_seconds {task_metrics['avg_completion_seconds']}")
        
        # System metrics
        system_metrics = self.get_system_metrics()
        lines.append("# HELP c2_cpu_percent CPU usage percentage")
        lines.append("# TYPE c2_cpu_percent gauge")
        lines.append(f"c2_cpu_percent {system_metrics['cpu_percent']}")
        
        lines.append("# HELP c2_memory_percent Memory usage percentage")
        lines.append("# TYPE c2_memory_percent gauge")
        lines.append(f"c2_memory_percent {system_metrics['memory_percent']}")
        
        lines.append("# HELP c2_uptime_seconds Server uptime in seconds")
        lines.append("# TYPE c2_uptime_seconds counter")
        lines.append(f"c2_uptime_seconds {system_metrics['uptime_seconds']}")
        
        # Database metrics
        db_metrics = self.get_database_metrics()
        lines.append("# HELP c2_database_size_mb Database size in MB")
        lines.append("# TYPE c2_database_size_mb gauge")
        lines.append(f"c2_database_size_mb {db_metrics['size_mb']}")
        
        return '\n'.join(lines) + '\n'
    
    def export_json(self) -> Dict:
        """Export all metrics as JSON."""
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": self.get_agent_metrics(),
            "tasks": self.get_task_metrics(),
            "system": self.get_system_metrics(),
            "database": self.get_database_metrics()
        }
