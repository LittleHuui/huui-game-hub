"""购买域 ORM 模型。"""

from typing import Optional

from sqlalchemy import BigInteger, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class PropPurchaseRecord(Base, TimestampMixin):
    """道具购买记录。"""

    __tablename__ = "prop_purchase_record"
    __table_args__ = (UniqueConstraint("user_id", "client_id", name="uq_prop_purchase_user_client"),)

    server_id: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    device_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    game_code: Mapped[str] = mapped_column(Text, nullable=False)
    prop_code: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[int] = mapped_column(Integer, nullable=False)
    synced_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
