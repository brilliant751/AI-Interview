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

