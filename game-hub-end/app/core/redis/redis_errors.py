"""Redis 基础设施异常。"""


class RedisOperationError(Exception):
    """Redis 读写操作失败（非 key 不存在）。"""

    def __init__(self, message: str = "redis operation failed") -> None:
        """
        初始化 Redis 操作异常。

        :param message: 错误描述。
        """
        super().__init__(message)
