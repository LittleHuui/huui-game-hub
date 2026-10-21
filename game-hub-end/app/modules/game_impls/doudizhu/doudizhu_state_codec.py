"""斗地主快照读取与旧倍率结构归一化。"""

import copy
from typing import Any, Dict

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_rule_policy import (
    CLASSIC_RULES_VERSION,
    resolve_rules_version,
)


def parse_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    复制快照，按明确版本保持本局规则，并读取旧版历史倍率结构。

    已生成的结算可能已交给平台入账，必须保留原理论结果。旧局明细与倍率
    不一致时显式拒绝归一化，不猜测或重放动作。移除旧字段后再次读取不会翻倍。

    :param raw_state: RuntimeSnapshot 中的斗地主状态。
    :return: 独立的规范状态副本。
    """
    state = copy.deepcopy(raw_state)
    state["rulesVersion"] = resolve_rules_version(state)
    players = state.get("players") or {}
    if state["rulesVersion"] == CLASSIC_RULES_VERSION:
        if any("personalMultiplier" in player for player in players.values()):
            raise ValidationException("新版斗地主快照混入旧个人倍率字段")
        return state
    legacy_players = [
        player for player in players.values() if "personalMultiplier" in player
    ]
    if not legacy_players or state.get("settlement") is not None:
        return state
    if len(legacy_players) != len(players):
        raise ValidationException("旧斗地主快照的个人倍率结构不完整")

    global_multiplier = 1
    total_multiplier = 1
    personal_multipliers = {player_id: 1 for player_id in players}
    details = state.get("multiplierDetails") or []
    if not isinstance(details, list):
        raise ValidationException("旧斗地主倍率明细格式无效")
    for detail in details:
        if not isinstance(detail, dict):
            raise ValidationException("旧斗地主倍率明细格式无效")
        multiplier = _positive_multiplier(detail.get("multiplier"))
        detail_type = str(detail.get("type") or "")
        if detail_type in ("SHOW_CARDS", "DOUBLE"):
            player_id = detail.get("playerId")
            if player_id not in personal_multipliers:
                raise ValidationException("旧斗地主倍率明细的玩家不存在")
            personal_multipliers[player_id] *= multiplier
        elif detail_type == "CALL_LANDLORD":
            if multiplier != 1:
                raise ValidationException("旧斗地主叫地主倍率必须为 1")
        elif detail_type in ("ROB_LANDLORD", "BOMB", "ROCKET", "SPRING", "ANTI_SPRING"):
            global_multiplier *= multiplier
        else:
            raise ValidationException("旧斗地主倍率明细来源无效")
        total_multiplier *= multiplier
        detail["globalMultiplierAfter"] = total_multiplier

    if global_multiplier != _positive_multiplier(state.get("globalMultiplier")):
        raise ValidationException("旧斗地主全局倍率与倍率明细不一致")
    for player_id, player in players.items():
        if personal_multipliers[player_id] != _positive_multiplier(
            player.get("personalMultiplier")
        ):
            raise ValidationException("旧斗地主个人倍率与倍率明细不一致")
        player.pop("personalMultiplier")
    state["globalMultiplier"] = total_multiplier
    return state


def _positive_multiplier(value: Any) -> int:
    """
    校验快照中的正整数倍率。

    :param value: 原始倍率。
    :return: 正整数倍率。
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationException("旧斗地主快照倍率无效")
    return value
