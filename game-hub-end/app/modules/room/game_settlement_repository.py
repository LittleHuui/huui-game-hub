"""平台积分结算数据访问。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.room.game_settlement_models import GameSettlementPlayerRecord, GameSettlementRecord


class GameSettlementRepository(object):
    """``game_settlement_record`` 与玩家明细表 CRUD。"""

    def __init__(self, session: Session) -> None:
        """
        初始化结算仓库。

        :param session: SQLAlchemy 会话。
        """
        self._session = session

    def get_by_settlement_id(self, settlement_id: str) -> Optional[GameSettlementRecord]:
        """
        按结算幂等 ID 查询主记录。

        :param settlement_id: 结算 ID。
        :return: 主记录或 ``None``。
        """
        normalized_id = str(settlement_id or "").strip()
        if not normalized_id:
            return None
        stmt = select(GameSettlementRecord).where(
            GameSettlementRecord.settlement_id == normalized_id,
        )
        return self._session.scalar(stmt)

    def list_player_records(self, settlement_id: str) -> List[GameSettlementPlayerRecord]:
        """
        列出某次结算的全部玩家明细。

        :param settlement_id: 结算 ID。
        :return: 玩家明细列表。
        """
        normalized_id = str(settlement_id or "").strip()
        if not normalized_id:
            return []
        stmt = select(GameSettlementPlayerRecord).where(
            GameSettlementPlayerRecord.settlement_id == normalized_id,
        )
        return list(self._session.scalars(stmt).all())

    def add_record(self, record: GameSettlementRecord) -> GameSettlementRecord:
        """
        持久化结算主记录。

        :param record: 主记录实体。
        :return: 已附加的实体。
        """
        self._session.add(record)
        return record

    def add_player_record(self, record: GameSettlementPlayerRecord) -> GameSettlementPlayerRecord:
        """
        持久化结算玩家明细。

        :param record: 玩家明细实体。
        :return: 已附加的实体。
        """
        self._session.add(record)
        return record
