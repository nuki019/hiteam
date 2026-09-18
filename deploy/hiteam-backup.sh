#!/bin/bash
set -euo pipefail

install -d -m 700 /var/backups/hiteam
stamp=$(date +%Y%m%d)
python3 - "$stamp" <<'PY'
import sqlite3
import sys

stamp = sys.argv[1]
src = sqlite3.connect("/var/lib/hiteam/hiteam.db")
dst = sqlite3.connect(f"/var/backups/hiteam/hiteam-{stamp}.db")
src.backup(dst)
dst.close()
src.close()
PY
find /var/backups/hiteam -type f -name 'hiteam-*.db' -mtime +14 -delete
chmod 600 /var/backups/hiteam/hiteam-"$stamp".db
