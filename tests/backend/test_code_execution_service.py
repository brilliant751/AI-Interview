"""代码执行服务回归测试。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.append("backend")

from app.services.code_execution_service import CodeExecutionService  # noqa: E402


class CodeExecutionServiceTestCase(unittest.TestCase):
    """验证代码执行服务的关键降级逻辑。"""

    def test_java_compile_falls_back_when_release_21_is_unsupported(self) -> None:
        """当 javac 不支持 release 21 时，应降级为当前版本可执行的编译命令。"""
        service = CodeExecutionService()
        workdir = Path(self.id())

        def fake_run(command: list[str], **kwargs) -> CompletedProcess[str]:
            """按命令形态返回编译结果。"""
            if command == ["javac", "--release", "21", "Main.java"]:
                return CompletedProcess(command, 2, "", "error: release version 21 not supported")
            if command == ["javac", "Main.java"]:
                return CompletedProcess(command, 0, "", "")
            raise AssertionError(f"unexpected command: {command}")

        with patch("app.services.code_execution_service.subprocess.run", side_effect=fake_run) as mocked_run:
            compile_output = service._compile_java(workdir)

        self.assertIsNone(compile_output)
        self.assertEqual(2, mocked_run.call_count)


if __name__ == "__main__":
    unittest.main()
