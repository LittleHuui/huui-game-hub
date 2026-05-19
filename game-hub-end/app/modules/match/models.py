"""对局域 ORM 模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Index, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class MatchRecord(Base, TimestampMixin):
    """对局历史记录。"""

    __tablename__ = "match_record"
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_match_record_user_client"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    prop_uses_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class MatchActionRecord(Base, TimestampMixin):
    """对局操作记录（用于回放）。"""

    __tablename__ = "match_action_record"
    __table_args__ = (
        UniqueConstraint("user_id", "client_id", name="uq_match_action_record_user_client"),
        Index("ix_match_action_record_match_seq", "match_id", "action_seq"),
    )

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    match_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    action_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    action_time_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
