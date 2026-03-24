"""Health monitoring."""
import psutil
import time
from pathlib import Path

class HealthMonitor:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.start_time = time.time()
    
    def check(self):
        """Comprehensive health check."""
        status = {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime": int(time.time() - self.start_time),
            "checks": {}
        }
        
        # Database check
        try:
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("SELECT 1").fetchone()
            conn.close()
            status["checks"]["database"] = "ok"
        except Exception as e:
            status["checks"]["database"] = f"error: {e}"
            status["status"] = "unhealthy"
        
        # Disk space
        try:
            disk = psutil.disk_usage(str(self.db_path.parent))
            status["checks"]["disk_free_gb"] = round(disk.free / (1024**3), 2)
            if disk.percent > 90:
                status["status"] = "degraded"
        except:
            pass
        
        # Memory
        try:
            mem = psutil.virtual_memory()
            status["checks"]["memory_percent"] = mem.percent
            if mem.percent > 90:
                status["status"] = "degraded"
        except:
            pass
        
        # CPU
        try:
            status["checks"]["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        except:
            pass
        
        return status
