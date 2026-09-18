"""隔离的 HiTeam 后端回归测试。

测试通过环境变量把后端指向临时 SQLite 数据库和临时端口，不读写项目根目录
下的 hiteam.db。运行：python -m unittest discover -s tests -v
"""

from __future__ import annotations

import http.client
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.cookies import SimpleCookie


ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class Client:
    def __init__(self, port: int) -> None:
        self.port = port
        self.cookie = ""

    def request(self, method: str, path: str, payload: dict | None = None) -> tuple[int, dict, http.client.HTTPMessage]:
        body = None
        headers = {"Accept": "application/json", "Origin": "http://127.0.0.1:8765"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.cookie:
            headers["Cookie"] = self.cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            raw = response.read()
            set_cookie = response.getheader("Set-Cookie")
            if set_cookie:
                morsel = SimpleCookie(set_cookie).get("hiteam_session")
                if morsel is not None:
                    self.cookie = f"hiteam_session={morsel.value}"
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return response.status, data, response.headers
        finally:
            connection.close()

    def register(self, account: str, password: str = "password-123", nickname: str | None = None) -> dict:
        status, data, _ = self.request("POST", "/api/auth/register", {
            "account": account, "password": password, "nickname": nickname or account,
        })
        assert status == 201, data
        return data["user"]

    def login(self, account: str, password: str = "password-123") -> dict:
        status, data, _ = self.request("POST", "/api/auth/login", {
            "account": account, "password": password,
        })
        assert status == 200, data
        return data["user"]


class BackendRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="hiteam-regression-")
        cls.port = free_port()
        env = os.environ.copy()
        env.update({
            "HITEAM_DB_PATH": str(Path(cls.temp_dir.name) / "isolated.db"),
            "HITEAM_HOST": "127.0.0.1",
            "HITEAM_PORT": str(cls.port),
            "HITEAM_PBKDF2_ROUNDS": "1000",
            "PYTHONUNBUFFERED": "1",
        })
        cls.process = subprocess.Popen(
            [sys.executable, str(ROOT / "backend" / "server.py")],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        cls.server_output = bytearray()

        def drain() -> None:
            stream = cls.process.stdout
            if stream is None:
                return
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                cls.server_output.extend(chunk)

        threading.Thread(target=drain, daemon=True).start()
        deadline = time.time() + 15
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                status, _, _ = Client(cls.port).request("GET", "/api/health")
                if status == 200:
                    break
            except OSError as exc:
                last_error = exc
            time.sleep(0.1)
        else:
            output = bytes(cls.server_output).decode("utf-8", errors="replace")
            cls.process.kill()
            raise RuntimeError(f"后端启动失败: {last_error}; 输出: {output}")
        cls.creator = Client(cls.port)
        cls.creator_account = "creator_" + secrets.token_hex(5)
        cls.creator_user = cls.creator.register(cls.creator_account, nickname="队长")

    @classmethod
    def tearDownClass(cls) -> None:
        if getattr(cls, "process", None) is not None:
            cls.process.kill()
            try:
                cls.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        try:
            cls.temp_dir.cleanup()
        except OSError:
            pass

    def new_user(self, prefix: str = "user") -> tuple[Client, str, dict]:
        account = f"{prefix}_{secrets.token_hex(5)}"
        client = Client(self.port)
        user = client.register(account)
        return client, account, user

    def test_registration_login_session_and_logout(self) -> None:
        account = f"auth_{secrets.token_hex(5)}"
        client = Client(self.port)
        user = client.register(account, nickname="认证用户")
        self.assertEqual(user["nickname"], "认证用户")
        status, data, _ = client.request("GET", "/api/auth/session")
        self.assertEqual(status, 200)
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["user"]["id"], user["id"])
        client.request("POST", "/api/auth/logout")
        status, data, _ = client.request("GET", "/api/auth/session")
        self.assertEqual(status, 200)
        self.assertFalse(data["authenticated"])
        login_client = Client(self.port)
        logged_in = login_client.login(account)
        self.assertEqual(logged_in["id"], user["id"])

    def test_workspace_requires_login(self) -> None:
        status, data, _ = Client(self.port).request("GET", "/api/workspace")
        self.assertEqual(status, 401)
        self.assertFalse(data["ok"])

    def test_normal_user_cannot_write_catalog(self) -> None:
        client, _, user = self.new_user("catalog")
        self.assertIsNone(user["systemRole"])
        status, data, _ = client.request("POST", "/api/catalog/tags", {"name": "越权标签"})
        self.assertEqual(status, 403)
        self.assertFalse(data["ok"])

    def test_normal_user_workspace_hides_platform_privileged_metadata(self) -> None:
        client, _, _ = self.new_user("platformprivacy")
        status, data, _ = client.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        platform = data["state"].get("platform", {})
        for privileged_key in ("auditLog", "creatorId", "adminIds"):
            with self.subTest(key=privileged_key):
                self.assertNotIn(privileged_key, platform)

    def test_workspace_does_not_expose_other_users_accounts(self) -> None:
        viewer, _, viewer_user = self.new_user("accountviewer")
        _, _, other_user = self.new_user("accountsubject")
        status, data, _ = viewer.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        exposed_other = next(
            profile for profile in data["state"]["users"]
            if profile["id"] == other_user["id"]
        )
        self.assertNotEqual(exposed_other["id"], viewer_user["id"])
        # 后端为兼容旧客户端保留 account 键，但他人值必须为空。
        self.assertEqual(exposed_other.get("account"), "")

    def test_private_contact_is_not_released_after_match(self) -> None:
        publisher, _, _ = self.new_user("privatepublisher")
        applicant, _, _ = self.new_user("privateapplicant")
        publisher_secret = "private-publisher-" + secrets.token_hex(8)
        applicant_secret = "private-applicant-" + secrets.token_hex(8)
        for client, secret in ((publisher, publisher_secret), (applicant, applicant_secret)):
            status, data, _ = client.request("PUT", "/api/profile", {
                "contact": secret,
                "contacts": [{"type": "wechat", "value": secret}],
                "contactVisibility": "private",
            })
            self.assertEqual(status, 200, data)
        status, data, _ = publisher.request("POST", "/api/recruitments", {
            "programId": "general-competition",
            "projectTitle": "私密联系方式回归项目",
            "competition": "年度项目",
            "campus": "本部",
            "summary": "验证匹配后的隐私边界",
            "requirement": "测试",
            "total": 2,
            "current": 0,
        })
        self.assertEqual(status, 201, data)
        recruitment_id = data["recruitment"]["id"]
        status, data, _ = applicant.request(
            "POST", f"/api/recruitments/{recruitment_id}/applications",
            {"message": "申请加入隐私测试"},
        )
        self.assertEqual(status, 201, data)
        application_id = data["application"]["id"]
        status, data, _ = publisher.request(
            "PATCH", f"/api/applications/{application_id}", {"status": "accepted"}
        )
        self.assertEqual(status, 200, data)
        for client in (publisher, applicant):
            status, data, _ = client.request("GET", "/api/workspace")
            self.assertEqual(status, 200)
            conversation_text = json.dumps(data["state"]["conversations"], ensure_ascii=False)
            self.assertNotIn(publisher_secret, conversation_text)
            self.assertNotIn(applicant_secret, conversation_text)

    def test_options_allows_delete(self) -> None:
        status, _, headers = Client(self.port).request("OPTIONS", "/api/drafts/example")
        self.assertEqual(status, 204)
        allowed_methods = {
            method.strip().upper()
            for method in headers.get("Access-Control-Allow-Methods", "").split(",")
            if method.strip()
        }
        self.assertIn("DELETE", allowed_methods)

    def test_draft_is_owned_by_creator(self) -> None:
        owner, _, _ = self.new_user("draftowner")
        other, _, _ = self.new_user("draftother")
        draft_id = "draft-regression-" + secrets.token_hex(4)
        status, data, _ = owner.request("POST", "/api/drafts", {"id": draft_id, "data": {"title": "仅所有者可见"}})
        self.assertEqual(status, 200, data)
        status, data, _ = other.request("POST", "/api/drafts", {"id": draft_id, "data": {"title": "恶意覆盖"}})
        self.assertEqual(status, 403)
        status, data, _ = other.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        self.assertNotIn(draft_id, {item["id"] for item in data["state"]["drafts"]})
        status, data, _ = owner.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        drafts = {item["id"]: item for item in data["state"]["drafts"]}
        self.assertEqual(drafts[draft_id]["data"]["title"], "仅所有者可见")

    def test_publish_apply_review_and_persistence(self) -> None:
        applicant, _, applicant_user = self.new_user("applicant")
        recruitment_payload = {
            "programId": "general-competition",
            "projectTitle": "回归测试项目",
            "competition": "年度项目",
            "campus": "本部",
            "summary": "端到端状态流",
            "requirement": "测试",
            "total": 2,
            "current": 0,
        }
        status, data, _ = self.creator.request("POST", "/api/recruitments", recruitment_payload)
        self.assertEqual(status, 201, data)
        recruitment = data["recruitment"]
        recruitment_id = recruitment["id"]
        self.assertEqual(recruitment["status"], "open")
        status, data, _ = applicant.request("POST", f"/api/recruitments/{recruitment_id}/applications", {"message": "希望加入"})
        self.assertEqual(status, 201, data)
        application_id = data["application"]["id"]
        self.assertEqual(data["application"]["status"], "pending")
        status, data, _ = applicant.request("POST", f"/api/recruitments/{recruitment_id}/applications", {"message": "重复申请"})
        self.assertEqual(status, 409)
        status, data, _ = self.creator.request("PATCH", f"/api/applications/{application_id}", {"status": "accepted"})
        self.assertEqual(status, 200, data)
        self.assertEqual(data["application"]["status"], "accepted")
        status, data, _ = self.creator.request("PATCH", f"/api/applications/{application_id}", {"status": "rejected"})
        self.assertEqual(status, 409)
        fresh_creator = Client(self.port)
        fresh_creator.login(self.creator_account)
        status, data, _ = fresh_creator.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        item = next(item for item in data["state"]["recruitments"] if item["id"] == recruitment_id)
        self.assertEqual(item["current"], 1)
        self.assertEqual(item["applications"][0]["status"], "accepted")
        fresh_applicant = Client(self.port)
        fresh_applicant.login(applicant_user["account"])
        status, data, _ = fresh_applicant.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        self.assertTrue(any(message["kind"] == "conversation" for message in data["state"]["conversations"]))
        created_at = item["applications"][0]["createdAt"]
        self.assertIn("T", str(created_at))

    def publish(self, client: Client | None = None, **overrides: object) -> dict:
        payload = {
            "programId": "general-competition",
            "projectTitle": "状态机回归项目",
            "competition": "年度项目",
            "campus": "一校区",
            "summary": "验证申请与审核边界",
            "requirement": "测试",
            "total": 2,
            "current": 0,
        }
        payload.update(overrides)
        status, data, _ = (client or self.creator).request("POST", "/api/recruitments", payload)
        self.assertEqual(status, 201, data)
        return data["recruitment"]

    def apply_to(self, client: Client, recruitment_id: str, message: str = "希望加入") -> tuple[int, dict]:
        status, data, _ = client.request(
            "POST",
            f"/api/recruitments/{recruitment_id}/applications",
            {"message": message},
        )
        return status, data

    def decide(self, client: Client, application_id: str, decision: str) -> tuple[int, dict]:
        status, data, _ = client.request(
            "PATCH",
            f"/api/applications/{application_id}",
            {"status": decision},
        )
        return status, data

    def test_matched_contact_is_released_after_accept(self) -> None:
        publisher, _, _ = self.new_user("matchedpublisher")
        applicant, _, _ = self.new_user("matchedapplicant")
        publisher_secret = "matched-publisher-" + secrets.token_hex(8)
        applicant_secret = "matched-applicant-" + secrets.token_hex(8)
        for client, secret in ((publisher, publisher_secret), (applicant, applicant_secret)):
            status, data, _ = client.request("PUT", "/api/profile", {
                "contact": secret,
                "contacts": [{"type": "wechat", "value": secret}],
                "contactVisibility": "matched",
            })
            self.assertEqual(status, 200, data)
        recruitment = self.publish(publisher, projectTitle="匹配可见联系方式")
        status, data = self.apply_to(applicant, recruitment["id"])
        self.assertEqual(status, 201, data)
        status, data = self.decide(publisher, data["application"]["id"], "accepted")
        self.assertEqual(status, 200, data)
        for client in (publisher, applicant):
            status, payload, _ = client.request("GET", "/api/workspace")
            self.assertEqual(status, 200)
            conversation_text = json.dumps(payload["state"]["conversations"], ensure_ascii=False)
            self.assertIn(publisher_secret, conversation_text)
            self.assertIn(applicant_secret, conversation_text)

    def test_cannot_accept_after_recruitment_is_closed_expired_or_full(self) -> None:
        publisher, _, _ = self.new_user("closepublisher")
        applicant, _, _ = self.new_user("closeapplicant")
        closed = self.publish(publisher, projectTitle="关闭后不可通过")
        status, data = self.apply_to(applicant, closed["id"])
        self.assertEqual(status, 201, data)
        closed_application = data["application"]["id"]
        status, data, _ = publisher.request("PATCH", f"/api/recruitments/{closed['id']}", {"status": "closed"})
        self.assertEqual(status, 200, data)
        status, data = self.decide(publisher, closed_application, "accepted")
        self.assertEqual(status, 409, data)
        self.assertIn("关闭", data["error"])
        status, data = self.decide(publisher, closed_application, "rejected")
        self.assertEqual(status, 200, data)
        self.assertEqual(data["application"]["status"], "rejected")

        expired_item = self.publish(
            publisher,
            projectTitle="截止后不可申请",
            deadline=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        )
        late_applicant, _, _ = self.new_user("lateapplicant")
        status, data = self.apply_to(late_applicant, expired_item["id"])
        self.assertEqual(status, 409, data)
        self.assertIn("截止", data["error"])

        pending_item = self.publish(
            publisher,
            projectTitle="先申请后截止",
            deadline=(datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),
        )
        pending_applicant, _, _ = self.new_user("pendingthenexpire")
        status, data = self.apply_to(pending_applicant, pending_item["id"])
        self.assertEqual(status, 201, data)
        pending_application = data["application"]["id"]
        time.sleep(2.2)
        status, data = self.decide(publisher, pending_application, "accepted")
        self.assertEqual(status, 409, data)
        self.assertIn("截止", data["error"])
        status, data = self.decide(publisher, pending_application, "rejected")
        self.assertEqual(status, 200, data)

        full_publisher, _, _ = self.new_user("fullpublisher")
        first, _, _ = self.new_user("fullfirst")
        second, _, _ = self.new_user("fullsecond")
        third, _, _ = self.new_user("fullthird")
        full = self.publish(full_publisher, projectTitle="满员后不可通过", total=1, current=0)
        status, data = self.apply_to(first, full["id"])
        self.assertEqual(status, 201, data)
        first_application = data["application"]["id"]
        status, data = self.apply_to(second, full["id"])
        self.assertEqual(status, 201, data)
        second_application = data["application"]["id"]
        status, data = self.decide(full_publisher, first_application, "accepted")
        self.assertEqual(status, 200, data)
        status, data = self.decide(full_publisher, second_application, "accepted")
        self.assertEqual(status, 409, data)
        self.assertIn("满员", data["error"])
        status, data = self.apply_to(third, full["id"])
        self.assertEqual(status, 409, data)
        self.assertIn("满员", data["error"])

    def test_reapply_after_rejection(self) -> None:
        publisher, _, _ = self.new_user("reapplypublisher")
        applicant, _, _ = self.new_user("reapplyapplicant")
        recruitment = self.publish(publisher, projectTitle="拒绝后可重申")
        status, data = self.apply_to(applicant, recruitment["id"], "第一次申请")
        self.assertEqual(status, 201, data)
        application_id = data["application"]["id"]
        status, data = self.decide(publisher, application_id, "rejected")
        self.assertEqual(status, 200, data)
        status, data = self.apply_to(applicant, recruitment["id"], "第二次申请")
        self.assertEqual(status, 201, data)
        self.assertEqual(data["application"]["id"], application_id)
        self.assertEqual(data["application"]["status"], "pending")
        self.assertEqual(data["application"]["message"], "第二次申请")
        status, data = self.apply_to(applicant, recruitment["id"], "第三次申请")
        self.assertEqual(status, 409, data)


if __name__ == "__main__":
    unittest.main()
