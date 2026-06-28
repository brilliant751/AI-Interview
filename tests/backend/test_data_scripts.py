"""数据脚本回归测试。"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

# 数据脚本测试说明：
# 1. 按文件路径动态加载脚本模块，避免依赖当前工作目录或安装包路径。
# 2. 使用临时目录构造输入输出，测试不会改动真实 data/material 目录。
# 3. 重点验证 normalize、validate、build_question_bank 等脚本的幂等和报告输出。
# 4. subprocess 路径使用当前 Python 解释器，确保测试环境一致。
# 5. 这些用例保护离线数据流水线，避免材料导入接口背后的脚本悄悄失效。
# 6. script_root 指向 backend/assets/scripts/data，是历史兼容路径的一部分。


class DataScriptsTestCase(unittest.TestCase):
    """验证数据脚本基础能力与幂等行为。"""

    def setUp(self) -> None:
        """初始化路径。"""
        self.repo_root = Path(__file__).resolve().parents[2]
        self.python_executable = sys.executable
        self.script_root = self.repo_root / "backend" / "assets" / "scripts" / "data"

    def load_script_module(self, module_name: str):
        """按文件路径加载数据脚本模块。"""
        if str(self.script_root) not in sys.path:
            sys.path.insert(0, str(self.script_root))
        module_path = self.script_root / f"{module_name}.py"
        spec = spec_from_file_location(module_name, module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def test_validate_and_normalize(self) -> None:
        """验证校验脚本与规范化 dry-run 可执行。"""
        validate = subprocess.run(
            [self.python_executable, "backend/assets/scripts/data/validate_materials.py", "--strict"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, validate.returncode, msg=validate.stderr)

        normalize = subprocess.run(
            [self.python_executable, "backend/assets/scripts/data/normalize_materials.py", "--dry-run"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, normalize.returncode, msg=normalize.stderr)

    def test_question_bank_build_is_idempotent(self) -> None:
        """验证同一材料文件重建时会替换旧快照而不是累积陈旧题目。"""
        normalize_materials = self.load_script_module("normalize_materials")
        build_question_bank = self.load_script_module("build_question_bank")
        source_path = self.repo_root / "backend" / "assets" / "material" / "web" / "interview.md"
        first_content = """
## 第1题：事件循环

### 题干

请解释浏览器事件循环。

### 类别

技术

### 解析

从宏任务和微任务切入。
""".strip()
        second_content = """
## 第8题：事件循环进阶

### 题干

请解释 Node.js 事件循环。

### 类别

场景

### 解析

结合阶段和任务队列说明。
""".strip()
        first_rows = normalize_materials.normalize_question_file("web", source_path, first_content)
        second_rows = normalize_materials.normalize_question_file("web", source_path, second_content)
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "question_bank.db"
            conn = sqlite3.connect(db_path)
            try:
                build_question_bank.init_schema(conn)
                with conn:
                    first = build_question_bank.upsert_rows(conn, first_rows)
                with conn:
                    second = build_question_bank.upsert_rows(conn, second_rows)
                stored = conn.execute(
                    """
                    SELECT record_id, question_no, title, category, question
                    FROM question_bank
                    WHERE role = ? AND source_path = ?
                    ORDER BY question_no
                    """,
                    ("web", "backend/assets/material/web/interview.md"),
                ).fetchall()
            finally:
                conn.close()

        self.assertEqual((1, 0), first)
        self.assertEqual((1, 0), second)
        self.assertEqual(1, len(stored))
        self.assertEqual(second_rows[0]["record_id"], stored[0][0])
        self.assertEqual(8, stored[0][1])
        self.assertEqual("事件循环进阶", stored[0][2])
        self.assertEqual("scenario", stored[0][3])
        self.assertEqual("请解释 Node.js 事件循环。", stored[0][4])

    def test_normalize_question_file_maps_category_to_standard_value(self) -> None:
        """验证题库规范化会将中文类别映射为标准枚举。"""
        normalize_materials = self.load_script_module("normalize_materials")
        source_path = self.repo_root / "backend" / "assets" / "material" / "web" / "interview.md"
        content = """
## 第1题：事件循环

### 题干

请解释浏览器事件循环。

### 类别

技术

### 解析

