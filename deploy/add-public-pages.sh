#!/bin/bash
# Install the public pages (/about/, /privacy/, /terms/) on a server by copying files
# (no git). Expects the files already in /tmp:
#   /tmp/public_views.py   /tmp/public/*.html
# Run as sammy:  bash /tmp/add-public-pages.sh
# Backs up urls.py, refuses to patch an unexpected file, rolls back if
# `manage.py check` fails, restarts gunicorn and tests the three URLs.

set -eu
PROJECT=$HOME/myprojectdir
URLS=$PROJECT/myproject/urls.py
BACKUP=$HOME/urls.py.before-public-pages

cd "$PROJECT"
[ -f /tmp/public_views.py ] && [ -d /tmp/public ] || { echo "files missing in /tmp"; exit 1; }

if grep -q 'public_views' "$URLS"; then
    echo "urls.py already has the public pages -- only refreshing the files"
else
    # exactly one of each anchor line, or we do not touch the file
    # [[:space:]]* also matches Windows (CRLF) line endings
    [ "$(grep -c '^from \. import views[[:space:]]*$' "$URLS")" = 1 ] || { echo "unexpected import line in urls.py -- not patching"; exit 1; }
    [ "$(grep -c "^ *path('', views.user_login),[[:space:]]*$" "$URLS")" = 1 ] || { echo "unexpected root route in urls.py -- not patching"; exit 1; }
fi

cp -p "$URLS" "$BACKUP"
cp /tmp/public_views.py myproject/public_views.py
mkdir -p templates/public
cp /tmp/public/*.html templates/public/

if ! grep -q 'public_views' "$URLS"; then
    sed -i 's/^from \. import views[[:space:]]*$/from . import views, public_views/' "$URLS"
    sed -i "s|^\( *\)path('', views.user_login),[[:space:]]*\$|\1# public pages (no login), e.g. for the Google OAuth consent screen\n\1path('about/', public_views.AboutView.as_view(), name='public-about'),\n\1path('privacy/', public_views.PrivacyView.as_view(), name='public-privacy'),\n\1path('terms/', public_views.TermsView.as_view(), name='public-terms'),\n\1path('', views.user_login),|" "$URLS"
fi

if ! myprojectenv/bin/python manage.py check; then
    echo "CHECK FAILED -- restoring the old urls.py"
    cp -p "$BACKUP" "$URLS"
    exit 1
fi

sudo systemctl restart gunicorn
sleep 3
for p in about privacy terms; do
    curl -sk -o /dev/null -w "/$p/ -> %{http_code}\n" -H 'Host: www.hfflex.com' "https://127.0.0.1/$p/"
done
curl -sk -o /dev/null -w "/login/ -> %{http_code}\n" -H 'Host: www.hfflex.com' https://127.0.0.1/login/
echo "Done. Backup of the old urls.py: $BACKUP"
