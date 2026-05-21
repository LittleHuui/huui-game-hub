"""管理配置导入单实体 upsert 与清理服务。"""

import json
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import new_entity_ids
from app.modules.game.models import GameClientConfig, GameDefinition, GameDifficulty
from app.modules.game.repository import (
    GameClientConfigRepository,
    GameDefinitionRepository,
    GameDifficultyRepository,
)
from app.modules.prop.models import GamePropRule, PropDefinition
from app.modules.prop.repository import GamePropRuleRepository, PropDefinitionRepository


def _bool_to_int(value: bool) -> int:
    """
    将布尔值转为数据库存储的 0/1。

    :param value: 布尔值。
    :return: 0 或 1。
    """
    return 1 if value else 0


def _serialize_json(value: Dict[str, Any]) -> str:
    """
    将字典序列化为紧凑 JSON 字符串。

    :param value: 配置字典。
    :return: JSON 字符串。
    """
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class PropDefinitionImportEntityService:
    """道具定义导入 upsert。"""

    def __init__(self, repository: PropDefinitionRepository) -> None:
        self._repository = repository

    def upsert(
        self,
        prop_code: str,
        prop_name: str,
        description: Optional[str],
        icon: Optional[str],
        base_price: int,
        enabled: bool,
    ) -> Tuple[PropDefinition, bool]:
        """
        按 prop_code 创建或更新道具定义。

        :param prop_code: 道具编码。
        :param prop_name: 道具名称。
        :param description: 描述。
        :param icon: 图标。
        :param base_price: 基础价格。
        :param enabled: 是否启用。
        :return: ``(实体, 是否新建)``。
        """
        existing = self._repository.get_by_prop_code(prop_code, active_only=False)
        enabled_int = _bool_to_int(enabled)
        if existing is not None:
            existing.prop_name = prop_name
            existing.description = description
            existing.icon = icon
            existing.base_price = base_price
            existing.enabled = enabled_int
            if existing.deleted_at is not None:
                existing.deleted_at = None
            return self._repository.save(existing), False
        server_id, created_at, updated_at = new_entity_ids("prop_def")
        entity = PropDefinition(
            server_id=server_id,
            prop_code=prop_code,
            prop_name=prop_name,
            description=description,
            icon=icon,
            base_price=base_price,
            enabled=enabled_int,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True

    def list_all(self, *, active_only: bool = False) -> List[PropDefinition]:
        """
        列出全部道具定义。

        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 道具定义列表。
        """
        return self._repository.list_all(active_only=active_only)

    def logical_disable(self, entity: PropDefinition) -> PropDefinition:
        """
        逻辑删除道具定义（软删 + 禁用）。

        :param entity: 道具定义实体。
        :return: 更新后的实体。
        """
        return self._repository.soft_delete(entity)

    def physical_remove(self, entity: PropDefinition) -> None:
        """
        物理删除道具定义。

        :param entity: 道具定义实体。
        """
        self._repository.physical_delete(entity)


class GameDefinitionImportEntityService:
    """游戏定义导入 upsert。"""

    def __init__(self, repository: GameDefinitionRepository) -> None:
        self._repository = repository

    def upsert(
        self,
        game_code: str,
        game_name: str,
        game_sub_name: Optional[str],
        support_online: bool,
        enabled: bool,
        sort_no: int,
        config_json: Optional[str],
    ) -> Tuple[GameDefinition, bool]:
        """
        按 game_code 创建或更新游戏定义。

        :param game_code: 游戏编码。
        :param game_name: 游戏名称。
        :param game_sub_name: 副标题。
        :param support_online: 是否支持联机。
        :param enabled: 是否启用。
        :param sort_no: 排序号。
        :param config_json: 扩展配置 JSON 字符串。
        :return: ``(实体, 是否新建)``。
        """
        existing = self._repository.get_by_game_code(game_code, active_only=False)
        enabled_int = _bool_to_int(enabled)
        support_online_int = _bool_to_int(support_online)
        if existing is not None:
            existing.game_name = game_name
            existing.game_sub_name = game_sub_name
            existing.support_online = support_online_int
            existing.enabled = enabled_int
            existing.sort_no = sort_no
            existing.config_json = config_json
            if existing.deleted_at is not None:
                existing.deleted_at = None
            return self._repository.save(existing), False
        server_id, created_at, updated_at = new_entity_ids("game_def")
        entity = GameDefinition(
            server_id=server_id,
            game_code=game_code,
            game_name=game_name,
            game_sub_name=game_sub_name,
            support_online=support_online_int,
            enabled=enabled_int,
            sort_no=sort_no,
            config_json=config_json,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True

    def list_all(self, *, active_only: bool = False) -> List[GameDefinition]:
        """
        列出全部游戏定义。

        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 游戏定义列表。
        """
        return self._repository.list_all(active_only=active_only)

    def logical_disable(self, entity: GameDefinition) -> GameDefinition:
        """
        逻辑删除游戏定义（软删 + 禁用）。

        :param entity: 游戏定义实体。
        :return: 更新后的实体。
        """
        return self._repository.soft_delete(entity)

    def physical_remove(self, entity: GameDefinition) -> None:
        """
        物理删除游戏定义。

        :param entity: 游戏定义实体。
        """
        self._repository.physical_delete(entity)


class GameDifficultyImportEntityService:
    """游戏难度导入 upsert。"""

    def __init__(self, repository: GameDifficultyRepository) -> None:
        self._repository = repository

    def upsert(
        self,
        game_code: str,
        difficulty_code: str,
        difficulty_name: str,
        config: Dict[str, Any],
        enabled: bool,
        sort_no: int,
    ) -> Tuple[GameDifficulty, bool]:
        """
        按 game_code + difficulty_code 创建或更新难度配置。

        :param game_code: 游戏编码。
        :param difficulty_code: 难度编码。
        :param difficulty_name: 难度名称。
        :param config: 难度配置字典。
        :param enabled: 是否启用。
        :param sort_no: 排序号。
        :return: ``(实体, 是否新建)``。
        """
        config_json = _serialize_json(config)
        existing = self._repository.get_by_game_and_code(
            game_code,
            difficulty_code,
            active_only=False,
        )
        enabled_int = _bool_to_int(enabled)
        if existing is not None:
            existing.difficulty_name = difficulty_name
            existing.config_json = config_json
            existing.enabled = enabled_int
            existing.sort_no = sort_no
            if existing.deleted_at is not None:
                existing.deleted_at = None
            return self._repository.save(existing), False
        server_id, created_at, updated_at = new_entity_ids("game_difficulty")
        entity = GameDifficulty(
            server_id=server_id,
            game_code=game_code,
            difficulty_code=difficulty_code,
            difficulty_name=difficulty_name,
            config_json=config_json,
            enabled=enabled_int,
            sort_no=sort_no,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True

    def list_by_game(self, game_code: str, *, active_only: bool = False) -> List[GameDifficulty]:
        """
        列出某游戏下全部难度配置。

        :param game_code: 游戏编码。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 难度配置列表。
        """
        return self._repository.list_by_game(game_code, active_only=active_only)

    def logical_disable(self, entity: GameDifficulty) -> GameDifficulty:
        """
        逻辑删除难度配置（软删 + 禁用）。

        :param entity: 难度配置实体。
        :return: 更新后的实体。
        """
        return self._repository.soft_delete(entity)

    def physical_remove(self, entity: GameDifficulty) -> None:
        """
        物理删除难度配置。

        :param entity: 难度配置实体。
        """
        self._repository.physical_delete(entity)

    def physical_remove_by_game_code(self, game_code: str) -> int:
        """
        按游戏编码物理删除全部难度配置。

        :param game_code: 游戏编码。
        :return: 删除行数。
        """
        return self._repository.physical_delete_by_game_code(game_code)


class GameClientConfigImportEntityService:
    """游戏客户端配置导入 upsert。"""

    def __init__(self, repository: GameClientConfigRepository) -> None:
        self._repository = repository

    def upsert(
        self,
        game_code: str,
        difficulty_code: Optional[str],
        client_type: str,
        config: Dict[str, Any],
        enabled: bool,
    ) -> Tuple[GameClientConfig, bool]:
        """
        按 game_code + difficulty_code + client_type 创建或更新客户端配置。

        :param game_code: 游戏编码。
        :param difficulty_code: 难度编码，可空。
        :param client_type: 客户端类型。
        :param config: 布局配置字典。
        :param enabled: 是否启用。
        :return: ``(实体, 是否新建)``。
        """
        config_json = _serialize_json(config)
        existing = self._repository.get_by_unique_key(
            game_code,
            difficulty_code,
            client_type,
            active_only=False,
        )
        enabled_int = _bool_to_int(enabled)
        if existing is not None:
            existing.config_json = config_json
            existing.enabled = enabled_int
            if existing.deleted_at is not None:
                existing.deleted_at = None
            return self._repository.save(existing), False
        server_id, created_at, updated_at = new_entity_ids("game_client_cfg")
        entity = GameClientConfig(
            server_id=server_id,
            game_code=game_code,
            difficulty_code=difficulty_code,
            client_type=client_type,
            config_json=config_json,
            enabled=enabled_int,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True

    def list_by_game(self, game_code: str, *, active_only: bool = False) -> List[GameClientConfig]:
        """
        列出某游戏下全部客户端配置。

        :param game_code: 游戏编码。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 客户端配置列表。
        """
        return self._repository.list_by_game(game_code, active_only=active_only)

    def logical_disable(self, entity: GameClientConfig) -> GameClientConfig:
        """
        逻辑删除客户端配置（软删 + 禁用）。

        :param entity: 客户端配置实体。
        :return: 更新后的实体。
        """
        return self._repository.soft_delete(entity)

    def physical_remove(self, entity: GameClientConfig) -> None:
        """
        物理删除客户端配置。

        :param entity: 客户端配置实体。
        """
        self._repository.physical_delete(entity)

    def physical_remove_by_game_code(self, game_code: str) -> int:
        """
        按游戏编码物理删除全部客户端配置。

        :param game_code: 游戏编码。
        :return: 删除行数。
        """
        return self._repository.physical_delete_by_game_code(game_code)


class GamePropRuleImportEntityService:
    """游戏道具规则导入 upsert。"""

    def __init__(self, repository: GamePropRuleRepository) -> None:
        self._repository = repository

    def upsert(
        self,
        game_code: str,
        prop_code: str,
        sort_no: int,
        price: int,
        max_use_per_match: Optional[int],
        trigger_type: Optional[str],
        effect_type: Optional[str],
        rule: Dict[str, Any],
        enabled: bool,
    ) -> Tuple[GamePropRule, bool]:
        """
        按 game_code + prop_code 创建或更新道具规则。

        :param game_code: 游戏编码。
        :param prop_code: 道具编码。
        :param sort_no: 排序号。
        :param price: 游戏内售价。
        :param max_use_per_match: 单局最大使用次数。
        :param trigger_type: 触发类型。
        :param effect_type: 效果类型。
        :param rule: 效果规则字典。
        :param enabled: 是否启用。
        :return: ``(实体, 是否新建)``。
        """
        rule_json = _serialize_json(rule)
        existing = self._repository.get_by_game_and_prop(
            game_code,
            prop_code,
            active_only=False,
        )
        enabled_int = _bool_to_int(enabled)
        if existing is not None:
            existing.sort_no = sort_no
            existing.price = price
            existing.max_use_per_match = max_use_per_match
            existing.trigger_type = trigger_type
            existing.effect_type = effect_type
            existing.rule_json = rule_json
            existing.enabled = enabled_int
            if existing.deleted_at is not None:
                existing.deleted_at = None
            return self._repository.save(existing), False
        server_id, created_at, updated_at = new_entity_ids("game_prop_rule")
        entity = GamePropRule(
            server_id=server_id,
            game_code=game_code,
            prop_code=prop_code,
            sort_no=sort_no,
            price=price,
            max_use_per_match=max_use_per_match,
            trigger_type=trigger_type,
            effect_type=effect_type,
            rule_json=rule_json,
            enabled=enabled_int,
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=None,
        )
        return self._repository.add(entity), True

    def list_by_game(self, game_code: str, *, active_only: bool = False) -> List[GamePropRule]:
        """
        列出某游戏下全部道具规则。

        :param game_code: 游戏编码。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 道具规则列表。
        """
        return self._repository.list_by_game(game_code, active_only=active_only)

    def list_by_prop_code(self, prop_code: str, *, active_only: bool = False) -> List[GamePropRule]:
        """
        列出引用指定道具编码的全部游戏规则。

        :param prop_code: 道具编码。
        :param active_only: 为 ``True`` 时仅返回未软删记录。
        :return: 道具规则列表。
        """
        return self._repository.list_by_prop_code(prop_code, active_only=active_only)

    def logical_disable(self, entity: GamePropRule) -> GamePropRule:
        """
        逻辑删除道具规则（软删 + 禁用）。

        :param entity: 道具规则实体。
        :return: 更新后的实体。
        """
        return self._repository.soft_delete(entity)

    def physical_remove(self, entity: GamePropRule) -> None:
        """
        物理删除道具规则。

        :param entity: 道具规则实体。
        """
        self._repository.physical_delete(entity)

    def physical_remove_by_game_code(self, game_code: str) -> int:
        """
        按游戏编码物理删除全部道具规则。

        :param game_code: 游戏编码。
        :return: 删除行数。
        """
        return self._repository.physical_delete_by_game_code(game_code)

    def physical_remove_by_prop_code(self, prop_code: str) -> int:
        """
        按道具编码物理删除全部游戏规则。

        :param prop_code: 道具编码。
        :return: 删除行数。
        """
        return self._repository.physical_delete_by_prop_code(prop_code)
