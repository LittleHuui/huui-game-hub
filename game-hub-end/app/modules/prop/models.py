"""道具域 ORM 模型。"""

from typing import Optional

from sqlalchemy import Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class PropDefinition(Base, TimestampMixin):
    """道具定义：平台内道具统一定义与基础价格。"""

    __tablename__ = "prop_definition"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    prop_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    prop_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_price: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class GamePropRule(Base, TimestampMixin):
    """游戏道具规则：某游戏中道具价格与使用规则。"""

    __tablename__ = "game_prop_rule"
    __table_args__ = (UniqueConstraint("game_code", "prop_code", name="uq_game_prop_rule_game_prop"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    prop_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    max_use_per_match: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    trigger_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effect_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
