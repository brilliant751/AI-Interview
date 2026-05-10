"""题库练习持久化仓储测试。"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from importlib import metadata as importlib_metadata
from pathlib import Path
from types import ModuleType, SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import networks as pydantic_networks

_original_version = importlib_metadata.version
_original_email_validator = sys.modules.get("email_validator")
_original_pydantic_version = pydantic_networks.version


def _patched_version(distribution_name: str) -> str:
    """为测试环境补齐 email-validator 版本元数据。"""
    if distribution_name == "email-validator":
        return "2.0.0"
    return _original_version(distribution_name)


def _install_email_validator_stub() -> None:
    """为当前测试模块按需安装临时 email_validator stub。"""
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
        return SimpleNamespace(email=email, normalized=email)

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
from app.repositories.interview_repository import InterviewRepository  # noqa: E402
from app.services.practice_service import PracticeService  # noqa: E402


class PracticeRepositoryTestCase(unittest.TestCase):
    """验证题库练习域的 SQLite schema 与仓储方法。"""

    def setUp(self) -> None:
        """初始化临时数据库与仓储实例。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "practice.db"
        self.repository = InterviewRepository(str(self.db_path))

    def tearDown(self) -> None:
        """清理临时目录。"""
        self.tmpdir.cleanup()

    def _table_names(self) -> set[str]:
        """读取数据库中的表名集合。"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        return {str(row[0]) for row in rows}

    def _index_names(self) -> set[str]:
        """读取数据库中的索引名集合。"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        return {str(row[0]) for row in rows}

    def _create_legacy_weak_practice_schema(self) -> None:
        """创建缺少完整性约束的旧版 practice 表结构。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE practice_sessions (
                  practice_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  job_role TEXT NOT NULL,
                  mode TEXT NOT NULL,
                  question_count INTEGER NOT NULL,
                  status TEXT NOT NULL DEFAULT 'ACTIVE',
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE practice_session_questions (
                  session_question_id TEXT PRIMARY KEY,
                  practice_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  question_order INTEGER NOT NULL,
                  source_question_id TEXT,
                  category TEXT,
                  stem TEXT NOT NULL,
                  analysis TEXT,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );

                CREATE TABLE practice_answers (
                  answer_id TEXT PRIMARY KEY,
                  practice_id TEXT NOT NULL,
                  session_question_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  answer_text TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                """
            )
            conn.execute(
                """
                INSERT INTO practice_sessions(practice_id, user_id, job_role, mode, question_count, status)
                VALUES ('prac_legacy', 'user-a', 'java', 'sequence', 2, 'ACTIVE')
                """
            )
            conn.execute(
                """
                INSERT INTO practice_session_questions(
                  session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, analysis
                )
                VALUES ('psq_legacy', 'prac_legacy', 'user-a', 1, 'qb-java-legacy', 'technical', '旧题目', '旧解析')
                """
            )
            conn.execute(
                """
                INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text)
                VALUES ('ans_legacy', 'prac_legacy', 'psq_legacy', 'user-a', '旧答案')
                """
            )

    def _run_practice_migration(self) -> None:
        """执行 practice 迁移脚本。"""
        migration_sql = Path("backend/migrations/0006_practice_domain.sql").read_text(encoding="utf-8")
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(migration_sql)

    def _assert_practice_constraints_enforced(self, require_duplicate_answer_guard: bool = True) -> None:
        """断言迁移后的 practice 表结构已启用目标约束。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute(
                """
                INSERT INTO practice_sessions(practice_id, user_id, job_role, mode, question_count, status)
                VALUES ('prac_check', 'user-a', 'java', 'sequence', 2, 'ACTIVE')
                """
            )
            conn.execute(
                """
                INSERT INTO practice_session_questions(
                  session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, analysis
                )
                VALUES ('psq_check', 'prac_check', 'user-a', 1, 'qb-check-1', 'technical', '检查题目', '检查解析')
                """
            )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO practice_session_questions(
                      session_question_id, practice_id, user_id, question_order, source_question_id, category, stem, analysis
                    )
                    VALUES ('psq_dup', 'prac_check', 'user-a', 1, 'qb-check-2', 'technical', '重复顺序题目', '重复解析')
                    """
                )
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text)
                    VALUES ('ans_orphan_check', 'prac_check', 'psq_missing', 'user-a', '孤立答案')
                    """
                )
            conn.execute(
                """
                INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text)
                VALUES ('ans_check', 'prac_check', 'psq_check', 'user-a', '第一份答案')
                """
            )
            if require_duplicate_answer_guard:
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute(
                        """
                        INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text)
                        VALUES ('ans_dup_check', 'prac_check', 'psq_check', 'user-a', '重复答案')
                        """
                    )

    def test_init_schema_creates_practice_tables(self) -> None:
        """初始化 schema 时应创建题库练习表与索引。"""
        self.repository.init_schema()

        table_names = self._table_names()
        index_names = self._index_names()

        self.assertIn("practice_sessions", table_names)
        self.assertIn("practice_session_questions", table_names)
        self.assertIn("practice_answers", table_names)
        self.assertIn("idx_practice_sessions_user_created", index_names)
        self.assertIn("idx_practice_questions_session_order", index_names)
        self.assertIn("idx_practice_answers_user_session", index_names)

    def test_create_session_and_list_question_snapshots_with_user_scope(self) -> None:
        """题目快照的创建与查询应遵循用户隔离。"""
        self.repository.init_schema()

        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 2,
            },
        )

        first_snapshot_id = self.repository.add_practice_question_snapshot(
            user_id="user-a",
            practice_id=session["practice_id"],
            question_order=1,
            question_data={
                "source_question_id": "qb-java-1",
                "category": "technical",
                "stem": "什么是 JVM 类加载机制？",
                "analysis": "从双亲委派与加载流程说明。",
            },
        )
        second_snapshot_id = self.repository.add_practice_question_snapshot(
            user_id="user-a",
            practice_id=session["practice_id"],
            question_order=2,
            question_data={
                "source_question_id": "qb-java-2",
                "category": "project",
                "stem": "你做过哪些性能优化？",
                "analysis": "关注定位手段与收益。",
            },
        )

        rows = self.repository.list_practice_question_snapshots("user-a", session["practice_id"])
        self.assertEqual(2, len(rows))
        self.assertEqual(first_snapshot_id, rows[0]["session_question_id"])
        self.assertEqual(second_snapshot_id, rows[1]["session_question_id"])
        self.assertEqual([], self.repository.list_practice_question_snapshots("user-b", session["practice_id"]))

    def test_store_and_list_answers_with_user_scope(self) -> None:
        """答案写入与查询应仅返回当前用户自己的记录。"""
        self.repository.init_schema()

        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 1,
            },
        )
        snapshot_id = self.repository.add_practice_question_snapshot(
            user_id="user-a",
            practice_id=session["practice_id"],
            question_order=1,
            question_data={
                "source_question_id": "qb-java-3",
                "category": "technical",
                "stem": "什么是线程池？",
                "analysis": "说明核心参数与使用场景。",
            },
        )

        answer_id = self.repository.add_practice_answer(
            user_id="user-a",
            practice_id=session["practice_id"],
            session_question_id=snapshot_id,
            answer_text="线程池用于复用线程并控制并发资源。",
        )

        rows = self.repository.list_practice_answers("user-a", session["practice_id"])
        self.assertEqual(1, len(rows))
        self.assertEqual(answer_id, rows[0]["answer_id"])
        self.assertEqual(snapshot_id, rows[0]["session_question_id"])
        self.assertEqual([], self.repository.list_practice_answers("user-b", session["practice_id"]))

    def test_duplicate_answer_must_be_rejected_within_one_session(self) -> None:
        """同一练习题在同一会话内不应接受重复答案。"""
        self.repository.init_schema()
        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 1,
            },
        )
        snapshot_id = self.repository.add_practice_question_snapshot(
            user_id="user-a",
            practice_id=session["practice_id"],
            question_order=1,
            question_data={
                "source_question_id": "qb-java-dup-1",
                "category": "technical",
                "stem": "什么是幂等？",
                "analysis": "说明请求重试的影响。",
            },
        )
        self.repository.add_practice_answer(
            user_id="user-a",
            practice_id=session["practice_id"],
            session_question_id=snapshot_id,
            answer_text="第一次答案",
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add_practice_answer(
                user_id="user-a",
                practice_id=session["practice_id"],
                session_question_id=snapshot_id,
                answer_text="重复答案",
            )

    def test_create_practice_session_with_snapshots_is_atomic(self) -> None:
        """批量创建会话与题目快照时任一步失败都应整体回滚。"""
        self.repository.init_schema()

        with self.assertRaises(KeyError):
            self.repository.create_practice_session_with_snapshots(
                user_id="user-a",
                payload={
                    "job_role": "java",
                    "mode": "sequence",
                    "question_count": 2,
                },
                question_snapshots=[
                    {
                        "source_question_id": "qb-java-atomic-1",
                        "category": "technical",
                        "stem": "第一题",
                        "analysis": "第一题解析",
                    },
                    {
                        "source_question_id": "qb-java-atomic-2",
                        "category": "technical",
                        "analysis": "第二题缺题干会失败",
                    },
                ],
            )

        with sqlite3.connect(self.db_path) as conn:
            session_count = conn.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0]
            snapshot_count = conn.execute("SELECT COUNT(*) FROM practice_session_questions").fetchone()[0]
        self.assertEqual(0, session_count)
        self.assertEqual(0, snapshot_count)

    def test_update_practice_session_status_and_get_by_id(self) -> None:
        """会话状态更新与按主键读取应收敛在仓储层。"""
        self.repository.init_schema()
        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 1,
            },
        )

        self.assertTrue(
            self.repository.update_practice_session_status(
                user_id="user-a",
                practice_id=session["practice_id"],
                status="FINISHED",
            )
        )
        self.assertFalse(
            self.repository.update_practice_session_status(
                user_id="user-b",
                practice_id=session["practice_id"],
                status="ACTIVE",
            )
        )

        refreshed = self.repository.get_practice_session_by_id(session["practice_id"])
        self.assertIsNotNone(refreshed)
        self.assertEqual("FINISHED", refreshed["status"])

    def test_list_practice_records_and_question_bank_items(self) -> None:
        """练习记录聚合与题库候选读取应由仓储提供。"""
        self.repository.init_schema()
        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 2,
            },
        )
        snapshot_id = self.repository.add_practice_question_snapshot(
            user_id="user-a",
            practice_id=session["practice_id"],
            question_order=1,
            question_data={
                "source_question_id": "qb-java-9",
                "category": "technical",
                "stem": "什么是线程上下文切换？",
                "analysis": "说明成本来源。",
            },
        )
        self.repository.add_practice_answer(
            user_id="user-a",
            practice_id=session["practice_id"],
            session_question_id=snapshot_id,
            answer_text="线程切换会带来调度和缓存失效开销。",
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE question_bank (
                  record_id TEXT PRIMARY KEY,
                  role TEXT NOT NULL,
                  question_no INTEGER NOT NULL,
                  title TEXT NOT NULL,
                  category TEXT,
                  question TEXT NOT NULL,
                  analysis TEXT,
                  source_path TEXT NOT NULL,
                  raw_markdown TEXT NOT NULL,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO question_bank(
                  record_id, role, question_no, title, category, question, analysis, source_path, raw_markdown
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("qb-java-1", "java", 1, "JVM", "technical", "什么是 JVM？", "说明运行时职责。", "mock-a", "raw-a"),
                    ("qb-java-2", "java", 2, "项目", "project", "你做过哪些性能优化？", "说明收益。", "mock-a", "raw-b"),
                ],
            )

        records = self.repository.list_practice_records("user-a")
        self.assertEqual(1, len(records))
        self.assertEqual(1, int(records[0]["answered_count"]))
        self.assertEqual([], self.repository.list_practice_records("user-b"))

        candidates = self.repository.list_question_bank_items("java", ["technical"])
        self.assertEqual(1, len(candidates))
        self.assertEqual("qb-java-1", candidates[0]["record_id"])

    def test_add_question_snapshot_raises_when_practice_not_owned(self) -> None:
        """无权访问练习会话时写入题目快照应显式失败。"""
        self.repository.init_schema()
        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 1,
            },
        )

        with self.assertRaisesRegex(ValueError, "练习会话不存在或无权访问"):
            self.repository.add_practice_question_snapshot(
                user_id="user-b",
                practice_id=session["practice_id"],
                question_order=1,
                question_data={
                    "source_question_id": "qb-java-4",
                    "category": "technical",
                    "stem": "什么是 GC？",
                    "analysis": "说明不同收集器的取舍。",
                },
            )

    def test_add_answer_raises_when_snapshot_not_owned(self) -> None:
        """无权访问题目快照时写入答案应显式失败。"""
        self.repository.init_schema()
        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 1,
            },
        )
        snapshot_id = self.repository.add_practice_question_snapshot(
            user_id="user-a",
            practice_id=session["practice_id"],
            question_order=1,
            question_data={
                "source_question_id": "qb-java-5",
                "category": "technical",
                "stem": "什么是对象池？",
                "analysis": "说明复用收益和适用边界。",
            },
        )

        with self.assertRaisesRegex(ValueError, "题目快照不存在或无权访问"):
            self.repository.add_practice_answer(
                user_id="user-b",
                practice_id=session["practice_id"],
                session_question_id=snapshot_id,
                answer_text="对象池用于复用昂贵对象。",
            )

    def test_question_order_must_be_unique_within_session(self) -> None:
        """同一练习会话内题目顺序应唯一。"""
        self.repository.init_schema()
        session = self.repository.create_practice_session(
            user_id="user-a",
            payload={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 2,
            },
        )
        self.repository.add_practice_question_snapshot(
            user_id="user-a",
            practice_id=session["practice_id"],
            question_order=1,
            question_data={
                "source_question_id": "qb-java-6",
                "category": "technical",
                "stem": "什么是 volatile？",
                "analysis": "说明可见性与有序性。",
            },
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add_practice_question_snapshot(
                user_id="user-a",
                practice_id=session["practice_id"],
                question_order=1,
                question_data={
                    "source_question_id": "qb-java-7",
                    "category": "technical",
                    "stem": "什么是 synchronized？",
                    "analysis": "说明锁升级和使用场景。",
                },
            )

    def test_foreign_keys_reject_orphan_answer_rows(self) -> None:
        """数据库约束应拒绝写入孤立答案记录。"""
        self.repository.init_schema()

        with self.repository._session() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("ans_orphan", "prac_missing", "psq_missing", "user-a", "孤立答案"),
                )

    def test_init_schema_upgrades_legacy_weak_practice_tables(self) -> None:
        """初始化应将旧版弱约束 practice 表升级为强约束结构。"""
        self._create_legacy_weak_practice_schema()

        self.repository.init_schema()

        rows = self.repository.list_practice_question_snapshots("user-a", "prac_legacy")
        self.assertEqual(1, len(rows))
        self.assertEqual("psq_legacy", rows[0]["session_question_id"])

        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.add_practice_question_snapshot(
                user_id="user-a",
                practice_id="prac_legacy",
                question_order=1,
                question_data={
                    "source_question_id": "qb-java-8",
                    "category": "technical",
                    "stem": "升级后不应允许重复顺序",
                    "analysis": "验证唯一约束生效。",
                },
            )

        with self.repository._session() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO practice_answers(answer_id, practice_id, session_question_id, user_id, answer_text)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("ans_upgrade_orphan", "prac_legacy", "psq_missing", "user-a", "升级后孤立答案应失败"),
                )

    def test_migration_sql_builds_strong_schema_on_fresh_db(self) -> None:
        """迁移脚本应可在空数据库上直接执行并产出强约束结构。"""
        self._run_practice_migration()
        self._assert_practice_constraints_enforced(require_duplicate_answer_guard=False)

    def test_migration_sql_upgrades_legacy_weak_schema(self) -> None:
        """迁移脚本应可升级旧版弱约束 practice 表结构。"""
        self._create_legacy_weak_practice_schema()
        self._run_practice_migration()

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT q.session_question_id, a.answer_id
                FROM practice_session_questions q
                LEFT JOIN practice_answers a
                  ON a.practice_id = q.practice_id
                 AND a.session_question_id = q.session_question_id
                WHERE q.practice_id = 'prac_legacy'
                """
            ).fetchall()
        self.assertEqual([("psq_legacy", "ans_legacy")], rows)
        self._assert_practice_constraints_enforced(require_duplicate_answer_guard=False)


