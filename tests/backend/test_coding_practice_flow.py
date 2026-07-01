"""在线编程练习后端流程测试。"""

from __future__ import annotations

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

# 编程练习后端测试说明：
# 1. 覆盖题目列表、创建/恢复 session、自测、正式提交和记录查询。
# 2. 题目数据通过启动同步或测试内插入准备，确保接口返回包含用户进度。
# 3. email_validator stub 复用认证相关测试策略，减少额外依赖对 CI 的影响。
# 4. 判题执行通常会被 mock 或使用轻量路径，避免测试受本机编译器环境影响。
# 5. 用户归属校验是重点，session_id 不能被其他用户直接访问。
# 6. 这些用例防止编程练习和普通题库练习的数据表混淆。


def _patched_version(distribution_name: str) -> str:
    """为测试环境补齐 email-validator 版本元数据。"""
    if distribution_name == "email-validator":
        return "2.0.0"
    return _original_version(distribution_name)


def _install_email_validator_stub() -> None:
    """安装最小 email_validator 替身。"""
    current_module = sys.modules.get("email_validator")
    if current_module is not None and getattr(current_module, "__version__", "") == "2.0.0-test-stub":
        importlib_metadata.version = _patched_version
        pydantic_networks.version = _patched_version
        return
    email_validator_stub = ModuleType("email_validator")

    class EmailNotValidError(ValueError):
        """兼容 Pydantic 的最小邮箱校验异常。"""

    def validate_email(email: str, *args, **kwargs) -> SimpleNamespace:
        """返回最小邮箱校验结果。"""
        return SimpleNamespace(email=email, normalized=email, local_part=email.split("@", 1)[0])

    email_validator_stub.EmailNotValidError = EmailNotValidError
    email_validator_stub.validate_email = validate_email
    email_validator_stub.__dict__["__version__"] = "2.0.0-test-stub"
    sys.modules["email_validator"] = email_validator_stub
    importlib_metadata.version = _patched_version
    pydantic_networks.version = _patched_version


def setUpModule() -> None:
    """为当前测试模块准备依赖替身。"""
    _install_email_validator_stub()


def tearDownModule() -> None:
    """恢复全局状态。"""
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


