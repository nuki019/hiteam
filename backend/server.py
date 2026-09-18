#!/usr/bin/env python3
"""Dependency-free HiTeam backend.

Authentication, profiles, recruitments, applications, notifications and drafts
are stored in SQLite. Binary files remain client-side until storage is
introduced deliberately.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("HITEAM_DB_PATH", ROOT / "hiteam.db"))
HOST = os.environ.get("HITEAM_HOST", "127.0.0.1")
PORT = int(os.environ.get("HITEAM_PORT", "8787"))
SESSION_DAYS = 14
PBKDF2_ROUNDS = int(os.environ.get("HITEAM_PBKDF2_ROUNDS", "240000"))
MAX_BODY_BYTES = 2 * 1024 * 1024
ALLOWED_ORIGINS = {
    "http://127.0.0.1:8765",
    "http://localhost:8765",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
}

DEFAULT_TAGS = [
    "Python",
    "C++",
    "Java",
    "前端",
    "后端",
    "嵌入式",
    "机器学习",
    "计算机视觉",
    "数据分析",
    "算法竞赛",
    "数学建模",
    "科研写作",
    "产品设计",
    "UI 设计",
    "英语答辩",
]
DEFAULT_COMPETITIONS = [
    ("general-innovation", "中国国际大学生创新大赛", "创新赛", "国家"),
    ("challenge-cup", "挑战杯", "挑战杯", "国家"),
    ("robomaster", "RoboMaster 机甲大师赛", "RoboMaster", "国家"),
    ("math-modeling", "全国大学生数学建模竞赛", "数模", "国家"),
    ("annual-project", "年度项目", "年度项目", "校"),
    ("innovation-training", "大创计划", "大创", "校"),
]


def now() -> int:
    return int(time.time())


def iso_time(value: int | float | None) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat().replace("+00:00", "Z")


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                account TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                nickname TEXT NOT NULL,
                system_role TEXT NOT NULL DEFAULT 'applicant',
                profile_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recruitments (
                id TEXT PRIMARY KEY,
                publisher_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'open',
                current_count INTEGER NOT NULL DEFAULT 0,
                payload_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                recruitment_id TEXT NOT NULL REFERENCES recruitments(id) ON DELETE CASCADE,
                applicant_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                reviewed_at INTEGER,
                UNIQUE(recruitment_id, applicant_id)
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                recipient_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                kind TEXT NOT NULL DEFAULT 'notification',
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                contact TEXT NOT NULL DEFAULT '',
                read INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS catalog_tags (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS catalog_competitions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                subtitle TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT '国家',
                aliases_json TEXT NOT NULL DEFAULT '[]',
                bonus_type TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tag_requests (
                id TEXT PRIMARY KEY,
                requester_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
                created_at INTEGER NOT NULL,
                reviewed_at INTEGER
            );

            CREATE TABLE IF NOT EXISTS catalog_projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL UNIQUE COLLATE NOCASE,
                program_id TEXT NOT NULL DEFAULT 'general_competition',
                summary TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                library_year TEXT NOT NULL DEFAULT '',
                advisor TEXT NOT NULL DEFAULT '',
                college TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS project_competition_links (
                project_id TEXT NOT NULL REFERENCES catalog_projects(id) ON DELETE CASCADE,
                competition_id TEXT NOT NULL REFERENCES catalog_competitions(id) ON DELETE CASCADE,
                PRIMARY KEY(project_id, competition_id)
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                operator_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                target_id TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                payload_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS idx_recruitments_status ON recruitments(status);
            CREATE INDEX IF NOT EXISTS idx_recruitments_publisher ON recruitments(publisher_id);
            CREATE INDEX IF NOT EXISTS idx_applications_recruitment ON applications(recruitment_id);
            CREATE INDEX IF NOT EXISTS idx_applications_applicant ON applications(applicant_id);
            CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_drafts_owner ON drafts(owner_id, updated_at);
            """
        )
        ensure_column(connection, "users", "profile_json", "TEXT NOT NULL DEFAULT '{}'")
        ensure_column(connection, "catalog_competitions", "level", "TEXT NOT NULL DEFAULT '国家'")
        ensure_column(connection, "catalog_competitions", "aliases_json", "TEXT NOT NULL DEFAULT '[]'")
        ensure_column(connection, "catalog_competitions", "bonus_type", "TEXT NOT NULL DEFAULT ''")
        ensure_column(connection, "catalog_projects", "program_id", "TEXT NOT NULL DEFAULT 'general_competition'")
        ensure_column(connection, "catalog_projects", "library_year", "TEXT NOT NULL DEFAULT ''")
        connection.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        # The old per-user collaboration workspace was only prototype data.
        connection.execute("DROP TABLE IF EXISTS collaboration_records")
        connection.execute(
            "UPDATE messages SET body = REPLACE(body, ?, ?) WHERE body LIKE ?",
            ("队长已通过你的申请，双方可以开始协作。", "队长已通过你的申请，请尽快与队伍成员建立群聊。", "%开始协作。%"),
        )
        connection.execute(
            "UPDATE messages SET body = REPLACE(body, ?, ?) WHERE body LIKE ?",
            ("已加入队伍，可以开始协作。", "已加入队伍，请尽快建立群聊。", "%可以开始协作。%"),
        )
        seed_catalog(connection)


