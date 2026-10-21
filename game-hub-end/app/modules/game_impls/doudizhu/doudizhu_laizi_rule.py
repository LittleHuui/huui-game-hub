"""斗地主癞子规则：癞子确定、标记与归一辅助。"""

import random
from typing import Dict, List, Optional, Tuple

from app.modules.game_impls.doudizhu.doudizhu_constants import DOUDIZHU_RANK_SPECS
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuLaiziUsage

# 顺子/连对/飞机允许的最大点数值（A）
_STRAIGHT_MAX_RANK_VALUE = 14

# rankCode -> rankValue 映射
_RANK_CODE_TO_VALUE = {spec[0]: spec[2] for spec in DOUDIZHU_RANK_SPECS}
_RANK_VALUE_TO_CODE = {spec[2]: spec[0] for spec in DOUDIZHU_RANK_SPECS}


def generate_laizi_rank_code() -> str:
    """
    在发牌前从普通点数中等概率确定癞子，不依赖牌堆或底牌。

    :return: 3 至 2 的普通点数编码，不包含大小王。
    """
    return random.choice(DOUDIZHU_RANK_SPECS)[0]


def is_laizi_card(
    card: DoudizhuCard,
    laizi_rank_code: Optional[str],
    enable_laizi: bool,
) -> bool:
    """
    判断单张牌在当前规则下是否为癞子。

    :param card: 牌实例。
    :param laizi_rank_code: 癞子点数编码。
    :param enable_laizi: 是否开启癞子玩法。
    :return: 是癞子为 ``True``。
    """
    if not enable_laizi or laizi_rank_code is None:
        return False
    if card.isJoker:
        return False
    return card.rankCode == laizi_rank_code


def mark_laizi_on_cards(
    cards: List[DoudizhuCard],
    laizi_rank_code: Optional[str],
    enable_laizi: bool,
) -> List[DoudizhuCard]:
    """
    为牌列表标记 ``isLaizi`` 字段（返回新实例，不修改入参）。

    :param cards: 原始牌列表。
    :param laizi_rank_code: 癞子点数编码。
    :param enable_laizi: 是否开启癞子玩法。
    :return: 标记后的牌列表。
    """
    marked = []
    for card in cards:
        is_laizi = is_laizi_card(card, laizi_rank_code, enable_laizi)
        if card.isLaizi == is_laizi:
            marked.append(card)
        else:
            marked.append(card.model_copy(update={"isLaizi": is_laizi}))
    return marked


def partition_cards(
    cards: List[DoudizhuCard],
    laizi_rank_code: Optional[str],
    enable_laizi: bool,
) -> Tuple[List[DoudizhuCard], List[DoudizhuCard], Dict[str, List[DoudizhuCard]]]:
    """
    将牌划分为王牌、癞子牌与自然牌。

    :param cards: 待划分牌列表。
    :param laizi_rank_code: 癞子点数编码。
    :param enable_laizi: 是否开启癞子玩法。
    :return: ``(王牌列表, 癞子列表, 自然牌按 rankCode 分组)``。
    """
    jokers = []  # type: List[DoudizhuCard]
    laizis = []  # type: List[DoudizhuCard]
    naturals = {}  # type: Dict[str, List[DoudizhuCard]]
    for card in cards:
        if card.isJoker:
            jokers.append(card)
        elif is_laizi_card(card, laizi_rank_code, enable_laizi):
            laizis.append(card)
        else:
            naturals.setdefault(card.rankCode, []).append(card)
    return jokers, laizis, naturals


def rank_value_for_code(rank_code: str) -> int:
    """
    获取点数编码对应的排序值。

    :param rank_code: 点数编码。
    :return: 点数值。
    """
    return _RANK_CODE_TO_VALUE[rank_code]


def rank_code_for_value(rank_value: int) -> str:
    """
    获取排序值对应的点数编码。

    :param rank_value: 点数值。
    :return: 点数编码。
    """
    return _RANK_VALUE_TO_CODE[rank_value]


def is_straight_eligible_rank_value(rank_value: int) -> bool:
    """
    判断点数值是否可用于顺子/连对/飞机主体。

    :param rank_value: 点数值。
    :return: 可用为 ``True``（排除 2 与王牌）。
    """
    return 3 <= rank_value <= _STRAIGHT_MAX_RANK_VALUE


def build_laizi_usage(
    laizi_cards: List[DoudizhuCard],
    assignments: Dict[str, str],
) -> List[DoudizhuLaiziUsage]:
    """
    根据癞子归一分配构建使用明细。

    :param laizi_cards: 癞子牌列表。
    :param assignments: 癞子实例 ID -> 归一点数编码。
    :return: 癞子使用明细列表。
    """
    usage = []
    for card in laizi_cards:
        assigned_code = assignments.get(card.cardInstanceId)
        if assigned_code is None:
            continue
        usage.append(
            DoudizhuLaiziUsage(
                laiziCardInstanceId=card.cardInstanceId,
                assignedRankCode=assigned_code,
                assignedRankValue=rank_value_for_code(assigned_code),
            )
        )
    return usage
