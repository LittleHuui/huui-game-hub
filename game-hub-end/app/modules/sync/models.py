"""同步域 ORM 模型。"""

from typing import Optional

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class SyncLog(Base, TimestampMixin):
    """客户端云存档同步审计日志。"""

    __tablename__ = "sync_log"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sync_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sync_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pending_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fail_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
