"""本地编程代码执行服务。"""

from __future__ import annotations

import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


# 本地执行服务的设计重点是“足够可控”：
# 1. 每次执行都在临时目录内写入源码，运行结束目录自动删除。
# 2. 编译和运行都设置 timeout，避免用户代码无限循环拖住后端进程。
# 3. 输出会截断，防止大 stdout/stderr 撑爆响应体或数据库记录。
# 4. RUN 和 SUBMIT 共用执行逻辑，只通过 submit_type 区分业务语义。
# 5. 当前服务依赖本机 g++/javac/java/node 环境，适合课程项目和本地部署。
@dataclass(frozen=True)
class _LanguageConfig:
    """语言执行配置。"""

    source_file: str
    compile_command: list[str] | None
    run_command: list[str]


class CodeExecutionService:
    """负责在本地受限环境中编译并运行代码。"""

    def __init__(self, timeout_seconds: int = 5, output_limit: int = 20000):
        """初始化执行参数。"""
        self.timeout_seconds = timeout_seconds
        self.output_limit = output_limit

    def execute_cases(self, language: str, source_code: str, cases: list[dict], submit_type: str) -> dict:
        """编译代码并批量执行测试用例。"""
        config = self._resolve_config(language)
        with tempfile.TemporaryDirectory(prefix="coding-practice-") as tmpdir:
            # 临时目录隔离每一次运行，避免不同用户或不同题目的源码互相覆盖。
            # 这里不复用历史文件，确保判题结果只受当前 source_code 和 cases 影响。
            workdir = Path(tmpdir)
            source_path = workdir / config.source_file
            source_path.write_text(source_code, encoding="utf-8")

            compile_result = self._compile_if_needed(workdir, config)
            if compile_result is not None:
                # 编译失败时不再运行任何测试用例，直接返回统一的 COMPILE_ERROR 结构。
                return {
                    "status": "COMPILE_ERROR",
                    "passed_count": 0,
                    "total_count": len(cases),
                    "submit_type": submit_type,
                    "message": "编译失败",
                    "results": [],
                    "compile_output": compile_result,
                }

            results: list[dict] = []
            passed_count = 0
            for index, case in enumerate(cases, start=1):
                # 一旦发现首个失败用例就提前返回，减少无意义的后续执行。
                # 前端只展示失败样例即可帮助用户定位问题。
                run_result = self._run_once(workdir, config, str(case.get("input") or ""))
                expected_output = str(case.get("output") or "")
                normalized_actual = self._normalize_output(run_result["stdout"])
                normalized_expected = self._normalize_output(expected_output)
                case_status = run_result["status"]
                if case_status == "ACCEPTED" and normalized_actual != normalized_expected:
                    case_status = "WRONG_ANSWER"
                if case_status == "ACCEPTED":
                    passed_count += 1
                else:
                    results.append(
                        {
                            "index": index,
                            "status": case_status,
                            "stdin": case.get("input") or "",
                            "expected_output": expected_output,
                            "actual_output": run_result["stdout"],
                            "stderr": run_result["stderr"],
                            "time_ms": run_result["time_ms"],
                        }
                    )
                    return {
                        "status": case_status,
                        "passed_count": passed_count,
                        "total_count": len(cases),
                        "submit_type": submit_type,
                        "message": "测试未通过",
                        "results": results,
                    }

            return {
                "status": "ACCEPTED",
                "passed_count": passed_count,
                "total_count": len(cases),
                "submit_type": submit_type,
                "message": "全部通过",
                "results": results,
            }

    def _resolve_config(self, language: str) -> _LanguageConfig:
        """解析语言配置。"""
        if language == "cpp":
            return _LanguageConfig(
                source_file="main.cpp",
                compile_command=["g++", "-std=c++11", "main.cpp", "-O2", "-pipe", "-o", "main"],
                run_command=["./main"],
            )
        if language == "java":
            return _LanguageConfig(
                source_file="Main.java",
                compile_command=None,
                run_command=["java", "-cp", ".", "Main"],
            )
        if language == "javascript":
            return _LanguageConfig(
                source_file="main.js",
                compile_command=None,
                run_command=["node", "main.js"],
            )
        raise ValueError("不支持的语言")

    def _compile_if_needed(self, workdir: Path, config: _LanguageConfig) -> str | None:
        """执行编译步骤。"""
        if config.source_file == "Main.java":
            return self._compile_java(workdir)
        if config.compile_command is None:
            return None
        return self._run_compile_command(workdir, config.compile_command)

    def _compile_java(self, workdir: Path) -> str | None:
        """编译 Java 代码，并在低版本 JDK 环境下自动降级。"""
        # 优先使用 --release 21 保持题目环境一致。
        # 如果本地 JDK 不支持 release 21，再回退到普通 javac，提升学生本机兼容性。
        primary_command = ["javac", "--release", "21", "Main.java"]
        compile_error = self._run_compile_command(workdir, primary_command)
        if compile_error is None:
            return None
        if "release version 21 not supported" not in compile_error.lower():
            return compile_error
        return self._run_compile_command(workdir, ["javac", "Main.java"])

    def _run_compile_command(self, workdir: Path, command: list[str]) -> str | None:
        """执行单条编译命令并返回错误输出。"""
        try:
            result = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "编译超时"
        if result.returncode == 0:
            return None
        return self._truncate_output(result.stderr or result.stdout or "编译失败")

    def _run_once(self, workdir: Path, config: _LanguageConfig, stdin_text: str) -> dict:
        """执行单次程序运行。"""
        started_at = time.perf_counter()
        try:
            result = subprocess.run(
                config.run_command,
                cwd=workdir,
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "status": "TIME_LIMIT_EXCEEDED",
                "stdout": self._truncate_output((exc.stdout or "") if isinstance(exc.stdout, str) else ""),
                "stderr": self._truncate_output((exc.stderr or "") if isinstance(exc.stderr, str) else ""),
                "time_ms": int((time.perf_counter() - started_at) * 1000),
            }

        status = "ACCEPTED"
        if result.returncode != 0:
            status = "RUNTIME_ERROR"
        return {
            "status": status,
            "stdout": self._truncate_output(result.stdout),
            "stderr": self._truncate_output(result.stderr),
            "time_ms": int((time.perf_counter() - started_at) * 1000),
        }

    def _truncate_output(self, output: str) -> str:
        """裁剪过长输出。"""
        if len(output) <= self.output_limit:
            return output
        return output[: self.output_limit] + "\n...[truncated]"

    def _normalize_output(self, output: str) -> str:
        """归一化输出，忽略末尾空白差异。"""
        return output.replace("\r\n", "\n").strip()
