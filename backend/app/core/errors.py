"""应用统一错误定义与转换。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse


@dataclass
class ApiError(Exception):
    """业务错误对象。"""

    code: str
    message: str
    status_code: int


KB_BUILD_ERROR_STATUS: dict[str, int] = {
    "KB_BUILD_400": 400,
    "KB_BUILD_409": 409,
    "KB_BUILD_424": 424,
    "KB_BUILD_500": 500,
    "KB_BUILD_502": 502,
}


def kb_build_error(code: str, message: str) -> ApiError:
    """构建并返回知识库任务错误。"""
    status_code = KB_BUILD_ERROR_STATUS.get(code)
    if status_code is None:
        return ApiError(code="KB_BUILD_500", message=message, status_code=500)
    return ApiError(code=code, message=message, status_code=status_code)


def error_response(error: ApiError) -> JSONResponse:
    """将业务错误转换为统一 JSON 响应。"""
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
            }
        },
    )


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    """FastAPI 全局业务异常处理器。"""
    return error_response(exc)
