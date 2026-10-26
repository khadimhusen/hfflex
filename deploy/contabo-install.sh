#!/bin/bash
# Install the software stack on the new Contabo VPS (Ubuntu 22.04).
# Run as the sammy user:   sudo bash contabo-install.sh
#
# Installs: PostgreSQL, nginx + certbot, Python build tools, Elasticsearch 8
# (security off, localhost only -- matches ELASTICSEARCH_DSL in settings.py),
# rclone. Does NOT deploy the app or restore any data.

set -eu
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
export DEBIAN_FRONTEND=noninteractive

echo "== apt packages =="
apt-get update -y
apt-get install -y \
    postgresql postgresql-contrib libpq-dev \
    nginx certbot python3-certbot-nginx \
    python3-venv python3-dev python3-pip build-essential git unzip \
    libjpeg-dev zlib1g-dev libxml2-dev libxslt1-dev libffi-dev libssl-dev \
    libcairo2-dev pkg-config gnupg apt-transport-https

echo "== PostgreSQL role and database =="
# Same name/password as DATABASES in myproject/settings.py; the server only
# listens on localhost. Change both together when the password is hardened.
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='myprojectuser'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE ROLE myprojectuser LOGIN PASSWORD 'password'"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='myproject'" | grep -q 1 \
    || sudo -u postgres createdb -O myprojectuser myproject

echo "== Elasticsearch 8 =="
if ! dpkg -s elasticsearch >/dev/null 2>&1; then
    curl -fsSL https://artifacts.elastic.co/GPG-KEY-elasticsearch | gpg --dearmor -o /usr/share/keyrings/elastic.gpg
    echo "deb [signed-by=/usr/share/keyrings/elastic.gpg] https://artifacts.elastic.co/packages/8.x/apt stable main" \
        > /etc/apt/sources.list.d/elastic-8.x.list
    apt-get update -y
    apt-get install -y elasticsearch
fi
cat > /etc/elasticsearch/jvm.options.d/heap.options <<EOF
-Xms1g
-Xmx1g
EOF
# Replace the whole file: the 8.x installer writes its own xpack.security.*,
# cluster.initial_master_nodes and http.host lines, and a duplicate key
# (or single-node + initial_master_nodes) stops Elasticsearch starting.
cat > /etc/elasticsearch/elasticsearch.yml <<EOF
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch
xpack.security.enabled: false
discovery.type: single-node
network.host: 127.0.0.1
EOF
systemctl daemon-reload
systemctl enable --now elasticsearch

echo "== rclone =="
command -v rclone >/dev/null || curl -fsSL https://rclone.org/install.sh | bash

echo "== versions =="
python3 --version
psql --version
nginx -v 2>&1
rclone version | head -1
for i in $(seq 1 30); do
    curl -fs http://127.0.0.1:9200 >/dev/null && break || sleep 3
done
curl -s http://127.0.0.1:9200 | grep -E '"number"|cluster_name' || echo "Elasticsearch not answering yet (give it a minute)"
echo "Install done."
