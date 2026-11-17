#!/usr/bin/env bash
# Nightly PostgreSQL backup. Add to cron:   0 3 * * *  /path/to/backend/scripts/backup.sh
# Needs: DATABASE_URL (postgres://...) and pg_dump. Keeps 14 days locally; copy the folder off-server (rclone/S3) too.
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
DIR="${BACKUP_DIR:-./backups}"; mkdir -p "$DIR"
FILE="$DIR/gimble-$(date +%F-%H%M).sql.gz"
pg_dump --no-owner --clean --if-exists "${DATABASE_URL/postgresql+psycopg:/postgresql:}" | gzip > "$FILE"
find "$DIR" -name 'gimble-*.sql.gz' -mtime +14 -delete
echo "Backup written: $FILE ($(du -h "$FILE" | cut -f1))"
# Restore:  gunzip -c backups/gimble-DATE.sql.gz | psql "$DATABASE_URL"
