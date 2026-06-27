"""管理端材料导入接口测试。"""

from __future__ import annotations

import os
import tempfile
import time
import unittest
import uuid
from importlib import metadata as importlib_metadata
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import networks as pydantic_networks

import sys

_original_version = importlib_metadata.version
_original_email_validator = sys.modules.get("email_validator")
_original_pydantic_version = pydantic_networks.version

# 管理端导入测试关注点：
# 1. 验证管理员鉴权、幂等键和异步任务状态查询是否协同正确。
# 2. 使用临时目录模拟材料导入，避免真实知识库或题库文件被测试覆盖。
# 3. email_validator stub 用于精简测试依赖，避免 CI 环境缺包导致 FastAPI 初始化失败。
# 4. 测试中会主动替换 pydantic 的版本探测函数，结束后需要恢复原始状态。
# 5. 导入任务通常涉及后台协程，因此用轮询方式等待任务进入终态。
# 6. 这些用例主要防止管理端按钮重复点击、权限绕过和任务报告丢失。


def _patched_version(distribution_name: str) -> str:
    """为测试环境补齐 email-validator 版本元数据。"""
    if distribution_name == "email-validator":
        return "2.0.0"
    return _original_version(distribution_name)


def _install_email_validator_stub() -> None:
    """为当前测试模块安装最小 email_validator 替身。"""
    current_module = sys.modules.get("email_validator")
    if current_module is not None and getattr(current_module, "__version__", "") == "2.0.0-test-stub":
        importlib_metadata.version = _patched_version
        pydantic_networks.version = _patched_version
        return
    email_validator_stub = ModuleType("email_validator")

    class EmailNotValidError(ValueError):
        """兼容 Pydantic 的最小邮箱校验异常。"""

    def validate_email(email: str, *args, **kwargs) -> SimpleNamespace:
        """返回最小邮箱校验结果，供测试环境使用。"""
        return SimpleNamespace(
            email=email,
            normalized=email,
            local_part=email.split("@", 1)[0],
        )

    email_validator_stub.EmailNotValidError = EmailNotValidError
    email_validator_stub.validate_email = validate_email
    email_validator_stub.__dict__["__version__"] = "2.0.0-test-stub"
    sys.modules["email_validator"] = email_validator_stub
    importlib_metadata.version = _patched_version
    pydantic_networks.version = _patched_version


def setUpModule() -> None:
    """为当前测试模块准备 email_validator 依赖替身。"""
    _install_email_validator_stub()


def tearDownModule() -> None:
    """恢复当前测试模块修改过的全局状态。"""
    if _original_email_validator is None:
        sys.modules.pop("email_validator", None)
    else:
        sys.modules["email_validator"] = _original_email_validator
    importlib_metadata.version = _original_version
    pydantic_networks.version = _original_pydantic_version


_install_email_validator_stub()

sys.path.append("backend")
from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.schemas import MaterialImportRequest  # noqa: E402
from app.services.material_import_service import _ImportTask  # noqa: E402


