"""配置加载与基础接口测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_settings_defaults_use_mock_providers() -> None:
    """默认测试环境应使用 mock provider，避免触发外部服务。"""
    settings = get_settings()

    assert settings.llm_provider == "mock"
    assert settings.asr_provider == "mock"
    assert settings.tts_provider == "mock"
    assert settings.db_path.endswith("test.db")


def test_openapi_and_docs_are_available() -> None:
    """FastAPI OpenAPI 与 Swagger 文档应可被 CI smoke test 访问。"""
    with TestClient(create_app()) as client:
        openapi_resp = client.get("/openapi.json")
        docs_resp = client.get("/docs")

    assert openapi_resp.status_code == 200
    assert openapi_resp.json()["info"]["title"] == "AI Interview API"
    assert docs_resp.status_code == 200


def test_provider_health_allows_mock_without_auth() -> None:
    """Provider 健康检查应不依赖本地模型服务，也不要求认证头。"""
    with TestClient(create_app()) as client:
        resp = client.get("/api/v1/admin/providers/health")

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["overall"] == "UP"
    assert payload["providers"]["llm"]["provider"] == "mock"
    assert payload["providers"]["asr"]["provider"] == "mock"
