"""斗地主非出牌阶段评分（明牌、叫分、加倍及旧版叫抢）。"""

from typing import Tuple

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import DoudizhuActionScoreConfig
from app.modules.game_impls.doudizhu.doudizhu_bidding_rule import BID_SCORES
from app.modules.game_impls.doudizhu.doudizhu_rule_policy import CLASSIC_RULES_VERSION
from app.modules.game_impls.doudizhu.doudizhu_scorer_support import DoudizhuScoreContext
from app.modules.strategy_turn.schemas import ResolvedGameAction


class DoudizhuPhaseScorer(object):
    """斗地主阶段动作评分。"""

    def __init__(self, config: DoudizhuActionScoreConfig) -> None:
        """保存阶段评分的具名权重配置。"""
        self._config = config

    def score_showing_action(
        self,
        context: DoudizhuScoreContext,
        action: ResolvedGameAction,
        prefer_show: bool,
    ) -> Tuple[float, str]:
        """
        明牌阶段评分。

        :param context: 评分上下文。
        :param action: 合法动作。
        :param prefer_show: 是否为明牌动作。
        :return: 分值与标签。
        """
        del action
        cfg = self._config
        strength = context.hand_strength
        if prefer_show:
            if strength >= cfg.show_threshold:
                return cfg.show_when_strong + strength * cfg.show_strength_weight, "showStrong"
            return -cfg.skip_when_weak * cfg.show_weak_penalty_ratio, "showWeak"
        if strength < cfg.show_threshold:
            return cfg.skip_when_weak + (cfg.show_threshold - strength), "skipWeak"
        return -cfg.show_when_strong * cfg.skip_strong_penalty_ratio, "skipStrong"

    def score_calling_action(
        self,
        context: DoudizhuScoreContext,
        action: ResolvedGameAction,
        prefer_call: bool,
    ) -> Tuple[float, str]:
        """
        按本局版本评估经典叫分或旧版叫地主候选。

        :param context: 评分上下文。
        :param action: 合法动作。
        :param prefer_call: 是否为叫地主动作。
        :return: 分值与标签。
        """
        if context.rules_version == CLASSIC_RULES_VERSION:
            return self._score_bid_action(context, action, prefer_call)
        cfg = self._config
        strength = context.hand_strength
        if prefer_call:
            if self._all_other_players_called_pass(context):
                return (
                    cfg.call_when_all_others_passed + (cfg.call_threshold - strength),
                    "callAfterAllPass",
                )
            if strength >= cfg.call_threshold:
                return cfg.call_when_strong + strength * cfg.call_strength_weight, "callStrong"
            return -cfg.pass_call_when_weak * cfg.call_weak_penalty_ratio, "callWeak"
        if strength < cfg.call_threshold:
            return cfg.pass_call_when_weak + (cfg.call_threshold - strength), "passWeak"
        return -cfg.call_when_strong * cfg.pass_call_strong_penalty_ratio, "passStrong"

    def _score_bid_action(
        self,
        context: DoudizhuScoreContext,
        action: ResolvedGameAction,
        prefer_call: bool,
    ) -> Tuple[float, str]:
        """按手牌强度确定愿承担的档位，候选评分不改变合法叫分规则。"""
        cfg = self._config
        supported_scores = [
            score for score, threshold in zip(BID_SCORES, cfg.bid_strength_thresholds)
            if context.hand_strength >= threshold
        ]
        desired_score = max(supported_scores, default=0)
        can_raise = desired_score > context.highest_bid_score
        if not prefer_call:
            return (cfg.bid_preferred_score if not can_raise else -cfg.bid_preferred_score), "bidPass"
        bid_score = int(action.payload["bidScore"])
        distance = abs(bid_score - desired_score)
        overbid = max(0, bid_score - desired_score)
        value = (
            cfg.bid_preferred_score
            - distance * cfg.bid_distance_penalty
            - overbid * cfg.bid_overreach_penalty
        )
        return value, "bidScore{0}".format(bid_score)

    def _all_other_players_called_pass(self, context: DoudizhuScoreContext) -> bool:
        """
        判断旧叫地主流程中，其余玩家是否均已明确不叫。

        :param context: 评分上下文。
        :return: 其余玩家均已选择不叫时返回 ``True``。
        """
        players = context.players_by_id
        if len(players) < 2:
            return False
        for player_id, player in players.items():
            if player_id == context.player_id:
                continue
            if not bool(player.get("callDecided")) or int(player.get("bidScore") or 0) > 0:
                return False
        return True

    def score_robbing_action(
        self,
        context: DoudizhuScoreContext,
        action: ResolvedGameAction,
        prefer_rob: bool,
    ) -> Tuple[float, str]:
        """
        抢地主阶段评分。

        :param context: 评分上下文。
        :param action: 合法动作。
        :param prefer_rob: 是否为抢地主动作。
        :return: 分值与标签。
        """
        del action
        cfg = self._config
        strength = context.hand_strength
        if prefer_rob:
            if strength >= cfg.rob_threshold:
                return cfg.rob_when_very_strong + strength * cfg.rob_strength_weight, "robStrong"
            return -cfg.pass_rob_when_moderate * cfg.rob_weak_penalty_ratio, "robWeak"
        if strength < cfg.rob_threshold:
            return cfg.pass_rob_when_moderate + (cfg.rob_threshold - strength), "passRob"
        return -cfg.rob_when_very_strong * cfg.pass_rob_strong_penalty_ratio, "passStrong"

    def score_doubling_action(
        self,
        context: DoudizhuScoreContext,
        action: ResolvedGameAction,
        prefer_double: bool,
    ) -> Tuple[float, str]:
        """
        加倍阶段评分。

        :param context: 评分上下文。
        :param action: 合法动作。
        :param prefer_double: 是否为加倍动作。
        :return: 分值与标签。
        """
        del action
        cfg = self._config
        strength = context.hand_strength
        bonus = 0.0
        if context.is_landlord and strength >= cfg.double_threshold:
            bonus += cfg.double_landlord_bonus
        if context.is_farmer and context.landlord_player_id:
            landlord_info = context.players_by_id.get(context.landlord_player_id) or {}
            if bool(landlord_info.get("showCards")):
                bonus += cfg.double_farmer_vs_weak_landlord * cfg.double_farmer_bonus_ratio
        effective_strength = strength + bonus
        if prefer_double:
            if effective_strength >= cfg.double_threshold:
                return cfg.double_when_strong + effective_strength * cfg.double_strength_weight, "doubleStrong"
            return -cfg.pass_double_when_weak * cfg.double_weak_penalty_ratio, "doubleWeak"
        if effective_strength < cfg.double_threshold:
            return cfg.pass_double_when_weak + (cfg.double_threshold - effective_strength), "passDouble"
        return -cfg.double_when_strong * cfg.pass_double_strong_penalty_ratio, "passStrong"