def ensure_column(connection: sqlite3.Connection, table: str, name: str, definition: str) -> None:
    columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
    if name not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def seed_catalog(connection: sqlite3.Connection) -> None:
    timestamp = now()
    for index, name in enumerate(DEFAULT_TAGS):
        connection.execute(
            "INSERT OR IGNORE INTO catalog_tags(id, name, created_at) VALUES (?, ?, ?)",
            (f"tag-{index + 1:03d}", name, timestamp),
        )
    for identifier, name, subtitle, level in DEFAULT_COMPETITIONS:
        connection.execute(
            """
            INSERT OR IGNORE INTO catalog_competitions(id, name, subtitle, level, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (identifier, name, subtitle, level, timestamp),
        )


def parse_json(raw: str, fallback: object) -> object:
    try:
        value = json.loads(raw)
        return value
    except (TypeError, json.JSONDecodeError):
        return fallback


def public_user(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "account": row["account"],
        "nickname": row["nickname"],
        "systemRole": row["system_role"] if row["system_role"] != "applicant" else None,
        "createdAt": iso_time(row["created_at"]),
    }


def profile_for(row: sqlite3.Row, viewer_id: str, reveal_contact: bool = False) -> dict:
    profile = parse_json(row["profile_json"], {})
    if not isinstance(profile, dict):
        profile = {}
    is_self = row["id"] == viewer_id
    result = {
        "id": row["id"],
        # Keep the field for existing clients, but never disclose another user's login name.
        "account": row["account"] if is_self else "",
        "nickname": row["nickname"],
        "realName": str(profile.get("realName", "")),
        "realNameVisibility": str(profile.get("realNameVisibility", "private")),
        "avatar": str(profile.get("avatar", "")),
        "campus": str(profile.get("campus", "")),
        "college": str(profile.get("college", "")),
        "major": str(profile.get("major", "")),
        "grade": str(profile.get("grade", "")),
        "gradeCohort": str(profile.get("gradeCohort", "")),
        "degree": str(profile.get("degree", "")),
        "contact": str(profile.get("contact", "")),
        "contacts": profile.get("contacts", []) if isinstance(profile.get("contacts", []), list) else [],
        "contactVisibility": str(profile.get("contactVisibility", "matched")),
        "tags": profile.get("tags", []) if isinstance(profile.get("tags", []), list) else [],
        "bio": str(profile.get("bio", "")),
        "awards": profile.get("awards", []) if isinstance(profile.get("awards", []), list) else [],
        "systemRole": row["system_role"] if row["system_role"] != "applicant" else None,
        "createdAt": iso_time(row["created_at"]),
    }
    if not is_self:
        if result["realNameVisibility"] != "public":
            result["realName"] = ""
        # "reveal_contact" is used only for an accepted match.  A private
        # contact remains private even then; public contacts stay visible to all.
        may_reveal_contact = result["contactVisibility"] == "public" or (
            reveal_contact and result["contactVisibility"] == "matched"
        )
        if not may_reveal_contact:
            result["contact"] = ""
            result["contacts"] = []
        result["avatar"] = result["avatar"] if result["avatar"].startswith("data:image/") else ""
    return result


def password_hash(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, expected_hex: str) -> bool:
    _, actual_hex = password_hash(password, salt_hex)
    return hmac.compare_digest(actual_hex, expected_hex)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    created = now()
    with get_connection() as connection:
        connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        connection.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token_hash(token), user_id, created + SESSION_DAYS * 86400, created),
        )
    return token


def current_user(handler: BaseHTTPRequestHandler) -> sqlite3.Row | None:
    morsel = SimpleCookie(handler.headers.get("Cookie", "")).get("hiteam_session")
    token = morsel.value if morsel else ""
    if not token:
        return None
    with get_connection() as connection:
        return connection.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at >= ?
            """,
            (token_hash(token), now()),
        ).fetchone()


def json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length > MAX_BODY_BYTES:
        raise ValueError("请求内容过大")
    raw = handler.rfile.read(length) if length else b"{}"
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("请求格式错误")
    return payload


def text_value(payload: dict, key: str, maximum: int = 120) -> str:
    value = str(payload.get(key, "")).strip()
    if len(value) > maximum:
        raise ValueError(f"{key} 内容过长")
    return value


def safe_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(12)}"


def recruitment_payload(row: sqlite3.Row) -> dict:
    stored = parse_json(row["payload_json"], {})
    return stored if isinstance(stored, dict) else {}


def recruitment_status_of(row: sqlite3.Row) -> str:
    try:
        value = row["recruitment_status"]
    except (IndexError, KeyError):
        value = row["status"]
    return str(value or "")


def recruitment_closed(row: sqlite3.Row) -> bool:
    return recruitment_status_of(row) != "open"


def recruitment_full(row: sqlite3.Row, stored: dict | None = None) -> bool:
    payload = stored if stored is not None else recruitment_payload(row)
    total = int(payload.get("total", 0) or 0)
    return bool(total) and int(row["current_count"]) >= total


def cannot_apply_reason(row: sqlite3.Row, stored: dict | None = None) -> str:
    payload = stored if stored is not None else recruitment_payload(row)
    if recruitment_closed(row):
        return "该招募当前不可申请"
    if deadline_expired(payload.get("deadline", "")):
        return "该招募已截止"
    if recruitment_full(row, payload):
        return "队伍已满员"
    return ""


def cannot_accept_reason(row: sqlite3.Row, stored: dict | None = None) -> str:
    payload = stored if stored is not None else recruitment_payload(row)
    if recruitment_closed(row):
        return "该招募已关闭，不能通过申请"
    if deadline_expired(payload.get("deadline", "")):
        return "该招募已截止，不能通过申请"
    if recruitment_full(row, payload):
        return "队伍已满员，不能继续通过申请"
    return ""


