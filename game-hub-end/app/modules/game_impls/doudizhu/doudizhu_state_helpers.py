"""斗地主状态解析与配置辅助函数。"""

import hashlib

from typing import Any, Dict, List, Optional

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_combo_rule import DoudizhuComboRuleConfig
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo
from app.modules.game_seed.doudizhu_seed import DOUDIZHU_ONLINE_GAME_RULE_SEED
from app.modules.game_seed.schemas import resolve_room_config_defaults
from app.modules.strategy_turn.schemas import StrategyTurnRuntimeRule


def parse_cards(raw_cards: List[Any]) -> List[DoudizhuCard]:
    """
    将原始字典列表解析为牌对象列表。

    :param raw_cards: 原始牌列表。
    :return: 牌对象列表。
    """
    cards = []
    for item in raw_cards:
        if isinstance(item, DoudizhuCard):
            cards.append(item)
        elif isinstance(item, dict):
            cards.append(DoudizhuCard.model_validate(item))
    return cards


def parse_combo_info(raw_combo: Any) -> Optional[DoudizhuComboInfo]:
    """
    解析斗地主标准牌型数据。

    :param raw_combo: 原始牌型数据。
    :return: 牌型信息或 ``None``。
    """
    if raw_combo is None:
        return None
    if isinstance(raw_combo, DoudizhuComboInfo):
        return raw_combo
    if isinstance(raw_combo, dict) and raw_combo:
        return DoudizhuComboInfo.model_validate(raw_combo)
    return None


def build_combo_signature(combo: DoudizhuComboInfo) -> str:
    """
    生成牌型签名，用于 Resolver 与 Executor 一致性校验。

    :param combo: 归一化牌型。
    :return: 牌型签名字符串。
    """
    return "{0}:{1}:{2}".format(
        str(combo.comboType or ""),
        int(combo.mainRankValue),
        int(combo.cardCount),
    )


def build_last_play_signature(state: Dict[str, Any]) -> str:
    """
    生成当前桌面上家出牌签名。

    :param state: 对局状态。
    :return: 上家出牌签名；无上家出牌时为 ``none``。
    """
    last_play = parse_combo_info(state.get("lastPlay"))
    if last_play is None:
        return "none"
    return build_combo_signature(last_play)


def build_combo_config(state: Dict[str, Any]) -> DoudizhuComboRuleConfig:
    """
    根据对局状态构建牌型识别配置。

    :param state: 对局状态。
    :return: 牌型配置。
    """
    room_config = state.get("roomConfig") or {}
    allow_single_attachment = room_config.get("allowSingleAttachment")
    if allow_single_attachment is None:
        allow_single_attachment = state.get("allowSingleAttachment", True)
    return DoudizhuComboRuleConfig(
        enable_laizi=bool(state.get("enableLaizi")),
        allow_single_attachment=bool(allow_single_attachment),
        laizi_rank_code=state.get("laiziRankCode"),
    )


def resolve_room_config(runtime_rule: StrategyTurnRuntimeRule) -> Dict[str, Any]:
    """
    合并运行时房间配置。

    :param runtime_rule: 运行时规则。
    :return: 房间配置字典。
    """
    merged = resolve_room_config_defaults(DOUDIZHU_ONLINE_GAME_RULE_SEED)
    runtime_config = runtime_rule.config or {}
    if isinstance(runtime_config, dict):
        merged.update(runtime_config)
    return merged


def resolve_rule_config() -> Dict[str, Any]:
    """
    读取斗地主固定规则配置。

    :return: 规则配置字典。
    """
    extension = DOUDIZHU_ONLINE_GAME_RULE_SEED.extensionConfig
    rule = extension.get("rule") if isinstance(extension, dict) else None
    config = rule.get("config") if isinstance(rule, dict) else None
    if not isinstance(config, dict):
        return {}
    return dict(config)


DOUDIZHU_DEFAULT_SETTLEMENT_DISPLAY_MS = 2200


