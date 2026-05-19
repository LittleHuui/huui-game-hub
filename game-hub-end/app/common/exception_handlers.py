"""FastAPI 全局异常处理器注册。"""

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.error_code import ErrorCode, ErrorCodeItem
from app.common.exceptions import BizException
from app.common.response import ApiResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


def _json_body(body):
    """
    将统一响应体序列化为 JSONResponse。

    :param body: ``ApiResponse`` 实例。
    :return: HTTP 200 的 JSON 响应（业务码在 body 内表达）。
    """
    payload = body.model_dump(exclude_none=True)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


def _fail_from_item(item, message=None, detail=None):
    """
    由 ``ErrorCodeItem`` 构造失败响应体。

    :param item: 错误码项。
    :param message: 覆盖默认文案，可空。
    :param detail: 可选详情。
    :return: ``ApiResponse`` 失败实例。
    """
    return ApiResponse.fail(
        item.code,
        message if message is not None else item.message,
        detail=detail,
    )


def _sanitize_validation_hint(exc):
    """
    从校验异常中提取简短字段提示，避免原样暴露完整 errors 结构。

    :param exc: ``RequestValidationError``。
    :return: 简短提示或 ``None``。
    """
    if not exc.errors():
        return None
    first = exc.errors()[0]
    loc_parts = [str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path")]
    field = ".".join(loc_parts) if loc_parts else ""
    msg = str(first.get("msg", ""))
    if field and msg:
        return "{0}: {1}".format(field, msg)
    if field:
        return field
    if msg:
        return msg
    return None


def register_exception_handlers(app):
    """
    将统一异常处理注册到 FastAPI 应用。

    :param app: FastAPI 应用实例。
    :return: ``None``。
    """

    @app.exception_handler(BizException)
    async def _biz_exc(_request, exc):
        logger.warning(
            "业务异常: code=%s message=%s detail=%s",
            exc.code,
            exc.message,
            exc.detail,
        )
        body = ApiResponse.fail(exc.code, exc.message, detail=exc.detail)
        return _json_body(body)

    @app.exception_handler(RequestValidationError)
    async def _req_validation(_request, exc):
        logger.warning("请求体验证失败: %s", exc.errors())
        hint = _sanitize_validation_hint(exc)
        message = ErrorCode.PARAM_ERROR.message
        if hint:
            message = "{0} ({1})".format(message, hint)
        body = _fail_from_item(ErrorCode.PARAM_ERROR, message=message)
        return _json_body(body)

    @app.exception_handler(ValidationError)
    async def _pydantic_validation(_request, _exc):
        logger.warning("Pydantic 校验失败: %s", _exc.errors())
        body = _fail_from_item(ErrorCode.PARAM_ERROR)
        return _json_body(body)

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(_request, exc):
        logger.warning("HTTP 异常: status=%s detail=%s", exc.status_code, exc.detail)
        detail_text = str(exc.detail) if exc.detail else None
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            body = _fail_from_item(ErrorCode.COMMON_ERROR, message=detail_text or ErrorCode.COMMON_ERROR.message)
        else:
            body = _fail_from_item(ErrorCode.COMMON_ERROR, message=detail_text or ErrorCode.COMMON_ERROR.message)
        return _json_body(body)

    @app.exception_handler(Exception)
    async def _unhandled(_request, exc):
        logger.exception("未处理异常", exc_info=exc)
        body = _fail_from_item(ErrorCode.SYSTEM_ERROR)
        return _json_body(body)
