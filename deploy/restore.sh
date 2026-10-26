#!/bin/bash
# Refresh THIS server from the Google Drive backup (the reverse of backup.sh).
# Run as the sammy user (not root) on the NEW Contabo server:
#
#   bash restore.sh                          # newest database dump
#   bash restore.sh myproject-2026-10-24.dump   # a specific dump from gcrypt:db
#   bash restore.sh --auto                   # unattended, for cron (see below)
#
# Nightly refresh from cron (as sammy), every 10 min between 2:00 and 4:50 IST;
# it acts once, as soon as the primary's backup of the day has finished:
#   */10 2-4 * * * /home/sammy/myprojectdir/deploy/restore.sh --auto >> /home/sammy/restore.log 2>&1
# Needs a narrow sudo rule (no password) -- see deploy/sudoers-restore.
#
# What it does:
#   1. keeps a safety copy of the current database (~/pre-restore-<time>.dump)
#   2. REPLACES the database with the dump (drops and recreates it)
#   3. tops up media files from Drive (copy only: never deletes anything)
#   4. rebuilds the Elasticsearch index
#   5. restarts the app
#
# It refuses to run on any other machine, so it can never overwrite the old
# production server by accident. Change ALLOWED_HOST if the server is rebuilt.

set -euo pipefail

ALLOWED_HOST=vmi3694826
PROJECT=$HOME/myprojectdir
DB=myproject
DB_USER=myprojectuser
DB_PASSWORD=${DB_PASSWORD:-password}   # same as DATABASES in settings.py
REMOTE=gcrypt:
RCLONE_CONFIG_FILE=$HOME/.config/rclone/rclone.conf
MIN_DUMP_BYTES=100000

rc() { rclone --config "$RCLONE_CONFIG_FILE" "$@"; }
log() { echo "$(date '+%F %T') $*"; }

[ "$(id -u)" -ne 0 ] || { echo "run as sammy, not root"; exit 1; }
if [ "$(hostname)" != "$ALLOWED_HOST" ]; then
    echo "REFUSED: this is '$(hostname)', not '$ALLOWED_HOST'. restore.sh only runs on the new server."
    exit 1
fi

AUTO=0
if [ "${1:-}" = "--auto" ]; then AUTO=1; shift; fi

if [ "$AUTO" -eq 1 ]; then
    # Unattended nightly refresh (cron). Only runs once per day, and only after
    # the primary server has finished today's backup (it writes last-ok.txt to
    # Drive at the end). Otherwise it exits quietly and cron simply tries again.
    TODAY=$(date +%F)
    DONE_FILE=$HOME/.last-restore
    [ "$(cat "$DONE_FILE" 2>/dev/null || true)" != "$TODAY" ] || exit 0
    [ "$(rc cat "${REMOTE}last-ok.txt" 2>/dev/null || true)" = "$TODAY" ] || { log "today's backup is not finished yet -- waiting"; exit 0; }
    exec 9>"$HOME/.hfflex-restore.lock"
    flock -n 9 || { log "another restore is running"; exit 0; }
    DUMP="${DB}-${TODAY}.dump"
    rc lsf "${REMOTE}db" | grep -qx "$DUMP" || { log "ERROR $DUMP is missing in Drive"; exit 1; }
else
    DUMP=${1:-$(rc lsf "${REMOTE}db" | grep "^${DB}-" | sort | tail -n 1)}
    [ -n "$DUMP" ] || { echo "no database dump found in ${REMOTE}db"; exit 1; }

    echo
    echo "This will REPLACE the '$DB' database on $(hostname) with:  $DUMP"
    echo "Anything saved on this server since then is lost (a safety copy is kept)."
    read -r -p "Type RESTORE to continue: " answer
    [ "$answer" = "RESTORE" ] || { echo "cancelled"; exit 1; }
fi
log "=== restore started: $DUMP ==="

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

log "downloading $DUMP"
rc copyto "${REMOTE}db/$DUMP" "$TMP/restore.dump"
size=$(stat -c %s "$TMP/restore.dump")
[ "$size" -ge "$MIN_DUMP_BYTES" ] || { echo "dump is only $size bytes -- not restoring"; exit 1; }
pg_restore -l "$TMP/restore.dump" > /dev/null || { echo "dump is not readable -- not restoring"; exit 1; }
log "dump ok ($size bytes)"

log "stopping the app"
sudo systemctl stop gunicorn.socket gunicorn.service

SAFETY=$HOME/pre-restore-$(date +%Y%m%d-%H%M%S).dump
log "safety copy of the current database -> $SAFETY"
sudo -u postgres pg_dump -Fc "$DB" > "$SAFETY"

log "recreating database $DB"
sudo -u postgres dropdb --force --if-exists "$DB"
sudo -u postgres createdb -O "$DB_USER" "$DB"
PGPASSWORD=$DB_PASSWORD pg_restore -h localhost -U "$DB_USER" -d "$DB" --no-owner --no-privileges "$TMP/restore.dump"
tables=$(PGPASSWORD=$DB_PASSWORD psql -h localhost -U "$DB_USER" -d "$DB" -tAc \
    "select count(*) from information_schema.tables where table_schema='public'")
log "database restored ($tables tables)"

log "media: copying new files from Drive"
mkdir -p "$PROJECT/media"
rc copy "${REMOTE}media" "$PROJECT/media" --transfers 8 --checkers 16 --retries 3 \
    --log-level NOTICE --stats 10m --stats-one-line --stats-log-level NOTICE

log "rebuilding the search index"
(cd "$PROJECT" && myprojectenv/bin/python manage.py search_index --rebuild -f | tail -n 3)

log "starting the app"
sudo systemctl start gunicorn.socket
sleep 2
code=$(curl -sk -o /dev/null -w '%{http_code}' -H 'Host: www.hfflex.com' https://127.0.0.1/ || true)
log "app answers: HTTP $code"
if [ "$AUTO" -eq 1 ]; then
    date +%F > "$DONE_FILE"
    # keep only the 3 newest safety copies so the disk does not fill up
    ls -1t "$HOME"/pre-restore-*.dump 2>/dev/null | tail -n +4 | xargs -r rm -f
fi
log "=== restore finished ==="
echo
echo "Done. Safety copy of the previous data: $SAFETY (delete it when you no longer need it)."
