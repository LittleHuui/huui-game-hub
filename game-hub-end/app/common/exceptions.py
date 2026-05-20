"""平台统一业务异常。"""

from app.common.error_code import ErrorCode, ErrorCodeItem


def _resolve_code_message(
    error=None,
    code=None,
    message=None,
):
    """
    解析 BizException 构造参数中的 code 与 message。

    :param error: ``ErrorCodeItem``（位置参数）。
    :param code: 显式错误码。
    :param message: 显式错误信息。
    :return: ``(code, message)`` 元组。
    :raises TypeError: 参数组合不合法时抛出。
    """
    if isinstance(error, ErrorCodeItem):
        resolved_code = error.code
        resolved_message = message if message is not None else error.message
        return resolved_code, resolved_message
    if code is not None:
        resolved_message = message if message is not None else ""
        return int(code), str(resolved_message)
    raise TypeError("BizException 需要 ErrorCodeItem，或提供 code=（可选 message=）")


class BizException(Exception):
    """
    通用业务异常，携带业务错误码、可读信息与可选详情。

    用法示例::

        raise BizException(ErrorCode.USER_NOT_FOUND)
        raise BizException(code=20001, message="用户不存在")
        raise BizException(ErrorCode.PARAM_ERROR, message="gameCode 不能为空", detail={"field": "gameCode"})
    """

    def __init__(
        self,
        error=None,
        code=None,
        message=None,
        detail=None,
    ):
        resolved_code, resolved_message = _resolve_code_message(error, code, message)
        self.code = resolved_code
        self.message = resolved_message
        self.detail = detail
        super().__init__(resolved_message)


class NotFoundException(BizException):
    """资源不存在。"""

    def __init__(
        self,
        message=None,
        error=None,
        detail=None,
    ):
        """
        :param message: 错误说明，省略时使用 ``error`` 或通用默认文案。
        :param error: 可选 ``ErrorCodeItem``，默认 ``ErrorCode.COMMON_ERROR``。
        :param detail: 可选附加详情。
        """
        item = error if isinstance(error, ErrorCodeItem) else ErrorCode.COMMON_ERROR
        resolved_message = message if message is not None else item.message
        super().__init__(error=item, message=resolved_message, detail=detail)


class ValidationException(BizException):
    """业务层校验失败（区别于请求体 JSON Schema 校验）。"""

    def __init__(
        self,
        message=None,
        error=None,
        detail=None,
    ):
        """
        :param message: 错误说明，省略时使用参数错误默认文案。
        :param error: 可选 ``ErrorCodeItem``，默认 ``ErrorCode.PARAM_ERROR``。
        :param detail: 可选附加详情。
        """
        item = error if isinstance(error, ErrorCodeItem) else ErrorCode.PARAM_ERROR
        resolved_message = message if message is not None else item.message
        super().__init__(error=item, message=resolved_message, detail=detail)


class RemoteSyncException(BizException):
    """与客户端或服务端同步相关的异常。"""

    def __init__(
        self,
        message=None,
        detail=None,
    ):
        """
        :param message: 错误说明，省略时使用同步数据无效默认文案。
        :param detail: 可选附加详情。
        """
        resolved_message = message if message is not None else ErrorCode.SYNC_DATA_INVALID.message
        super().__init__(error=ErrorCode.SYNC_DATA_INVALID, message=resolved_message, detail=detail)
