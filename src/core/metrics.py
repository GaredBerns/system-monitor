"""Metrics collection for monitoring."""
import time
from datetime import datetime
from pathlib import Path

class MetricsCollector:
    def __init__(self, db_path):
        self.db_path = db_path
        self.start_time = time.time()
    
    def get_stats(self):
        import sqlite3
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        
        stats = {
            "agents_total": conn.execute("SELECT COUNT(*) c FROM agents").fetchone()["c"],
            "agents_alive": conn.execute("SELECT COUNT(*) c FROM agents WHERE is_alive=1").fetchone()["c"],
            "tasks_pending": conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='pending'").fetchone()["c"],
            "tasks_completed": conn.execute("SELECT COUNT(*) c FROM tasks WHERE status='completed'").fetchone()["c"],
            "uptime": int(time.time() - self.start_time)
        }
        conn.close()
        return stats
    
    def export_prometheus(self):
        stats = self.get_stats()
        return f"""# HELP c2_agents_total Total agents
# TYPE c2_agents_total gauge
c2_agents_total {stats['agents_total']}
# HELP c2_agents_alive Alive agents
# TYPE c2_agents_alive gauge
c2_agents_alive {stats['agents_alive']}
# HELP c2_tasks_pending Pending tasks
# TYPE c2_tasks_pending gauge
c2_tasks_pending {stats['tasks_pending']}
# HELP c2_tasks_completed Completed tasks
# TYPE c2_tasks_completed counter
c2_tasks_completed {stats['tasks_completed']}
# HELP c2_uptime_seconds Server uptime
# TYPE c2_uptime_seconds counter
c2_uptime_seconds {stats['uptime']}
"""
    
    def export_json(self):
        return self.get_stats()
