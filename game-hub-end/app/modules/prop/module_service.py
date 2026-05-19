"""道具域模块级编排服务。"""

import json
from typing import Any, Dict, List, Optional

from app.core.exceptions import ValidationException
from app.modules.game.schemas import GamePropRuleResponse
from app.modules.prop.entity_service import GamePropRuleEntityService, PropDefinitionEntityService
from app.modules.prop.models import GamePropRule, PropDefinition
from app.modules.prop.schemas import PropDefinitionResponse


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
        raise ValidationException("rule JSON 解析失败: {0}".format(exc)) from exc
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        raise ValidationException("rule JSON 必须为对象")
    return parsed


def _to_prop_definition_response(entity: PropDefinition) -> PropDefinitionResponse:
    """
    将道具定义 ORM 转为 HTTP 响应。

    :param entity: 道具定义实体。
    :return: ``PropDefinitionResponse``。
    """
    return PropDefinitionResponse(
        serverId=entity.server_id,
        createdAt=entity.created_at,
        updatedAt=entity.updated_at,
        deletedAt=entity.deleted_at,
        propCode=entity.prop_code,
        propName=entity.prop_name,
        description=entity.description,
        icon=entity.icon,
        basePrice=entity.base_price,
        enabled=bool(entity.enabled),
    )


def _to_game_prop_rule_response(
    rule: GamePropRule,
    prop_name: Optional[str],
) -> GamePropRuleResponse:
    """
    将游戏道具规则 ORM 转为 HTTP 响应。

    :param rule: 道具规则实体。
    :param prop_name: 关联道具名称，可空。
    :return: ``GamePropRuleResponse``。
    """
    return GamePropRuleResponse(
        serverId=rule.server_id,
        createdAt=rule.created_at,
        updatedAt=rule.updated_at,
        deletedAt=rule.deleted_at,
        gameCode=rule.game_code,
        propCode=rule.prop_code,
        propName=prop_name,
        price=rule.price,
        maxUsePerMatch=rule.max_use_per_match,
        triggerType=rule.trigger_type,
        effectType=rule.effect_type,
        rule=_parse_optional_json_dict(rule.rule_json),
        enabled=bool(rule.enabled),
    )


class PropModuleService:
    """道具模块：仅负责道具定义、规则与配置查询。"""

    def __init__(
        self,
        definition_entity: PropDefinitionEntityService,
        rule_entity: GamePropRuleEntityService,
    ) -> None:
        self._definitions = definition_entity
        self._rules = rule_entity

    def list_prop_definitions(self, *, enabled: Optional[bool] = None) -> List[PropDefinitionResponse]:
        """
        列出道具定义。

        :param enabled: 为 ``True``/``False`` 时按启用状态过滤，为 ``None`` 时不过滤。
        :return: 道具定义响应列表。
        """
        entities = self._definitions.list_all(enabled=enabled)
        return [_to_prop_definition_response(entity) for entity in entities]

    def list_game_prop_rules(self, game_code: str) -> List[GamePropRuleResponse]:
        """
        列出某游戏下已启用的道具规则。

        :param game_code: 游戏编码。
        :return: 游戏规则响应列表。
        """
        pairs = self._rules.list_enabled_with_definitions(game_code)
        return [
            _to_game_prop_rule_response(rule, definition.prop_name)
            for rule, definition in pairs
        ]

    def require_enabled_definition(self, prop_code: str) -> PropDefinition:
        """
        读取已启用道具定义。

        :param prop_code: 道具编码。
        :return: 道具定义。
        """
        return self._definitions.require_enabled(prop_code)

    def require_enabled_rule(self, game_code: str, prop_code: str) -> GamePropRule:
        """
        读取某游戏下已启用道具规则。

        :param game_code: 游戏编码。
        :param prop_code: 道具编码。
        :return: 游戏规则。
        """
        return self._rules.require_enabled_rule(game_code, prop_code)
