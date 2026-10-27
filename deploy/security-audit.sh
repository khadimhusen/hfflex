#!/bin/bash
# Read-only security audit of THIS server. It changes nothing and does not print
# passwords, keys or tokens (SSH keys are shown as fingerprints only).
#
#   sudo bash ~/myprojectdir/deploy/security-audit.sh > ~/audit.txt 2>&1
#   less ~/audit.txt        # or: cat ~/audit.txt
#
# Works on the DigitalOcean droplet (user sammy) and on the Contabo server.

PROJECT=${PROJECT:-/home/sammy/myprojectdir}
APP_USER=${APP_USER:-sammy}

sec() { echo; echo "=== $* ==="; }

sec "1. SYSTEM"
lsb_release -ds 2>/dev/null; echo "kernel: $(uname -r)"; uptime -p
if [ -f /var/run/reboot-required ]; then echo "!! REBOOT REQUIRED (kernel/libs updated but not loaded)"; else echo "no reboot pending"; fi
echo "upgradable packages : $(apt list --upgradable 2>/dev/null | grep -c upgradable)"
echo "of which security   : $(apt list --upgradable 2>/dev/null | grep -c -- -security)"
echo "unattended-upgrades : enabled=$(systemctl is-enabled unattended-upgrades 2>/dev/null) active=$(systemctl is-active unattended-upgrades 2>/dev/null)"
df -h / | tail -1

sec "2. SSH (effective settings)"
sshd -T 2>/dev/null | grep -E '^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|permitemptypasswords|maxauthtries|logingracetime|allowusers|allowgroups|x11forwarding)'
echo "-- authorized_keys (fingerprints) --"
for f in /root/.ssh/authorized_keys /home/*/.ssh/authorized_keys; do
    [ -f "$f" ] || continue
    echo "$f ($(stat -c '%a %U, modified %y' "$f" | cut -c1-40))"
    ssh-keygen -lf "$f" 2>/dev/null | sed 's/^/   /'
done
echo "-- fail2ban --"
systemctl is-active fail2ban 2>/dev/null || echo "fail2ban NOT running"
fail2ban-client status sshd 2>/dev/null | grep -E "Currently|Total"

sec "3. LOGINS"
echo "-- last successful logins --"
last -i -n 15 2>/dev/null | head -17
echo "-- accepted SSH logins in the logs (date, method, user, from) --"
zgrep -h "Accepted" /var/log/auth.log* 2>/dev/null | awk '{print $1,$2,$3,$7,$9,$11}' | tail -20
echo "-- failed SSH password attempts: total and top source IPs --"
zgrep -h "Failed password" /var/log/auth.log* 2>/dev/null | wc -l
zgrep -h "Failed password" /var/log/auth.log* 2>/dev/null | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -5

sec "4. USERS AND PRIVILEGES"
awk -F: '$3==0 {print "UID 0 account: "$1}' /etc/passwd
echo "-- accounts with a login shell --"
awk -F: '$7 !~ /(nologin|false)$/ {print $1" (uid "$3") "$7}' /etc/passwd
echo "-- privileged groups --"
getent group sudo docker adm 2>/dev/null
echo "-- sudo rules without a password --"
grep -rn "NOPASSWD" /etc/sudoers /etc/sudoers.d 2>/dev/null || echo "none"
echo "-- accounts with an EMPTY password --"
awk -F: '($2=="") {print "EMPTY PASSWORD: "$1}' /etc/shadow 2>/dev/null | grep . || echo "none"

sec "5. NETWORK EXPOSURE"
echo "-- listening ports (a bind to 0.0.0.0 or :: is reachable from outside unless firewalled) --"
ss -ltnup 2>/dev/null | awk 'NR==1 || /LISTEN|UNCONN/' | cut -c1-150
echo "-- host firewall --"
ufw status verbose 2>&1 | head -15
echo "-- iptables INPUT policy / Docker chain --"
iptables -S INPUT 2>/dev/null | head -5
iptables -S DOCKER-USER 2>/dev/null | head -5
echo "-- established connections to other hosts (not localhost) --"
ss -tnp state established 2>/dev/null | awk 'NR>1 && $4 !~ /^(127\.|\[::1\]|\[::ffff:127)/ {print $4, $3, $5}' | head -25

sec "6. DOCKER"
if command -v docker >/dev/null; then
    docker ps -a --format 'container {{.Names}}  image={{.Image}}  ports={{.Ports}}  status={{.Status}}' 2>&1 | head -10
    docker images --format 'image {{.Repository}}:{{.Tag}}  {{.Size}}  {{.CreatedSince}}' 2>&1 | head -10
else echo "docker not installed"; fi

sec "7. WEB SERVER (nginx)"
nginx -v 2>&1
echo "-- sites enabled --"; ls /etc/nginx/sites-enabled 2>/dev/null
nginx -T 2>/dev/null | grep -nE "^\s*(server_tokens|ssl_protocols|ssl_ciphers|autoindex|add_header|server_name|listen)\b" | head -40
echo "-- HTTPS certificate renewal --"
systemctl list-timers --no-pager 2>/dev/null | grep -i certbot || echo "no certbot timer found"
certbot certificates 2>/dev/null | grep -E "Certificate Name|Domains|Expiry" | head -12

sec "8. DJANGO APP"
runuser -u "$APP_USER" -- bash -c "cd '$PROJECT' && source myprojectenv/bin/activate && python --version && python -c 'import django; print(\"Django\", django.get_version())' && python manage.py check --deploy 2>&1 | tail -30"
echo "-- security-related lines in settings.py (SECRET_KEY is not printed) --"
grep -nE "^(DEBUG|ALLOWED_HOSTS|SECURE_[A-Z_]+|SESSION_COOKIE_[A-Z_]+|CSRF_[A-Z_]+|X_FRAME_OPTIONS)\b" "$PROJECT/myproject/settings.py" 2>/dev/null | cut -c1-140
echo "-- permissions of secret files --"
stat -c '%a %U:%G %n' "$PROJECT/myproject/settings.py" "$PROJECT/.env" /home/*/.config/rclone/rclone.conf 2>/dev/null
echo "-- world-writable files/dirs under the project (first 15) --"
find "$PROJECT" -xdev -perm -0002 ! -type l ! -path '*/node_modules/*' ! -path '*/__pycache__/*' ! -path '*/myprojectenv/*' 2>/dev/null | head -15

