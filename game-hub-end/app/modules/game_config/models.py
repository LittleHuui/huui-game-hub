"""游戏域 ORM 模型。"""

from typing import Optional

from sqlalchemy import Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class GameDefinition(Base, TimestampMixin):
    """游戏注册表：平台有哪些游戏。"""

    __tablename__ = "game_definition"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    game_code: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    game_name: Mapped[str] = mapped_column(Text, nullable=False)
    game_sub_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    support_online: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class GameDifficulty(Base, TimestampMixin):
    """游戏难度配置：每局的规格（格子数、雷数、奖励等）。"""

    __tablename__ = "game_difficulty"
    __table_args__ = (UniqueConstraint("game_code", "difficulty_code", name="uq_game_difficulty_game_diff"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    difficulty_code: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty_name: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    sort_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class GameClientConfig(Base, TimestampMixin):
    """游戏客户端配置：PC / 手机横屏 / 手机竖屏等布局适配。"""

    __tablename__ = "game_client_config"
    __table_args__ = (
        UniqueConstraint(
            "game_code",
            "difficulty_code",
            "client_type",
            name="uq_game_client_config_game_diff_type",
        ),
    )

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    difficulty_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_type: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
