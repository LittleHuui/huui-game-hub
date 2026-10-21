"""斗地主非出牌阶段评分（明牌、叫地主、抢地主、加倍）。"""

from typing import Tuple

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import DoudizhuActionScoreConfig
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
        叫地主阶段评分。

        :param context: 评分上下文。
        :param action: 合法动作。
        :param prefer_call: 是否为叫地主动作。
        :return: 分值与标签。
        """
        del action
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

    def _all_other_players_called_pass(self, context: DoudizhuScoreContext) -> bool:
        """
        判断当前玩家是否为本轮唯一尚未决定叫地主的玩家。

        :param context: 评分上下文。
        :return: 其余玩家均已选择不叫时返回 ``True``。
        """
        players = context.players_by_id
        if len(players) < 2:
            return False
        for player_id, player in players.items():
            if player_id == context.player_id:
                continue
            if not bool(player.get("callDecided")):
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
