"""游戏域模块级编排服务。"""

import json
from typing import Any, Dict, List, Optional

from app.common.exceptions import NotFoundException, ValidationException
from app.modules.game.entity_service import (
    GameClientConfigEntityService,
    GameDefinitionEntityService,
    GameDifficultyEntityService,
)
from app.modules.game.models import GameClientConfig, GameDefinition, GameDifficulty
from app.modules.game.schemas import (
    GameClientConfigListData,
    GameClientConfigRead,
    GameClientConfigResponse,
    GameConfigResponse,
    GameDifficultyResponse,
    GamePropRuleResponse,
    GameSummaryResponse,
)
from app.modules.prop.entity_service import GamePropRuleEntityService
from app.modules.prop.models import GamePropRule


def _parse_json_dict(raw: Optional[str], *, field_name: str) -> Dict[str, Any]:
    """
    将存库 JSON 文本解析为字典。

    :param raw: JSON 文本。
    :param field_name: 字段名，用于错误提示。
    :return: 配置字典。
    :raises ValidationException: 解析失败或类型非对象。
    """
    text = "{}" if raw is None or not str(raw).strip() else str(raw)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationException(f"{field_name} JSON 解析失败: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValidationException(f"{field_name} JSON 必须为对象")
    return parsed


def _parse_optional_json_dict(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    将可空 JSON 文本解析为字典。

    :param raw: JSON 文本，可空。
    :return: 字典或 ``None``。
    :raises ValidationException: 非空但解析失败或类型非对象。
    """
    if raw is None or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationException(f"rule JSON 解析失败: {exc}") from exc
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise ValidationException("rule JSON 必须为对象")
    return parsed


def _to_game_summary(game: GameDefinition) -> GameSummaryResponse:
    """
    将游戏定义 ORM 转为摘要响应。

    :param game: 游戏定义实体。
    :return: ``GameSummaryResponse``。
    """
    return GameSummaryResponse(
        gameCode=game.game_code,
        gameName=game.game_name,
        gameSubName=game.game_sub_name,
        supportOnline=bool(game.support_online),
        enabled=bool(game.enabled),
        sortNo=game.sort_no,
    )


def _to_difficulty_response(difficulty: GameDifficulty) -> GameDifficultyResponse:
    """
    将难度配置 ORM 转为响应。

    :param difficulty: 难度实体。
    :return: ``GameDifficultyResponse``。
    """
    return GameDifficultyResponse(
        serverId=difficulty.server_id,
        createdAt=difficulty.created_at,
        updatedAt=difficulty.updated_at,
        deletedAt=difficulty.deleted_at,
        gameCode=difficulty.game_code,
        difficultyCode=difficulty.difficulty_code,
        difficultyName=difficulty.difficulty_name,
        config=_parse_json_dict(difficulty.config_json, field_name="config"),
        enabled=bool(difficulty.enabled),
        sortNo=difficulty.sort_no,
    )


def _to_client_config_response(config: GameClientConfig) -> GameClientConfigResponse:
    """
    将客户端配置 ORM 转为响应。

    :param config: 客户端配置实体。
    :return: ``GameClientConfigResponse``。
    """
    return GameClientConfigResponse(
        serverId=config.server_id,
        createdAt=config.created_at,
        updatedAt=config.updated_at,
        deletedAt=config.deleted_at,
        gameCode=config.game_code,
        difficultyCode=config.difficulty_code,
        clientType=config.client_type,
        config=_parse_json_dict(config.config_json, field_name="config"),
        enabled=bool(config.enabled),
    )


def _to_prop_rule_response(rule: GamePropRule) -> GamePropRuleResponse:
    """
    将道具规则 ORM 转为响应。

    :param rule: 道具规则实体。
    :return: ``GamePropRuleResponse``。
    """
    return GamePropRuleResponse(
        serverId=rule.server_id,
        createdAt=rule.created_at,
        updatedAt=rule.updated_at,
        deletedAt=rule.deleted_at,
        gameCode=rule.game_code,
        propCode=rule.prop_code,
        price=rule.price,
        maxUsePerMatch=rule.max_use_per_match,
        triggerType=rule.trigger_type,
        effectType=rule.effect_type,
        rule=_parse_optional_json_dict(rule.rule_json),
        enabled=bool(rule.enabled),
        sortNo=rule.sort_no,
    )


class GameModuleService:
    """游戏配置模块对外业务能力。"""

    def __init__(
        self,
        definition_entity: GameDefinitionEntityService,
        difficulty_entity: GameDifficultyEntityService,
        client_config_entity: GameClientConfigEntityService,
        prop_rule_entity: GamePropRuleEntityService,
    ) -> None:
        self._definitions = definition_entity
        self._difficulties = difficulty_entity
        self._client_configs = client_config_entity
        self._prop_rules = prop_rule_entity

    def list_enabled_games(self) -> List[GameDefinition]:
        """列出全部已启用游戏。"""
        return self._definitions.list_enabled()

    def get_game_config(self, game_code: str) -> GameConfigResponse:
        """
        返回游戏基础信息及全部已启用配置。

        :param game_code: 游戏编码。
        :return: ``GameConfigResponse``。
        :raises NotFoundException: 游戏不存在或未启用。
        """
        game = self._definitions.require_enabled_by_game_code(game_code)
        difficulties = self._difficulties.list_by_game(game_code, enabled_only=True)
        client_configs = self._client_configs.list_by_game(game_code, enabled_only=True)
        prop_rules = self._prop_rules.list_enabled_by_game(game_code)
        return GameConfigResponse(
            game=_to_game_summary(game),
            difficulties=[_to_difficulty_response(d) for d in difficulties],
            clientConfigs=[_to_client_config_response(c) for c in client_configs],
            props=[_to_prop_rule_response(r) for r in prop_rules],
        )

    def get_game_difficulties(self, game_code: str) -> List[GameDifficulty]:
        """
        列出某游戏全部难度配置（已启用）。

        :param game_code: 游戏编码。
        :return: 难度列表。
        :raises NotFoundException: 游戏不存在。
        """
        self._definitions.require_enabled_by_game_code(game_code)
        return self._difficulties.list_by_game(game_code, enabled_only=True)

    def get_client_config(
        self,
        game_code: str,
        *,
        difficulty_code: Optional[str] = None,
    ) -> GameClientConfigListData:
        """
        列出某游戏（可按难度过滤）的客户端配置。

        :param game_code: 游戏编码。
        :param difficulty_code: 可选难度过滤。
        :return: ``GameClientConfigListData``。
        :raises NotFoundException: 游戏不存在。
        """
        self._definitions.require_enabled_by_game_code(game_code)
        items = self._client_configs.list_by_game(
            game_code,
            difficulty_code=difficulty_code,
            enabled_only=True,
        )
        return GameClientConfigListData(
            items=[GameClientConfigRead.model_validate(c) for c in items],
        )
