"""斗地主评分上下文与牌型解析辅助。"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.modules.game_impls.doudizhu.doudizhu_combo_rule import (
    DoudizhuComboRuleConfig,
    recognize_combo,
)
from app.modules.game_impls.doudizhu.doudizhu_constants import ROLE_FARMER, ROLE_LANDLORD
from app.modules.game_impls.doudizhu.doudizhu_rule_policy import resolve_rules_version
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    build_combo_config,
    parse_cards,
    parse_combo_info,
    select_cards_by_instance_ids,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo


@dataclass
class DoudizhuScoreContext(object):
    """斗地主评分上下文，仅持有本人手牌及白名单公开字段。"""

    player_id: str
    phase: str
    players_by_id: Dict[str, Dict[str, Any]]
    player_ids: List[str]
    current_player_id: str
    round_lead_player_id: Optional[str]
    consecutive_pass_count: int
    hand_cards: List[DoudizhuCard]
    hand_strength: float
    is_landlord: bool
    is_farmer: bool
    enable_laizi: bool
    laizi_rank_code: Optional[str]
    last_play: Optional[DoudizhuComboInfo]
    last_play_player_id: Optional[str]
    landlord_player_id: Optional[str]
    combo_config: DoudizhuComboRuleConfig
    rules_version: int
    highest_bid_score: int


def build_score_context(
    state: Dict[str, Any],
    player_id: str,
    hand_strength_evaluator,
) -> Optional[DoudizhuScoreContext]:
    """
    从运行时状态解析评分上下文。

    :param state: 对局状态。
    :param player_id: 当前行动玩家 ID。
    :param hand_strength_evaluator: 手牌强度评估器实例。
    :return: 上下文，数据不足时返回 ``None``。
    """
    normalized_player_id = str(player_id or "").strip()
    if not normalized_player_id:
        return None
    phase = str(state.get("phase") or "").strip()
    players_raw = state.get("players")
    if not isinstance(players_raw, dict):
        return None
    players_by_id = {}
    for pid, item in players_raw.items():
        if isinstance(item, dict):
            players_by_id[str(pid)] = {
                "playerId": str(pid),
                "handCount": max(0, int(item.get("handCount") or 0)),
                "role": str(item.get("role") or ""),
                "isLandlord": bool(item.get("isLandlord")),
                "callDecided": bool(item.get("callDecided")),
                "bidScore": int(item.get("bidScore") or 0),
                "showCards": bool(item.get("showCards")),
            }
    player_raw = players_raw.get(normalized_player_id) or {}
    hand_cards = parse_cards(player_raw.get("handCards") or [])
    combo_config = build_combo_config(state)
    enable_laizi = bool(state.get("enableLaizi"))
    laizi_rank_code = state.get("laiziRankCode")
    if laizi_rank_code is not None:
        laizi_rank_code = str(laizi_rank_code).strip() or None
    role = str(player_raw.get("role") or "").strip().upper()
    is_landlord = role == ROLE_LANDLORD or bool(player_raw.get("isLandlord"))
    is_farmer = role == ROLE_FARMER or (not is_landlord and role != "")
    hand_strength = hand_strength_evaluator.evaluate_hand_strength(hand_cards, combo_config)
    last_play = parse_combo_info(state.get("lastPlay"))
    last_play_player_id = state.get("lastPlayPlayerId")
    if last_play_player_id is not None:
        last_play_player_id = str(last_play_player_id).strip() or None
    landlord_player_id = state.get("landlordPlayerId")
    if landlord_player_id is not None:
        landlord_player_id = str(landlord_player_id).strip() or None
    if normalized_player_id in players_by_id:
        players_by_id[normalized_player_id]["handCount"] = len(hand_cards)
    return DoudizhuScoreContext(
        player_id=normalized_player_id,
        phase=phase,
        players_by_id=players_by_id,
        player_ids=[str(pid) for pid in state.get("playerIds") or []],
        current_player_id=str(state.get("currentPlayerId") or ""),
        round_lead_player_id=str(state.get("roundLeadPlayerId") or "") or None,
        consecutive_pass_count=int(state.get("consecutivePassCount") or 0),
        hand_cards=hand_cards,
        hand_strength=hand_strength,
        is_landlord=is_landlord,
        is_farmer=is_farmer,
        enable_laizi=enable_laizi,
        laizi_rank_code=laizi_rank_code,
        last_play=last_play,
        last_play_player_id=last_play_player_id,
        landlord_player_id=landlord_player_id,
        combo_config=combo_config,
        rules_version=resolve_rules_version(state),
        highest_bid_score=int(state.get("bidScore") or 0),
    )


def resolve_combo_from_payload(
    context: DoudizhuScoreContext,
    payload: Dict[str, Any],
    card_ids: List[Any],
) -> Optional[DoudizhuComboInfo]:
    """
    从动作载荷解析牌型，缺少归一牌型时复用规则识别。

    :param context: 评分上下文。
    :param payload: 动作 payload。
    :param card_ids: 出牌实例 ID 列表。
    :return: 牌型信息或 ``None``。
    """
    combo = parse_combo_info(payload.get("normalizedCombo"))
    if combo is not None:
        return combo
    selected = select_cards_by_instance_ids(context.hand_cards, card_ids)
    if not selected:
        return None
    return recognize_combo(selected, context.combo_config, context.last_play)