class CodingPracticeRepositoryTestCase(unittest.TestCase):
    """验证编程练习仓储基础能力。"""

    def setUp(self) -> None:
        """初始化临时仓储。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "coding-practice.db"
        self.repository = InterviewRepository(str(self.db_path))
        self.repository.init_schema()

    def tearDown(self) -> None:
        """释放临时目录。"""
        self.tmpdir.cleanup()

    def test_upsert_and_list_coding_questions(self) -> None:
        """编程题应支持幂等写入和列表查询。"""
        self.repository.upsert_coding_question(
            {
                "question_id": "coding-1",
                "slug": "a-plus-b",
                "title": "A+B",
                "difficulty": "easy",
                "topic_tags": ["模拟"],
                "prompt_markdown": "给定两个整数，输出和。",
                "input_spec": "一行两个整数",
                "output_spec": "输出一个整数",
                "constraints_text": "范围在 32 位内",
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
        )

        rows = self.repository.list_coding_questions()

        self.assertEqual(1, len(rows))
        self.assertEqual("coding-1", rows[0]["question_id"])
        self.assertEqual("A+B", rows[0]["title"])

    def test_coding_session_creates_without_draft_records(self) -> None:
        """创建会话后不应默认生成代码草稿记录。"""
        self.repository.upsert_coding_question(
            {
                "question_id": "coding-2",
                "slug": "sum-array",
                "title": "数组求和",
                "difficulty": "easy",
                "topic_tags": ["数组"],
                "prompt_markdown": "输出数组元素和。",
                "input_spec": "第一行 n，第二行 n 个整数",
                "output_spec": "输出总和",
                "constraints_text": "n <= 1000",
                "sample_cases": [{"input": "3\n1 2 3\n", "output": "6\n"}],
                "judge_cases": [{"input": "1\n5\n", "output": "5\n"}] * 10,
                "self_test_case": {"input": "2\n4 5\n", "output": "9\n"},
                "starter_codes": {
                    "cpp": "#include <iostream>\nint main(){return 0;}\n",
                    "java": "public class Main { public static void main(String[] args) {} }\n",
                    "javascript": "process.stdin.on('data', () => {})\n",
                },
                "source": {"origin": "unit-test"},
            }
        )
        session = self.repository.create_or_get_coding_session(user_id="user-a", question_id="coding-2")

        draft = self.repository.get_coding_draft(user_id="user-a", session_id=session["session_id"], language="javascript")
        self.assertIsNone(draft)


class CodingPracticeFlowTestCase(unittest.TestCase):
    """验证编程练习 API 主路径。"""

    def setUp(self) -> None:
        """初始化 API 测试环境。"""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "coding-api.db"
        self._set_env("AI_INTERVIEW_DB_PATH", str(self.db_path))
        self._set_env("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN", "true")
        get_settings.cache_clear()
        self.client = TestClient(create_app())
        self.client.__enter__()
        self.user_headers = {"Authorization": "Bearer user-token"}
        self.admin_headers = {"Authorization": "Bearer admin-token"}
        self._seed_coding_question()
        self.execution_calls: list[dict] = []
        self.client.app.state.coding_practice_service.execution_service.execute_cases = self._fake_execute_cases

    def tearDown(self) -> None:
        """清理测试环境。"""
        self.client.__exit__(None, None, None)
        self.tmpdir.cleanup()
        self._clear_env("AI_INTERVIEW_DB_PATH")
        self._clear_env("AI_INTERVIEW_AUTH_ENABLE_DEV_STATIC_TOKEN")
        get_settings.cache_clear()

    def _set_env(self, key: str, value: str) -> None:
        """设置环境变量。"""
        import os

        os.environ[key] = value

    def _clear_env(self, key: str) -> None:
        """清理环境变量。"""
        import os

        os.environ.pop(key, None)

    def _seed_coding_question(self) -> None:
        """写入最小编程题数据。"""
        repo = self.client.app.state.repo
        repo.upsert_coding_question(
            {
                "question_id": "coding-a-plus-b",
                "slug": "a-plus-b",
                "title": "A+B",
                "difficulty": "easy",
                "topic_tags": ["模拟", "输入输出"],
                "prompt_markdown": "给定两个整数，输出它们的和。",
                "input_spec": "输入一行，包含两个整数 a 和 b。",
                "output_spec": "输出一个整数，表示 a+b。",
                "constraints_text": "a、b 在 32 位有符号整数范围内。",
                "sample_cases": [{"input": "1 2\n", "output": "3\n"}],
                "judge_cases": [
                    {"input": "1 2\n", "output": "3\n"},
                    {"input": "3 4\n", "output": "7\n"},
                    {"input": "0 0\n", "output": "0\n"},
                    {"input": "-1 3\n", "output": "2\n"},
                    {"input": "100 200\n", "output": "300\n"},
                    {"input": "-5 -6\n", "output": "-11\n"},
                    {"input": "7 8\n", "output": "15\n"},
                    {"input": "11 22\n", "output": "33\n"},
                    {"input": "9 -2\n", "output": "7\n"},
                    {"input": "123 456\n", "output": "579\n"},
                ],
                "self_test_case": {"input": "8 9\n", "output": "17\n"},
                "starter_codes": {
                    "cpp": "#include <iostream>\nusing namespace std;\nint main(){return 0;}\n",
                    "java": "public class Main { public static void main(String[] args) throws Exception {} }\n",
                    "javascript": "process.stdin.resume();\n",
                },
                "source": {"origin": "unit-test"},
            }
        )

    def _fake_execute_cases(self, language: str, source_code: str, cases: list[dict], submit_type: str) -> dict:
        """替代真实编译器执行，保证 API 流程测试不依赖本地工具链。"""
        self.execution_calls.append(
            {
                "language": language,
                "source_code": source_code,
                "case_count": len(cases),
                "submit_type": submit_type,
            }
        )
        return {
            "status": "ACCEPTED",
            "passed_count": len(cases),
            "total_count": len(cases),
            "submit_type": submit_type,
            "message": "全部通过",
            "results": [],
        }

    def test_list_questions_and_create_session(self) -> None:
        """应能获取题目列表并创建练习会话。"""
        listed = self.client.get("/api/v1/coding-practice/questions", headers=self.user_headers)
        self.assertEqual(200, listed.status_code, msg=listed.text)
        self.assertGreaterEqual(listed.json()["total"], 1)
        self.assertIn("coding-a-plus-b", [item["question_id"] for item in listed.json()["items"]])

        created = self.client.post(
            "/api/v1/coding-practice/sessions",
            json={"question_id": "coding-a-plus-b"},
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        payload = created.json()
        self.assertEqual("coding-a-plus-b", payload["question"]["question_id"])
        self.assertEqual("cpp", payload["active_language"])
        self.assertNotIn("starter_codes", payload["question"])
        self.assertNotIn("active_draft", payload)
        self.assertNotIn("drafts", payload)

    def test_run_and_submit_flow_without_persisting_source_code(self) -> None:
        """应支持直接运行和提交，但不通过会话接口回传代码。"""
        created = self.client.post(
            "/api/v1/coding-practice/sessions",
            json={"question_id": "coding-a-plus-b"},
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        session_id = created.json()["session_id"]

        run_resp = self.client.post(
            f"/api/v1/coding-practice/sessions/{session_id}/run",
            json={
                "language": "javascript",
                "source_code": "const fs = require('fs'); const [a,b]=fs.readFileSync(0,'utf8').trim().split(/\\s+/).map(Number); console.log(a+b);",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, run_resp.status_code, msg=run_resp.text)
        self.assertEqual("ACCEPTED", run_resp.json()["result"]["status"])
        self.assertEqual(1, run_resp.json()["result"]["total_count"])

        submit_resp = self.client.post(
            f"/api/v1/coding-practice/sessions/{session_id}/submit",
            json={
                "language": "javascript",
                "source_code": "const fs = require('fs'); const [a,b]=fs.readFileSync(0,'utf8').trim().split(/\\s+/).map(Number); console.log(a+b);",
            },
            headers=self.user_headers,
        )
        self.assertEqual(200, submit_resp.status_code, msg=submit_resp.text)
        self.assertEqual("ACCEPTED", submit_resp.json()["result"]["status"])
        self.assertEqual(10, submit_resp.json()["result"]["passed_count"])
        self.assertEqual(10, submit_resp.json()["result"]["total_count"])

        detail = self.client.get(
            f"/api/v1/coding-practice/sessions/{session_id}",
            headers=self.user_headers,
        )
        self.assertEqual(200, detail.status_code, msg=detail.text)
        self.assertNotIn("starter_codes", detail.json()["question"])
        self.assertNotIn("active_draft", detail.json())
        self.assertNotIn("drafts", detail.json())

        records = self.client.get("/api/v1/coding-practice/records", headers=self.user_headers)
        self.assertEqual(200, records.status_code, msg=records.text)
        self.assertEqual(1, records.json()["total"])

    def test_run_supports_cpp_java_and_javascript(self) -> None:
        """三种目标语言都应支持真实运行自测。"""
        created = self.client.post(
            "/api/v1/coding-practice/sessions",
            json={"question_id": "coding-a-plus-b"},
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        session_id = created.json()["session_id"]

        cases = {
            "cpp": "#include <iostream>\nusing namespace std;\nint main(){ long long a,b; cin>>a>>b; cout << a + b << \"\\n\"; return 0; }\n",
            "java": "import java.util.*;\npublic class Main { public static void main(String[] args) { Scanner scanner = new Scanner(System.in); long a = scanner.nextLong(); long b = scanner.nextLong(); System.out.println(a + b); } }\n",
            "javascript": "const fs = require('fs'); const [a, b] = fs.readFileSync(0, 'utf8').trim().split(/\\s+/).map(Number); console.log(a + b);\n",
        }

        for language, source_code in cases.items():
            run_resp = self.client.post(
                f"/api/v1/coding-practice/sessions/{session_id}/run",
                json={"language": language, "source_code": source_code},
                headers=self.user_headers,
            )
            self.assertEqual(200, run_resp.status_code, msg=f"{language}: {run_resp.text}")
            self.assertEqual("ACCEPTED", run_resp.json()["result"]["status"], msg=f"{language}: {run_resp.text}")
            self.assertEqual(1, run_resp.json()["result"]["passed_count"], msg=f"{language}: {run_resp.text}")
        self.assertEqual(["cpp", "java", "javascript"], [call["language"] for call in self.execution_calls])

    def test_scope_protection(self) -> None:
        """不同用户不能读取他人的编程练习会话。"""
        created = self.client.post(
            "/api/v1/coding-practice/sessions",
            json={"question_id": "coding-a-plus-b"},
            headers=self.user_headers,
        )
        self.assertEqual(200, created.status_code, msg=created.text)
        session_id = created.json()["session_id"]

        forbidden = self.client.get(
            f"/api/v1/coding-practice/sessions/{session_id}",
            headers=self.admin_headers,
        )
        self.assertEqual(403, forbidden.status_code, msg=forbidden.text)


if __name__ == "__main__":
    unittest.main()
