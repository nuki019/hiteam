#!/bin/bash
set -euo pipefail

install -d -m 750 /etc/hiteam

smtp_user=""
smtp_key=""

printf 'Brevo SMTP login (xxx@smtp-brevo.com, NOT your Gmail): '
IFS= read -r smtp_user || true
smtp_user="${smtp_user%$'\r'}"
smtp_user="${smtp_user#"${smtp_user%%[![:space:]]*}"}"
smtp_user="${smtp_user%"${smtp_user##*[![:space:]]}"}"

printf 'Brevo SMTP key (input is hidden): '
IFS= read -rs smtp_key || true
smtp_key="${smtp_key%$'\r'}"
smtp_key="${smtp_key#"${smtp_key%%[![:space:]]*}"}"
smtp_key="${smtp_key%"${smtp_key##*[![:space:]]}"}"
printf '\n'

if [[ -z "${smtp_user}" || -z "${smtp_key}" ]]; then
  echo "SMTP login and key cannot be empty." >&2
  exit 1
fi

umask 077
{
  printf '%s\n' "HITEAM_SMTP_HOST=smtp-relay.brevo.com"
  printf '%s\n' "HITEAM_SMTP_PORT=587"
  printf '%s\n' "HITEAM_SMTP_USER=${smtp_user}"
  printf '%s\n' "HITEAM_SMTP_KEY=${smtp_key}"
  printf '%s\n' "HITEAM_SMTP_FROM=HiTeam <tribbie@mail.hiteam.xyz>"
} > /etc/hiteam/secrets.env

chmod 600 /etc/hiteam/secrets.env
chown root:root /etc/hiteam/secrets.env

systemctl daemon-reload
systemctl restart hiteam-backend.service
systemctl is-active --quiet hiteam-backend.service

echo "Saved /etc/hiteam/secrets.env (mode 600, root only)."
grep -E '^(HITEAM_SMTP_HOST|HITEAM_SMTP_PORT|HITEAM_SMTP_USER|HITEAM_SMTP_FROM)=' /etc/hiteam/secrets.env
echo "HITEAM_SMTP_KEY is set (not printed)."
