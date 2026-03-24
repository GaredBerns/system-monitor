#!/usr/bin/env python3
"""Database backup utility."""
import shutil
import time
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent.parent
DB_PATH = BASE_DIR / "data" / "c2.db"
BACKUP_DIR = BASE_DIR / "data" / "backups"

def backup_database():
    """Create database backup."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"c2_backup_{timestamp}.db"
    
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_path)
        print(f"✓ Backup created: {backup_path}")
        
        # Keep only last 10 backups
        backups = sorted(BACKUP_DIR.glob("c2_backup_*.db"))
        if len(backups) > 10:
            for old in backups[:-10]:
                old.unlink()
                print(f"✓ Removed old backup: {old.name}")
        
        return backup_path
    return None

def restore_database(backup_file):
    """Restore database from backup."""
    backup_path = BACKUP_DIR / backup_file
    if backup_path.exists():
        shutil.copy2(backup_path, DB_PATH)
        print(f"✓ Database restored from: {backup_file}")
        return True
    return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) > 2:
            restore_database(sys.argv[2])
        else:
            print("Usage: python backup.py restore <backup_file>")
    else:
        backup_database()
