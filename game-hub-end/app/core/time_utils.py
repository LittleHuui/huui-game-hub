"""时间工具：业务时间一律使用 Unix 毫秒时间戳。"""

import time


def now_ms() -> int:
    """返回当前 Unix 毫秒时间戳。"""
    return int(time.time() * 1000)
