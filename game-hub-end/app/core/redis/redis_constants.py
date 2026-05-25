"""Redis 工具层常量。"""

from enum import Enum


class TimeUnit(str, Enum):
    """Redis 过期时间单位。"""

    SECONDS = "seconds"
    MINUTES = "minutes"
    HOURS = "hours"
