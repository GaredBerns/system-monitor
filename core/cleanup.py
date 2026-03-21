"""Automated cleanup system for C2 Server"""
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta

def cleanup_old_logs(db_path: str, days: int = 7):
    """Delete logs older than N days"""
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    deleted = conn.execute("DELETE FROM logs WHERE ts < ?", (cutoff,)).rowcount
    conn.commit()
    conn.close()
    return deleted

def cleanup_old_tasks(db_path: str, days: int = 30):
    """Delete completed tasks older than N days"""
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    deleted = conn.execute(
        "DELETE FROM tasks WHERE status='completed' AND completed_at < ?", 
        (cutoff,)
    ).rowcount
    conn.commit()
    conn.close()
    return deleted

def cleanup_dead_agents(db_path: str, days: int = 7):
    """Remove agents not seen for N days"""
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    deleted = conn.execute(
        "DELETE FROM agents WHERE is_alive=0 AND last_seen < ?", 
        (cutoff,)
    ).rowcount
    conn.commit()
    conn.close()
    return deleted

def vacuum_database(db_path: str):
    """Optimize database"""
    conn = sqlite3.connect(db_path)
    conn.execute("VACUUM")
    conn.close()

def cleanup_old_files(directory: Path, days: int = 7):
    """Delete files older than N days"""
    if not directory.exists():
        return 0
    
    cutoff = time.time() - (days * 86400)
    deleted = 0
    
    for f in directory.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            deleted += 1
    
    return deleted

def run_cleanup(db_path: str, data_dir: Path):
    """Run all cleanup tasks"""
    results = {
        'logs': cleanup_old_logs(db_path, days=7),
        'tasks': cleanup_old_tasks(db_path, days=30),
        'agents': cleanup_dead_agents(db_path, days=7),
        'screenshots': cleanup_old_files(data_dir / 'screenshots', days=7),
        'uploads': cleanup_old_files(data_dir / 'uploads', days=30)
    }
    
    vacuum_database(db_path)
    
    return results

if __name__ == '__main__':
    from pathlib import Path
    base_dir = Path(__file__).parent.parent
    db_path = str(base_dir / 'data' / 'c2.db')
    data_dir = base_dir / 'data'
    
    results = run_cleanup(db_path, data_dir)
    print(f"Cleanup complete: {results}")
