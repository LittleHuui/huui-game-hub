"""钱包域 ORM 模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class UserWallet(Base, TimestampMixin):
    """用户钱包余额快照（流水重放可校正）。"""

    __tablename__ = "user_wallet"

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class WalletLedger(Base, TimestampMixin):
    """积分流水（权威来源）。"""

    __tablename__ = "wallet_ledger"
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_wallet_ledger_user_client"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    game_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    synced_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