从宏任务和微任务切入。
""".strip()

        rows = normalize_materials.normalize_question_file("web", source_path, content)

        self.assertEqual(1, len(rows))
        self.assertEqual("technical", rows[0]["category"])

    def test_question_bank_build_preserves_standard_category(self) -> None:
        """验证构建题库时会把规范化后的标准类别写入 SQLite。"""
        normalize_materials = self.load_script_module("normalize_materials")
        build_question_bank = self.load_script_module("build_question_bank")
        source_path = self.repo_root / "backend" / "assets" / "material" / "java" / "java-interview" / "sample.md"
        content = """
## 第2题：项目复盘

### 题干

请介绍你做过的核心项目。

### 类别

项目

### 解析

重点说明职责和取舍。
""".strip()

        rows = normalize_materials.normalize_question_file("java", source_path, content)
        conn = sqlite3.connect(":memory:")
        try:
            build_question_bank.init_schema(conn)
            ok, failed = build_question_bank.upsert_rows(conn, rows)
            stored = conn.execute("SELECT category FROM question_bank WHERE record_id = ?", (rows[0]["record_id"],))
            fetched = stored.fetchone()
        finally:
            conn.close()

        self.assertEqual((1, 0), (ok, failed))
        self.assertIsNotNone(fetched)
        self.assertEqual("project", fetched[0])

    def test_question_bank_build_raises_clear_error_for_invalid_row(self) -> None:
        """验证构建题库遇到坏数据时会抛出包含行标识的清晰异常。"""
        build_question_bank = self.load_script_module("build_question_bank")
        bad_rows = [
            {
                "record_id": "bad-record",
                "role": "web",
                "question_no": 1,
                "title": "坏数据",
                "category": "technical",
                "analysis": "",
                "source_path": "backend/assets/material/web/interview.md",
                "raw_markdown": "### 题干",
            }
        ]

        conn = sqlite3.connect(":memory:")
        try:
            build_question_bank.init_schema(conn)
            with self.assertRaisesRegex(RuntimeError, "bad-record"):
                build_question_bank.upsert_rows(conn, bad_rows)
        finally:
            conn.close()

    def test_import_choice_questions_is_idempotent(self) -> None:
        """验证选择题导入脚本重复执行时保持幂等。"""
        import_choice_questions = self.load_script_module("import_choice_questions")
        sample_rows = [
            {
                "question_id": "choice-1",
                "domain": "java",
                "question_type": "single_choice",
                "stem": "JVM 是什么？",
                "options": [{"key": "A", "text": "虚拟机"}],
                "answer_keys": ["A"],
                "explanation": "用于执行 Java 字节码。",
                "source": {"repo_full_name": "demo/repo"},
                "metadata": {"source_key": "demo/repo::a.md"},
            }
        ]
        conn = sqlite3.connect(":memory:")
        try:
            import_choice_questions.init_schema(conn)
            with conn:
                first = import_choice_questions.upsert_rows(conn, sample_rows)
            with conn:
                second = import_choice_questions.upsert_rows(conn, sample_rows)
            count = conn.execute("SELECT COUNT(*) FROM practice_choice_questions").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual((1, 0), first)
        self.assertEqual((1, 0), second)
        self.assertEqual(1, count)

    def test_import_choice_questions_skips_non_single_choice(self) -> None:
        """导入脚本应跳过非 single_choice 题目。"""
        import_choice_questions = self.load_script_module("import_choice_questions")
        sample_rows = [
            {
                "question_id": "choice-1",
                "domain": "java",
                "question_type": "single_choice",
                "stem": "JVM 是什么？",
                "options": [{"key": "A", "text": "虚拟机"}],
                "answer_keys": ["A"],
                "explanation": "用于执行 Java 字节码。",
                "source": {},
                "metadata": {},
            },
            {
                "question_id": "choice-2",
                "domain": "java",
                "question_type": "multiple_choice",
                "stem": "哪些是集合？",
                "options": [{"key": "A", "text": "List"}],
                "answer_keys": ["A"],
                "explanation": "",
                "source": {},
                "metadata": {},
            },
        ]
        conn = sqlite3.connect(":memory:")
        try:
            import_choice_questions.init_schema(conn)
            with conn:
                upserted, skipped = import_choice_questions.upsert_rows(conn, sample_rows)
            count = conn.execute("SELECT COUNT(*) FROM practice_choice_questions").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(1, upserted)
        self.assertEqual(1, skipped)
        self.assertEqual(1, count)

    def test_import_coding_practice_questions_is_idempotent(self) -> None:
        """验证编程题导入脚本重复执行时保持幂等。"""
        import_coding_questions = self.load_script_module("import_coding_practice_questions")
        sample_rows = [
            {
                "question_id": "coding-1",
                "slug": "a-plus-b",
                "title": "A+B",
                "difficulty": "easy",
                "topic_tags": ["模拟"],
                "prompt_markdown": "给定两个整数，输出它们的和。",
                "input_spec": "一行两个整数。",
                "output_spec": "输出一个整数。",
                "constraints_text": "整数范围在 32 位内。",
                "sample_cases": [{"input": "1 2\n", "output": "3\n"}],
                "judge_cases": [{"input": "3 4\n", "output": "7\n"}] * 10,
                "self_test_case": {"input": "5 6\n", "output": "11\n"},
                "starter_codes": {
                    "cpp": "#include <iostream>\nint main(){return 0;}\n",
                    "java": "public class Main { public static void main(String[] args) {} }\n",
                    "javascript": "process.stdin.on('data', () => {})\n",
                },
                "source": {"origin": "unit-test"},
            }
        ]
        conn = sqlite3.connect(":memory:")
        try:
            import_coding_questions.init_schema(conn)
            with conn:
                first = import_coding_questions.upsert_rows(conn, sample_rows)
            with conn:
                second = import_coding_questions.upsert_rows(conn, sample_rows)
            count = conn.execute("SELECT COUNT(*) FROM coding_questions").fetchone()[0]
        finally:
            conn.close()

        self.assertEqual((1, 0), first)
        self.assertEqual((1, 0), second)
        self.assertEqual(1, count)

    def test_import_coding_practice_questions_rejects_invalid_case_count(self) -> None:
        """编程题导入脚本应拒绝正式用例不足 10 条的题目。"""
        import_coding_questions = self.load_script_module("import_coding_practice_questions")
        bad_rows = [
            {
                "question_id": "coding-bad",
                "slug": "bad-problem",
                "title": "坏题目",
                "difficulty": "easy",
                "topic_tags": ["模拟"],
                "prompt_markdown": "坏题目",
                "input_spec": "输入",
                "output_spec": "输出",
                "constraints_text": "约束",
                "sample_cases": [{"input": "1\n", "output": "1\n"}],
                "judge_cases": [{"input": "1\n", "output": "1\n"}],
                "self_test_case": {"input": "1\n", "output": "1\n"},
                "starter_codes": {
                    "cpp": "#include <iostream>\nint main(){return 0;}\n",
                    "java": "public class Main { public static void main(String[] args) {} }\n",
                    "javascript": "process.stdin.on('data', () => {})\n",
                },
                "source": {"origin": "unit-test"},
            }
        ]
        conn = sqlite3.connect(":memory:")
        try:
            import_coding_questions.init_schema(conn)
            with self.assertRaisesRegex(RuntimeError, "10"):
                import_coding_questions.upsert_rows(conn, bad_rows)
        finally:
            conn.close()

    def test_vectorstore_build_dry_run(self) -> None:
        """验证向量索引构建 dry-run 可执行并输出关键字段。"""
        cmd = [
            self.python_executable,
            "backend/assets/scripts/data/build_knowledge_vectorstore.py",
            "--dry-run",
            "--rebuild-mode",
            "incremental",
            "--roles",
            "java",
        ]
        result = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, msg=result.stderr)
        report_path = (
            self.repo_root / "backend" / "assets" / "data" / "reports" / "knowledge_vectorstore_build_report.json"
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("collection_version", report)
        self.assertTrue(report["dry_run"])

    def test_retrieval_eval_script(self) -> None:
        """验证检索评测脚本可执行并输出基础指标。"""
        cmd = [self.python_executable, "backend/assets/scripts/data/evaluate_retrieval.py"]
        result = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, msg=result.stderr)
        report_path = self.repo_root / "backend" / "assets" / "data" / "reports" / "retrieval_eval_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("hit_at_3", report)
        self.assertIn("mrr", report)


if __name__ == "__main__":
    unittest.main()