def animation_durations(rule_config: Dict[str, Any]) -> Dict[str, int]:
    """
    读取动画时长配置。

    :param rule_config: 规则配置。
    :return: 动画毫秒映射。
    """
    durations = rule_config.get("animationDurationsMs")
    if not isinstance(durations, dict):
        return {}
    result = {}
    for key, value in durations.items():
        try:
            result[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return result


def resolve_settlement_display_duration_ms(state: Dict[str, Any]) -> int:
    """
    读取斗地主终局展示时长（毫秒）。

    :param state: 对局状态。
    :return: 终局展示毫秒数。
    """
    rule_config = state.get("ruleConfig")
    if not isinstance(rule_config, dict):
        rule_config = resolve_rule_config()
    durations = animation_durations(rule_config)
    return int(durations.get("settlement", DOUDIZHU_DEFAULT_SETTLEMENT_DISPLAY_MS))


def empty_player_state(player_id: str, seat_index: int) -> Dict[str, Any]:
    """
    构建玩家初始状态。

    :param player_id: 玩家 ID。
    :param seat_index: 座位序号。
    :return: 玩家状态字典。
    """
    return {
        "playerId": player_id,
        "seatIndex": seat_index,
        "handCards": [],
        "handCount": 0,
        "role": None,
        "isLandlord": False,
        "showCards": False,
        "showCardsDecided": False,
        "isDoubled": False,
        "callDecided": False,
        "doubleDecided": False,
        "playCount": 0,
        "passCount": 0,
    }


def all_players_decided(state: Dict[str, Any], flag_key: str) -> bool:
    """
    判断所有玩家是否已完成某阶段决策。

    :param state: 对局状态。
    :param flag_key: 玩家标记字段名。
    :return: 全部完成为 ``True``。
    """
    players = state.get("players") or {}
    for player_id in list(state.get("playerIds") or []):
        player_raw = players.get(player_id) or {}
        if not bool(player_raw.get(flag_key)):
            return False
    return True


def next_seat_player_id(
    state: Dict[str, Any],
    current_player_id: Optional[str],
) -> Optional[str]:
    """
    按座位顺序获取下一位玩家 ID。

    :param state: 对局状态。
    :param current_player_id: 当前玩家 ID。
    :return: 下一位玩家 ID。
    """
    player_ids = list(state.get("playerIds") or [])
    if not player_ids:
        return None
    if current_player_id is None:
        return player_ids[0]
    current_index = player_ids.index(str(current_player_id))
    return player_ids[(current_index + 1) % len(player_ids)]


def next_calling_player_id(state: Dict[str, Any]) -> Optional[str]:
    """
    按叫地主起始座位获取下一位未决策玩家。

    :param state: 对局状态。
    :return: 下一位玩家 ID。
    """
    player_ids = list(state.get("playerIds") or [])
    start_index = int(state.get("callingStartSeatIndex") or 0)
    ordered = [
        player_ids[(start_index + offset) % len(player_ids)]
        for offset in range(len(player_ids))
    ]
    current_id = str(state.get("currentPlayerId") or "")
    players = state.get("players") or {}
    if current_id in ordered:
        start_offset = ordered.index(current_id) + 1
    else:
        start_offset = 0
    for offset in range(start_offset, len(ordered)):
        candidate_id = ordered[offset]
        player_raw = players.get(candidate_id) or {}
        if not bool(player_raw.get("callDecided")):
            return candidate_id
    return ordered[0]


def resolve_bidding_start_seat_index(state: Dict[str, Any]) -> Optional[int]:
    """
    基于首轮已落盘的牌局种子确定本轮叫地主起始座位。

    首轮根据洗牌结果生成一次私有种子；重新发牌沿用该种子并按轮次轮换起叫
    座位。这样既不依赖进程级随机状态，又保证同一 RuntimeSnapshot 可复现，
    并使连续三轮发牌中每个座位恰好各起叫一次。

    :param state: 当前对局状态。
    :return: 起叫座位序号；无玩家时返回 ``None``。
    """
    player_ids = list(state.get("playerIds") or [])
    if not player_ids:
        return None
    seed = state.get("biddingStartSeed")
    if not isinstance(seed, int):
        seed = _build_bidding_start_seed(state)
        state["biddingStartSeed"] = seed
    dealing_round = max(1, int(state.get("dealingRound") or 1))
    return (seed + dealing_round - 1) % len(player_ids)


def _build_bidding_start_seed(state: Dict[str, Any]) -> int:
    """
    由首轮已发出的牌实例顺序生成斗地主私有起叫种子。

    牌局首轮的洗牌结果已经是 RuntimeSnapshot 的一部分，以其构造种子可以在
    恢复、重放和进程切换后保持同一首叫顺序，而无需扩展通用运行时规则。

    :param state: 当前对局状态。
    :return: 非负 32 位起叫种子。
    """
    material = []
    player_ids = list(state.get("playerIds") or [])
    players = state.get("players") or {}
    for player_id in player_ids:
        material.append(str(player_id))
        player_raw = players.get(player_id) or {}
        for card_raw in player_raw.get("handCards") or []:
            if isinstance(card_raw, dict):
                material.append(str(card_raw.get("cardInstanceId") or ""))
    for card_raw in state.get("bottomCards") or []:
        if isinstance(card_raw, dict):
            material.append(str(card_raw.get("cardInstanceId") or ""))
    digest = hashlib.sha256("\x1f".join(material).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def first_seat_player_id(state: Dict[str, Any]) -> Optional[str]:
    """
    获取座位 0 玩家 ID。

    :param state: 对局状态。
    :return: 玩家 ID。
    """
    player_ids = list(state.get("playerIds") or [])
    return player_ids[0] if player_ids else None


def build_phase_auto_advance(delay_ms: int, reason: str) -> Dict[str, Any]:
    """
    构建阶段自动推进声明。

    :param delay_ms: 延迟毫秒。
    :param reason: 推进原因。
    :return: phaseAutoAdvance 字典。
    """
    return {
        "enabled": True,
        "delayMs": int(delay_ms),
        "reason": reason,
    }


def clear_seat_action_feedback(state: Dict[str, Any]) -> None:
    """
    清除客户端座位旁展示的最近操作反馈。

    操作反馈是领域状态的展示摘要，不参与牌型、轮次或结算判定。

    :param state: 当前对局状态。
    :return: 无。
    """
    state["lastActionEvent"] = None


def record_seat_action_feedback(
    state: Dict[str, Any],
    player_id: str,
    action_type: str,
) -> None:
    """
    记录可公开展示的最近一次座位操作。

    :param state: 当前对局状态。
    :param player_id: 操作玩家 ID。
    :param action_type: 已解析动作类型。
    :return: 无。
    """
    normalized_player_id = str(player_id or "").strip()
    normalized_action_type = str(action_type or "").strip()
    if not normalized_player_id or not normalized_action_type:
        clear_seat_action_feedback(state)
        return
    state["lastActionEvent"] = {
        "playerId": normalized_player_id,
        "actionType": normalized_action_type,
    }


def apply_global_multiplier(
    state: Dict[str, Any],
    detail_type: str,
    player_id: Optional[str],
    multiplier: int,
    event_type: str,
) -> None:
    """
    累乘全桌倍率并记录本次来源，两者随同一个动作提交。

    :param state: 对局状态。
    :param detail_type: 明细类型。
    :param player_id: 关联玩家 ID。
    :param multiplier: 本次倍数。
    :param event_type: 关联事件类型。
    :return: 无。
    """
    if multiplier < 1:
        raise ValidationException("全局倍率因子必须大于 0")
    state["globalMultiplier"] = int(state.get("globalMultiplier") or 1) * multiplier
    details = list(state.get("multiplierDetails") or [])
    details.append(
        {
            "type": detail_type,
            "playerId": player_id,
            "multiplier": multiplier,
            "globalMultiplierAfter": int(state.get("globalMultiplier") or 1),
            "eventType": event_type,
        }
    )
    state["multiplierDetails"] = details


def select_cards_by_instance_ids(
    hand_cards: List[DoudizhuCard],
    card_instance_ids: List[Any],
) -> List[DoudizhuCard]:
    """
    按实例 ID 从手牌中选取对应牌。

    :param hand_cards: 手牌列表。
    :param card_instance_ids: 实例 ID 列表。
    :return: 选中的牌列表。
    """
    selected_ids = {
        str(card_id).strip()
        for card_id in card_instance_ids
        if str(card_id).strip()
    }
    return [
        card
        for card in hand_cards
        if str(card.cardInstanceId or "").strip() in selected_ids
    ]


def build_simple_action(action_type: str, player_id: str, action_suffix: str):
    """
    构建无选牌要求的合法操作。

    :param action_type: 操作类型。
    :param player_id: 玩家 ID。
    :param action_suffix: actionId 后缀。
    :return: 合法操作。
    """
    from app.modules.strategy_turn.schemas import ResolvedGameAction

    return ResolvedGameAction(
        actionId="{0}|{1}".format(action_type, action_suffix),
        actionType=action_type,
        playerId=player_id,
        payload={},
    )
