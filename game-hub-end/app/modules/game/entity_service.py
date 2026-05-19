"""游戏域单实体服务。"""

from typing import List, Optional

from app.core.database import new_entity_ids
from app.core.exceptions import NotFoundException, ValidationException
from app.modules.game.models import GameClientConfig, GameDefinition, GameDifficulty
from app.modules.game.repository import (
    GameClientConfigRepository,
    GameDefinitionRepository,
    GameDifficultyRepository,
)


class GameDefinitionEntityService:
    """游戏定义实体的基础查询与写入。"""

    def __init__(self, repository: GameDefinitionRepository) -> None:
        self._repository = repository

    def get_by_game_code(self, game_code: str, *, active_only: bool = True) -> Optional[GameDefinition]:
        """按游戏编码读取。"""
        return self._repository.get_by_game_code(game_code, active_only=active_only)

    def require_by_game_code(self, game_code: str) -> GameDefinition:
        """读取游戏定义，不存在则抛出 NotFoundException。"""
        entity = self._repository.get_by_game_code(game_code)
        if entity is None:
            raise NotFoundException("游戏不存在")
        return entity

    def require_enabled_by_game_code(self, game_code: str) -> GameDefinition:
        """
        读取已启用且未软删的游戏定义。

        :param game_code: 游戏编码。
        :return: 游戏定义实体。
        :raises NotFoundException: 不存在、已禁用或已软删。
        """
        entity = self._repository.get_by_game_code(game_code)
        if entity is None or entity.enabled != 1:
            raise NotFoundException("游戏不存在")
        return entity

    def list_enabled(self) -> List[GameDefinition]:
        """列出已启用游戏。"""
        return self._repository.list_enabled()

    def create_if_not_exists(
        self,
        game_code: str,
        game_name: str,
        game_sub_name: Optional[str],
        support_online: int,
        enabled: int,
        sort_no: int,
        config_json: Optional[str],
    ) -> GameDefinition:
        """
        幂等创建游戏定义；已存在则直接返回现有记录。

        :param game_code: 唯一游戏编码。
        :param game_name: 游戏名称。
        :param game_sub_name: 副标题，可空。
        :param support_online: 是否支持联机（0/1）。
        :param enabled: 是否启用（0/1）。
        :param sort_no: 排序号。
        :param config_json: 扩展配置 JSON，可空。
        :return: 游戏定义实体。
        """
        existing = self._repository.get_by_game_code(game_code)
        if existing is not None:
            return existing
        server_id, created_at, updated_at = new_entity_ids("game_def")
        entity = GameDefinition(
            server_id=server_id,
            game_code=game_code,
            game_name=game_name,
            game_sub_name=game_sub_name,
            support_online=support_online,
            enabled=enabled,
            sort_no=sort_no,
            config_json=config_json,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)


class GameDifficultyEntityService:
    """游戏难度实体的基础查询与写入。"""

    def __init__(self, repository: GameDifficultyRepository) -> None:
        self._repository = repository

    def get_by_game_and_code(
        self,
        game_code: str,
        difficulty_code: str,
        *,
        active_only: bool = True,
    ) -> Optional[GameDifficulty]:
        """按游戏与难度编码读取。"""
        return self._repository.get_by_game_and_code(game_code, difficulty_code, active_only=active_only)

    def list_by_game(self, game_code: str, *, enabled_only: bool = False) -> List[GameDifficulty]:
        """列出某游戏的难度配置。"""
        return self._repository.list_by_game(game_code, enabled_only=enabled_only)

    def create_if_not_exists(
        self,
        game_code: str,
        difficulty_code: str,
        difficulty_name: str,
        config_json: str,
        enabled: int,
        sort_no: int,
    ) -> GameDifficulty:
        """
        幂等创建难度配置；已存在则直接返回。

        :param game_code: 游戏编码。
        :param difficulty_code: 难度编码。
        :param difficulty_name: 难度展示名。
        :param config_json: 规格配置 JSON。
        :param enabled: 是否启用（0/1）。
        :param sort_no: 排序号。
        :return: 难度配置实体。
        """
        existing = self._repository.get_by_game_and_code(game_code, difficulty_code)
        if existing is not None:
            return existing
        server_id, created_at, updated_at = new_entity_ids("game_difficulty")
        entity = GameDifficulty(
            server_id=server_id,
            game_code=game_code,
            difficulty_code=difficulty_code,
            difficulty_name=difficulty_name,
            config_json=config_json,
            enabled=enabled,
            sort_no=sort_no,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)

    def require_enabled(self, game_code: str, difficulty_code: str) -> GameDifficulty:
        """读取已启用难度，不存在或禁用时抛错。"""
        entity = self._repository.get_by_game_and_code(game_code, difficulty_code)
        if entity is None:
            raise NotFoundException("难度配置不存在")
        if entity.enabled != 1:
            raise ValidationException("难度配置未启用")
        return entity


class GameClientConfigEntityService:
    """游戏客户端配置实体的基础查询与写入。"""

    def __init__(self, repository: GameClientConfigRepository) -> None:
        self._repository = repository

    def get_by_unique_key(
        self,
        game_code: str,
        difficulty_code: Optional[str],
        client_type: str,
    ) -> Optional[GameClientConfig]:
        """按唯一键读取。"""
        return self._repository.get_by_unique_key(game_code, difficulty_code, client_type)

    def list_by_game(
        self,
        game_code: str,
        *,
        difficulty_code: Optional[str] = None,
        enabled_only: bool = False,
    ) -> List[GameClientConfig]:
        """列出游戏客户端配置。"""
        return self._repository.list_by_game(game_code, difficulty_code=difficulty_code, enabled_only=enabled_only)

    def create_if_not_exists(
        self,
        game_code: str,
        difficulty_code: Optional[str],
        client_type: str,
        config_json: str,
        enabled: int,
    ) -> GameClientConfig:
        """
        幂等创建客户端配置；已存在则直接返回。

        :param game_code: 游戏编码。
        :param difficulty_code: 难度编码，可空（表示全局配置）。
        :param client_type: 客户端类型，如 pc / mobile_portrait / mobile_landscape。
        :param config_json: 布局配置 JSON。
        :param enabled: 是否启用（0/1）。
        :return: 客户端配置实体。
        """
        existing = self._repository.get_by_unique_key(game_code, difficulty_code, client_type)
        if existing is not None:
            return existing
        server_id, created_at, updated_at = new_entity_ids("game_client_cfg")
        entity = GameClientConfig(
            server_id=server_id,
            game_code=game_code,
            difficulty_code=difficulty_code,
            client_type=client_type,
            config_json=config_json,
            enabled=enabled,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity)
