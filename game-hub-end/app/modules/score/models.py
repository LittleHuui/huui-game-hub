"""成绩域 ORM 模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class ScoreRecord(Base, TimestampMixin):
    """可参与排行榜的有效成绩记录。"""

    __tablename__ = "score_record"
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_score_record_user_client"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