class PracticeFlowTestCase(unittest.TestCase):
    """验证题库练习 API 主路径与权限边界。"""

    def setUp(self) -> None:
        """初始化测试环境、客户端与题库数据。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "practice-api.db"
        self._set_env("AI_INTERVIEW_DB_PATH", str(self.db_path))
        self._set_env("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", "true")
        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.user_headers = {"Authorization": "Bearer user-token"}
        self.admin_headers = {"Authorization": "Bearer admin-token"}
        self._seed_question_bank()

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        self._clear_env("AI_INTERVIEW_DB_PATH")
        self._clear_env("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN")
        get_settings.cache_clear()

    def _set_env(self, key: str, value: str) -> None:
        """设置测试环境变量。"""
        import os

        os.environ[key] = value

    def _clear_env(self, key: str) -> None:
        """移除测试环境变量。"""
        import os

        os.environ.pop(key, None)

    def _seed_question_bank(self) -> None:
        """为练习流程准备最小题库数据。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS question_bank (
                  record_id TEXT PRIMARY KEY,
                  role TEXT NOT NULL,
                  question_no INTEGER NOT NULL,
                  title TEXT NOT NULL,
                  category TEXT,
                  question TEXT NOT NULL,
                  analysis TEXT,
                  source_path TEXT NOT NULL,
                  raw_markdown TEXT NOT NULL,
                  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            conn.executemany(
                """
                INSERT INTO question_bank(
                  record_id, role, question_no, title, category, question, analysis, source_path, raw_markdown
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        "qb-java-1",
                        "java",
                        1,
                        "JVM",
                        "technical",
                        "什么是 JVM 类加载机制？",
                        "说明双亲委派与加载流程。",
                        "backend/assets/material/java/java-interview/mock.md",
                        "raw-1",
                    ),
                    (
                        "qb-java-2",
                        "java",
                        2,
                        "性能优化",
                        "project",
                        "你做过哪些性能优化？",
                        "说明定位手段与收益。",
                        "backend/assets/material/java/java-interview/mock.md",
                        "raw-2",
                    ),
                    (
                        "qb-java-3",
                        "java",
                        3,
                        "并发",
                        "technical",
                        "volatile 有什么作用？",
                        "说明可见性与有序性。",
                        "backend/assets/material/java/java-interview/mock.md",
                        "raw-3",
                    ),
                ],
            )

    def test_sequence_practice_flow(self) -> None:
        """验证顺序模式练习可创建、推进并自动结束。"""
        created = self.client.post(
            "/api/v1/practice/sessions",
            json={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 2,
                "category_filters": ["technical", "project"],
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        created_payload = created.json()
        self.assertEqual("ACTIVE", created_payload["status"])
        self.assertEqual("sequence", created_payload["mode"])
        self.assertEqual(0, created_payload["completed_count"])
        self.assertFalse(created_payload["finished"])
        self.assertIn("current_question", created_payload)
        self.assertEqual(2, created_payload["total_questions"])

        practice_id = created_payload["practice_id"]
        first_question = created_payload["current_question"]

        status_resp = self.client.get(
            f"/api/v1/practice/sessions/{practice_id}",
            headers=self.user_headers,
        )
        self.assertEqual(200, status_resp.status_code, msg=status_resp.text)
        self.assertEqual(first_question["session_question_id"], status_resp.json()["current_question"]["session_question_id"])

        answered = self.client.post(
            f"/api/v1/practice/sessions/{practice_id}/answers",
            json={
                "session_question_id": first_question["session_question_id"],
                "answer_text": "第一题答案",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, answered.status_code, msg=answered.text)
        answered_payload = answered.json()
        self.assertEqual("ACTIVE", answered_payload["status"])
        self.assertEqual(1, answered_payload["completed_count"])
        self.assertFalse(answered_payload["finished"])
        self.assertIsNotNone(answered_payload["next_question"])

        finished = self.client.post(
            f"/api/v1/practice/sessions/{practice_id}/answers",
            json={
                "session_question_id": answered_payload["next_question"]["session_question_id"],
                "answer_text": "第二题答案",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, finished.status_code, msg=finished.text)
        finished_payload = finished.json()
        self.assertEqual("FINISHED", finished_payload["status"])
        self.assertEqual(2, finished_payload["completed_count"])
        self.assertTrue(finished_payload["finished"])
        self.assertIsNone(finished_payload["next_question"])

        records_resp = self.client.get("/api/v1/practice/records", headers=self.user_headers)
        self.assertEqual(200, records_resp.status_code, msg=records_resp.text)
        self.assertEqual(1, records_resp.json()["total"])
        self.assertEqual(2, records_resp.json()["items"][0]["answered_count"])

        detail_resp = self.client.get(
            f"/api/v1/practice/sessions/{practice_id}/records",
            headers=self.user_headers,
        )
        self.assertEqual(200, detail_resp.status_code, msg=detail_resp.text)
        detail_payload = detail_resp.json()
        self.assertEqual(practice_id, detail_payload["practice_id"])
        self.assertEqual(2, detail_payload["completed_count"])
        self.assertEqual(2, len(detail_payload["items"]))
        self.assertEqual("第一题答案", detail_payload["items"][0]["answer_text"])

    def test_finish_and_scope_protection(self) -> None:
        """验证手动结束会话与跨用户访问保护。"""
        created = self.client.post(
            "/api/v1/practice/sessions",
            json={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 1,
                "category_filters": ["technical"],
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        practice_id = created.json()["practice_id"]

        forbidden = self.client.get(
            f"/api/v1/practice/sessions/{practice_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(403, forbidden.status_code)

        finished = self.client.post(
            f"/api/v1/practice/sessions/{practice_id}/finish",
            headers=self.user_headers,
        )
        self.assertEqual(200, finished.status_code, msg=finished.text)
        self.assertEqual("FINISHED", finished.json()["status"])
        self.assertTrue(finished.json()["finished"])

        after_finish = self.client.post(
            f"/api/v1/practice/sessions/{practice_id}/answers",
            json={
                "session_question_id": created.json()["current_question"]["session_question_id"],
                "answer_text": "结束后继续提交",
            },
            headers=self.user_headers,
        )
        self.assertEqual(409, after_finish.status_code)

    def test_followup_mode_returns_stable_shape(self) -> None:
        """验证追问模式至少返回稳定的响应结构。"""
        created = self.client.post(
            "/api/v1/practice/sessions",
            json={
                "job_role": "java",
                "mode": "followup",
                "question_count": 2,
                "category_filters": ["technical"],
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        payload = created.json()
        self.assertEqual("followup", payload["mode"])
        self.assertEqual("followup_placeholder", payload["question_strategy"])
        self.assertIn("current_question", payload)
        self.assertEqual(2, payload["total_questions"])
        self.assertEqual(0, payload["completed_count"])

        answered = self.client.post(
            f"/api/v1/practice/sessions/{payload['practice_id']}/answers",
            json={
                "session_question_id": payload["current_question"]["session_question_id"],
                "answer_text": "追问模式第一题答案",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, answered.status_code, msg=answered.text)
        answer_payload = answered.json()
        self.assertEqual("followup_placeholder", answer_payload["question_strategy"])
        self.assertEqual("ACTIVE", answer_payload["status"])
        self.assertFalse(answer_payload["finished"])
        self.assertIsNotNone(answer_payload["next_question"])

    def test_duplicate_submit_fails_without_inflating_progress(self) -> None:
        """重复提交同一题时应明确失败，且进度不增加。"""
        created = self.client.post(
            "/api/v1/practice/sessions",
            json={
                "job_role": "java",
                "mode": "sequence",
                "question_count": 2,
                "category_filters": ["technical", "project"],
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        practice_id = created.json()["practice_id"]
        current_question = created.json()["current_question"]

        first_submit = self.client.post(
            f"/api/v1/practice/sessions/{practice_id}/answers",
            json={
                "session_question_id": current_question["session_question_id"],
                "answer_text": "第一次提交",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, first_submit.status_code, msg=first_submit.text)

        duplicate_submit = self.client.post(
            f"/api/v1/practice/sessions/{practice_id}/answers",
            json={
                "session_question_id": current_question["session_question_id"],
                "answer_text": "重复提交",
            },
            headers=self.user_headers,
        )
        self.assertEqual(409, duplicate_submit.status_code, msg=duplicate_submit.text)
        self.assertEqual("PRACTICE_409_DUPLICATE_ANSWER", duplicate_submit.json()["error"]["code"])

        status_resp = self.client.get(
            f"/api/v1/practice/sessions/{practice_id}",
            headers=self.user_headers,
        )
        self.assertEqual(200, status_resp.status_code, msg=status_resp.text)
        self.assertEqual(1, status_resp.json()["completed_count"])

    def test_create_session_rollback_when_snapshot_write_fails(self) -> None:
        """题目快照写入失败时，接口层不应留下半成品练习会话。"""
        repo = self.client.app.state.repo
        original_method = repo.create_practice_session_with_snapshots

        def broken_create(*args, **kwargs):
            """模拟仓储批量写入期间抛错。"""
            return original_method(
                *args,
                **{
                    **kwargs,
                    "question_snapshots": [
                        kwargs["question_snapshots"][0],
                        {
                            "source_question_id": "broken-q",
                            "category": "technical",
                            "analysis": "缺失题干触发失败",
                        },
                    ],
                },
            )

        repo.create_practice_session_with_snapshots = broken_create
        try:
            with self.assertRaises(KeyError):
                self.client.post(
                    "/api/v1/practice/sessions",
                    json={
                        "job_role": "java",
                        "mode": "sequence",
                        "question_count": 2,
                        "category_filters": ["technical", "project"],
                    },
                    headers=self.user_headers,
                )
        finally:
            repo.create_practice_session_with_snapshots = original_method

        records_resp = self.client.get("/api/v1/practice/records", headers=self.user_headers)
        self.assertEqual(200, records_resp.status_code, msg=records_resp.text)
        self.assertEqual(0, records_resp.json()["total"])

    def test_practice_admin_routes_require_admin_role(self) -> None:
        """题库管理接口应拒绝普通用户访问。"""
        list_resp = self.client.get(
            "/api/v1/practice/questions?job_role=java&page=1&page_size=10",
            headers=self.user_headers,
        )
        self.assertEqual(403, list_resp.status_code, msg=list_resp.text)

        create_resp = self.client.post(
            "/api/v1/practice/questions",
            json={
                "job_role": "java",
                "category": "technical",
                "title": "JVM",
                "question": "什么是 JVM？",
                "analysis": "说明运行时职责。",
                "source_note": "user",
            },
            headers=self.user_headers,
        )
        self.assertEqual(403, create_resp.status_code, msg=create_resp.text)


if __name__ == "__main__":
    unittest.main()
