"""兼容层：异常定义与处理器已迁移至 ``app.common``。"""

from app.common.exception_handlers import register_exception_handlers
from app.common.exceptions import (
    BizException,
    NotFoundException,
    RemoteSyncException,
    ValidationException,
)

__all__ = [
    "BizException",
    "NotFoundException",
    "RemoteSyncException",
    "ValidationException",
    "register_exception_handlers",
]
