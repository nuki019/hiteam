#!/usr/bin/env python3
"""One-shot: wipe HiTeam users and create the first creator. Password comes from a temp file."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

DB_PATH = Path("/var/lib/hiteam/hiteam.db")
PASSWORD_FILE = Path("/tmp/hiteam-boot.pass")
EMAIL = os.environ.get("HITEAM_BOOTSTRAP_EMAIL", "").strip().lower()
NICKNAME = os.environ.get("HITEAM_BOOTSTRAP_NICKNAME", "").strip()
ROUNDS = int(os.environ.get("HITEAM_PBKDF2_ROUNDS", "240000"))
API = "http://127.0.0.1:8788"


def read_password() -> str:
    password = PASSWORD_FILE.read_text(encoding="utf-8").strip()
    try:
        PASSWORD_FILE.unlink()
    except OSError:
        pass
    if not password:
        raise SystemExit("bootstrap password file was empty")
    return password


def wipe_and_create(password: str) -> None:
    stamp = time.strftime("%Y%m%d%H%M%S")
    shutil.copy2(DB_PATH, DB_PATH.with_name(f"hiteam.db.bak.{stamp}"))
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ROUNDS)
    user_id = "u-" + secrets.token_hex(12)
    nickname = NICKNAME or EMAIL.split("@", 1)[0]
    created = int(time.time())
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        connection.execute("DELETE FROM users")
        connection.execute("DELETE FROM otp_challenges")
        connection.execute(
            """
            INSERT INTO users(
                id, account, password_hash, password_salt, nickname,
                system_role, profile_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'creator', '{}', ?, ?)
            """,
            (user_id, EMAIL, digest.hex(), salt.hex(), nickname, created, created),
        )
        connection.commit()
        row = connection.execute(
            "SELECT account, system_role, COUNT(*) OVER () AS users FROM users"
        ).fetchone()
    finally:
        connection.close()
    print(f"creator={row['account']} role={row['system_role']} users={row['users']}")


def post(path: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        API + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"error": body}


def main() -> None:
    if not EMAIL.endswith("@stu.hit.edu.cn"):
        raise SystemExit("bootstrap email must be @stu.hit.edu.cn")
    password = read_password()
    wipe_and_create(password)
    status, data = post("/api/auth/login", {"account": EMAIL, "password": password})
    if status != 200 or not data.get("ok"):
        raise SystemExit(f"password login failed: {status} {data}")
    print(f"password_login=ok role={data['user'].get('systemRole')}")
    status, data = post("/api/auth/otp/send", {"email": EMAIL})
    if status != 200 or not data.get("sent"):
        raise SystemExit(f"otp send failed: {status} {data}")
    print("otp_send=ok")


if __name__ == "__main__":
    main()
