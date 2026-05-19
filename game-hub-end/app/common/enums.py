"""全局枚举（兼容导入，错误码请使用 ``app.common.error_code``）。"""

from app.common.error_code import ErrorCode, ErrorCodeItem

__all__ = ["ErrorCode", "ErrorCodeItem"]
