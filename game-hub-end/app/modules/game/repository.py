"""游戏域数据访问。"""

from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.time_utils import now_ms
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

    def list_all(self, *, active_only: bool = True) -> List[GameDefinition]:
        """
        列出全部游戏定义。

        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 按 ``sort_no`` 升序排列的游戏列表。
        """
        stmt = select(GameDefinition).order_by(GameDefinition.sort_no.asc())
        if active_only:
            stmt = stmt.where(GameDefinition.deleted_at.is_(None))
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

    def soft_delete(self, entity: GameDefinition) -> GameDefinition:
        """软删除游戏定义并禁用。"""
        now = now_ms()
        entity.deleted_at = now
        entity.enabled = 0
        entity.updated_at = now
        return self.save(entity)

    def physical_delete(self, entity: GameDefinition) -> None:
        """物理删除游戏定义。"""
        self._session.delete(entity)
        self._session.flush()


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

    def list_by_game(
        self,
        game_code: str,
        *,
        enabled_only: bool = False,
        active_only: bool = True,
    ) -> List[GameDifficulty]:
        """
        列出某游戏全部难度，按 sort_no 升序。

        :param game_code: 游戏编码。
        :param enabled_only: 为 ``True`` 时仅返回已启用记录。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 难度配置列表。
        """
        stmt = select(GameDifficulty).where(GameDifficulty.game_code == game_code)
        if active_only:
            stmt = stmt.where(GameDifficulty.deleted_at.is_(None))
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

    def soft_delete(self, entity: GameDifficulty) -> GameDifficulty:
        """软删除难度配置并禁用。"""
        now = now_ms()
        entity.deleted_at = now
        entity.enabled = 0
        entity.updated_at = now
        return self.save(entity)

    def physical_delete(self, entity: GameDifficulty) -> None:
        """物理删除难度配置。"""
        self._session.delete(entity)
        self._session.flush()

    def physical_delete_by_game_code(self, game_code: str) -> int:
        """
        按游戏编码物理删除全部难度配置。

        :param game_code: 游戏编码。
        :return: 删除行数。
        """
        stmt = delete(GameDifficulty).where(GameDifficulty.game_code == game_code)
        result = self._session.execute(stmt)
        self._session.flush()
        return int(result.rowcount or 0)


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
        active_only: bool = True,
    ) -> List[GameClientConfig]:
        """
        列出某游戏（可按难度过滤）的客户端配置，按创建时间升序。

        :param game_code: 游戏编码。
        :param difficulty_code: 难度编码过滤，省略则不过滤。
        :param enabled_only: 为 ``True`` 时仅返回已启用记录。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 客户端配置列表。
        """
        stmt = select(GameClientConfig).where(GameClientConfig.game_code == game_code)
        if active_only:
            stmt = stmt.where(GameClientConfig.deleted_at.is_(None))
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

    def soft_delete(self, entity: GameClientConfig) -> GameClientConfig:
        """软删除客户端配置并禁用。"""
        now = now_ms()
        entity.deleted_at = now
        entity.enabled = 0
        entity.updated_at = now
        return self.save(entity)

    def physical_delete(self, entity: GameClientConfig) -> None:
        """物理删除客户端配置。"""
        self._session.delete(entity)
        self._session.flush()

    def physical_delete_by_game_code(self, game_code: str) -> int:
        """
        按游戏编码物理删除全部客户端配置。

        :param game_code: 游戏编码。
        :return: 删除行数。
        """
        stmt = delete(GameClientConfig).where(GameClientConfig.game_code == game_code)
        result = self._session.execute(stmt)
        self._session.flush()
        return int(result.rowcount or 0)
