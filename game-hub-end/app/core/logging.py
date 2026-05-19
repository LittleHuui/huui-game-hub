"""统一日志初始化。"""

import logging
import sys
from typing import Any, Dict

from app.core.config import settings


def setup_logging() -> None:
    """根据配置初始化根日志器与控制台处理器。"""
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取命名日志器。

    :param name: 通常为 ``__name__``。
    :return: 配置好的 ``Logger`` 实例。
    """
    return logging.getLogger(name)


def log_extra(**kwargs: Any) -> Dict[str, Any]:
    """
    构造结构化日志额外字段（便于后续接入 JSON 日志）。

    :param kwargs: 任意键值对。
    :return: 适合 ``logger.info(..., extra=...)`` 的字典。
    """
    return {"extra_fields": kwargs}
