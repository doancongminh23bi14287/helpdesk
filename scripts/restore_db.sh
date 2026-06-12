#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRM_RESTORE:-}" != "yes" ]]; then
  echo "Refusing to restore without CONFIRM_RESTORE=yes" >&2
  exit 2
fi

backup_file="${1:?Usage: CONFIRM_RESTORE=yes scripts/restore_db.sh <dump.sql.gz|dump.sql>}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3307}"
DB_NAME="${DB_NAME:-helpdesk_db}"
DB_USER="${DB_USER:?DB_USER is required}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD is required}"

if [[ ! -f "$backup_file" ]]; then
  echo "Backup file not found: $backup_file" >&2
  exit 1
fi

if [[ "$backup_file" == *.gz ]]; then
  reader=(gzip -dc "$backup_file")
else
  reader=(cat "$backup_file")
fi

"${reader[@]}" | MYSQL_PWD="$DB_PASSWORD" mysql \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --user="$DB_USER" \
  "$DB_NAME"

echo "Restored $backup_file into $DB_NAME"
