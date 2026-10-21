"""斗地主评分专用的候选后局面与公开牌权机会，不执行真实动作。"""

from dataclasses import dataclass
from math import exp
from typing import Dict, List, Optional, Tuple

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import DoudizhuActionScoreConfig
from app.modules.game_impls.doudizhu.doudizhu_combo_rule import can_beat
from app.modules.game_impls.doudizhu.doudizhu_constants import ACTION_PASS, ACTION_PLAY_CARDS, PHASE_PLAYING
from app.modules.game_impls.doudizhu.doudizhu_scorer_combo_features import combo_rank_bounds, combo_strength
from app.modules.game_impls.doudizhu.doudizhu_scorer_support import DoudizhuScoreContext, resolve_combo_from_payload
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo
from app.modules.strategy_turn.schemas import ResolvedGameAction


@dataclass(frozen=True)
class DoudizhuScoredPosition(object):
    """候选执行后的只读摘要；下一行动者与自由首出者分别建模。"""

    remaining_hand: List[DoudizhuCard]
    hand_counts: Dict[str, int]
    last_play: Optional[DoudizhuComboInfo]
    last_play_player_id: Optional[str]
    next_player_id: str
    free_lead_player_id: Optional[str]
    consecutive_pass_count: int
    won: bool


def project_scoring_position(
    context: DoudizhuScoreContext,
    action: ResolvedGameAction,
) -> Optional[DoudizhuScoredPosition]:
    """依据已解析合法候选推演一次牌权变化，仅复制本人手牌和公开余牌数。"""
    ids = context.player_ids
    if (
        context.phase != PHASE_PLAYING
        or context.current_player_id != context.player_id
        or context.player_id not in ids
        or len(ids) != len(set(ids))
        or not context.hand_cards
        or action.playerId != context.player_id
    ):
        return None
    counts = {pid: int(context.players_by_id[pid]["handCount"]) for pid in ids}
    next_id = ids[(ids.index(context.player_id) + 1) % len(ids)]
    if action.actionType == ACTION_PLAY_CARDS:
        payload = action.payload or {}
        selected_ids = payload.get("cardInstanceIds") or []
        selected = set(selected_ids)
        actual_ids = {card.cardInstanceId for card in context.hand_cards}
        if not selected or len(selected) != len(selected_ids) or not selected.issubset(actual_ids):
            return None
        combo = resolve_combo_from_payload(context, payload, selected_ids)
        if combo is None:
            return None
        remaining = [card for card in context.hand_cards if card.cardInstanceId not in selected]
        counts[context.player_id] = len(remaining)
        return DoudizhuScoredPosition(
            remaining, counts, combo, context.player_id, next_id, None, 0, not remaining,
        )
    if action.actionType != ACTION_PASS or context.last_play is None:
        return None
    passes = context.consecutive_pass_count + 1
    lead = context.round_lead_player_id
    closed = passes >= len(ids) - 1
    if closed and lead not in ids:
        return None
    return DoudizhuScoredPosition(
        list(context.hand_cards), counts,
        None if closed else context.last_play,
        None if closed else context.last_play_player_id,
        lead if closed else next_id,
        lead if closed else None,
        0 if closed else passes,
        False,
    )


class DoudizhuPositionEvaluator(object):
    """以公开牌型、余牌数和座次估计阵营机会；分值不是概率或胜率。"""

    def __init__(self, config: DoudizhuActionScoreConfig) -> None:
        """保留本模块的启发式参数。"""
        self._config = config

    def opportunities(
        self,
        context: DoudizhuScoreContext,
        position: DoudizhuScoredPosition,
    ) -> Tuple[float, float]:
        """将总和为一的牌权权重乘 exp(-公开余牌数/scale)，分别汇总阵营。"""
        weights = self.lead_weights(context, position)
        own_landlord = context.player_id == context.landlord_player_id
        alliance = 0.0
        opponent = 0.0
        for pid, weight in weights.items():
            opportunity = weight * exp(-position.hand_counts[pid] / self._config.finish_distance_scale)
            if (pid == context.landlord_player_id) == own_landlord:
                alliance += opportunity
            else:
                opponent += opportunity
        return alliance, opponent

    def lead_weights(
        self,
        context: DoudizhuScoreContext,
        position: DoudizhuScoredPosition,
    ) -> Dict[str, float]:
        """自由首出归实际领牌者；应牌时仅计入到当前最大出牌者之前的响应席位。"""
        if position.free_lead_player_id:
            return {pid: float(pid == position.free_lead_player_id) for pid in context.player_ids}
        owner = position.last_play_player_id
        if owner not in context.player_ids or position.last_play is None:
            raise ValueError("评分局面缺少当前领牌者")
        raw = {pid: 0.0 for pid in context.player_ids}
        raw[owner] = 1.0
        next_index = context.player_ids.index(position.next_player_id)
        for offset in range(len(context.player_ids)):
            pid = context.player_ids[(next_index + offset) % len(context.player_ids)]
            if pid == owner:
                break
            raw[pid] = (
                self._config.response_order_decay ** offset
                * self._challenge(position.last_play, position.hand_counts[pid])
            )
        total = sum(raw.values())
        return {pid: value / total for pid, value in raw.items()}

    def _challenge(self, combo: DoudizhuComboInfo, count: int) -> float:
        """按同型上界与炸弹资源权重估计应牌空间，不查询未知手牌。"""
        if combo.isRocket or count <= 0:
            return 0.0
        cfg = self._config
        _, highest_rank = combo_rank_bounds(combo)
        upper_combo = combo.model_copy(update={"mainRankValue": highest_rank})
        same_type = 0.0
        if count >= combo.cardCount and can_beat(upper_combo, combo):
            type_weight = cfg.bomb_response_weight if combo.isBomb else cfg.ordinary_response_weight
            same_type = type_weight * (1.0 - combo_strength(combo))
        bomb = cfg.bomb_response_weight if count >= 4 and not combo.isBomb else 0.0
        rocket = cfg.rocket_response_weight if count >= 2 else 0.0
        return min(1.0, same_type + bomb + rocket)
