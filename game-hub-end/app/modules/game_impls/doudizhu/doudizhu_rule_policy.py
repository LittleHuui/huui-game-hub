"""斗地主规则版本与计分参数解析，保持一局内的规则口径不变。"""

from typing import Any, Dict, Optional

from app.common.exceptions import ValidationException


LEGACY_RULES_VERSION = 1
CLASSIC_RULES_VERSION = 2


def resolve_rules_version(state: Dict[str, Any]) -> int:
    """读取明确规则版本；未携带版本的历史快照只属于旧叫抢全桌规则。"""
    version = state.get("rulesVersion", LEGACY_RULES_VERSION)
    if isinstance(version, bool) or version not in (LEGACY_RULES_VERSION, CLASSIC_RULES_VERSION):
        raise ValidationException("斗地主规则版本无效")
    if not isinstance(version, int):
        raise ValidationException("斗地主规则版本必须为整数")
    return version


def uses_classic_bid_rules(state: Dict[str, Any]) -> bool:
    """判断本局是否采用经典叫分与成对计分规则。"""
    return resolve_rules_version(state) == CLASSIC_RULES_VERSION


def _positive_rule_value(state: Dict[str, Any], key: str) -> int:
    """从本局固定规则读取正整数参数，不读取当前发布版本的规则定义。"""
    rule_config = state.get("ruleConfig")
    value = rule_config.get(key) if isinstance(rule_config, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationException("斗地主本局规则参数无效: {0}".format(key))
    return value


def resolve_base_score(state: Dict[str, Any]) -> Optional[int]:
    """由本局基础分与已确认的叫分派生底分；新规则尚未定地主时为空。"""
    room_base_score = _positive_rule_value(state, "baseScore")
    if not uses_classic_bid_rules(state):
        return room_base_score
    if not state.get("landlordPlayerId"):
        return None
    bid_score = state.get("bidScore")
    if isinstance(bid_score, bool) or not isinstance(bid_score, int) or bid_score not in (1, 2, 3):
        raise ValidationException("斗地主已确认地主的叫分无效")
    return room_base_score * bid_score


def resolve_personal_multipliers(state: Dict[str, Any]) -> Dict[str, int]:
    """解析每人的行为系数；旧版全桌倍率已含这些行为，个人因素恒为一。"""
    player_ids = list(state.get("playerIds") or [])
    if not uses_classic_bid_rules(state):
        return {player_id: 1 for player_id in player_ids}
    show_factor = _positive_rule_value(state, "showCardsMultiplier")
    double_factor = _positive_rule_value(state, "doubleMultiplier")
    players = state.get("players") or {}
    result = {}
    for player_id in player_ids:
        player = players.get(player_id)
        if not isinstance(player, dict):
            raise ValidationException("斗地主计分玩家状态缺失")
        result[player_id] = (
            (show_factor if player.get("showCards") else 1)
            * (double_factor if player.get("isDoubled") else 1)
        )
    return result
