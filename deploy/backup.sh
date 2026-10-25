#!/bin/bash
# Nightly off-site backup of the hfflex server to Google Drive.
#
# Everything is streamed through rclone's "gcrypt" remote, which encrypts it
# before it leaves the server, so no large temporary files are written locally
# (the disk is small) and nothing readable ends up in Drive.
#
# The website keeps running the whole time (pg_dump is a consistent snapshot).
# The database is dumped BEFORE the media is copied, so every file the dump
# refers to is already on disk when the media copy runs; a file uploaded in
# between is simply picked up the next night.
#
#   database(s)   pg_dump -Fc  ->  gcrypt:db/<name>-<date>.dump       (kept KEEP_DB_DAYS)
#   media files   rclone copy  ->  gcrypt:media/                      (new files only; never deletes)
#   config files  tar.gz       ->  gcrypt:config/config-<date>.tar.gz (kept KEEP_CONFIG_DAYS)
#
# Run as root (it needs `sudo -u postgres`), from root's crontab:
#   0 2 * * * /home/sammy/myprojectdir/deploy/backup.sh >> /var/log/hfflex-backup.log 2>&1
#
# NOT backed up here, on purpose: rclone.conf. Keep the two crypt passwords in a
# password manager -- without them these backups cannot be read.

set -u -o pipefail

# ---- settings ------------------------------------------------------------
RCLONE_CONFIG_FILE=/home/sammy/.config/rclone/rclone.conf
REMOTE=gcrypt:
PROJECT=/home/sammy/myprojectdir
DATABASES="myproject"        # space separated; add e.g. "myproject webhf" to back up more
KEEP_DB_DAYS=14
KEEP_CONFIG_DAYS=60
MIN_DUMP_BYTES=100000        # a dump smaller than this is treated as a failed backup
# Optional: a healthchecks.io style URL to ping on success (and /fail on failure).
# Put   HEALTHCHECK_URL=https://hc-ping.com/xxxx   in /home/sammy/.backup.env
ENV_FILE=/home/sammy/.backup.env
# --------------------------------------------------------------------------

[ -f "$ENV_FILE" ] && . "$ENV_FILE"

rc() { rclone --config "$RCLONE_CONFIG_FILE" "$@"; }
log() { echo "$(date '+%F %T') $*"; }

# One run at a time: the very first upload of the media folder takes hours.
exec 9>/var/lock/hfflex-backup.lock
if ! flock -n 9; then
    log "another backup is still running -- skipping this one"
    exit 0
fi

DATE=$(date +%F)
failed=0
log "=== backup started ==="

# ---- 1. databases ----------------------------------------------------------
for db in $DATABASES; do
    log "database $db: dump and upload"
    name="${db}-${DATE}.dump"
    if sudo -u postgres pg_dump -Fc "$db" | rc rcat "${REMOTE}db/${name}"; then
        size=$(rc lsf --format s --include "$name" "${REMOTE}db" | head -n 1)
        if [ -z "$size" ] || [ "$size" -lt "$MIN_DUMP_BYTES" ]; then
            log "ERROR database $db: uploaded dump is missing or too small (${size:-none} bytes)"
            failed=1
        else
            log "database $db: ok ($size bytes)"
        fi
    else
        log "ERROR database $db: dump or upload failed"
        rc deletefile "${REMOTE}db/${name}" 2>/dev/null
        failed=1
    fi
done

# ---- 2. media files (copy never deletes anything already in Drive) --------
log "media: copying new files"
if rc copy "$PROJECT/media" "${REMOTE}media" \
        --transfers 4 --checkers 8 --drive-chunk-size 64M --retries 3 \
        --log-level NOTICE --stats 10m --stats-one-line --stats-log-level NOTICE; then
    log "media: ok"
else
    log "ERROR media: copy failed"
    failed=1
fi

# ---- 3. config files -------------------------------------------------------
log "config: archive and upload"
# Besides settings.py, include everything the app needs that git does not hold:
# .env (SECRET_KEY), static/ (css/js/fonts), and every app's migrations/ folder.
# Not included on purpose: /etc/letsencrypt (certbot re-issues certificates).
UNTRACKED=$(cd "$PROJECT" && find . -type d -name migrations -not -path './myprojectenv/*' \
        -not -path './media/*' -not -path './staticfiles/*' | sed "s|^\./|${PROJECT#/}/|")
if tar czf - --ignore-failed-read -C / \
        "${PROJECT#/}/myproject/settings.py" "${PROJECT#/}/.env" "${PROJECT#/}/static" $UNTRACKED \
        etc/nginx etc/systemd/system 2>/dev/null \
        | rc rcat "${REMOTE}config/config-${DATE}.tar.gz"; then
    log "config: ok"
else
    log "ERROR config: archive or upload failed"
    failed=1
fi

# ---- 4. tidy old copies (only db dumps and config archives) ----------------
rc delete "${REMOTE}db" --min-age "${KEEP_DB_DAYS}d" --log-level NOTICE || log "WARN: could not prune old dumps"
rc delete "${REMOTE}config" --min-age "${KEEP_CONFIG_DAYS}d" --log-level NOTICE || log "WARN: could not prune old config archives"

# ---- result ----------------------------------------------------------------
if [ "$failed" -eq 0 ]; then
    date '+%F %T' > /var/log/hfflex-backup.last-ok
    # Marker in Drive for the standby server (restore.sh --auto): today's backup is complete.
    echo "$DATE" | rc rcat "${REMOTE}last-ok.txt" || log "WARN: could not write last-ok.txt"
    log "=== backup finished OK ==="
    [ -n "${HEALTHCHECK_URL:-}" ] && curl -fsS -m 10 --retry 3 "$HEALTHCHECK_URL" > /dev/null
else
    log "=== backup finished WITH ERRORS ==="
    [ -n "${HEALTHCHECK_URL:-}" ] && curl -fsS -m 10 --retry 3 "${HEALTHCHECK_URL}/fail" > /dev/null
fi
exit "$failed"