def deadline_expired(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp() < time.time()
    except (TypeError, ValueError, OverflowError):
        return False


def message_payload(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "title": row["title"],
        "body": row["body"],
        "contact": row["contact"],
        "read": bool(row["read"]),
        "createdAt": iso_time(row["created_at"]),
    }


def insert_message(
    connection: sqlite3.Connection,
    recipient_id: str,
    kind: str,
    title: str,
    body: str,
    contact: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO messages(id, recipient_id, kind, title, body, contact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (safe_id("conv" if kind == "conversation" else "msg"), recipient_id, kind, title, body, contact, now()),
    )


def payload_recruitment(row: sqlite3.Row, connection: sqlite3.Connection, viewer_id: str) -> dict:
    payload = parse_json(row["payload_json"], {})
    if not isinstance(payload, dict):
        payload = {}
    item = dict(payload)
    item["id"] = row["id"]
    item["publisherId"] = row["publisher_id"]
    item["status"] = row["status"]
    item["current"] = row["current_count"]
    item.setdefault("applications", [])
    if row["status"] == "open" and deadline_expired(item.get("deadline", "")):
        item["status"] = "expired"

    applications = connection.execute(
        """
        SELECT * FROM applications
        WHERE recruitment_id = ? AND (applicant_id = ? OR recruitment_id IN (
            SELECT id FROM recruitments WHERE publisher_id = ?
        ))
        ORDER BY created_at DESC
        """,
        (row["id"], viewer_id, viewer_id),
    ).fetchall()
    item["applications"] = [
        {
            "id": application["id"],
            "userId": application["applicant_id"],
            "message": application["message"],
            "status": application["status"],
            "createdAt": iso_time(application["created_at"]),
            "reviewedAt": iso_time(application["reviewed_at"]),
        }
        for application in applications
    ]
    return item


def workspace_payload(viewer: sqlite3.Row) -> dict:
    viewer_id = viewer["id"]
    with get_connection() as connection:
        user_rows = connection.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
        recruitment_rows = connection.execute(
            "SELECT * FROM recruitments ORDER BY created_at DESC"
        ).fetchall()
        notification_rows = connection.execute(
            "SELECT * FROM messages WHERE recipient_id = ? AND kind != 'conversation' ORDER BY created_at DESC",
            (viewer_id,),
        ).fetchall()
        conversation_rows = connection.execute(
            "SELECT * FROM messages WHERE recipient_id = ? AND kind = 'conversation' ORDER BY created_at DESC",
            (viewer_id,),
        ).fetchall()
        tag_usage: dict[str, int] = {}
        for user_row in user_rows:
            profile = parse_json(user_row["profile_json"], {})
            if not isinstance(profile, dict):
                continue
            values = profile.get("tags", [])
            if not isinstance(values, list):
                continue
            for value in values:
                name = str(value).strip().casefold()
                if name:
                    tag_usage[name] = tag_usage.get(name, 0) + 1
        tags = [
            {
                "id": row["id"],
                "name": row["name"],
                "status": "official",
                "active": bool(row["active"]),
                "usageCount": tag_usage.get(row["name"].strip().casefold(), 0),
            }
            for row in connection.execute("SELECT * FROM catalog_tags WHERE active = 1 ORDER BY name")
        ]
        competitions = [
            {
                "id": row["id"],
                "name": row["name"],
                "subtitle": row["subtitle"],
                "level": row["level"],
                "aliases": parse_json(row["aliases_json"], []) if isinstance(parse_json(row["aliases_json"], []), list) else [],
                "bonusType": row["bonus_type"],
                "active": bool(row["active"]),
            }
            for row in connection.execute(
                "SELECT * FROM catalog_competitions WHERE active = 1 ORDER BY name"
            )
        ]
        projects = [
            {
                "id": row["id"],
                "title": row["title"],
                "programId": row["program_id"],
                "summary": row["summary"],
                "source": row["source"],
                "libraryYear": row["library_year"],
                "advisor": row["advisor"],
                "college": row["college"],
                "active": bool(row["active"]),
            }
            for row in connection.execute("SELECT * FROM catalog_projects WHERE active = 1 ORDER BY title")
        ]
        links = [
            {"projectId": row["project_id"], "competitionId": row["competition_id"]}
            for row in connection.execute("SELECT * FROM project_competition_links")
        ]
        can_view_platform_admin = viewer["system_role"] in {"admin", "creator"}
        if can_view_platform_admin:
            creator = connection.execute(
                "SELECT id FROM users WHERE system_role = 'creator' ORDER BY created_at LIMIT 1"
            ).fetchone()
            admins = connection.execute(
                "SELECT id FROM users WHERE system_role IN ('admin', 'creator') ORDER BY created_at"
            ).fetchall()
            audit_logs = connection.execute(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        request_rows = connection.execute(
            """
            SELECT tag_requests.*, users.nickname AS requester_name
            FROM tag_requests
            JOIN users ON users.id = tag_requests.requester_id
            WHERE tag_requests.requester_id = ? OR ? IN ('admin', 'creator')
            ORDER BY tag_requests.created_at DESC
            """,
            (viewer_id, viewer["system_role"]),
        ).fetchall()
        draft_rows = connection.execute(
            "SELECT * FROM drafts WHERE owner_id = ? ORDER BY updated_at DESC",
            (viewer_id,),
        ).fetchall()
        return {
            "version": "5.0-match-completion",
            "serverUpdatedAt": now(),
            "users": [profile_for(row, viewer_id) for row in user_rows],
            "tags": tags,
            "competitions": competitions,
            "projects": projects,
            "projectCompetitionLinks": links,
            "recruitments": [
                payload_recruitment(row, connection, viewer_id) for row in recruitment_rows
            ],
            "messages": [message_payload(row) for row in notification_rows],
            "conversations": [message_payload(row) for row in conversation_rows],
            "drafts": [
                {
                    "id": row["id"],
                    "data": parse_json(row["payload_json"], {}),
                    "updatedAt": iso_time(row["updated_at"]),
                }
                for row in draft_rows
            ],
            # The client supplies defaults for this object, so an empty value
            # preserves its state shape without leaking platform governance data.
            "platform": (
                {
                    "creatorId": creator["id"] if creator else None,
                    "adminIds": [row["id"] for row in admins],
                    "auditLog": [
                        {
                            "id": row["id"],
                            "action": row["action"],
                            "targetId": row["target_id"],
                            "operator": row["operator_id"],
                            "detail": row["detail"],
                            "createdAt": iso_time(row["created_at"]),
                        }
                        for row in audit_logs
                    ],
                }
                if can_view_platform_admin
                else {}
            ),
            "customTags": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "requester": row["requester_name"],
                    "requesterId": row["requester_id"],
                    "status": row["status"],
                    "createdAt": iso_time(row["created_at"]),
                    "reviewedAt": iso_time(row["reviewed_at"]),
                }
                for row in request_rows
            ],
            "profile": profile_for(viewer, viewer_id, reveal_contact=True),
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "HiTeam/2.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {self.address_string()} {fmt % args}")

    def end_headers(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def send_json(self, status: int, payload: dict, cookie: str = "") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def error(self, status: int, message: str) -> None:
        self.send_json(status, {"ok": False, "error": message})

    def session_cookie(self, token: str, clear: bool = False) -> str:
        max_age = 0 if clear else SESSION_DAYS * 86400
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        return f"hiteam_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure}"

    def require_user(self) -> sqlite3.Row | None:
        user = current_user(self)
        if user is None:
            self.error(HTTPStatus.UNAUTHORIZED, "请先登录")
        return user

    def require_admin(self) -> sqlite3.Row | None:
        user = self.require_user()
        if user and user["system_role"] not in {"admin", "creator"}:
            self.error(HTTPStatus.FORBIDDEN, "只有系统管理员或平台创建者可以维护目录")
            return None
        return user

    def require_creator(self) -> sqlite3.Row | None:
        user = self.require_user()
        if user and user["system_role"] != "creator":
            self.error(HTTPStatus.FORBIDDEN, "只有平台创建者可以执行此操作")
            return None
        return user

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json(HTTPStatus.OK, {"ok": True, "service": "hiteam-backend"})
            return
        if path == "/api/auth/session":
            user = public_user(current_user(self))
            self.send_json(HTTPStatus.OK, {"ok": True, "authenticated": user is not None, "user": user})
            return
        if path == "/api/workspace":
            user = self.require_user()
            if user:
                self.send_json(HTTPStatus.OK, {"ok": True, "state": workspace_payload(user)})
            return
        self.error(HTTPStatus.NOT_FOUND, "接口不存在")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/auth/register":
                self.register()
                return
            if path == "/api/auth/login":
                self.login()
                return
            if path == "/api/auth/logout":
                self.logout()
                return
            if path == "/api/profile":
                self.update_profile()
                return
            if path == "/api/recruitments":
                self.create_recruitment()
                return
            if path == "/api/messages/read":
                self.mark_messages_read()
                return
            if path == "/api/catalog/tags":
                self.create_tag()
                return
            if path == "/api/catalog/tag-requests":
                self.create_tag_request()
                return
            if path == "/api/catalog/competitions":
                self.create_competition()
                return
            if path == "/api/catalog/projects":
                self.create_project()
                return
            if path == "/api/drafts":
                self.save_draft()
                return
            recruitment_id = self.path_id("/api/recruitments/")
            if recruitment_id and path.endswith("/applications"):
                self.create_application(recruitment_id)
                return
            self.error(HTTPStatus.NOT_FOUND, "接口不存在")
        except ValueError as exc:
            self.error(HTTPStatus.BAD_REQUEST, str(exc))
        except sqlite3.IntegrityError:
            self.error(HTTPStatus.CONFLICT, "数据已存在或状态已变化")
        except Exception as exc:  # pragma: no cover
            print(f"request failed: {exc}")
            self.error(HTTPStatus.INTERNAL_SERVER_ERROR, "服务器暂时无法处理请求")

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/profile":
                self.update_profile()
                return
            self.error(HTTPStatus.NOT_FOUND, "接口不存在")
        except ValueError as exc:
            self.error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover
            print(f"request failed: {exc}")
            self.error(HTTPStatus.INTERNAL_SERVER_ERROR, "服务器暂时无法处理请求")

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            draft_id = self.path_id("/api/drafts/")
            if draft_id:
                self.delete_draft(draft_id)
                return
            self.error(HTTPStatus.NOT_FOUND, "接口不存在")
        except ValueError as exc:
            self.error(HTTPStatus.BAD_REQUEST, str(exc))
        except Exception as exc:  # pragma: no cover
            print(f"request failed: {exc}")
            self.error(HTTPStatus.INTERNAL_SERVER_ERROR, "服务器暂时无法处理请求")

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            application_id = self.path_id("/api/applications/")
            if application_id:
                self.review_application(application_id)
                return
            admin_user_id = self.path_id("/api/admin/users/")
            if admin_user_id:
                self.update_admin_role(admin_user_id)
                return
            tag_id = self.path_id("/api/catalog/tags/")
            if tag_id:
                self.update_catalog_item("tags", tag_id)
                return
            tag_request_id = self.path_id("/api/catalog/tag-requests/")
            if tag_request_id:
                self.review_tag_request(tag_request_id)
                return
            competition_id = self.path_id("/api/catalog/competitions/")
            if competition_id:
                self.update_catalog_item("competitions", competition_id)
                return
            project_id = self.path_id("/api/catalog/projects/")
            if project_id:
                self.update_catalog_item("projects", project_id)
                return
            recruitment_id = self.path_id("/api/recruitments/")
            if recruitment_id:
                self.update_recruitment(recruitment_id)
                return
            self.error(HTTPStatus.NOT_FOUND, "接口不存在")
        except ValueError as exc:
            self.error(HTTPStatus.BAD_REQUEST, str(exc))
        except sqlite3.IntegrityError:
            self.error(HTTPStatus.CONFLICT, "数据已存在或状态已变化")
        except Exception as exc:  # pragma: no cover
            print(f"request failed: {exc}")
            self.error(HTTPStatus.INTERNAL_SERVER_ERROR, "服务器暂时无法处理请求")

    def path_id(self, prefix: str) -> str:
        path = unquote(urlparse(self.path).path)
        if not path.startswith(prefix):
            return ""
        remainder = path[len(prefix):].strip("/")
        return remainder.split("/", 1)[0] if remainder else ""

    def write_audit(
        self,
        connection: sqlite3.Connection,
        operator_id: str,
        action: str,
        target_id: str = "",
        detail: str = "",
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_logs(id, operator_id, action, target_id, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (safe_id("audit"), operator_id, action, target_id, detail, now()),
        )

    def create_tag(self) -> None:
        user = self.require_admin()
        if not user:
            return
        payload = json_body(self)
        name = text_value(payload, "name", 80)
        if not name:
            raise ValueError("标签名称不能为空")
        identifier = safe_id("tag")
        with get_connection() as connection:
            connection.execute(
                "INSERT INTO catalog_tags(id, name, created_at) VALUES (?, ?, ?)",
                (identifier, name, now()),
            )
            self.write_audit(connection, user["id"], "create_tag", identifier, name)
        self.send_json(HTTPStatus.CREATED, {"ok": True, "id": identifier})

    def create_tag_request(self) -> None:
        user = self.require_user()
        if not user:
            return
        payload = json_body(self)
        name = text_value(payload, "name", 80)
        if not name:
            raise ValueError("标签名称不能为空")
        with get_connection() as connection:
            official = connection.execute(
                "SELECT id FROM catalog_tags WHERE name = ? COLLATE NOCASE AND active = 1",
                (name,),
            ).fetchone()
            if official:
                self.send_json(HTTPStatus.OK, {"ok": True, "status": "official", "id": official["id"]})
                return
            pending = connection.execute(
                """
                SELECT id FROM tag_requests
                WHERE requester_id = ? AND name = ? COLLATE NOCASE AND status = 'pending'
                """,
                (user["id"], name),
            ).fetchone()
            if pending:
                self.send_json(HTTPStatus.OK, {"ok": True, "status": "pending", "id": pending["id"]})
                return
            identifier = safe_id("tag-request")
            connection.execute(
                """
                INSERT INTO tag_requests(id, requester_id, name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (identifier, user["id"], name, now()),
            )
        self.send_json(HTTPStatus.CREATED, {"ok": True, "status": "pending", "id": identifier})

    def create_competition(self) -> None:
        user = self.require_admin()
        if not user:
            return
        payload = json_body(self)
        name = text_value(payload, "name", 160)
        subtitle = text_value(payload, "subtitle", 80)
        level = text_value(payload, "level", 40) or "国家"
        aliases = payload.get("aliases", [])
        if not isinstance(aliases, list):
            aliases = [item.strip() for item in str(aliases).split(",") if item.strip()]
        aliases = list(dict.fromkeys(str(item).strip() for item in aliases if str(item).strip()))[:20]
        bonus_type = text_value(payload, "bonusType", 40)
        if not name:
            raise ValueError("竞赛名称不能为空")
        identifier = safe_id("competition")
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO catalog_competitions(
                    id, name, subtitle, level, aliases_json, bonus_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (identifier, name, subtitle, level, json.dumps(aliases, ensure_ascii=False), bonus_type, now()),
            )
            self.write_audit(connection, user["id"], "create_competition", identifier, name)
        self.send_json(HTTPStatus.CREATED, {"ok": True, "id": identifier})

    def create_project(self) -> None:
        user = self.require_admin()
        if not user:
            return
        payload = json_body(self)
        title = text_value(payload, "title", 200)
        summary = text_value(payload, "summary", 2000)
        program_id = text_value(payload, "programId", 60) or "general_competition"
        source = text_value(payload, "source", 80) or "library"
        library_year = text_value(payload, "libraryYear", 80)
        advisor = text_value(payload, "advisor", 120)
        college = text_value(payload, "college", 120)
        if not title:
            raise ValueError("项目题目不能为空")
        identifier = safe_id("project")
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO catalog_projects(
                    id, title, program_id, summary, source, library_year,
                    advisor, college, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    title,
                    program_id,
                    summary,
                    source,
                    library_year,
                    advisor,
                    college,
                    now(),
                ),
            )
            self.write_audit(connection, user["id"], "create_project", identifier, title)
        self.send_json(HTTPStatus.CREATED, {"ok": True, "id": identifier})

    def update_catalog_item(self, kind: str, identifier: str) -> None:
        user = self.require_admin()
        if not user:
            return
        payload = json_body(self)
        active = bool(payload["active"]) if "active" in payload else True
        table = {
            "tags": "catalog_tags",
            "competitions": "catalog_competitions",
            "projects": "catalog_projects",
        }[kind]
        with get_connection() as connection:
            existing = connection.execute(
                f"SELECT * FROM {table} WHERE id = ?", (identifier,)
            ).fetchone()
            if existing is None:
                self.error(HTTPStatus.NOT_FOUND, "目录项不存在")
                return
            if kind == "competitions" and ("aliases" in payload or "bonusType" in payload or "mergeInto" in payload):
                merge_into = text_value(payload, "mergeInto", 120)
                if merge_into:
                    target = connection.execute(
                        "SELECT * FROM catalog_competitions WHERE id = ? AND active = 1", (merge_into,)
                    ).fetchone()
                    if target is None or target["id"] == identifier:
                        raise ValueError("合并目标竞赛不存在")
                    source_aliases = parse_json(existing["aliases_json"], [])
                    target_aliases = parse_json(target["aliases_json"], [])
                    merged = list(dict.fromkeys(
                        [existing["name"], *source_aliases, *target_aliases]
                    ))[:20]
                    connection.execute(
                        "UPDATE catalog_competitions SET aliases_json = ? WHERE id = ?",
                        (json.dumps(merged, ensure_ascii=False), target["id"]),
                    )
                    connection.execute(
                        "UPDATE catalog_competitions SET active = 0 WHERE id = ?", (identifier,)
                    )
                    self.write_audit(connection, user["id"], "merge_competition", identifier, target["id"])
                    self.send_json(HTTPStatus.OK, {"ok": True, "mergedInto": target["id"]})
                    return
                aliases = payload.get("aliases", parse_json(existing["aliases_json"], []))
                if not isinstance(aliases, list):
                    aliases = [item.strip() for item in str(aliases).split(",") if item.strip()]
                aliases = list(dict.fromkeys(str(item).strip() for item in aliases if str(item).strip()))[:20]
                bonus_type = text_value(payload, "bonusType", existing["bonus_type"])
                connection.execute(
                    """
                    UPDATE catalog_competitions
                    SET active = ?, aliases_json = ?, bonus_type = ?
                    WHERE id = ?
                    """,
                    (1 if active else 0, json.dumps(aliases, ensure_ascii=False), bonus_type, identifier),
                )
            else:
                connection.execute(
                    f"UPDATE {table} SET active = ? WHERE id = ?", (1 if active else 0, identifier)
                )
            self.write_audit(
                connection,
                user["id"],
                f"{'activate' if active else 'deactivate'}_{kind[:-1]}",
                identifier,
            )
        self.send_json(HTTPStatus.OK, {"ok": True})

    def review_tag_request(self, identifier: str) -> None:
        user = self.require_admin()
        if not user:
            return
        payload = json_body(self)
        status = str(payload.get("status", "")).strip()
        if status not in {"approved", "rejected"}:
            raise ValueError("标签审核状态不正确")
        with get_connection() as connection:
            request = connection.execute(
                "SELECT * FROM tag_requests WHERE id = ?", (identifier,)
            ).fetchone()
            if request is None:
                self.error(HTTPStatus.NOT_FOUND, "标签申请不存在")
                return
            if request["status"] != "pending":
                self.error(HTTPStatus.CONFLICT, "标签申请已处理")
                return
            if status == "approved":
                existing = connection.execute(
                    "SELECT id FROM catalog_tags WHERE name = ? COLLATE NOCASE", (request["name"],)
                ).fetchone()
                if not existing:
                    connection.execute(
                        "INSERT INTO catalog_tags(id, name, created_at) VALUES (?, ?, ?)",
                        (safe_id("tag"), request["name"], now()),
                    )
            connection.execute(
                """
                UPDATE tag_requests
                SET status = ?, reviewed_by = ?, reviewed_at = ?
                WHERE id = ?
                """,
                (status, user["id"], now(), identifier),
            )
            self.write_audit(connection, user["id"], f"{status}_tag_request", identifier, request["name"])
        self.send_json(HTTPStatus.OK, {"ok": True, "status": status})

    def save_draft(self) -> None:
        user = self.require_user()
        if not user:
            return
        payload = json_body(self)
        draft_id = text_value(payload, "id", 120) or safe_id("draft")
        data = payload.get("data", {})
        if not isinstance(data, dict):
            raise ValueError("草稿格式错误")
        encoded = json.dumps(data, ensure_ascii=False)
        if len(encoded.encode("utf-8")) > MAX_BODY_BYTES:
            raise ValueError("草稿内容过大")
        updated = now()
        with get_connection() as connection:
            existing = connection.execute(
                "SELECT owner_id FROM drafts WHERE id = ?", (draft_id,)
            ).fetchone()
            if existing and existing["owner_id"] != user["id"]:
                self.error(HTTPStatus.FORBIDDEN, "没有权限修改这份草稿")
                return
            connection.execute(
                """
                INSERT INTO drafts(id, owner_id, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (draft_id, user["id"], encoded, updated),
            )
        self.send_json(
            HTTPStatus.OK,
            {"ok": True, "draft": {"id": draft_id, "data": data, "updatedAt": iso_time(updated)}},
        )

    def delete_draft(self, draft_id: str) -> None:
        user = self.require_user()
        if not user:
            return
        with get_connection() as connection:
            connection.execute(
                "DELETE FROM drafts WHERE id = ? AND owner_id = ?", (draft_id, user["id"])
            )
        self.send_json(HTTPStatus.OK, {"ok": True})

    def update_admin_role(self, target_id: str) -> None:
        user = self.require_creator()
        if not user:
            return
        payload = json_body(self)
        requested = str(payload.get("systemRole", "")).strip()
        role = "admin" if requested == "admin" else "applicant"
        with get_connection() as connection:
            target = connection.execute(
                "SELECT * FROM users WHERE id = ?", (target_id,)
            ).fetchone()
            if target is None:
                self.error(HTTPStatus.NOT_FOUND, "用户不存在")
                return
            if target["id"] == user["id"] or target["system_role"] == "creator":
                self.error(HTTPStatus.FORBIDDEN, "不能修改平台创建者的角色")
                return
            connection.execute(
                "UPDATE users SET system_role = ?, updated_at = ? WHERE id = ?",
                (role, now(), target_id),
            )
            self.write_audit(
                connection,
                user["id"],
                "appoint_admin" if role == "admin" else "revoke_admin",
                target_id,
                target["nickname"],
            )
        self.send_json(HTTPStatus.OK, {"ok": True, "systemRole": role if role != "applicant" else None})

    def register(self) -> None:
        payload = json_body(self)
        account = text_value(payload, "account", 80)
        password = text_value(payload, "password", 200)
        nickname = text_value(payload, "nickname", 80) or account
        if len(account) < 3:
            raise ValueError("账号至少需要 3 个字符")
        if len(password) < 8:
            raise ValueError("密码至少需要 8 个字符")
        salt, digest = password_hash(password)
        user_id = safe_id("u")
        created = now()
        with get_connection() as connection:
            existing_count = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            initial_role = "creator" if existing_count == 0 else "applicant"
            connection.execute(
                """
                INSERT INTO users(
                    id, account, password_hash, password_salt, nickname,
                    system_role, profile_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, '{}', ?, ?)
                """,
                (user_id, account, digest, salt, nickname, initial_role, created, created),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        token = create_session(user_id)
        self.send_json(
            HTTPStatus.CREATED,
            {"ok": True, "user": public_user(row)},
            self.session_cookie(token),
        )

    def login(self) -> None:
        payload = json_body(self)
        account = text_value(payload, "account", 80)
        password = text_value(payload, "password", 200)
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE account = ? COLLATE NOCASE", (account,)
            ).fetchone()
        if row is None or not verify_password(password, row["password_salt"], row["password_hash"]):
            self.error(HTTPStatus.UNAUTHORIZED, "账号或密码错误")
            return
        token = create_session(row["id"])
        self.send_json(HTTPStatus.OK, {"ok": True, "user": public_user(row)}, self.session_cookie(token))

    def logout(self) -> None:
        morsel = SimpleCookie(self.headers.get("Cookie", "")).get("hiteam_session")
        token = morsel.value if morsel else ""
        if token:
            with get_connection() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
        self.send_json(HTTPStatus.OK, {"ok": True}, self.session_cookie("", clear=True))

    def update_profile(self) -> None:
        user = self.require_user()
        if not user:
            return
        payload = json_body(self)
        nickname = text_value(payload, "nickname", 80) or user["nickname"]
        allowed = {
            "realName": 120,
            "realNameVisibility": 20,
            "avatar": 600_000,
            "campus": 80,
            "college": 120,
            "major": 120,
            "grade": 40,
            "gradeCohort": 12,
            "degree": 20,
            "contact": 240,
            "contactVisibility": 20,
            "bio": 2000,
        }
        profile = parse_json(user["profile_json"], {})
        if not isinstance(profile, dict):
            profile = {}
        for key, maximum in allowed.items():
            if key in payload:
                value = str(payload.get(key, "")).strip()
                if len(value) > maximum:
                    raise ValueError(f"{key} 内容过长")
                profile[key] = value
        for key in ("tags", "awards"):
            if key in payload:
                value = payload[key]
                if not isinstance(value, list):
                    raise ValueError(f"{key} 格式错误")
                if len(value) > 80:
                    raise ValueError(f"{key} 数量过多")
                profile[key] = value
        if "contacts" in payload:
            contacts = payload["contacts"]
            if not isinstance(contacts, list) or len(contacts) > 20:
                raise ValueError("联系方式格式错误")
            normalized_contacts = []
            for item in contacts:
                if not isinstance(item, dict):
                    raise ValueError("联系方式格式错误")
                contact_type = str(item.get("type", "")).strip()
                value = str(item.get("value", "")).strip()
                if contact_type not in {"phone", "wechat", "qq", "email"}:
                    raise ValueError("联系方式类型不正确")
                if len(value) > 240:
                    raise ValueError("联系方式内容过长")
                if value:
                    normalized_contacts.append({"type": contact_type, "value": value})
            profile["contacts"] = normalized_contacts
            if "contact" not in payload:
                profile["contact"] = " / ".join(
                    f"{item['type']}: {item['value']}" for item in normalized_contacts
                )
        updated = now()
        with get_connection() as connection:
            connection.execute(
                "UPDATE users SET nickname = ?, profile_json = ?, updated_at = ? WHERE id = ?",
                (nickname, json.dumps(profile, ensure_ascii=False), updated, user["id"]),
            )
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        self.send_json(
            HTTPStatus.OK,
            {"ok": True, "profile": profile_for(row, row["id"], reveal_contact=True)},
        )

    def create_recruitment(self) -> None:
        user = self.require_user()
        if not user:
            return
        payload = json_body(self)
        required = ("programId", "projectTitle", "competition", "campus", "summary", "requirement")
        for key in required:
            if not text_value(payload, key, 500):
                raise ValueError(f"缺少 {key}")
        total = int(payload.get("total", 0))
        current = int(payload.get("current", 0))
        if total < 0 or total > 1000 or current < 0 or current > total:
            raise ValueError("队伍人数范围不正确")
        recruitment_id = safe_id("r")
        created = now()
        stored = dict(payload)
        stored.pop("id", None)
        stored.pop("publisherId", None)
        stored.pop("applications", None)
        stored["createdAt"] = stored.get("createdAt") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created))
        stored["publisherId"] = user["id"]
        stored["status"] = "open"
        stored["current"] = current
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO recruitments(
                    id, publisher_id, status, current_count, payload_json, created_at, updated_at
                ) VALUES (?, ?, 'open', ?, ?, ?, ?)
                """,
                (
                    recruitment_id,
                    user["id"],
                    current,
                    json.dumps(stored, ensure_ascii=False),
                    created,
                    created,
                ),
            )
            insert_message(
                connection,
                user["id"],
                "notification",
                "招募已发布",
                f"{stored.get('competition', '新招募')} 已进入发现列表。",
            )
            row = connection.execute(
                "SELECT * FROM recruitments WHERE id = ?", (recruitment_id,)
            ).fetchone()
            item = payload_recruitment(row, connection, user["id"])
        self.send_json(HTTPStatus.CREATED, {"ok": True, "recruitment": item})

    def update_recruitment(self, recruitment_id: str) -> None:
        user = self.require_user()
        if not user:
            return
        payload = json_body(self)
        status = text_value(payload, "status", 20)
        if status not in {"open", "closed"}:
            raise ValueError("招募状态不正确")
        with get_connection() as connection:
            row = connection.execute(
                "SELECT * FROM recruitments WHERE id = ?", (recruitment_id,)
            ).fetchone()
            if row is None:
                self.error(HTTPStatus.NOT_FOUND, "招募不存在")
                return
            if row["publisher_id"] != user["id"] and user["system_role"] not in {"admin", "creator"}:
                self.error(HTTPStatus.FORBIDDEN, "没有权限修改这条招募")
                return
            connection.execute(
                "UPDATE recruitments SET status = ?, updated_at = ? WHERE id = ?",
                (status, now(), recruitment_id),
            )
            title = "招募已重新开放" if status == "open" else "招募已关闭"
            insert_message(connection, user["id"], "notification", title, "招募状态已更新。")
            updated = connection.execute(
                "SELECT * FROM recruitments WHERE id = ?", (recruitment_id,)
            ).fetchone()
            item = payload_recruitment(updated, connection, user["id"])
        self.send_json(HTTPStatus.OK, {"ok": True, "recruitment": item})

    def create_application(self, recruitment_id: str) -> None:
        user = self.require_user()
        if not user:
            return
        payload = json_body(self)
        message = text_value(payload, "message", 2000)
        if not message:
            raise ValueError("请填写申请留言")
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            recruitment = connection.execute(
                "SELECT * FROM recruitments WHERE id = ?", (recruitment_id,)
            ).fetchone()
            if recruitment is None:
                self.error(HTTPStatus.NOT_FOUND, "招募不存在")
                return
            if recruitment["publisher_id"] == user["id"]:
                self.error(HTTPStatus.FORBIDDEN, "不能申请自己的招募")
                return
            stored = recruitment_payload(recruitment)
            blocked = cannot_apply_reason(recruitment, stored)
            if blocked:
                self.error(HTTPStatus.CONFLICT, blocked)
                return
            existing = connection.execute(
                """
                SELECT * FROM applications
                WHERE recruitment_id = ? AND applicant_id = ?
                """,
                (recruitment_id, user["id"]),
            ).fetchone()
            if existing and existing["status"] != "rejected":
                self.error(HTTPStatus.CONFLICT, "你已经申请过这条招募")
                return
            created = now()
            if existing:
                application_id = existing["id"]
                connection.execute(
                    """
                    UPDATE applications
                    SET message = ?, status = 'pending', created_at = ?, reviewed_at = NULL
                    WHERE id = ?
                    """,
                    (message, created, application_id),
                )
            else:
                application_id = safe_id("app")
                connection.execute(
                    """
                    INSERT INTO applications(
                        id, recruitment_id, applicant_id, message, status, created_at
                    ) VALUES (?, ?, ?, ?, 'pending', ?)
                    """,
                    (application_id, recruitment_id, user["id"], message, created),
                )
            competition = stored.get("competition", "该招募")
            insert_message(
                connection,
                user["id"],
                "notification",
                "申请已提交",
                f"你已申请加入 {competition}，等待队长审核。",
            )
            insert_message(
                connection,
                recruitment["publisher_id"],
                "notification",
                "收到新的组队申请",
                f"{user['nickname']} 申请加入 {competition}，请在队长审核中查看。",
            )
            application = connection.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
        self.send_json(HTTPStatus.CREATED, {"ok": True, "application": application_dict(application)})

    def review_application(self, application_id: str) -> None:
        user = self.require_user()
        if not user:
            return
        payload = json_body(self)
        decision = text_value(payload, "status", 20)
        if decision not in {"accepted", "rejected"}:
            raise ValueError("审核状态不正确")
        with get_connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            application = connection.execute(
                """
                SELECT applications.*, recruitments.publisher_id, recruitments.status AS recruitment_status,
                       recruitments.current_count, recruitments.payload_json,
                       users.nickname AS applicant_nickname
                FROM applications
                JOIN recruitments ON recruitments.id = applications.recruitment_id
                JOIN users ON users.id = applications.applicant_id
                WHERE applications.id = ?
                """,
                (application_id,),
            ).fetchone()
            if application is None:
                self.error(HTTPStatus.NOT_FOUND, "申请不存在")
                return
            if application["publisher_id"] != user["id"] and user["system_role"] not in {"admin", "creator"}:
                self.error(HTTPStatus.FORBIDDEN, "没有权限审核这条申请")
                return
            if application["status"] != "pending":
                self.error(HTTPStatus.CONFLICT, "这条申请已经处理过")
                return
            stored = recruitment_payload(application)
            if decision == "accepted":
                blocked = cannot_accept_reason(application, stored)
                if blocked:
                    self.error(HTTPStatus.CONFLICT, blocked)
                    return
            reviewed = now()
            connection.execute(
                "UPDATE applications SET status = ?, reviewed_at = ? WHERE id = ?",
                (decision, reviewed, application_id),
            )
            competition = stored.get("competition", "该招募")
            if decision == "accepted":
                new_current = application["current_count"] + 1
                connection.execute(
                    "UPDATE recruitments SET current_count = ?, updated_at = ? WHERE id = ?",
                    (new_current, reviewed, application["recruitment_id"]),
                )
                applicant_row = connection.execute(
                    "SELECT * FROM users WHERE id = ?", (application["applicant_id"],)
                ).fetchone()
                publisher_row = connection.execute(
                    "SELECT * FROM users WHERE id = ?", (application["publisher_id"],)
                ).fetchone()
                contact = contact_card(applicant_row, publisher_row)
                insert_message(
                    connection,
                    application["applicant_id"],
                    "conversation",
                    f"{competition} · 申请已通过",
                    "队长已通过你的申请，请尽快与队伍成员建立群聊。",
                    contact,
                )
                insert_message(
                    connection,
                    application["publisher_id"],
                    "conversation",
                    f"{competition} · 新成员已加入",
                    f"{application['applicant_nickname']} 已加入队伍，请尽快建立群聊。",
                    contact,
                )
            else:
                insert_message(
                    connection,
                    application["applicant_id"],
                    "notification",
                    "申请已拒绝",
                    f"你对 {competition} 的申请未通过，本次不会释放联系方式。",
                )
            updated = connection.execute(
                "SELECT * FROM applications WHERE id = ?", (application_id,)
            ).fetchone()
        self.send_json(HTTPStatus.OK, {"ok": True, "application": application_dict(updated)})

    def mark_messages_read(self) -> None:
        user = self.require_user()
        if not user:
            return
        with get_connection() as connection:
            connection.execute("UPDATE messages SET read = 1 WHERE recipient_id = ?", (user["id"],))
        self.send_json(HTTPStatus.OK, {"ok": True})


def application_dict(row: sqlite3.Row | None) -> dict:
    if row is None:
        return {}
    return {
        "id": row["id"],
        "userId": row["applicant_id"],
        "recruitmentId": row["recruitment_id"],
        "message": row["message"],
        "status": row["status"],
        "createdAt": iso_time(row["created_at"]),
        "reviewedAt": iso_time(row["reviewed_at"]),
    }


def contact_card(applicant: sqlite3.Row, publisher: sqlite3.Row) -> str:
    applicant_profile = profile_for(applicant, publisher["id"], reveal_contact=True)
    publisher_profile = profile_for(publisher, applicant["id"], reveal_contact=True)
    applicant_contact = contact_text(applicant_profile)
    publisher_contact = contact_text(publisher_profile)
    return f"{applicant['nickname']}: {applicant_contact} | {publisher['nickname']}: {publisher_contact}"


def contact_text(profile: dict) -> str:
    labels = {"phone": "手机", "wechat": "微信", "qq": "QQ", "email": "邮箱"}
    contacts = profile.get("contacts", [])
    if isinstance(contacts, list) and contacts:
        visible = " / ".join(
            f"{labels.get(item.get('type'), '联系方式')}: {item.get('value', '')}"
            for item in contacts
            if isinstance(item, dict) and str(item.get("value", "")).strip()
        )
        if visible:
            return visible
    legacy = str(profile.get("contact", "")).strip()
    if legacy:
        return legacy
    if str(profile.get("contactVisibility", "matched")) == "private":
        return "联系方式未公开"
    return "未填写联系方式"


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"HiTeam backend listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
