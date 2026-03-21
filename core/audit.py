"""Audit logging system for C2 Server"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import sqlite3

class AuditLogger:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize audit log table"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id TEXT,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                success INTEGER DEFAULT 1
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)")
        conn.commit()
        conn.close()
    
    def log(self, action: str, user_id: Optional[int] = None, username: Optional[str] = None,
            resource_type: Optional[str] = None, resource_id: Optional[str] = None,
            details: Optional[dict] = None, ip_address: Optional[str] = None,
            user_agent: Optional[str] = None, success: bool = True):
        """Log an audit event"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            INSERT INTO audit_log 
            (timestamp, user_id, username, action, resource_type, resource_id, 
             details, ip_address, user_agent, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            user_id,
            username,
            action,
            resource_type,
            resource_id,
            json.dumps(details) if details else None,
            ip_address,
            user_agent,
            1 if success else 0
        ))
        conn.commit()
        conn.close()
    
    def query(self, user_id: Optional[int] = None, action: Optional[str] = None,
              start_date: Optional[str] = None, end_date: Optional[str] = None,
              limit: int = 100) -> list:
        """Query audit logs"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        
        if action:
            query += " AND action = ?"
            params.append(action)
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_user_activity(self, user_id: int, days: int = 30) -> dict:
        """Get user activity summary"""
        conn = sqlite3.connect(str(self.db_path))
        
        start_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        total = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE user_id = ? AND timestamp >= ?",
            (user_id, start_date)
        ).fetchone()[0]
        
        by_action = {}
        rows = conn.execute(
            "SELECT action, COUNT(*) as count FROM audit_log WHERE user_id = ? AND timestamp >= ? GROUP BY action",
            (user_id, start_date)
        ).fetchall()
        
        for row in rows:
            by_action[row[0]] = row[1]
        
        conn.close()
        
        return {
            "total": total,
            "by_action": by_action,
            "period_days": days
        }
    
    def cleanup(self, days: int = 90):
        """Delete old audit logs"""
        conn = sqlite3.connect(str(self.db_path))
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn.execute("DELETE FROM audit_log WHERE timestamp < ?", (cutoff,))
        conn.commit()
        conn.close()

from datetime import timedelta
