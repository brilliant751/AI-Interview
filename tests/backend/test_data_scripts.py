"""数据脚本回归测试。"""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


class DataScriptsTestCase(unittest.TestCase):
    """验证数据脚本基础能力与幂等行为。"""

    def setUp(self) -> None:
        """初始化路径。"""
        self.repo_root = Path(__file__).resolve().parents[2]

    def test_validate_and_normalize(self) -> None:
        """验证校验脚本与规范化 dry-run 可执行。"""
        validate = subprocess.run(
            ["python", "backend/assets/scripts/data/validate_materials.py", "--strict"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, validate.returncode, msg=validate.stderr)

        normalize = subprocess.run(
            ["python", "backend/assets/scripts/data/normalize_materials.py", "--dry-run"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, normalize.returncode, msg=normalize.stderr)

    def test_question_bank_build_is_idempotent(self) -> None:
        """验证题库构建脚本可重复执行。"""
        cmd = ["python", "backend/assets/scripts/data/build_question_bank.py", "--dry-run"]
        first = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=False)
        second = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=False)
        self.assertEqual(0, first.returncode, msg=first.stderr)
        self.assertEqual(0, second.returncode, msg=second.stderr)

        report_path = (
            self.repo_root / "backend" / "assets" / "data" / "reports" / "question_bank_build_report.json"
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("total_rows", report)
        self.assertTrue(report["dry_run"])

    def test_vectorstore_build_dry_run(self) -> None:
        """验证向量索引构建 dry-run 可执行并输出关键字段。"""
        cmd = [
            "python",
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
        cmd = ["python", "backend/assets/scripts/data/evaluate_retrieval.py"]
        result = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, msg=result.stderr)
        report_path = self.repo_root / "backend" / "assets" / "data" / "reports" / "retrieval_eval_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertIn("hit_at_3", report)
        self.assertIn("mrr", report)


if __name__ == "__main__":
    unittest.main()
