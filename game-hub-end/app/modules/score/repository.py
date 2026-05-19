"""成绩域数据访问。"""

from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.models import ScoreRecord
from app.modules.score.ranking_rules import (
    MATCH3_LEADERBOARD_CANDIDATE_LIMIT,
    SCORE_RESULT_WIN,
    is_match3_leaderboard,
    resolve_order_by,
    sort_match3_leaderboard_rows,
)
from app.modules.user.models import UserAccount


class ScoreRecordRepository:
    """``score_record`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
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
        stmt = stmt.order_by(ScoreRecord.created_at.desc()).limit(limit)
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

    def list_leaderboard(
        self,
        game_code: str,
        mode: str,
        difficulty_code: Optional[str],
        limit: int,
    ) -> List[LeaderboardRow]:
        """
        查询排行榜候选行（关联用户昵称）。

        :param game_code: 游戏编码。
        :param mode: 玩法模式。
        :param difficulty_code: 难度编码，为 None 时不按难度过滤。
        :param limit: 返回条数上限。
        :return: 排行榜原始行列表。
        """
        conditions = [
            ScoreRecord.game_code == game_code,
            ScoreRecord.mode == mode,
            ScoreRecord.result == SCORE_RESULT_WIN,
            ScoreRecord.deleted_at.is_(None),
            UserAccount.deleted_at.is_(None),
        ]
        if difficulty_code is not None:
            conditions.append(ScoreRecord.difficulty_code == difficulty_code)
        if is_match3_leaderboard(game_code, mode):
            return self._list_match3_leaderboard(conditions, mode, limit)
        stmt = (
            select(
                ScoreRecord.user_id,
                UserAccount.nickname,
                ScoreRecord.score,
                ScoreRecord.duration_ms,
                ScoreRecord.created_at,
            )
            .join(UserAccount, ScoreRecord.user_id == UserAccount.server_id)
            .where(*conditions)
            .order_by(*resolve_order_by(game_code))
            .limit(limit)
        )
        rows = self._session.execute(stmt).all()
        return [
            LeaderboardRow(
                user_id=row[0],
                nickname=row[1],
                score=row[2],
                duration_ms=row[3],
                created_at=row[4],
            )
            for row in rows
        ]

    def _list_match3_leaderboard(
        self,
        conditions: List[Any],
        mode: str,
        limit: int,
    ) -> List[LeaderboardRow]:
        """
        查询 Color Crush 排行榜候选行并在 Python 层按 payload 排序。

        先按 score 降序取前 ``MATCH3_LEADERBOARD_CANDIDATE_LIMIT`` 条作为候选，
        再按 match3 规则排序并截断至 ``limit``。

        :param conditions: 已组装的通用过滤条件。
        :param mode: 玩法模式。
        :param limit: 返回条数上限（接口层最大 100）。
        :return: 排序后的排行榜原始行列表。
        """
        stmt = (
            select(
                ScoreRecord.user_id,
                UserAccount.nickname,
                ScoreRecord.score,
                ScoreRecord.duration_ms,
                ScoreRecord.created_at,
                ScoreRecord.payload_json,
            )
            .join(UserAccount, ScoreRecord.user_id == UserAccount.server_id)
            .where(*conditions)
            .order_by(ScoreRecord.score.desc())
            .limit(MATCH3_LEADERBOARD_CANDIDATE_LIMIT)
        )
        rows = self._session.execute(stmt).all()
        leaderboard_rows = [
            LeaderboardRow(
                user_id=row[0],
                nickname=row[1],
                score=row[2],
                duration_ms=row[3],
                created_at=row[4],
                payload_json=row[5],
            )
            for row in rows
        ]
        return sort_match3_leaderboard_rows(leaderboard_rows, mode, limit)
