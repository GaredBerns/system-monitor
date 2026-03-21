"""Backup and restore system for C2 Server"""
import shutil
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import tarfile
import tempfile

class BackupManager:
    def __init__(self, data_dir: Path, backup_dir: Path):
        self.data_dir = data_dir
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, name: str = None) -> Path:
        """Create full backup"""
        if not name:
            name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = self.backup_dir / f"{name}.tar.gz"
        
        with tarfile.open(backup_path, "w:gz") as tar:
            # Database
            db_path = self.data_dir / "c2.db"
            if db_path.exists():
                tar.add(db_path, arcname="c2.db")
            
            # Accounts
            accounts_path = self.data_dir / "accounts.json"
            if accounts_path.exists():
                tar.add(accounts_path, arcname="accounts.json")
            
            # Config
            for f in self.data_dir.glob("*.json"):
                if f.name not in ["accounts.json"]:
                    tar.add(f, arcname=f.name)
            
            # Uploads (limit size)
            uploads_dir = self.data_dir / "uploads"
            if uploads_dir.exists():
                for f in uploads_dir.iterdir():
                    if f.stat().st_size < 10 * 1024 * 1024:  # 10MB limit
                        tar.add(f, arcname=f"uploads/{f.name}")
        
        return backup_path
    
    def restore_backup(self, backup_path: Path) -> bool:
        """Restore from backup"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Extract
                with tarfile.open(backup_path, "r:gz") as tar:
                    tar.extractall(tmpdir)
                
                tmpdir_path = Path(tmpdir)
                
                # Restore database
                db_backup = tmpdir_path / "c2.db"
                if db_backup.exists():
                    shutil.copy(db_backup, self.data_dir / "c2.db")
                
                # Restore accounts
                accounts_backup = tmpdir_path / "accounts.json"
                if accounts_backup.exists():
                    shutil.copy(accounts_backup, self.data_dir / "accounts.json")
                
                # Restore config files
                for f in tmpdir_path.glob("*.json"):
                    if f.name not in ["accounts.json"]:
                        shutil.copy(f, self.data_dir / f.name)
                
                # Restore uploads
                uploads_backup = tmpdir_path / "uploads"
                if uploads_backup.exists():
                    uploads_dir = self.data_dir / "uploads"
                    uploads_dir.mkdir(exist_ok=True)
                    for f in uploads_backup.iterdir():
                        shutil.copy(f, uploads_dir / f.name)
                
                return True
        except Exception as e:
            print(f"Restore failed: {e}")
            return False
    
    def list_backups(self) -> list:
        """List available backups"""
        backups = []
        for f in self.backup_dir.glob("*.tar.gz"):
            backups.append({
                "name": f.stem,
                "path": str(f),
                "size": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        return sorted(backups, key=lambda x: x["created"], reverse=True)
    
    def delete_backup(self, name: str):
        """Delete a backup"""
        backup_path = self.backup_dir / f"{name}.tar.gz"
        if backup_path.exists():
            backup_path.unlink()
    
    def export_database(self, output_path: Path):
        """Export database to SQL"""
        db_path = self.data_dir / "c2.db"
        conn = sqlite3.connect(str(db_path))
        
        with open(output_path, 'w') as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
        
        conn.close()
    
    def import_database(self, sql_path: Path):
        """Import database from SQL"""
        db_path = self.data_dir / "c2.db"
        
        # Backup current
        if db_path.exists():
            shutil.copy(db_path, db_path.with_suffix('.db.bak'))
        
        conn = sqlite3.connect(str(db_path))
        with open(sql_path) as f:
            conn.executescript(f.read())
        conn.close()
