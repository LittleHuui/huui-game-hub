"""平台积分结算 ORM 模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class GameSettlementRecord(Base, TimestampMixin):
    """一局游戏平台积分结算主记录。"""

    __tablename__ = "game_settlement_record"
    __table_args__ = (UniqueConstraint("settlement_id", name="uq_game_settlement_record_settlement_id"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    settlement_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False)
    match_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    system_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class GameSettlementPlayerRecord(Base, TimestampMixin):
    """平台积分结算玩家明细。"""

    __tablename__ = "game_settlement_player_record"
    __table_args__ = (
        UniqueConstraint(
            "settlement_id",
            "player_id",
            name="uq_game_settlement_player_record_settlement_player",
        ),
    )

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    settlement_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    player_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    expected_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    insufficient_amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
