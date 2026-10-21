"""斗地主牌型识别 Facade（统一入口）。"""

from typing import List, Optional

from app.modules.game_impls.doudizhu.doudizhu_attachment_combo_rule import (
    try_airplane_with_pairs,
    try_airplane_with_singles,
    try_four_with_two_pairs,
    try_four_with_two_singles,
    try_triple_with_pair,
    try_triple_with_single,
)
from app.modules.game_impls.doudizhu.doudizhu_basic_combo_rule import (
    try_laizi_bomb,
    try_natural_bomb,
    try_pair,
    try_rocket,
    try_single,
    try_triple,
)
from app.modules.game_impls.doudizhu.doudizhu_combo_comparator import can_beat
from app.modules.game_impls.doudizhu.doudizhu_combo_models import (
    AIRPLANE_MIN_GROUPS,
    ATTACHMENT_NONE,
    ATTACHMENT_PAIR,
    ATTACHMENT_SINGLE,
    COMBO_AIRPLANE,
    COMBO_AIRPLANE_WITH_PAIRS,
    COMBO_AIRPLANE_WITH_SINGLES,
    COMBO_BOMB,
    COMBO_FOUR_WITH_TWO_PAIRS,
    COMBO_FOUR_WITH_TWO_SINGLES,
    COMBO_LAIZI_BOMB,
    COMBO_PAIR,
    COMBO_PAIR_STRAIGHT,
    COMBO_ROCKET,
    COMBO_SINGLE,
    COMBO_STRAIGHT,
    COMBO_TRIPLE,
    COMBO_TRIPLE_WITH_PAIR,
    COMBO_TRIPLE_WITH_SINGLE,
    DoudizhuComboRuleConfig,
    PAIR_STRAIGHT_MIN_PAIRS,
    STRAIGHT_MIN_LENGTH,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import partition_cards
from app.modules.game_impls.doudizhu.doudizhu_sequence_combo_rule import (
    try_airplane,
    try_pair_straight,
    try_straight,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo


def recognize_combo(
    cards: List[DoudizhuCard],
    config: Optional[DoudizhuComboRuleConfig] = None,
    target: Optional[DoudizhuComboInfo] = None,
) -> Optional[DoudizhuComboInfo]:
    """
    按固定家族优先级识别牌型；跟牌时选择可压过目标的解释。

    :param cards: 待识别牌列表。
    :param config: 规则配置；默认关闭癞子且允许带单。
    :param target: 待压过的牌型；为空时仅识别牌组。
    :return: 牌型信息；不存在符合上下文的解释时返回 ``None``。
    """
    if not cards:
        return None
    # 实例顺序只用于稳定元数据及癞子分配，不参与牌型大小判定。
    ordered_cards = sorted(cards, key=lambda card: card.cardInstanceId)
    rule_config = config or DoudizhuComboRuleConfig()
    jokers, laizis, naturals = partition_cards(
        ordered_cards,
        rule_config.laiziRankCode,
        rule_config.enableLaizi,
    )
    detectors = [
        try_rocket,
        try_natural_bomb,
        try_laizi_bomb,
        try_four_with_two_pairs,
        try_four_with_two_singles,
        try_airplane_with_pairs,
        try_airplane_with_singles,
        try_airplane,
        try_pair_straight,
        try_straight,
        try_triple_with_pair,
        try_triple_with_single,
        try_triple,
        try_pair,
        try_single,
    ]
    for detector in detectors:
        combo = detector(ordered_cards, jokers, laizis, naturals, rule_config)
        if combo is not None and can_beat(combo, target):
            return combo
    return None


__all__ = [
    "AIRPLANE_MIN_GROUPS",
    "ATTACHMENT_NONE",
    "ATTACHMENT_PAIR",
    "ATTACHMENT_SINGLE",
    "COMBO_AIRPLANE",
    "COMBO_AIRPLANE_WITH_PAIRS",
    "COMBO_AIRPLANE_WITH_SINGLES",
    "COMBO_BOMB",
    "COMBO_FOUR_WITH_TWO_PAIRS",
    "COMBO_FOUR_WITH_TWO_SINGLES",
    "COMBO_LAIZI_BOMB",
    "COMBO_PAIR",
    "COMBO_PAIR_STRAIGHT",
    "COMBO_ROCKET",
    "COMBO_SINGLE",
    "COMBO_STRAIGHT",
    "COMBO_TRIPLE",
    "COMBO_TRIPLE_WITH_PAIR",
    "COMBO_TRIPLE_WITH_SINGLE",
    "DoudizhuComboRuleConfig",
    "PAIR_STRAIGHT_MIN_PAIRS",
    "STRAIGHT_MIN_LENGTH",
    "can_beat",
    "recognize_combo",
]
