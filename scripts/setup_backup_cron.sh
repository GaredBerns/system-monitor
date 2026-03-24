#!/bin/bash
# Setup automatic backups via cron

PROJECT_DIR="/mnt/F/C2_server-main"

# Add cron job for daily backups at 3 AM
(crontab -l 2>/dev/null | grep -v "c2_backup"; echo "0 3 * * * cd $PROJECT_DIR && python3 scripts/backup.py >> logs/backup.log 2>&1") | crontab -

echo "✓ Automatic backups configured (daily at 3 AM)"
echo "✓ Backup logs: $PROJECT_DIR/logs/backup.log"
