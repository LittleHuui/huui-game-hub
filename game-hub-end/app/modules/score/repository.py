"""成绩域数据访问。"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.models import ScoreRecord
from app.modules.user.models import UserAccount


class ScoreRecordRepository:
    """``score_record`` 表 CRUD。"""

    def __init__(
        self,
        session: Session,
    ) -> None:
        """注入成绩记录查询使用的事务会话。"""
        self._session = session

    def get_by_user_and_client_id(
        self,
        user_id: str,
        client_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[ScoreRecord]:
        """
        按幂等键查询成绩记录。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :param active_only: 是否只查未软删行。
        :return: 成绩实体或 ``None``。
        """
        stmt = select(ScoreRecord).where(
            ScoreRecord.user_id == user_id,
            ScoreRecord.client_id == client_id,
        )
        if active_only:
            stmt = stmt.where(ScoreRecord.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_any_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[ScoreRecord]:
        """
        按幂等键查询成绩记录（含软删）。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 成绩实体或 ``None``。
        """
        stmt = select(ScoreRecord).where(
            ScoreRecord.user_id == user_id,
            ScoreRecord.client_id == client_id,
        )
        return self._session.scalar(stmt)

    def list_by_user(self, user_id: str, limit: int = 200, *, active_only: bool = True) -> List[ScoreRecord]:
        """
        按创建时间倒序列出用户成绩记录。

        :param user_id: 用户主键。
        :param limit: 返回条数上限。
        :param active_only: 是否只查未软删行。
        :return: 成绩列表。
        """
        stmt = select(ScoreRecord).where(ScoreRecord.user_id == user_id)
        if active_only:
            stmt = stmt.where(ScoreRecord.deleted_at.is_(None))
        stmt = stmt.order_by(
            ScoreRecord.updated_at.desc(),
            ScoreRecord.created_at.desc(),
        ).limit(limit)
        return list(self._session.scalars(stmt).all())

    def add(self, entity: ScoreRecord) -> ScoreRecord:
        """
        插入成绩记录。

        :param entity: ORM 实体。
        :return: 持久化后的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: ScoreRecord) -> ScoreRecord:
        """
        持久化成绩记录变更。

        :param entity: ORM 实体。
        :return: 持久化后的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def soft_delete(self, entity: ScoreRecord) -> ScoreRecord:
        """
        软删除成绩记录。

        :param entity: ORM 实体。
        :return: 持久化后的实体。
        """
        entity.deleted_at = now_ms()
        return self.save(entity)

    def query_leaderboard_rows(
        self,
        game_code: str,
        mode: str,
        difficulty_code: Optional[str],
        result: str,
        order_by: List[Any],
        limit: int,
        include_payload: bool,
    ) -> List[LeaderboardRow]:
        """按已确定的过滤条件、排序表达式和上限读取原始排行候选。"""
        columns = [ScoreRecord.user_id, UserAccount.nickname, ScoreRecord.score,
                   ScoreRecord.duration_ms, ScoreRecord.created_at]
        if include_payload:
            columns.append(ScoreRecord.payload_json)
        conditions = [ScoreRecord.game_code == game_code, ScoreRecord.mode == mode,
                      ScoreRecord.result == result, ScoreRecord.deleted_at.is_(None),
                      UserAccount.deleted_at.is_(None)]
        if difficulty_code is not None:
            conditions.append(ScoreRecord.difficulty_code == difficulty_code)
        stmt = (select(*columns)
                .join(UserAccount, ScoreRecord.user_id == UserAccount.server_id)
                .where(*conditions).order_by(*order_by).limit(limit))
        return [LeaderboardRow(user_id=row[0], nickname=row[1], score=row[2],
                               duration_ms=row[3], created_at=row[4],
                               payload_json=row[5] if include_payload else None)
                for row in self._session.execute(stmt).all()]
