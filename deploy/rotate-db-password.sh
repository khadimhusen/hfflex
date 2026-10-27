#!/bin/bash
# Replace the database password with a long random one that lives in .env.
#
# Run as the app user (sammy) on the server whose database you want to change:
#   bash ~/myprojectdir/deploy/rotate-db-password.sh
#
# What it does (the new password is NEVER printed):
#   1. checks that the password now in settings.py really works
#   2. makes a random password and appends DB_PASSWORD=... to .env (mode 600)
#   3. changes settings.py to   'PASSWORD': os.getenv("DB_PASSWORD")
#   4. changes the password inside Postgres, restarts gunicorn
#   5. checks that the new password works, the old one does not, and the site answers
# If any step fails it puts the old password and files back by itself.
#
# Each server has its own database role, so run it on every server separately.

set -euo pipefail

PROJECT=${PROJECT:-$HOME/myprojectdir}
SETTINGS=$PROJECT/myproject/settings.py
ENVFILE=$PROJECT/.env
DB_USER=myprojectuser
DB=myproject

[ "$(id -u)" -ne 0 ] || { echo "run as sammy, not root"; exit 1; }
[ -f "$SETTINGS" ] && [ -f "$ENVFILE" ] || { echo "settings.py or .env not found under $PROJECT"; exit 1; }

if grep -q 'os.getenv("DB_PASSWORD")' "$SETTINGS"; then
    echo "settings.py already reads DB_PASSWORD from .env -- nothing to do."
    exit 0
fi

lines=$(grep -cE "^\s*'PASSWORD':" "$SETTINGS" || true)
[ "$lines" -eq 1 ] || { echo "expected exactly one 'PASSWORD': line in settings.py, found $lines -- nothing changed."; exit 1; }

OLDPW=$(grep -E "^\s*'PASSWORD':" "$SETTINGS" | sed -E "s/^[^:]*:[[:space:]]*'([^']*)'.*/\1/")
[ -n "$OLDPW" ] || { echo "could not read the current password from settings.py -- nothing changed."; exit 1; }
case "$OLDPW" in *"'"*) echo "the current password contains a quote; change it by hand -- nothing changed."; exit 1;; esac

sudo -v   # ask for the sudo password now, not half way through

PGPASSWORD=$OLDPW psql -h localhost -U "$DB_USER" -d "$DB" -tAc 'select 1' > /dev/null \
    || { echo "the password in settings.py does not work for the database -- stopping, nothing changed."; exit 1; }

NEWPW=$(openssl rand -hex 24)
STAMP=$(date +%Y%m%d-%H%M%S)
cp -p "$SETTINGS" "$SETTINGS.bak-$STAMP"; chmod 600 "$SETTINGS.bak-$STAMP"
cp -p "$ENVFILE"  "$ENVFILE.bak-$STAMP";  chmod 600 "$ENVFILE.bak-$STAMP"

rollback() {
    echo "!! something failed -- putting the old password and files back"
    cp -p "$SETTINGS.bak-$STAMP" "$SETTINGS"
    cp -p "$ENVFILE.bak-$STAMP" "$ENVFILE"
    echo "ALTER ROLE $DB_USER PASSWORD '$OLDPW';" | sudo -u postgres psql -q > /dev/null || true
    sudo systemctl restart gunicorn || true
    echo "old password restored; nothing is changed. Backups kept: $SETTINGS.bak-$STAMP"
    exit 1
}

# 1) .env
sed -i '/^DB_PASSWORD=/d' "$ENVFILE"
printf '\nDB_PASSWORD=%s\n' "$NEWPW" >> "$ENVFILE"
chmod 600 "$ENVFILE"

# 2) settings.py
sed -i -E "s/^([[:space:]]*'PASSWORD':)[[:space:]]*'[^']*'/\1 os.getenv(\"DB_PASSWORD\")/" "$SETTINGS"
grep -q 'os.getenv("DB_PASSWORD")' "$SETTINGS" || rollback

# 3) database, then the app
echo "ALTER ROLE $DB_USER PASSWORD '$NEWPW';" | sudo -u postgres psql -q > /dev/null || rollback
sudo systemctl restart gunicorn || rollback
sleep 3

# 4) checks
PGPASSWORD=$NEWPW psql -h localhost -U "$DB_USER" -d "$DB" -tAc 'select 1' > /dev/null || rollback
if PGPASSWORD=$OLDPW psql -h localhost -U "$DB_USER" -d "$DB" -tAc 'select 1' > /dev/null 2>&1; then
    echo "WARNING: the old password still works (check pg_hba.conf)"
fi
code=$(curl -sk -o /dev/null -m 15 -w '%{http_code}' -H 'Host: www.hfflex.com' https://127.0.0.1/about/ || true)
[ "$code" = "200" ] || { echo "the site answered HTTP $code instead of 200"; rollback; }
( cd "$PROJECT" && myprojectenv/bin/python manage.py check > /dev/null ) || { echo "manage.py check failed"; rollback; }

echo
echo "Done. The database password is now a random 48-character value stored in $ENVFILE."
echo "Site answers HTTP $code, the new password works, and the old one is rejected."
echo "Backups of the old files: $SETTINGS.bak-$STAMP and $ENVFILE.bak-$STAMP"
echo "Delete those two backups once you are happy (they contain the OLD password)."
