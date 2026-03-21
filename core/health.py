"""Health monitoring utilities for C2 Server"""
import psutil
import sqlite3
from pathlib import Path
from typing import Dict

def get_system_health() -> Dict:
    """Get system resource usage"""
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
    }

def get_database_health(db_path: str) -> Dict:
    """Get database statistics"""
    conn = sqlite3.connect(db_path)
    
    stats = {
        'agents_total': conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0],
        'agents_alive': conn.execute("SELECT COUNT(*) FROM agents WHERE is_alive=1").fetchone()[0],
        'tasks_pending': conn.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'").fetchone()[0],
        'tasks_total': conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
        'logs_count': conn.execute("SELECT COUNT(*) FROM logs").fetchone()[0],
        'db_size_mb': Path(db_path).stat().st_size / (1024 * 1024)
    }
    
    conn.close()
    return stats

def get_service_health() -> Dict:
    """Get service status"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, socket_connect_timeout=1)
        redis_status = 'connected' if r.ping() else 'disconnected'
    except:
        redis_status = 'unavailable'
    
    return {
        'redis': redis_status,
        'uptime': psutil.boot_time()
    }

def check_health(db_path: str) -> Dict:
    """Complete health check"""
    return {
        'system': get_system_health(),
        'database': get_database_health(db_path),
        'services': get_service_health(),
        'status': 'healthy'
    }

if __name__ == '__main__':
    from pathlib import Path
    base_dir = Path(__file__).parent.parent
    db_path = str(base_dir / 'data' / 'c2.db')
    
    health = check_health(db_path)
    print(f"Health: {health}")
