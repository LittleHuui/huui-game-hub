"""斗地主连续牌型识别：顺子、连对、飞机主体。"""

from typing import Dict, List, Optional

from app.modules.game_impls.doudizhu.doudizhu_combo_models import (
    ATTACHMENT_NONE,
    COMBO_AIRPLANE,
    COMBO_PAIR_STRAIGHT,
    COMBO_STRAIGHT,
    AIRPLANE_MIN_GROUPS,
    PAIR_STRAIGHT_MIN_PAIRS,
    STRAIGHT_MIN_LENGTH,
    DoudizhuComboRuleConfig,
    base_combo_fields,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_combo_rule import (
    match_consecutive_pairs,
    match_consecutive_singles,
    match_consecutive_triples,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import rank_code_for_value
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo

def try_straight(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别顺子。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 顺子信息或 ``None``。
    """
    if jokers:
        return None
    length = len(cards)
    if length < STRAIGHT_MIN_LENGTH:
        return None
    match = match_consecutive_singles(naturals, laizis, config, length)
    if match is None:
        return None
    main_value, assignments = match
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_STRAIGHT,
            "mainRankCode": rank_code_for_value(main_value),
            "mainRankValue": main_value,
            "chainLength": length,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": list(range(main_value - length + 1, main_value + 1)),
        }
    )
    return DoudizhuComboInfo(**fields)


def try_pair_straight(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别连对。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 连对信息或 ``None``。
    """
    if jokers:
        return None
    if len(cards) % 2 != 0:
        return None
    pair_count = len(cards) // 2
    if pair_count < PAIR_STRAIGHT_MIN_PAIRS:
        return None
    match = match_consecutive_pairs(naturals, laizis, config, pair_count)
    if match is None:
        return None
    main_value, assignments = match
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_PAIR_STRAIGHT,
            "mainRankCode": rank_code_for_value(main_value),
            "mainRankValue": main_value,
            "chainLength": pair_count,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": list(
                range(main_value - pair_count + 1, main_value + 1)
            ),
        }
    )
    return DoudizhuComboInfo(**fields)


def try_airplane(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别飞机不带。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 飞机信息或 ``None``。
    """
    if jokers:
        return None
    if len(cards) % 3 != 0:
        return None
    group_count = len(cards) // 3
    if group_count < AIRPLANE_MIN_GROUPS:
        return None
    match = match_consecutive_triples(naturals, laizis, config, group_count)
    if match is None:
        return None
    main_value, assignments = match
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_AIRPLANE,
            "mainRankCode": rank_code_for_value(main_value),
            "mainRankValue": main_value,
            "chainLength": group_count,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": list(
                range(main_value - group_count + 1, main_value + 1)
            ),
        }
    )
    return DoudizhuComboInfo(**fields)
