"""斗地主私有牌型强度特征，不参与合法性判定。"""

from typing import Tuple

from app.modules.game_impls.doudizhu.doudizhu_combo_rule import (
    COMBO_AIRPLANE,
    COMBO_AIRPLANE_WITH_PAIRS,
    COMBO_AIRPLANE_WITH_SINGLES,
    COMBO_PAIR_STRAIGHT,
    COMBO_SINGLE,
    COMBO_STRAIGHT,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuComboInfo


def combo_rank_bounds(combo: DoudizhuComboInfo) -> Tuple[int, int]:
    """返回同型比较主点数的区间，连续牌型按主体末端计算。"""
    if combo.comboType in (
        COMBO_STRAIGHT, COMBO_PAIR_STRAIGHT, COMBO_AIRPLANE,
        COMBO_AIRPLANE_WITH_PAIRS, COMBO_AIRPLANE_WITH_SINGLES,
    ):
        return 3 + max(1, combo.chainLength) - 1, 14
    return 3, 17 if combo.comboType == COMBO_SINGLE else 15


def combo_strength(combo: DoudizhuComboInfo) -> float:
    """将同型牌组点数映射到零至一；此值不是压制概率或胜率。"""
    if combo.isRocket:
        return 1.0
    lower, upper = combo_rank_bounds(combo)
    if upper <= lower:
        return 1.0
    return max(0.0, min(1.0, (combo.mainRankValue - lower) / float(upper - lower)))