sec "9. DATABASE AND SEARCH"
echo "-- postgres listens on --"
ss -ltn 2>/dev/null | grep -E ':5432\b' || echo "postgres not listening on TCP"
echo "-- pg_hba.conf active rules --"
grep -hvE '^\s*(#|$)' /etc/postgresql/*/main/pg_hba.conf 2>/dev/null | head -12
echo "-- does the database accept the password 'password'? (a result of 1 = WEAK) --"
PGPASSWORD=password psql -h localhost -U myprojectuser -d myproject -tAc 'select 1' 2>&1 | head -1
echo "-- Elasticsearch (should be reachable from localhost only) --"
curl -s -m 3 http://127.0.0.1:9200 2>/dev/null | grep -E '"number"|cluster_name' || echo "no answer on 9200"
curl -s -m 3 -o /dev/null -w "ES answers without a login: HTTP %{http_code}\n" http://127.0.0.1:9200/_cluster/health 2>/dev/null

sec "10. SCHEDULED JOBS AND SERVICES"
for u in $(cut -d: -f1 /etc/passwd); do
    crontab -l -u "$u" 2>/dev/null | grep -vE '^\s*(#|$)' | sed "s/^/[crontab $u] /"
done
echo "-- /etc/cron.d --"; ls /etc/cron.d 2>/dev/null
echo "-- running services --"
systemctl list-units --type=service --state=running --no-pager 2>/dev/null | awk 'NR>1 {print $1}' | grep -E '\.service$' | head -40

sec "11. SIGNS OF TAMPERING"
echo "-- busiest processes --"
ps aux --sort=-%cpu 2>/dev/null | head -8 | cut -c1-150
echo "-- executables in /tmp, /var/tmp, /dev/shm --"
find /tmp /var/tmp /dev/shm -type f -perm /111 2>/dev/null | head -10
echo "-- ld.so.preload (should not exist) --"; ls -la /etc/ld.so.preload 2>&1 | head -2
echo "-- files in /etc changed in the last 14 days (first 30) --"
find /etc -xdev -type f -mtime -14 2>/dev/null | head -30
echo "-- setuid programs outside the usual places --"
find / -xdev -perm -4000 -type f 2>/dev/null | grep -vE '^/(usr/bin/(sudo|su|passwd|chsh|chfn|gpasswd|newgrp|mount|umount|pkexec|fusermount3|at|crontab)|usr/lib/(dbus-1.0/dbus-daemon-launch-helper|openssh/ssh-keysign|snapd/snap-confine|polkit-1/polkit-agent-helper-1|eject/dmcrypt-get-device)|bin/(su|mount|umount|ping|fusermount))$' | head -15

sec "12. BACKUP STATE"
echo "last OK: $(cat /var/log/hfflex-backup.last-ok 2>/dev/null || echo 'file missing')"
tail -3 /var/log/hfflex-backup.log 2>/dev/null

sec "END OF AUDIT"
