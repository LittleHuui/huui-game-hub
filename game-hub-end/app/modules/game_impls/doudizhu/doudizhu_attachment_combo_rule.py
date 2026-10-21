"""斗地主附带牌型识别：三带、飞机带牌、四带牌。"""

from typing import Dict, List, Optional

from app.modules.game_impls.doudizhu.doudizhu_combo_models import (
    ATTACHMENT_PAIR,
    ATTACHMENT_SINGLE,
    COMBO_AIRPLANE_WITH_PAIRS,
    COMBO_AIRPLANE_WITH_SINGLES,
    COMBO_FOUR_WITH_TWO_PAIRS,
    COMBO_FOUR_WITH_TWO_SINGLES,
    COMBO_TRIPLE_WITH_PAIR,
    COMBO_TRIPLE_WITH_SINGLE,
    AIRPLANE_MIN_GROUPS,
    DoudizhuComboRuleConfig,
    base_combo_fields,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_combo_rule import (
    match_airplane_with_attachments,
    match_fixed_counts,
    match_four_with_attachments,
    match_two_rank_counts,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import rank_code_for_value, rank_value_for_code
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo

def try_triple_with_single(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别三带一。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 三带一信息或 ``None``。
    """
    if len(cards) != 4 or not config.allowSingleAttachment:
        return None
    if jokers:
        if len(jokers) != 1:
            return None
        match = match_fixed_counts(
            naturals,
            laizis,
            config,
            {None: 3},
            allow_laizi_fill=True,
        )
        if match is None:
            return None
        main_rank, assignments = match
        rank_value = rank_value_for_code(main_rank)
        fields = base_combo_fields(cards, laizis, naturals, assignments)
        fields.update(
            {
                "comboType": COMBO_TRIPLE_WITH_SINGLE,
                "mainRankCode": main_rank,
                "mainRankValue": rank_value,
                "chainLength": 1,
                "attachmentType": ATTACHMENT_SINGLE,
                "isBomb": False,
                "isRocket": False,
                "isLaiziBomb": False,
                "isNaturalBomb": False,
                "normalizedRankValues": [rank_value],
            }
        )
        return DoudizhuComboInfo(**fields)
    match = match_two_rank_counts(
        naturals,
        laizis,
        config,
        main_count=3,
        attach_count=1,
    )
    if match is None:
        return None
    main_rank, assignments = match
    rank_value = rank_value_for_code(main_rank)
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_TRIPLE_WITH_SINGLE,
            "mainRankCode": main_rank,
            "mainRankValue": rank_value,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_SINGLE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [rank_value],
        }
    )
    return DoudizhuComboInfo(**fields)


def try_triple_with_pair(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别三带一对。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 三带一对信息或 ``None``。
    """
    if jokers:
        return None
    if len(cards) != 5:
        return None
    match = match_two_rank_counts(
        naturals,
        laizis,
        config,
        main_count=3,
        attach_count=2,
    )
    if match is None:
        return None
    main_rank, assignments = match
    rank_value = rank_value_for_code(main_rank)
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_TRIPLE_WITH_PAIR,
            "mainRankCode": main_rank,
            "mainRankValue": rank_value,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_PAIR,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [rank_value],
        }
    )
    return DoudizhuComboInfo(**fields)
def try_airplane_with_singles(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别飞机带单。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 飞机带单信息或 ``None``。
    """
    if not config.allowSingleAttachment or len(cards) % 4 != 0:
        return None
    group_count = len(cards) // 4
    if group_count < AIRPLANE_MIN_GROUPS:
        return None
    if jokers and len(jokers) > group_count:
        return None
    match = match_airplane_with_attachments(
        naturals,
        laizis,
        config,
        group_count,
        attachment_size=1,
        joker_single_count=len(jokers),
    )
    if match is None:
        return None
    main_value, assignments = match
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_AIRPLANE_WITH_SINGLES,
            "mainRankCode": rank_code_for_value(main_value),
            "mainRankValue": main_value,
            "chainLength": group_count,
            "attachmentType": ATTACHMENT_SINGLE,
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


def try_airplane_with_pairs(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别飞机带对。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 飞机带对信息或 ``None``。
    """
    if jokers:
        return None
    if len(cards) % 5 != 0:
        return None
    group_count = len(cards) // 5
    if group_count < AIRPLANE_MIN_GROUPS:
        return None
    match = match_airplane_with_attachments(
        naturals,
        laizis,
        config,
        group_count,
        attachment_size=2,
    )
    if match is None:
        return None
    main_value, assignments = match
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_AIRPLANE_WITH_PAIRS,
            "mainRankCode": rank_code_for_value(main_value),
            "mainRankValue": main_value,
            "chainLength": group_count,
            "attachmentType": ATTACHMENT_PAIR,
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


def try_four_with_two_singles(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别四带二单。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 四带二单信息或 ``None``。
    """
    if len(cards) != 6:
        return None
    if jokers and len(jokers) > 2:
        return None
    match = match_four_with_attachments(
        naturals,
        laizis,
        config,
        single_attachments=2,
        pair_attachments=0,
        joker_single_count=len(jokers),
    )
    if match is None:
        return None
    main_rank, assignments = match
    rank_value = rank_value_for_code(main_rank)
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_FOUR_WITH_TWO_SINGLES,
            "mainRankCode": main_rank,
            "mainRankValue": rank_value,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_SINGLE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [rank_value],
        }
    )
    return DoudizhuComboInfo(**fields)


def try_four_with_two_pairs(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别四带二对。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 四带二对信息或 ``None``。
    """
    if jokers:
        return None
    if len(cards) != 8:
        return None
    match = match_four_with_attachments(
        naturals,
        laizis,
        config,
        single_attachments=0,
        pair_attachments=2,
    )
    if match is None:
        return None
    main_rank, assignments = match
    rank_value = rank_value_for_code(main_rank)
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_FOUR_WITH_TWO_PAIRS,
            "mainRankCode": main_rank,
            "mainRankValue": rank_value,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_PAIR,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [rank_value],
        }
    )
    return DoudizhuComboInfo(**fields)
