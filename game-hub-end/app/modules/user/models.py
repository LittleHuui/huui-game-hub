"""用户域 ORM 模型。"""

from typing import List, Optional

from sqlalchemy import BigInteger, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class UserAccount(Base, TimestampMixin):
    """平台用户账号。"""

    __tablename__ = "user_account"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(Text, nullable=False)
    avatar: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="normal")

    devices: Mapped[List["UserDevice"]] = relationship(back_populates="user", lazy="selectin")
    game_settings: Mapped[List["UserGameSetting"]] = relationship(back_populates="user", lazy="selectin")
    system_setting: Mapped[Optional["UserSystemSetting"]] = relationship(
        back_populates="user",
        lazy="selectin",
        uselist=False,
    )


class UserDevice(Base, TimestampMixin):
    """用户设备绑定。"""

    __tablename__ = "user_device"
    __table_args__ = (UniqueConstraint("user_id", "device_id", name="uq_user_device_user_id_device_id"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("user_account.server_id"), nullable=False, index=True)
    device_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    device_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_login_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    user: Mapped[UserAccount] = relationship(back_populates="devices")


class UserGameSetting(Base, TimestampMixin):
    """用户在某款游戏中的个性化设置。"""

    __tablename__ = "user_game_setting"
    __table_args__ = (UniqueConstraint("user_id", "game_code", name="uq_user_game_setting_user_game"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("user_account.server_id"), nullable=False, index=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    setting_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[UserAccount] = relationship(back_populates="game_settings")


class UserSystemSetting(Base, TimestampMixin):
    """平台级用户系统偏好设置（非游戏维度）。"""

    __tablename__ = "user_system_setting"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_system_setting_user_id"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("user_account.server_id"), nullable=False, index=True)
    setting_json: Mapped[str] = mapped_column(Text, nullable=False)

    user: Mapped[UserAccount] = relationship(back_populates="system_setting")
