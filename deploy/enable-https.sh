#!/bin/bash
set -euo pipefail

NGINX=/www/server/nginx/sbin/nginx
VHOST=/www/server/panel/vhost/nginx/hiteam.conf
WEBROOT=/var/www/hiteam
STAMP=$(date +%Y%m%d%H%M%S)

cp -a "$VHOST" "${VHOST}.bak.${STAMP}"
cp -a /etc/systemd/system/hiteam-backend.service "/etc/systemd/system/hiteam-backend.service.bak.${STAMP}"

mkdir -p "${WEBROOT}/.well-known/acme-challenge"
chown -R www:www "${WEBROOT}/.well-known"
echo ok > "${WEBROOT}/.well-known/acme-challenge/ping"
chmod 644 "${WEBROOT}/.well-known/acme-challenge/ping"

cat > "$VHOST" <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name 191.40.41.14 hiteam.xyz www.hiteam.xyz _;

    root /var/www/hiteam;

    location ^~ /.well-known/acme-challenge/ {
        default_type "text/plain";
        try_files $uri =404;
    }

    location / {
        return 301 https://hiteam.xyz$request_uri;
    }
}
EOF

"$NGINX" -t
"$NGINX" -s reload

curl -fsS "http://127.0.0.1/.well-known/acme-challenge/ping" -H "Host: hiteam.xyz" | grep -qx ok
curl -fsS "http://hiteam.xyz/.well-known/acme-challenge/ping" | grep -qx ok

if [[ ! -x /root/.acme.sh/acme.sh ]]; then
  curl -fsSL https://get.acme.sh | sh -s email=admin@hiteam.xyz
fi

/root/.acme.sh/acme.sh --set-default-ca --server letsencrypt
/root/.acme.sh/acme.sh --issue -d hiteam.xyz -d www.hiteam.xyz -w "$WEBROOT" --keylength 2048

install -d -m 755 /etc/letsencrypt/live/hiteam.xyz
/root/.acme.sh/acme.sh --install-cert -d hiteam.xyz \
  --key-file /etc/letsencrypt/live/hiteam.xyz/privkey.pem \
  --fullchain-file /etc/letsencrypt/live/hiteam.xyz/fullchain.pem \
  --reloadcmd "$NGINX -s reload"

install -m 644 /tmp/hiteam.conf "$VHOST"
install -m 644 /tmp/hiteam-backend.service /etc/systemd/system/hiteam-backend.service
if [[ -f /tmp/hiteam-security-headers.conf ]]; then
  install -d -m 750 /etc/hiteam
  install -m 644 /tmp/hiteam-security-headers.conf /etc/hiteam/security-headers.conf
  sed -i 's/\r$//' /etc/hiteam/security-headers.conf
fi

"$NGINX" -t
"$NGINX" -s reload
systemctl daemon-reload
systemctl restart hiteam-backend.service
systemctl is-active --quiet hiteam-backend.service

rm -f "${WEBROOT}/.well-known/acme-challenge/ping"

echo "===== LOCAL CHECKS ====="
curl -sS -D - -o /dev/null -H "Host: hiteam.xyz" http://127.0.0.1/ | head -n 12
curl -sS -D - -o /dev/null --resolve hiteam.xyz:443:127.0.0.1 https://hiteam.xyz/ | head -n 15
curl -sS --resolve hiteam.xyz:443:127.0.0.1 https://hiteam.xyz/api/health
echo
curl -sS -H "Host: qqptr.top" http://127.0.0.1/ | grep -iE "<title>" | head
echo "HTTPS enable finished"
