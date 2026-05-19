"""统一 API 返回结构。"""

import time
from typing import Any, Generic, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, Field

from app.common.error_code import ErrorCodeItem

T = TypeVar("T")


def current_timestamp_ms():
    """
    返回当前 Unix 毫秒时间戳。

    :return: 整型毫秒时间戳。
    """
    return int(time.time() * 1000)


class ApiResponse(BaseModel, Generic[T]):
    """
    所有 HTTP JSON 响应的统一外壳（Pydantic v2 泛型模型）。

    接口声明示例：``response_model=ApiResponse[UserResponse]``。
    """

    model_config = ConfigDict(from_attributes=True)

    def model_dump(self, *args, **kwargs):
        """
        序列化时默认排除 ``None`` 字段（如成功响应中的 ``detail``）。

        :return: 可 JSON 化的字典。
        """
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)

    code: int = Field(description="0 表示成功，非 0 为业务错误码")
    message: str = Field(description="人类可读信息")
    data: Optional[T] = Field(default=None, description="成功时为业务数据，失败时为 null")
    success: bool = Field(description="是否成功")
    timestamp: int = Field(description="响应生成时的 Unix 毫秒时间戳")
    detail: Optional[Any] = Field(default=None, description="失败时的可选附加详情")

    @classmethod
    def current_timestamp_ms(cls):
        """
        返回当前 Unix 毫秒时间戳。

        :return: 整型毫秒时间戳。
        """
        return current_timestamp_ms()

    @classmethod
    def ok(cls, data=None):
        """
        构造成功响应体（类方法名避免与字段 ``success`` 冲突）。

        :param data: 业务数据载荷，可为空。
        :return: ``code=0``、``success=True`` 的响应对象。
        """
        return cls(
            code=0,
            message="success",
            data=data,
            success=True,
            timestamp=current_timestamp_ms(),
        )

    @classmethod
    def fail(cls, code, message, detail=None):
        """
        构造失败响应体。

        :param code: 业务错误码或 ``ErrorCodeItem``。
        :param message: 错误说明；当 ``code`` 为 ``ErrorCodeItem`` 时可省略。
        :param detail: 可选附加详情。
        :return: ``success=False``、``data=null`` 的响应对象。
        """
        resolved_code = code
        resolved_message = message
        if isinstance(code, ErrorCodeItem):
            resolved_code = code.code
            if message is None:
                resolved_message = code.message
        return cls(
            code=int(resolved_code),
            message=str(resolved_message),
            data=None,
            success=False,
            timestamp=current_timestamp_ms(),
            detail=detail,
        )


def success(data=None):
    """
    构造统一成功响应（推荐在接口层使用此函数）。

    :param data: 业务数据载荷。
    :return: ``ApiResponse`` 成功实例。
    """
    return ApiResponse.ok(data)
