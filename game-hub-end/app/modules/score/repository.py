"""成绩域数据访问。"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
from app.modules.game.repository import GameDefinitionRepository
from app.modules.ranking.schemas import LeaderboardRow
from app.modules.score.leaderboard_rule import (
    SCORE_RESULT_WIN,
    build_sql_order_by,
    candidate_preorder_by,
    resolve_mode_rule,
    rule_requires_payload_sort,
    sort_leaderboard_rows,
)
from app.modules.score.models import ScoreRecord
from app.modules.user.models import UserAccount


class ScoreRecordRepository:
    """``score_record`` 表 CRUD。"""

    def __init__(
        self,
        session: Session,
        game_definitions: Optional[GameDefinitionRepository] = None,
    ) -> None:
        self._session = session
        self._game_definitions = game_definitions

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

    def list_leaderboard(
        self,
        game_code: str,
        mode: str,
        difficulty_code: Optional[str],
        limit: int,
    ) -> List[LeaderboardRow]:
        """
        查询排行榜候选行（关联用户昵称），按游戏配置排序。

        :param game_code: 游戏编码。
        :param mode: 玩法模式。
        :param difficulty_code: 难度编码，为 None 时不按难度过滤。
        :param limit: 返回条数上限。
        :return: 排行榜原始行列表。
        """
        rule = resolve_mode_rule(self._load_game_config(game_code), mode)
        conditions = [
            ScoreRecord.game_code == game_code,
            ScoreRecord.mode == mode,
            ScoreRecord.result == SCORE_RESULT_WIN,
            ScoreRecord.deleted_at.is_(None),
            UserAccount.deleted_at.is_(None),
        ]
        if difficulty_code is not None:
            conditions.append(ScoreRecord.difficulty_code == difficulty_code)
        if rule_requires_payload_sort(rule):
            return self._list_leaderboard_with_payload(conditions, rule, limit)
        return self._list_leaderboard_sql(conditions, rule, limit)

    def _list_leaderboard_sql(
        self,
        conditions: List[Any],
        rule: Any,
        limit: int,
    ) -> List[LeaderboardRow]:
        """
        纯 SQL 列排序的排行榜查询。

        :param conditions: 过滤条件。
        :param rule: 模式规则。
        :param limit: 返回条数上限。
        :return: 排行榜行列表。
        """
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
            .order_by(*build_sql_order_by(rule))
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

    def _list_leaderboard_with_payload(
        self,
        conditions: List[Any],
        rule: Any,
        limit: int,
    ) -> List[LeaderboardRow]:
        """
        含 payload 指标时：先按主 SQL 指标取候选池，再 Python 排序。

        :param conditions: 过滤条件。
        :param rule: 模式规则。
        :param limit: 返回条数上限。
        :return: 排序后的排行榜行列表。
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
            .order_by(*candidate_preorder_by(rule))
            .limit(rule.candidate_limit)
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
        return sort_leaderboard_rows(leaderboard_rows, rule, limit)

    def _load_game_config(self, game_code: str) -> Dict[str, Any]:
        """
        读取游戏扩展配置对象。

        :param game_code: 游戏编码。
        :return: 配置字典，缺失或解析失败时返回空对象。
        """
        if self._game_definitions is None:
            return {}
        game = self._game_definitions.get_by_game_code(game_code)
        if game is None or game.config_json is None or not str(game.config_json).strip():
            return {}
        try:
            parsed = json.loads(game.config_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed
