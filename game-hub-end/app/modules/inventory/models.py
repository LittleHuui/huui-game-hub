"""背包域 ORM 模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class UserPropBag(Base, TimestampMixin):
    """用户道具背包：按游戏维度的道具数量聚合。"""

    __tablename__ = "user_prop_bag"
    __table_args__ = (
        UniqueConstraint("user_id", "game_code", "prop_code", name="uq_user_prop_bag_user_game_prop"),
    )

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    prop_code: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class PropUsageRecord(Base, TimestampMixin):
    """道具使用记录。"""

    __tablename__ = "prop_usage_record"
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_prop_usage_user_client"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False)
    match_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prop_code: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    use_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
