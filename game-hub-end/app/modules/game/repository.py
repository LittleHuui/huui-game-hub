"""游戏域数据访问。"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.game.models import GameClientConfig, GameDefinition, GameDifficulty


class GameDefinitionRepository:
    """``game_definition`` 表查询。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_game_code(self, game_code: str, *, active_only: bool = True) -> Optional[GameDefinition]:
        """按游戏编码查询。"""
        stmt = select(GameDefinition).where(GameDefinition.game_code == game_code)
        if active_only:
            stmt = stmt.where(GameDefinition.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_enabled(self) -> List[GameDefinition]:
        """列出已启用且未软删的游戏，按 sort_no 升序。"""
        stmt = (
            select(GameDefinition)
            .where(
                GameDefinition.enabled == 1,
                GameDefinition.deleted_at.is_(None),
            )
            .order_by(GameDefinition.sort_no.asc(), GameDefinition.created_at.asc())
        )
        return list(self._session.scalars(stmt).all())

    def list_all_active(self) -> List[GameDefinition]:
        """列出全部未软删游戏（含禁用）。"""
        stmt = (
            select(GameDefinition)
            .where(GameDefinition.deleted_at.is_(None))
            .order_by(GameDefinition.sort_no.asc())
        )
        return list(self._session.scalars(stmt).all())

    def add(self, entity: GameDefinition) -> GameDefinition:
        """插入游戏定义。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: GameDefinition) -> GameDefinition:
        """持久化变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity


class GameDifficultyRepository:
    """``game_difficulty`` 表查询。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_game_and_code(
        self,
        game_code: str,
        difficulty_code: str,
        *,
        active_only: bool = True,
    ) -> Optional[GameDifficulty]:
        """按游戏与难度编码查询。"""
        stmt = select(GameDifficulty).where(
            GameDifficulty.game_code == game_code,
            GameDifficulty.difficulty_code == difficulty_code,
        )
        if active_only:
            stmt = stmt.where(GameDifficulty.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_game(self, game_code: str, *, enabled_only: bool = False) -> List[GameDifficulty]:
        """列出某游戏全部难度，按 sort_no 升序。"""
        stmt = select(GameDifficulty).where(
            GameDifficulty.game_code == game_code,
            GameDifficulty.deleted_at.is_(None),
        )
        if enabled_only:
            stmt = stmt.where(GameDifficulty.enabled == 1)
        stmt = stmt.order_by(GameDifficulty.sort_no.asc(), GameDifficulty.created_at.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: GameDifficulty) -> GameDifficulty:
        """插入难度配置。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: GameDifficulty) -> GameDifficulty:
        """持久化变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity


class GameClientConfigRepository:
    """``game_client_config`` 表查询。"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_unique_key(
        self,
        game_code: str,
        difficulty_code: Optional[str],
        client_type: str,
        *,
        active_only: bool = True,
    ) -> Optional[GameClientConfig]:
        """按唯一键查询。"""
        stmt = select(GameClientConfig).where(
            GameClientConfig.game_code == game_code,
            GameClientConfig.client_type == client_type,
        )
        if difficulty_code is None:
            stmt = stmt.where(GameClientConfig.difficulty_code.is_(None))
        else:
            stmt = stmt.where(GameClientConfig.difficulty_code == difficulty_code)
        if active_only:
            stmt = stmt.where(GameClientConfig.deleted_at.is_(None))
        return self._session.scalar(stmt)

    def list_by_game(
        self,
        game_code: str,
        *,
        difficulty_code: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[GameClientConfig]:
        """列出某游戏（可按难度过滤）的客户端配置，按创建时间升序。"""
        stmt = select(GameClientConfig).where(
            GameClientConfig.game_code == game_code,
            GameClientConfig.deleted_at.is_(None),
        )
        if difficulty_code is not None:
            stmt = stmt.where(GameClientConfig.difficulty_code == difficulty_code)
        if enabled_only:
            stmt = stmt.where(GameClientConfig.enabled == 1)
        stmt = stmt.order_by(GameClientConfig.created_at.asc())
        return list(self._session.scalars(stmt).all())

    def add(self, entity: GameClientConfig) -> GameClientConfig:
        """插入客户端配置。"""
        self._session.add(entity)
        self._session.flush()
        return entity

    def save(self, entity: GameClientConfig) -> GameClientConfig:
        """持久化变更。"""
        self._session.add(entity)
        self._session.flush()
        return entity
