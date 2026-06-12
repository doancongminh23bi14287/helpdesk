# Database Backup and Restore

Scripts are in `scripts/` and use environment variables.

## Backup

```bash
DB_USER=helpdesk \
DB_PASSWORD=helpdesk_pass \
DB_HOST=127.0.0.1 \
DB_PORT=3307 \
DB_NAME=helpdesk_db \
BACKUP_DIR=./backups \
scripts/backup_db.sh
```

The script creates `BACKUP_DIR/<db>_<timestamp>.sql.gz`.

Optional upload hook:

```bash
BACKUP_UPLOAD_CMD='aws s3 cp "$BACKUP_FILE" s3://bucket/workdesk/' scripts/backup_db.sh
```

## Restore

Restore refuses to run unless `CONFIRM_RESTORE=yes` is set.

```bash
CONFIRM_RESTORE=yes \
DB_USER=helpdesk \
DB_PASSWORD=helpdesk_pass \
DB_HOST=127.0.0.1 \
DB_PORT=3307 \
DB_NAME=helpdesk_db \
scripts/restore_db.sh backups/helpdesk_db_20260608T000000Z.sql.gz
```

## Restore Test
- Restore into a disposable database first.
- Run `alembic current`.
- Start backend against the restored database.
- Check `/ready`.
- Manually verify login, ticket list, invoice list, and attachment download.
