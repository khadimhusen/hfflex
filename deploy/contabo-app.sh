#!/bin/bash
# Wire up the CRM on the new Contabo VPS: gunicorn (systemd) + nginx.
# Run as the sammy user (not root):   bash contabo-app.sh
#
# Needs: repo in ~/myprojectdir with its venv, settings.py restored,
# ~/config-restore from the config backup (for the gunicorn unit files).
#
# nginx is plain HTTP for now: the old Let's Encrypt certificates are not in
# the backup. After DNS points at this server run:
#   sudo certbot --nginx -d www.hfflex.com

set -eu
PROJECT=$HOME/myprojectdir
NEW_IP=13.140.252.89

cd "$PROJECT"

echo "== ALLOWED_HOSTS =="
grep -q "$NEW_IP" myproject/settings.py \
    || sed -i "s/^ALLOWED_HOSTS = \[/ALLOWED_HOSTS = [\"$NEW_IP\", /" myproject/settings.py
grep -n '^ALLOWED_HOSTS' myproject/settings.py

echo "== collectstatic =="
myprojectenv/bin/python manage.py collectstatic --noinput | tail -2

echo "== gunicorn (systemd) =="
sudo install -m 644 "$HOME/config-restore/etc/systemd/system/gunicorn.service" /etc/systemd/system/gunicorn.service
sudo install -m 644 "$HOME/config-restore/etc/systemd/system/gunicorn.socket"  /etc/systemd/system/gunicorn.socket
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn.socket

echo "== nginx =="
# nginx (www-data) must be able to walk into the home dir to reach static/media
chmod o+x "$HOME"
# Temporary self-signed certificate so the site can be tried over HTTPS (the
# settings force HTTPS and secure cookies) before DNS moves. Replaced by certbot.
SELFSIGNED=/etc/ssl/hfflex-selftest
if [ ! -f "$SELFSIGNED/cert.pem" ]; then
    sudo mkdir -p "$SELFSIGNED"
    sudo openssl req -x509 -nodes -newkey rsa:2048 -days 90 -subj "/CN=www.hfflex.com" \
        -keyout "$SELFSIGNED/key.pem" -out "$SELFSIGNED/cert.pem" 2>/dev/null
fi
sudo tee /etc/nginx/sites-available/myproject >/dev/null <<EOF
server {
    listen 80 default_server;
    listen 443 ssl default_server;
    ssl_certificate     $SELFSIGNED/cert.pem;
    ssl_certificate_key $SELFSIGNED/key.pem;
    server_name www.hfflex.com hfflex.com $NEW_IP _;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias $PROJECT/staticfiles/;
    }

    # Protected -- Document model files, gated through Django (X-Accel-Redirect)
    location /media/documents/ {
        internal;
        root $PROJECT;
    }

    # Everything else in /media/ -- served directly, no Django involved
    location /media/ {
        root $PROJECT;
    }

    location /crm/ {
        alias $PROJECT/crm_static/;
        try_files \$uri \$uri/ /crm/index.html;

        location = /crm/index.html {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
        }
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }

    client_max_body_size 50M;
}
EOF
sudo ln -sf /etc/nginx/sites-available/myproject /etc/nginx/sites-enabled/myproject
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "== smoke test =="
curl -sk -o /dev/null -w "app  /          -> %{http_code}\n" https://127.0.0.1/accounts/login/ -H 'Host: www.hfflex.com'
curl -sk -o /dev/null -w "crm  /crm/      -> %{http_code}\n" https://127.0.0.1/crm/ -H 'Host: www.hfflex.com'
curl -sk -o /dev/null -w "static admin css -> %{http_code}\n" https://127.0.0.1/static/admin/css/base.css -H 'Host: www.hfflex.com'
echo "Done. Test from your PC: hosts entry  $NEW_IP www.hfflex.com  then https://www.hfflex.com/"
