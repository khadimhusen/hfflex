#!/bin/bash
# First-boot hardening for the new Contabo VPS (Ubuntu). Run as root:
#
#   bash contabo-bootstrap.sh            # step 1: user, key, firewall, updates
#   bash contabo-bootstrap.sh lock-ssh   # step 2: disable SSH password login
#                                        #   (only after `ssh sammy@<ip>` works with the key)
#
# Safe to run more than once.

set -eu

PUBKEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFS7gnv/Cm2E7Nh3TAfRkDhJVMEcO1nA0MtAu1wKEa3o mylaptop'
APP_USER=sammy
TZ_NAME=Asia/Kolkata      # same as the old server, so cron times and log times match

[ "$(id -u)" -eq 0 ] || { echo "run as root"; exit 1; }

if [ "${1:-}" = "lock-ssh" ]; then
    # 00- so it wins over cloud-init's 50-cloud-init.conf (first value read wins)
    cat > /etc/ssh/sshd_config.d/00-hardening.conf <<EOF
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
    sshd -t
    systemctl reload ssh 2>/dev/null || systemctl reload sshd
    echo "SSH password login is now disabled."
    sshd -T | grep -Ei '^(passwordauthentication|permitrootlogin|kbdinteractiveauthentication) '
    exit 0
fi

echo "== OS =="; . /etc/os-release; echo "$PRETTY_NAME"

echo "== packages =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y
apt-get install -y ufw fail2ban unattended-upgrades curl ca-certificates

echo "== timezone =="
timedatectl set-timezone "$TZ_NAME"

echo "== user $APP_USER =="
if ! id "$APP_USER" >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" "$APP_USER"
fi
usermod -aG sudo "$APP_USER"
# no password is set for this user (key-only), so sudo cannot ask for one
echo "$APP_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-$APP_USER
chmod 440 /etc/sudoers.d/90-$APP_USER

for home in /root /home/$APP_USER; do
    mkdir -p "$home/.ssh"
    touch "$home/.ssh/authorized_keys"
    grep -qxF "$PUBKEY" "$home/.ssh/authorized_keys" || echo "$PUBKEY" >> "$home/.ssh/authorized_keys"
    chmod 700 "$home/.ssh"; chmod 600 "$home/.ssh/authorized_keys"
done
chown -R $APP_USER:$APP_USER /home/$APP_USER/.ssh

echo "== firewall (ufw) =="
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "== fail2ban / auto security updates =="
systemctl enable --now fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades

echo "== swap (2G) =="
if ! swapon --show | grep -q .; then
    fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo
echo "Step 1 done. Now test from your PC:   ssh -i ~/.ssh/hfflex_server $APP_USER@<ip>"
echo "Then run:   sudo bash contabo-bootstrap.sh lock-ssh"
