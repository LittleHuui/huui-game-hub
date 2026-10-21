"""斗地主手牌强度与结构潜力特征提取。"""

from typing import Dict, List

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import DoudizhuActionScoreConfig
from app.modules.game_impls.doudizhu.doudizhu_combo_rule import DoudizhuComboRuleConfig
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import partition_cards
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard


class DoudizhuHandStrengthEvaluator(object):
    """斗地主手牌强度评估器。"""

    def __init__(self, config: DoudizhuActionScoreConfig) -> None:
        self._config = config

    def evaluate_hand_strength(
        self,
        hand_cards: List[DoudizhuCard],
        combo_config: DoudizhuComboRuleConfig,
    ) -> float:
        """
        评估手牌整体强度。

        :param hand_cards: 手牌列表。
        :param combo_config: 牌型配置。
        :return: 强度分。
        """
        if not hand_cards:
            return 0.0
        cfg = self._config
        score = 0.0
        jokers, laizis, naturals = partition_cards(
            hand_cards,
            combo_config.laiziRankCode,
            combo_config.enableLaizi,
        )
        if len(jokers) == 2:
            score += cfg.strength_rocket
        score += len(laizis) * cfg.strength_laizi_each
        for rank_code, cards in naturals.items():
            if rank_code == "2":
                score += len(cards) * cfg.strength_rank2_each
            elif rank_code == "A":
                score += len(cards) * cfg.strength_rank_a_each
            if len(cards) == 4:
                score += cfg.strength_bomb_each
        singletons = 0
        pairs = 0
        for rank_code, cards in naturals.items():
            count = len(cards)
            if count == 1:
                singletons += 1
                if cards[0].rankValue <= 10:
                    score += cfg.strength_singleton_small_penalty
            elif count == 2:
                pairs += 1
        score += pairs * cfg.strength_pair_count_bonus
        if self.has_long_straight_potential(naturals):
            score += cfg.strength_long_straight
        if self.has_airplane_potential(naturals):
            score += cfg.strength_airplane_body
        if singletons >= 5:
            score += cfg.strength_fragment_penalty * (singletons - 4)
        return score

    def has_long_straight_potential(self, naturals: Dict[str, List[DoudizhuCard]]) -> bool:
        """
        检测手牌是否存在较长顺子潜力。

        :param naturals: 天然牌按点数分组。
        :return: 有潜力为 ``True``。
        """
        values = []
        for rank_code, cards in naturals.items():
            if not cards:
                continue
            if cards[0].rankValue >= 15:
                continue
            values.append(cards[0].rankValue)
        if len(values) < 5:
            return False
        values = sorted(set(values))
        best_run = 1
        current_run = 1
        for index in range(1, len(values)):
            if values[index] == values[index - 1] + 1:
                current_run += 1
                best_run = max(best_run, current_run)
            else:
                current_run = 1
        return best_run >= 5

    def has_airplane_potential(self, naturals: Dict[str, List[DoudizhuCard]]) -> bool:
        """
        检测手牌是否存在飞机主体潜力。

        :param naturals: 天然牌按点数分组。
        :return: 有潜力为 ``True``。
        """
        triple_values = sorted(
            cards[0].rankValue
            for rank_code, cards in naturals.items()
            if len(cards) >= 3 and rank_code not in ("2", "small_joker", "big_joker")
        )
        if len(triple_values) < 2:
            return False
        for index in range(len(triple_values) - 1):
            if triple_values[index + 1] == triple_values[index] + 1:
                return True
        return False