class AdminImportsTestCase(unittest.TestCase):
    """验证导入任务接口行为。"""

    def setUp(self) -> None:
        """初始化测试环境与客户端。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["AI_INTERVIEW_DB_PATH"] = os.path.join(self.tmpdir.name, "test.db")
        os.environ["AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN"] = "true"
        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.admin_headers = {"Authorization": "Bearer admin-token"}
        self.material_root = Path(self.tmpdir.name) / "backend" / "assets" / "material"
        self.material_root.mkdir(parents=True, exist_ok=True)
        self.client.app.state.question_bank_service.material_root = self.material_root
        self.client.app.state.question_bank_service.repo_root = Path(self.tmpdir.name)

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        os.environ.pop("AI_INTERVIEW_DB_PATH", None)
        os.environ.pop("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", None)
        get_settings.cache_clear()

    def test_trigger_task_and_query_status(self) -> None:
        """验证触发任务后可查询状态。"""
        idem_key = str(uuid.uuid4())
        resp = self.client.post(
            "/api/v1/admin/imports/materials",
            json={"dry_run": True, "rebuild_mode": "incremental", "roles": ["java"]},
            headers={**self.admin_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertEqual(202, resp.status_code, msg=resp.text)
        payload = resp.json()
        self.assertIn("task_id", payload)

        status_payload = payload
        for _ in range(40):
            status_resp = self.client.get(
                f"/api/v1/admin/imports/materials/{payload['task_id']}",
                headers=self.admin_headers,
            )
            self.assertEqual(200, status_resp.status_code, msg=status_resp.text)
            status_payload = status_resp.json()
            if status_payload["status"] in {"SUCCESS", "FAILED", "PARTIAL_SUCCESS"}:
                break
            time.sleep(0.1)
        self.assertIn(status_payload["status"], {"SUCCESS", "FAILED", "PARTIAL_SUCCESS"})

    def test_same_idempotency_key_returns_same_task(self) -> None:
        """验证同幂等键返回同一个任务。"""
        idem_key = str(uuid.uuid4())
        payload = {"dry_run": True, "rebuild_mode": "incremental", "roles": ["java"]}
        first = self.client.post(
            "/api/v1/admin/imports/materials",
            json=payload,
            headers={**self.admin_headers, "X-Idempotency-Key": idem_key},
        )
        second = self.client.post(
            "/api/v1/admin/imports/materials",
            json=payload,
            headers={**self.admin_headers, "X-Idempotency-Key": idem_key},
        )
        self.assertEqual(202, first.status_code, msg=first.text)
        self.assertEqual(202, second.status_code, msg=second.text)
        self.assertEqual(first.json()["task_id"], second.json()["task_id"])

    def test_reject_unsupported_models(self) -> None:
        """验证不支持模型时返回 400。"""
        resp = self.client.post(
            "/api/v1/admin/imports/materials",
            json={
                "dry_run": True,
                "rebuild_mode": "incremental",
                "roles": ["java"],
                "chunk_model": "other-model",
                "embedding_model": "nomic-embed-text",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(400, resp.status_code, msg=resp.text)
        self.assertEqual("KB_BUILD_400", resp.json()["error"]["code"])

    def test_full_rebuild_conflict(self) -> None:
        """验证全量任务并发冲突返回 409。"""
        service = self.client.app.state.material_import_service
        service._tasks["mock-running-full"] = _ImportTask(
            payload=MaterialImportRequest(
                rebuild_mode="full",
                roles=["java"],
                dry_run=False,
                chunk_model="qwen3.5-2b",
                embedding_model="nomic-embed-text",
            ),
            status="RUNNING",
            stage="embedding",
            progress=50,
            last_error="",
            report_path="",
            task_type="full_pipeline",
            runner=None,
        )
        second = self.client.post(
            "/api/v1/admin/imports/materials",
            json={"dry_run": False, "rebuild_mode": "full", "roles": ["web"]},
            headers={**self.admin_headers, "X-Idempotency-Key": str(uuid.uuid4())},
        )
        self.assertEqual(409, second.status_code, msg=second.text)
        self.assertEqual("KB_BUILD_409", second.json()["error"]["code"])

    def test_question_bank_markdown_upload_triggers_import_task(self) -> None:
        """上传题库 Markdown 后应复用导入任务并可查询状态。"""
        response = self.client.post(
            "/api/v1/practice/questions/upload",
            data={"job_role": "java"},
            files={
                "file": (
                    "batch-import.md",
                    "# Java 题库\n\n## 第 1 题：JVM\n\n### 题干\n\n什么是 JVM？\n\n### 类别\n\n技术\n\n### 解析\n\n说明运行时职责。",
                    "text/markdown",
                )
            },
            headers=self.admin_headers,
        )
        self.assertEqual(202, response.status_code, msg=response.text)
        payload = response.json()
        self.assertEqual("question_bank", payload["task_type"])
        self.assertTrue(payload["task_id"].startswith("kb-build-"))

        saved_file = self.material_root / "java" / "java-interview" / "batch-import.md"
        self.assertTrue(saved_file.exists())

        status_resp = self.client.get(
            f"/api/v1/practice/admin/import-tasks/{payload['task_id']}",
            headers=self.admin_headers,
        )
        self.assertEqual(200, status_resp.status_code, msg=status_resp.text)
        status_payload = status_resp.json()
        self.assertEqual(payload["task_id"], status_payload["task_id"])
        self.assertEqual("question_bank", status_payload["task_type"])

    def test_web_upload_writes_into_interview_markdown_source_of_truth(self) -> None:
        """Web 题库上传应保留原文件名并落到 web 材料目录。"""
        response = self.client.post(
            "/api/v1/practice/questions/upload",
            data={"job_role": "web"},
            files={
                "file": (
                    "batch-web.md",
                    "# Web 题库\n\n### 第 1 题：缓存\n\n#### 题干\n\n什么是强缓存和协商缓存？\n\n#### 类别\n\n技术\n\n#### 解析\n\n说明命中顺序。",
                    "text/markdown",
                )
            },
            headers=self.admin_headers,
        )
        self.assertEqual(202, response.status_code, msg=response.text)
        target_file = self.material_root / "web" / "batch-web.md"
        self.assertTrue(target_file.exists())
        self.assertIn("### 第 1 题：缓存", target_file.read_text(encoding="utf-8"))

    def test_upload_rejects_non_markdown_extension(self) -> None:
        """上传文件扩展名不是 Markdown 时应拒绝。"""
        response = self.client.post(
            "/api/v1/practice/questions/upload",
            data={"job_role": "java"},
            files={
                "file": (
                    "bad.txt",
                    "# 非法文件",
                    "text/plain",
                )
            },
            headers=self.admin_headers,
        )
        self.assertEqual(400, response.status_code, msg=response.text)

    def test_upload_rejects_unknown_category_value(self) -> None:
        """上传题库 Markdown 时应拒绝非法类别值。"""
        response = self.client.post(
            "/api/v1/practice/questions/upload",
            data={"job_role": "java"},
            files={
                "file": (
                    "bad-category.md",
                    "# Java 题库\n\n## 第1题：JVM\n\n### 类别\n\n算法\n\n### 题干\n\n什么是 JVM？\n\n### 解析\n\n说明运行时职责。",
                    "text/markdown",
                )
            },
            headers=self.admin_headers,
        )
        self.assertEqual(400, response.status_code, msg=response.text)
        self.assertEqual("QUESTION_BANK_400", response.json()["error"]["code"])

    def test_upload_rejects_wrong_heading_hierarchy_for_role(self) -> None:
        """上传题库 Markdown 时应拒绝不符合岗位约定的 heading 层级。"""
        response = self.client.post(
            "/api/v1/practice/questions/upload",
            data={"job_role": "web"},
            files={
                "file": (
                    "bad-web-heading.md",
                    "# Web 题库\n\n## 第 1 题：缓存\n\n### 题干\n\n什么是强缓存？\n\n### 类别\n\n技术\n\n### 解析\n\n说明命中顺序。",
                    "text/markdown",
                )
            },
            headers=self.admin_headers,
        )
        self.assertEqual(400, response.status_code, msg=response.text)
        self.assertEqual("QUESTION_BANK_400", response.json()["error"]["code"])

    def test_create_single_question_writes_incremental_material(self) -> None:
        """单题录入应生成标准 Markdown 文件并触发导入任务。"""
        response = self.client.post(
            "/api/v1/practice/questions",
            json={
                "job_role": "web",
                "category": "scenario",
                "title": "首屏优化",
                "question": "你会如何优化首屏加载速度？",
                "analysis": "从资源加载、缓存和渲染链路展开。",
                "source_note": "admin-form",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(202, response.status_code, msg=response.text)
        payload = response.json()
        self.assertEqual("question_bank", payload["task_type"])

        generated_files = list((self.material_root / "web").glob("admin-added-*.md"))
        self.assertEqual(1, len(generated_files))
        target_file = generated_files[0]
        self.assertTrue(target_file.exists())
        content = target_file.read_text(encoding="utf-8")
        self.assertIn("### 第 1 题：首屏优化", content)
        self.assertIn("#### 类别", content)
        self.assertIn("场景", content)
        self.assertIn("#### 题干", content)
        self.assertNotIn("#### 题目", content)
        self.assertNotIn("# 管理端新增题目", content)

    def test_create_java_question_matches_existing_material_convention(self) -> None:
        """Java 单题录入应遵循现有 ##/### 题库结构且不增加额外包装。"""
        response = self.client.post(
            "/api/v1/practice/questions",
            json={
                "job_role": "java",
                "category": "technical",
                "title": "JVM 原理",
                "question": "请说明 JVM 的核心职责。",
                "analysis": "从字节码执行和内存模型展开。",
                "source_note": "admin-form",
            },
            headers=self.admin_headers,
        )
        self.assertEqual(202, response.status_code, msg=response.text)

        generated_files = list((self.material_root / "java" / "java-interview").glob("admin-added-*.md"))
        self.assertEqual(1, len(generated_files))
        content = generated_files[0].read_text(encoding="utf-8")
        self.assertIn("## 第 1 题：JVM 原理", content)
        self.assertIn("### 题干", content)
        self.assertIn("### 类别", content)
        self.assertNotIn("# 管理端新增题目", content)

    def test_list_question_bank_for_admin(self) -> None:
        """管理员应可分页读取题库列表。"""
        repo = self.client.app.state.repo
        with repo._session() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS practice_choice_questions (
                  question_id TEXT PRIMARY KEY,
                  domain TEXT NOT NULL,
                  question_type TEXT NOT NULL CHECK(question_type = 'single_choice'),
                  stem TEXT NOT NULL,
                  options TEXT NOT NULL DEFAULT '[]',
                  answer_keys TEXT NOT NULL DEFAULT '[]',
                  explanation TEXT NOT NULL DEFAULT '',
                  source TEXT NOT NULL DEFAULT '{}',
                  metadata TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO practice_choice_questions(
                  question_id, domain, question_type, stem, options, answer_keys, explanation, source, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("qb-admin-1", "java", "single_choice", "什么是 JVM？", "[]", "[\"A\"]", "说明运行时职责。", "{}", "{}"),
                    ("qb-admin-2", "java", "single_choice", "你做过哪些性能优化？", "[]", "[\"B\"]", "说明定位手段。", "{}", "{}"),
                ],
            )

        response = self.client.get(
            "/api/v1/practice/questions?job_role=java&keyword=JVM&page=1&page_size=10",
            headers=self.admin_headers,
        )
        self.assertEqual(200, response.status_code, msg=response.text)
        payload = response.json()
        self.assertEqual(1, payload["total"])
        self.assertEqual("qb-admin-1", payload["items"][0]["record_id"])

    def test_list_question_bank_category_pagination_total_is_consistent(self) -> None:
        """带 category 分页时 total 应与过滤结果一致且分页稳定。"""
        repo = self.client.app.state.repo
        with repo._session() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS practice_choice_questions (
                  question_id TEXT PRIMARY KEY,
                  domain TEXT NOT NULL,
                  question_type TEXT NOT NULL CHECK(question_type = 'single_choice'),
                  stem TEXT NOT NULL,
                  options TEXT NOT NULL DEFAULT '[]',
                  answer_keys TEXT NOT NULL DEFAULT '[]',
                  explanation TEXT NOT NULL DEFAULT '',
                  source TEXT NOT NULL DEFAULT '{}',
                  metadata TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO practice_choice_questions(
                  question_id, domain, question_type, stem, options, answer_keys, explanation, source, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("qb-admin-a", "java", "single_choice", "A", "[]", "[\"A\"]", "", "{}", "{\"category\":\"technical\"}"),
                    ("qb-admin-b", "java", "single_choice", "B", "[]", "[\"A\"]", "", "{}", "{\"category\":\"technical\"}"),
                    ("qb-admin-c", "java", "single_choice", "C", "[]", "[\"A\"]", "", "{}", "{\"category\":\"technical\"}"),
                    ("qb-admin-d", "java", "single_choice", "D", "[]", "[\"A\"]", "", "{}", "{\"category\":\"project\"}"),
                ],
            )

        page1 = self.client.get(
            "/api/v1/practice/questions?job_role=java&category=technical&page=1&page_size=2",
            headers=self.admin_headers,
        )
        self.assertEqual(200, page1.status_code, msg=page1.text)
        payload1 = page1.json()
        self.assertEqual(3, payload1["total"])
        self.assertEqual(2, len(payload1["items"]))

        page2 = self.client.get(
            "/api/v1/practice/questions?job_role=java&category=technical&page=2&page_size=2",
            headers=self.admin_headers,
        )
        self.assertEqual(200, page2.status_code, msg=page2.text)
        payload2 = page2.json()
        self.assertEqual(3, payload2["total"])
        self.assertEqual(1, len(payload2["items"]))

        page1_ids = {item["record_id"] for item in payload1["items"]}
        page2_ids = {item["record_id"] for item in payload2["items"]}
        self.assertTrue(page1_ids.isdisjoint(page2_ids))


if __name__ == "__main__":
    unittest.main()
