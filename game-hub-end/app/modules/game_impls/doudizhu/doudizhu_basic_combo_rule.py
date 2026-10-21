"""斗地主基础牌型识别：单牌、对子、三张、炸弹、王炸。"""

from typing import Dict, List, Optional

from app.modules.game_impls.doudizhu.doudizhu_combo_models import (
    ATTACHMENT_NONE,
    COMBO_BOMB,
    COMBO_LAIZI_BOMB,
    COMBO_PAIR,
    COMBO_ROCKET,
    COMBO_SINGLE,
    COMBO_TRIPLE,
    DoudizhuComboRuleConfig,
    base_combo_fields,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_combo_rule import match_fixed_counts
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import rank_value_for_code
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo

def try_rocket(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别王炸。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 王炸信息或 ``None``。
    """
    del naturals, config
    if len(cards) != 2 or laizis:
        return None
    if len(jokers) != 2:
        return None
    rank_codes = {card.rankCode for card in jokers}
    if rank_codes != {"small_joker", "big_joker"}:
        return None
    fields = base_combo_fields(cards, laizis, {})
    fields.update(
        {
            "comboType": COMBO_ROCKET,
            "mainRankCode": "big_joker",
            "mainRankValue": 17,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": True,
            "isRocket": True,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [16, 17],
        }
    )
    return DoudizhuComboInfo(**fields)


def try_natural_bomb(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别天然炸弹。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 炸弹信息或 ``None``。
    """
    del config
    if len(cards) != 4 or jokers or laizis:
        return None
    if len(naturals) != 1:
        return None
    rank_code, group = next(iter(naturals.items()))
    if len(group) != 4:
        return None
    rank_value = rank_value_for_code(rank_code)
    fields = base_combo_fields(cards, laizis, naturals)
    fields.update(
        {
            "comboType": COMBO_BOMB,
            "mainRankCode": rank_code,
            "mainRankValue": rank_value,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": True,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": True,
            "normalizedRankValues": [rank_value],
        }
    )
    return DoudizhuComboInfo(**fields)


def try_laizi_bomb(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别癞子炸弹。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 癞子炸弹信息或 ``None``。
    """
    if len(cards) != 4 or jokers or not config.enableLaizi or not laizis:
        return None
    for rank_code, group in naturals.items():
        if len(group) == 4:
            return None
    candidate_ranks = set(naturals.keys())
    if not naturals and laizis and config.laiziRankCode:
        candidate_ranks.add(config.laiziRankCode)
    for target_rank in sorted(
        candidate_ranks,
        key=lambda code: rank_value_for_code(code),
        reverse=True,
    ):
        other_count = sum(
            len(group)
            for code, group in naturals.items()
            if code != target_rank
        )
        if other_count > 0:
            continue
        natural_count = len(naturals.get(target_rank, []))
        if natural_count == 4:
            continue
        if natural_count + len(laizis) != 4:
            continue
        assignments = {
            card.cardInstanceId: target_rank for card in laizis
        }
        rank_value = rank_value_for_code(target_rank)
        fields = base_combo_fields(cards, laizis, naturals, assignments)
        fields.update(
            {
                "comboType": COMBO_LAIZI_BOMB,
                "mainRankCode": target_rank,
                "mainRankValue": rank_value,
                "chainLength": 1,
                "attachmentType": ATTACHMENT_NONE,
                "isBomb": True,
                "isRocket": False,
                "isLaiziBomb": True,
                "isNaturalBomb": False,
                "normalizedRankValues": [rank_value],
            }
        )
        return DoudizhuComboInfo(**fields)
    return None


def try_single(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别单张。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 单张信息或 ``None``。
    """
    del jokers, config
    if len(cards) != 1:
        return None
    card = cards[0]
    fields = base_combo_fields(cards, laizis, naturals)
    fields.update(
        {
            "comboType": COMBO_SINGLE,
            "mainRankCode": card.rankCode,
            "mainRankValue": card.rankValue,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [card.rankValue],
        }
    )
    return DoudizhuComboInfo(**fields)


def try_pair(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别对子。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 对子信息或 ``None``。
    """
    if jokers:
        return None
    if len(cards) != 2:
        return None
    match = match_fixed_counts(
        naturals,
        laizis,
        config,
        {None: 2},
        allow_laizi_fill=True,
    )
    if match is None:
        return None
    rank_code, assignments = match
    rank_value = rank_value_for_code(rank_code)
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_PAIR,
            "mainRankCode": rank_code,
            "mainRankValue": rank_value,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [rank_value],
        }
    )
    return DoudizhuComboInfo(**fields)


def try_triple(
    cards: List[DoudizhuCard],
    jokers: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    config: DoudizhuComboRuleConfig,
) -> Optional[DoudizhuComboInfo]:
    """
    尝试识别三张。

    :param cards: 全部牌。
    :param jokers: 王牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param config: 规则配置。
    :return: 三张信息或 ``None``。
    """
    if jokers:
        return None
    if len(cards) != 3:
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
    rank_code, assignments = match
    rank_value = rank_value_for_code(rank_code)
    fields = base_combo_fields(cards, laizis, naturals, assignments)
    fields.update(
        {
            "comboType": COMBO_TRIPLE,
            "mainRankCode": rank_code,
            "mainRankValue": rank_value,
            "chainLength": 1,
            "attachmentType": ATTACHMENT_NONE,
            "isBomb": False,
            "isRocket": False,
            "isLaiziBomb": False,
            "isNaturalBomb": False,
            "normalizedRankValues": [rank_value],
        }
    )
    return DoudizhuComboInfo(**fields)
