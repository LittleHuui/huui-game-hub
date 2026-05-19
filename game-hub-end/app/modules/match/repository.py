"""对局域数据访问。"""

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.modules.match.models import MatchActionRecord, MatchRecord


class MatchRecordRepository:
    """``match_record`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_server_id(self, server_id: str, *, active_only: bool = True) -> Optional[MatchRecord]:
        """
        按主键查询对局记录。

        :param server_id: 服务端主键。
        :param active_only: 是否只查未软删行。
        :return: 对局实体或 ``None``。
        """
        stmt = select(MatchRecord).where(MatchRecord.server_id == server_id)
        if active_only:
            stmt = stmt.where(MatchRecord.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_by_user_and_client_id(
        self,
        user_id: str,
        client_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[MatchRecord]:
        """
        按幂等键查询对局记录。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :param active_only: 是否只查未软删行。
        :return: 对局实体或 ``None``。
        """
        stmt = select(MatchRecord).where(
            MatchRecord.user_id == user_id,
            MatchRecord.client_id == client_id,
        )
        if active_only:
            stmt = stmt.where(MatchRecord.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_any_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[MatchRecord]:
        """
        按幂等键查询对局记录（含软删），用于复活占用唯一键的旧行。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 对局实体或 ``None``。
        """
        stmt = select(MatchRecord).where(
            MatchRecord.user_id == user_id,
            MatchRecord.client_id == client_id,
        )
        return self._session.scalar(stmt)

    def list_by_user(self, user_id: str, limit: int = 50, *, active_only: bool = True) -> List[MatchRecord]:
        """
        按创建时间倒序列出用户最近对局。

        :param user_id: 用户主键。
        :param limit: 返回条数上限。
        :param active_only: 是否只查未软删行。
        :return: 对局列表。
        """
        stmt = select(MatchRecord).where(MatchRecord.user_id == user_id)
        if active_only:
            stmt = stmt.where(MatchRecord.deleted_at.is_(None))
        stmt = stmt.order_by(MatchRecord.created_at.desc()).limit(limit)
        return list(self._session.scalars(stmt).all())

    def _apply_user_list_filters(
        self,
        stmt: Select,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        mode: Optional[str] = None,
        result: Optional[str] = None,
        difficulty_code: Optional[str] = None,
        active_only: bool = True,
    ) -> Select:
        """
        为用户历史对局查询附加过滤条件。

        :param stmt: 基础查询语句。
        :param user_id: 用户主键。
        :param game_code: 游戏编码，非空时过滤。
        :param mode: 玩法模式，非空时过滤。
        :param result: 对局结果，非空时过滤。
        :param difficulty_code: 难度编码，非空时过滤。
        :param active_only: 是否只查未软删行。
        :return: 附加条件后的查询语句。
        """
        stmt = stmt.where(MatchRecord.user_id == user_id)
        if active_only:
            stmt = stmt.where(MatchRecord.deleted_at.is_(None))
        if game_code is not None and game_code.strip():
            stmt = stmt.where(MatchRecord.game_code == game_code.strip())
        if mode is not None and mode.strip():
            stmt = stmt.where(MatchRecord.mode == mode.strip())
        if result is not None and result.strip():
            stmt = stmt.where(MatchRecord.result == result.strip())
        if difficulty_code is not None and difficulty_code.strip():
            stmt = stmt.where(MatchRecord.difficulty_code == difficulty_code.strip())
        return stmt

    def count_by_user_filtered(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        mode: Optional[str] = None,
        result: Optional[str] = None,
        difficulty_code: Optional[str] = None,
        active_only: bool = True,
    ) -> int:
        """
        统计用户历史对局条数（含筛选条件）。

        :param user_id: 用户主键。
        :param game_code: 游戏编码，非空时过滤。
        :param mode: 玩法模式，非空时过滤。
        :param result: 对局结果，非空时过滤。
        :param difficulty_code: 难度编码，非空时过滤。
        :param active_only: 是否只查未软删行。
        :return: 符合条件的总记录数。
        """
        stmt = select(func.count()).select_from(MatchRecord)
        stmt = self._apply_user_list_filters(
            stmt,
            user_id,
            game_code=game_code,
            mode=mode,
            result=result,
            difficulty_code=difficulty_code,
            active_only=active_only,
        )
        total = self._session.scalar(stmt)
        return int(total or 0)

    def page_by_user_filtered(
        self,
        user_id: str,
        *,
        game_code: Optional[str] = None,
        mode: Optional[str] = None,
        result: Optional[str] = None,
        difficulty_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> List[MatchRecord]:
        """
        分页查询用户历史对局（按 ``created_at`` 倒序）。

        :param user_id: 用户主键。
        :param game_code: 游戏编码，非空时过滤。
        :param mode: 玩法模式，非空时过滤。
        :param result: 对局结果，非空时过滤。
        :param difficulty_code: 难度编码，非空时过滤。
        :param page_num: 页码，从 1 开始。
        :param page_size: 每页条数。
        :param active_only: 是否只查未软删行。
        :return: 当前页对局列表。
        """
        offset = (page_num - 1) * page_size
        stmt = select(MatchRecord)
        stmt = self._apply_user_list_filters(
            stmt,
            user_id,
            game_code=game_code,
            mode=mode,
            result=result,
            difficulty_code=difficulty_code,
            active_only=active_only,
        )
        stmt = stmt.order_by(MatchRecord.created_at.desc()).offset(offset).limit(page_size)
        return list(self._session.scalars(stmt).all())

    def add(self, entity: MatchRecord) -> MatchRecord:
        """
        插入对局记录。

        :param entity: ORM 实体。
        :return: 持久化后的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: MatchRecord) -> MatchRecord:
        """
        持久化对局记录变更。

        :param entity: ORM 实体。
        :return: 持久化后的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity


class MatchActionRecordRepository:
    """``match_action_record`` 表 CRUD。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_and_client_id(
        self,
        user_id: str,
        client_id: str,
        *,
        active_only: bool = True,
    ) -> Optional[MatchActionRecord]:
        """
        按幂等键查询操作记录。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :param active_only: 是否只查未软删行。
        :return: 操作实体或 ``None``。
        """
        stmt = select(MatchActionRecord).where(
            MatchActionRecord.user_id == user_id,
            MatchActionRecord.client_id == client_id,
        )
        if active_only:
            stmt = stmt.where(MatchActionRecord.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def get_any_by_user_and_client_id(self, user_id: str, client_id: str) -> Optional[MatchActionRecord]:
        """
        按幂等键查询操作记录（含软删）。

        :param user_id: 用户主键。
        :param client_id: 客户端幂等 ID。
        :return: 操作实体或 ``None``。
        """
        stmt = select(MatchActionRecord).where(
            MatchActionRecord.user_id == user_id,
            MatchActionRecord.client_id == client_id,
        )
        return self._session.scalar(stmt)

    def list_by_match_id(self, match_id: str, *, active_only: bool = True) -> List[MatchActionRecord]:
        """
        按 ``match_id`` 与 ``action_seq`` 升序列出操作记录。

        :param match_id: 对局主键（``match_record.server_id``）。
        :param active_only: 是否只查未软删行。
        :return: 操作列表。
        """
        stmt = select(MatchActionRecord).where(MatchActionRecord.match_id == match_id)
        if active_only:
            stmt = stmt.where(MatchActionRecord.deleted_at.is_(None))
        stmt = stmt.order_by(MatchActionRecord.action_seq.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: MatchActionRecord) -> MatchActionRecord:
        """
        插入操作记录。

        :param entity: ORM 实体。
        :return: 持久化后的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: MatchActionRecord) -> MatchActionRecord:
        """
        持久化操作记录变更。

        :param entity: ORM 实体。
        :return: 持久化后的实体。
        """
        self._session.add(entity)
        self._session.flush()
        return entity
