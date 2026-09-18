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


def start_backend(extra_env: dict | None = None) -> tuple[tempfile.TemporaryDirectory, int, subprocess.Popen, bytearray]:
    temp_dir = tempfile.TemporaryDirectory(prefix="hiteam-regression-")
    port = free_port()
    env = os.environ.copy()
    env.pop("HITEAM_EMAIL_SUFFIX", None)
    env.update({
        "HITEAM_DB_PATH": str(Path(temp_dir.name) / "isolated.db"),
        "HITEAM_HOST": "127.0.0.1",
        "HITEAM_PORT": str(port),
        "HITEAM_PBKDF2_ROUNDS": "1000",
        "HITEAM_OTP_ECHO": "1",
        "HITEAM_REGISTER_IP_HOURLY_LIMIT": "1000",
        "HITEAM_LOGIN_IP_HOURLY_LIMIT": "1000",
        "PYTHONUNBUFFERED": "1",
    })
    if extra_env:
        env.update(extra_env)
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "backend" / "server.py")],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    output = bytearray()

    def drain() -> None:
        stream = process.stdout
        if stream is None:
            return
        while True:
            chunk = stream.read(4096)
            if not chunk:
                break
            output.extend(chunk)

    threading.Thread(target=drain, daemon=True).start()
    deadline = time.time() + 30
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            status, _, _ = Client(port).request("GET", "/api/health")
            if status == 200:
                return temp_dir, port, process, output
        except OSError as exc:
            last_error = exc
        time.sleep(0.1)
    dumped = bytes(output).decode("utf-8", errors="replace")
    process.kill()
    raise RuntimeError(f"后端启动失败: {last_error}; 输出: {dumped}")


def stop_backend(temp_dir: tempfile.TemporaryDirectory | None, process: subprocess.Popen | None) -> None:
    if process is not None:
        process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        if process.stdout:
            try:
                process.stdout.close()
            except OSError:
                pass
    if temp_dir is not None:
        try:
            temp_dir.cleanup()
        except OSError:
            pass


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
        cls.temp_dir, cls.port, cls.process, cls.server_output = start_backend()
        cls.creator = Client(cls.port)
        cls.creator_account = "creator_" + secrets.token_hex(5)
        cls.creator_user = cls.creator.register(cls.creator_account, nickname="队长")

    @classmethod
    def tearDownClass(cls) -> None:
        stop_backend(getattr(cls, "temp_dir", None), getattr(cls, "process", None))

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

    def test_root_redirects_to_frontend(self) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request("GET", "/", headers={"Accept": "text/html"})
            response = connection.getresponse()
            body = response.read().decode("utf-8")
        finally:
            connection.close()
        self.assertEqual(response.status, 302)
        self.assertIn("/index.html", response.getheader("Location") or "")
        self.assertIn("8765", body)
        self.assertIn("#bonus", body)

    def test_reverse_proxy_origin_and_frontend_redirect(self) -> None:
        public = "http://47.120.13.65"
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request(
                "GET",
                "/",
                headers={
                    "Accept": "text/html",
                    "Host": "47.120.13.65",
                    "X-Forwarded-Host": "47.120.13.65",
                    "X-Forwarded-Proto": "http",
                },
            )
            response = connection.getresponse()
            body = response.read().decode("utf-8")
        finally:
            connection.close()
        self.assertEqual(response.status, 302)
        self.assertEqual(response.getheader("Location"), f"{public}/index.html")
        self.assertIn(public, body)

        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            connection.request(
                "GET",
                "/api/health",
                headers={
                    "Origin": public,
                    "Host": "47.120.13.65",
                    "X-Forwarded-Host": "47.120.13.65",
                    "X-Forwarded-Proto": "http",
                },
            )
            response = connection.getresponse()
            response.read()
        finally:
            connection.close()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), public)

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

    def test_workspace_does_not_expose_unrelated_users(self) -> None:
        viewer, _, viewer_user = self.new_user("accountviewer")
        _, _, other_user = self.new_user("accountsubject")
        status, data, _ = viewer.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        user_ids = {profile["id"] for profile in data["state"]["users"]}
        self.assertIn(viewer_user["id"], user_ids)
        self.assertNotIn(other_user["id"], user_ids)

    def test_publisher_sees_applicant_but_not_unrelated_users(self) -> None:
        publisher, _, publisher_user = self.new_user("relpub")
        applicant, _, applicant_user = self.new_user("relapp")
        lurker, _, lurker_user = self.new_user("rellurk")
        recruitment = self.publish(publisher, projectTitle="相关用户可见")
        status, data = self.apply_to(applicant, recruitment["id"])
        self.assertEqual(status, 201, data)
        status, data, _ = publisher.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        by_id = {profile["id"]: profile for profile in data["state"]["users"]}
        self.assertIn(publisher_user["id"], by_id)
        self.assertIn(applicant_user["id"], by_id)
        self.assertNotIn(lurker_user["id"], by_id)
        self.assertEqual(by_id[applicant_user["id"]].get("account"), "")

    def test_creator_directory_omits_resume_fields_for_unrelated_users(self) -> None:
        lurker_client, _, lurker = self.new_user("dirlurk")
        status, data, _ = lurker_client.request("PUT", "/api/profile", {
            "bio": "不该出现在任免目录里的简介",
            "awards": [{"name": "隐藏奖项", "year": 2024, "kind": "competition"}],
            "contacts": [{"type": "wechat", "value": "secret-wechat"}],
            "realName": "隐藏姓名",
            "realNameVisibility": "public",
            "college": "计算学部",
            "campus": "一校区",
        })
        self.assertEqual(status, 200, data)
        status, workspace, _ = self.creator.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        listed = next(profile for profile in workspace["state"]["users"] if profile["id"] == lurker["id"])
        self.assertEqual(listed.get("nickname"), lurker["nickname"] or lurker["account"].split("@", 1)[0])
        self.assertEqual(listed.get("college"), "计算学部")
        self.assertEqual(listed.get("campus"), "一校区")
        self.assertEqual(listed.get("account"), "")
        self.assertEqual(listed.get("bio"), "")
        self.assertEqual(listed.get("awards"), [])
        self.assertEqual(listed.get("contacts"), [])
        self.assertEqual(listed.get("realName"), "")
        self.assertEqual(listed.get("avatar"), "")

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

        expired_publisher, _, _ = self.new_user("expiredpublisher")
        expired_item = self.publish(
            expired_publisher,
            projectTitle="截止后不可申请",
            deadline=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
        )
        late_applicant, _, _ = self.new_user("lateapplicant")
        status, data = self.apply_to(late_applicant, expired_item["id"])
        self.assertEqual(status, 409, data)
        self.assertIn("截止", data["error"])

        pending_publisher, _, _ = self.new_user("pendingpublisher")
        pending_item = self.publish(
            pending_publisher,
            projectTitle="先申请后截止",
            deadline=(datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat().replace("+00:00", "Z"),
        )
        pending_applicant, _, _ = self.new_user("pendingthenexpire")
        status, data = self.apply_to(pending_applicant, pending_item["id"])
        self.assertEqual(status, 201, data)
        pending_application = data["application"]["id"]
        time.sleep(2.2)
        status, data = self.decide(pending_publisher, pending_application, "accepted")
        self.assertEqual(status, 409, data)
        self.assertIn("截止", data["error"])
        status, data = self.decide(pending_publisher, pending_application, "rejected")
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

    def test_bonus_catalog_matches_hit_2024_notes(self) -> None:
        status, data, _ = self.creator.request("GET", "/api/workspace")
        self.assertEqual(status, 200, data)
        competitions = data["state"]["competitions"]
        official = [item for item in competitions if item.get("catalogGroup") == "hit_2024"]
        self.assertGreaterEqual(len(official), 64, [item["name"] for item in official])
        names = {item["name"] for item in official}
        self.assertIn("中国国际大学生创新大赛", names)
        self.assertIn("“挑战杯”全国大学生课外学术科技作品竞赛", names)
        self.assertIn("全国大学生电子设计竞赛（含专题邀请赛）", names)
        self.assertIn("全国海洋航行器设计与制作大赛", names)
        innovation = next(item for item in official if item["name"] == "中国国际大学生创新大赛")
        self.assertTrue(innovation["extraBonus"])
        self.assertNotIn("prestige", innovation)
        self.assertEqual(innovation["bonusType"], "extra_bonus")
        school_names = {item["name"] for item in competitions if item.get("catalogGroup") == "school"}
        self.assertIn("年度项目", school_names)
        self.assertIn("大创计划", school_names)
        guide = data["state"]["bonusGuide"]
        self.assertIn("校本教务〔2024〕18 号", guide["source"])
        self.assertEqual(len(guide["scoring"]["rows"]), 3)
        self.assertEqual(len(guide["extraBonus"]["rows"]), 8)
        self.assertIn("揭榜挂帅", json.dumps(guide["challengeSpecials"], ensure_ascii=False))
        self.assertIn("综测成绩", guide["conclusions"][0])
        self.assertEqual(len(guide["conclusions"]), 3)
        self.assertIn("丰富简历", guide["uses"])
        self.assertNotIn("papers", guide)
        self.assertFalse(any("优秀加分只覆盖" in str(item) for item in guide["conclusions"]))

    def test_logged_in_user_can_propose_competition_and_admin_can_approve(self) -> None:
        client, _, _ = self.new_user("proposer")
        name = "提案收录竞赛 " + secrets.token_hex(3)
        status, data, _ = client.request("POST", "/api/catalog/proposals", {
            "kind": "competition_add",
            "payload": {
                "name": name,
                "aliases": "提案赛",
                "level": "国家",
                "bonusType": "",
                "bonusNote": "",
                "remark": "用户申请收录",
                "extraBonus": False,
                "note": "用于回归测试",
            },
        })
        self.assertEqual(status, 201, data)
        proposal_id = data["id"]
        status, data, _ = client.request("GET", "/api/workspace")
        self.assertEqual(status, 200, data)
        mine = {item["id"]: item for item in data["state"]["catalogProposals"]}
        self.assertEqual(mine[proposal_id]["status"], "pending")
        self.assertEqual(mine[proposal_id]["payload"]["name"], name)
        status, data, _ = client.request("POST", "/api/catalog/competitions", {"name": "越权竞赛"})
        self.assertEqual(status, 403, data)
        status, data, _ = self.creator.request(
            "PATCH", f"/api/catalog/proposals/{proposal_id}", {"status": "approved"}
        )
        self.assertEqual(status, 200, data)
        status, data, _ = self.creator.request("GET", "/api/workspace")
        self.assertEqual(status, 200, data)
        names = {item["name"] for item in data["state"]["competitions"]}
        self.assertIn(name, names)
        sample = next(item for item in data["state"]["competitions"] if item["name"] == name)
        status, data, _ = self.creator.request(
            "PATCH", f"/api/catalog/competitions/{sample['id']}",
            {"remark": "管理员行内修改", "bonusType": "default", "active": True},
        )
        self.assertEqual(status, 200, data)
        status, data, _ = self.creator.request("GET", "/api/workspace")
        updated = next(item for item in data["state"]["competitions"] if item["id"] == sample["id"])
        self.assertEqual(updated["remark"], "管理员行内修改")
        self.assertEqual(updated["bonusType"], "default")

    def test_project_library_is_reference_only(self) -> None:
        status, data, _ = self.creator.request("GET", "/api/workspace")
        self.assertEqual(status, 200, data)
        note = data["state"]["projectLibraryNote"]
        self.assertIn("题目只是一个参考", note)
        self.assertIn("共同拟定新的题目", note)
        self.assertIn("也可以不是项目库里的老师", note)
        projects = data["state"]["projects"]
        self.assertGreaterEqual(len(projects), 600)
        titles = {item["title"] for item in projects}
        self.assertIn("3D打印高强度航天钛基金属材料", titles)
        self.assertTrue(any("题目待师生共同拟定" in title for title in titles))
        self.assertFalse(any("每位老师可填写" in title for title in titles))
        sample = next(item for item in projects if item["title"] == "3D打印高强度航天钛基金属材料")
        self.assertEqual(sample["college"], "材料科学与工程学院")
        self.assertEqual(sample["advisor"], "安琦")
        self.assertTrue(sample["referenceOnly"])
        self.assertEqual(sample["programId"], "innovation_training")
        self.assertIn("anqi1993@hit.edu.cn", sample["contact"])
        school_names = {
            item["name"]
            for item in data["state"]["competitions"]
            if item.get("catalogGroup") == "school"
        }
        self.assertIn("大创计划", school_names)
        self.assertNotIn("大创计划", titles)


    def test_otp_verify_does_not_create_session(self) -> None:
        email = f"otp_{secrets.token_hex(4)}@stu.hit.edu.cn"
        client = Client(self.port)
        status, data, _ = client.request("POST", "/api/auth/otp/send", {"email": email})
        self.assertEqual(status, 200, data)
        self.assertTrue(data.get("sent"))
        code = data.get("debugCode")
        self.assertRegex(str(code or ""), r"^\d{6}$")
        status, data, _ = client.request("POST", "/api/auth/otp/verify", {"email": email, "code": "000000"})
        self.assertEqual(status, 401, data)
        status, data, _ = client.request("POST", "/api/auth/otp/verify", {"email": email, "code": code})
        self.assertEqual(status, 200, data)
        self.assertTrue(data.get("verified"))
        self.assertNotIn("user", data)
        status, session, _ = client.request("GET", "/api/auth/session")
        self.assertEqual(status, 200)
        self.assertFalse(session["authenticated"])

    def test_otp_send_rejects_invalid_account_and_rate_limits(self) -> None:
        client = Client(self.port)
        status, data, _ = client.request("POST", "/api/auth/otp/send", {"email": "ab"})
        self.assertEqual(status, 400, data)
        email = f"limit_{secrets.token_hex(4)}@stu.hit.edu.cn"
        status, data, _ = client.request("POST", "/api/auth/otp/send", {"email": email})
        self.assertEqual(status, 200, data)
        status, data, _ = client.request("POST", "/api/auth/otp/send", {"email": email})
        self.assertEqual(status, 429, data)

    def test_same_user_cannot_publish_twice_in_one_china_day(self) -> None:
        publisher, _, _ = self.new_user("daylimit")
        payload = {
            "programId": "general-competition",
            "projectTitle": "每日限额项目",
            "competition": "年度项目",
            "campus": "一校区",
            "summary": "招" * 2000,
            "requirement": "测" * 2000,
            "total": 2,
            "current": 0,
        }
        too_long = dict(payload)
        too_long["summary"] = "招" * 2001
        status, data, _ = publisher.request("POST", "/api/recruitments", too_long)
        self.assertEqual(status, 400, data)
        status, data, _ = publisher.request("POST", "/api/recruitments", payload)
        self.assertEqual(status, 201, data)
        status, data, _ = publisher.request("POST", "/api/recruitments", {
            **payload,
            "projectTitle": "第二次发布应被拒绝",
        })
        self.assertEqual(status, 409, data)
        self.assertIn("今天已经发布过", data.get("error", ""))

    def test_change_password_requires_old_password(self) -> None:
        client, account, _ = self.new_user("pwdchange")
        status, data, _ = client.request("PATCH", "/api/auth/password", {
            "oldPassword": "wrong-password",
            "newPassword": "newpass-123",
        })
        self.assertEqual(status, 401, data)
        status, data, _ = client.request("PATCH", "/api/auth/password", {
            "oldPassword": "password-123",
            "newPassword": "newpass-123",
        })
        self.assertEqual(status, 200, data)
        client.request("POST", "/api/auth/logout")
        other = Client(self.port)
        status, data, _ = other.request("POST", "/api/auth/login", {
            "account": account, "password": "password-123",
        })
        self.assertEqual(status, 401, data)
        logged_in = other.login(account, "newpass-123")
        self.assertEqual(logged_in["account"], account)

    def test_login_failures_are_rate_limited(self) -> None:
        client, account, _ = self.new_user("loginfail")
        client.request("POST", "/api/auth/logout")
        attacker = Client(self.port)
        for _ in range(8):
            status, data, _ = attacker.request("POST", "/api/auth/login", {
                "account": account, "password": "wrong-password",
            })
            self.assertEqual(status, 401, data)
        status, data, _ = attacker.request("POST", "/api/auth/login", {
            "account": account, "password": "wrong-password",
        })
        self.assertEqual(status, 429, data)

    def test_register_is_rate_limited_per_ip(self) -> None:
        temp_dir, port, process, _output = start_backend({
            "HITEAM_REGISTER_IP_HOURLY_LIMIT": "2",
            "HITEAM_LOGIN_IP_HOURLY_LIMIT": "1000",
        })
        try:
            client = Client(port)
            status, data, _ = client.request("POST", "/api/auth/register", {
                "account": "rateone_" + secrets.token_hex(3), "password": "password-123",
            })
            self.assertEqual(status, 201, data)
            status, data, _ = client.request("POST", "/api/auth/register", {
                "account": "ratetwo_" + secrets.token_hex(3), "password": "password-123",
            })
            self.assertEqual(status, 201, data)
            status, data, _ = client.request("POST", "/api/auth/register", {
                "account": "ratethree_" + secrets.token_hex(3), "password": "password-123",
            })
            self.assertEqual(status, 429, data)
        finally:
            stop_backend(temp_dir, process)

    def test_creator_can_provision_accounts_and_members_cannot(self) -> None:
        member_client, _, _ = self.new_user("provmem")
        status, data, _ = member_client.request("POST", "/api/admin/users", {
            "account": "someone", "password": "password-123",
        })
        self.assertEqual(status, 403, data)
        account = f"provisioned_{secrets.token_hex(4)}"
        status, data, _ = self.creator.request("POST", "/api/admin/users", {
            "account": account, "password": "opened-123",
        })
        self.assertEqual(status, 201, data)
        self.assertTrue(data.get("created"))
        opener = Client(self.port)
        opener.login(account, "opened-123")
        status, data, _ = self.creator.request("POST", "/api/admin/users", {
            "account": account, "password": "resetpw-123",
        })
        self.assertEqual(status, 200, data)
        self.assertFalse(data.get("created"))
        reset_client = Client(self.port)
        reset_client.login(account, "resetpw-123")

    def test_email_suffix_requires_otp_and_allows_student_id_login(self) -> None:
        temp_dir, port, process, _output = start_backend({
            "HITEAM_EMAIL_SUFFIX": "@stu.hit.edu.cn",
            "HITEAM_OTP_ECHO": "1",
        })
        try:
            client = Client(port)
            student_id = f"20{secrets.randbelow(10 ** 8):08d}"
            email = f"{student_id}@stu.hit.edu.cn"
            status, data, _ = client.request("POST", "/api/auth/register", {
                "account": student_id, "password": "password-123",
            })
            self.assertEqual(status, 400, data)
            status, data, _ = client.request("POST", "/api/auth/otp/send", {"account": student_id})
            self.assertEqual(status, 200, data)
            code = data.get("debugCode")
            status, data, _ = client.request("POST", "/api/auth/register", {
                "account": student_id, "password": "password-123", "code": code,
            })
            self.assertEqual(status, 201, data)
            self.assertEqual(data["user"]["account"], email)
            client.request("POST", "/api/auth/logout")
            login_client = Client(port)
            logged_in = login_client.login(student_id)
            self.assertEqual(logged_in["account"], email)
            status, data, _ = Client(port).request("POST", "/api/auth/register", {
                "account": student_id, "password": "password-123", "code": "123456",
            })
            self.assertEqual(status, 409, data)
        finally:
            stop_backend(temp_dir, process)

    def test_creator_can_appoint_and_revoke_admin(self) -> None:
        self.assertEqual(self.creator_user.get("systemRole"), "creator")
        member_client, _, member = self.new_user("appointmember")
        status, data, _ = member_client.request(
            "PATCH",
            f"/api/admin/users/{member['id']}",
            {"systemRole": "admin"},
        )
        self.assertEqual(status, 403)
        self.assertFalse(data["ok"])

        status, data, _ = self.creator.request(
            "PATCH",
            f"/api/admin/users/{member['id']}",
            {"systemRole": "admin"},
        )
        self.assertEqual(status, 200, data)
        self.assertEqual(data.get("systemRole"), "admin")

        status, workspace, _ = self.creator.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        appointed = next(user for user in workspace["state"]["users"] if user["id"] == member["id"])
        self.assertEqual(appointed["systemRole"], "admin")
        self.assertIn(
            "appoint_admin",
            [log["action"] for log in workspace["state"]["platform"].get("auditLog", [])],
        )

        other_client, _, other = self.new_user("appointother")
        status, data, _ = member_client.request(
            "PATCH",
            f"/api/admin/users/{other['id']}",
            {"systemRole": "admin"},
        )
        self.assertEqual(status, 403)

        status, data, _ = self.creator.request(
            "PATCH",
            f"/api/admin/users/{member['id']}",
            {"systemRole": None},
        )
        self.assertEqual(status, 200, data)
        self.assertIsNone(data.get("systemRole"))

        status, workspace, _ = self.creator.request("GET", "/api/workspace")
        self.assertEqual(status, 200)
        revoked = next(user for user in workspace["state"]["users"] if user["id"] == member["id"])
        self.assertIsNone(revoked.get("systemRole"))
        self.assertIn(
            "revoke_admin",
            [log["action"] for log in workspace["state"]["platform"].get("auditLog", [])],
        )

    def test_campus_email_suffix_is_enforced_when_configured(self) -> None:
        sys.path.insert(0, str(ROOT / "backend"))
        import server as hiteam_server
        old = os.environ.get("HITEAM_EMAIL_SUFFIX")
        os.environ["HITEAM_EMAIL_SUFFIX"] = "@stu.hit.edu.cn"
        try:
            self.assertEqual(
                hiteam_server.normalize_account("2025110520"),
                "2025110520@stu.hit.edu.cn",
            )
            self.assertEqual(
                hiteam_server.normalize_login_email("2025110520@STU.HIT.EDU.CN"),
                "2025110520@stu.hit.edu.cn",
            )
            with self.assertRaises(ValueError):
                hiteam_server.normalize_login_email("someone@gmail.com")
        finally:
            if old is None:
                os.environ.pop("HITEAM_EMAIL_SUFFIX", None)
            else:
                os.environ["HITEAM_EMAIL_SUFFIX"] = old


if __name__ == "__main__":
    unittest.main()
