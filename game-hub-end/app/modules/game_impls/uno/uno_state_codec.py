"""UNO 对局状态编解码与房间配置解析。"""

from typing import Any, Dict, Set

from app.modules.game_seed.schemas import resolve_room_config_defaults
from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED
from app.modules.game_impls.uno.schemas import UnoRuntimeState
from app.modules.strategy_turn.schemas import StrategyTurnRuntimeRule


def parse_state(state: Dict[str, Any]) -> UnoRuntimeState:
    """
    将对局状态字典解析为 ``UnoRuntimeState``。

    :param state: 状态字典。
    :return: 运行时状态模型。
    """
    if "lastActionEvents" in state or "eventSequence" in state:
        raise ValueError("UNO state 不允许包含框架事件字段")
    cleaned = dict(state)
    cleaned.pop("roomConfig", None)
    return UnoRuntimeState.model_validate(cleaned)


def dump_state(runtime_state: UnoRuntimeState) -> Dict[str, Any]:
    """
    序列化运行时状态（不含事件与房间配置）。

    :param runtime_state: 运行时状态。
    :return: 状态字典。
    """
    return runtime_state.model_dump()


def resolve_room_config(runtime_rule: StrategyTurnRuntimeRule) -> Dict[str, Any]:
    """
    合并运行时规则中的房间配置与种子默认值。

    :param runtime_rule: 运行时规则。
    :return: 房间配置字典。
    """
    merged = resolve_room_config_defaults(UNO_ONLINE_GAME_RULE_SEED)
    if isinstance(runtime_rule.config, dict):
        merged.update(runtime_rule.config)
    return merged


def resolve_room_config_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    从状态字典中的运行时规则快照解析房间配置。

    :param state: 对局状态字典。
    :return: 房间配置字典。
    """
    merged = resolve_room_config_defaults(UNO_ONLINE_GAME_RULE_SEED)
    runtime_rule = state.get("runtimeRule")
    if isinstance(runtime_rule, dict):
        config = runtime_rule.get("config")
        if isinstance(config, dict):
            merged.update(config)
    room_config = state.get("roomConfig")
    if isinstance(room_config, dict):
        merged.update(room_config)
    return merged


def resolve_ai_player_ids(runtime_rule: StrategyTurnRuntimeRule) -> Set[str]:
    """
    从运行时规则配置解析 AI 玩家 ID 集合。

    :param runtime_rule: 运行时规则。
    :return: AI 玩家 ID 集合。
    """
    config = runtime_rule.config if isinstance(runtime_rule.config, dict) else {}
    raw_ids = config.get("aiPlayerIds", [])
    if not isinstance(raw_ids, list):
        return set()
    result = set()
    for item in raw_ids:
        normalized = str(item).strip()
        if normalized:
            result.add(normalized)
    return result
