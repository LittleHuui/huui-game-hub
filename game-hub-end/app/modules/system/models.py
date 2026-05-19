"""系统域 ORM 模型。"""

from typing import Optional

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class SystemConfig(Base, TimestampMixin):
    """平台级系统配置（不含具体游戏规则）。"""

    __tablename__ = "system_config"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    config_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    config_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class RequestLog(Base, TimestampMixin):
    """HTTP 请求审计日志。"""

    __tablename__ = "request_log"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    request_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    query_string: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class LoginLog(Base, TimestampMixin):
    """用户登录审计日志。"""

    __tablename__ = "login_log"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    login_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    login_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
