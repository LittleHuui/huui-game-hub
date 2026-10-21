"""斗地主牌型枚举、配置与公共字段构建。"""

from typing import Dict, List, Optional

from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import build_laizi_usage
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard

COMBO_SINGLE = "SINGLE"
COMBO_PAIR = "PAIR"
COMBO_TRIPLE = "TRIPLE"
COMBO_TRIPLE_WITH_SINGLE = "TRIPLE_WITH_SINGLE"
COMBO_TRIPLE_WITH_PAIR = "TRIPLE_WITH_PAIR"
COMBO_STRAIGHT = "STRAIGHT"
COMBO_PAIR_STRAIGHT = "PAIR_STRAIGHT"
COMBO_AIRPLANE = "AIRPLANE"
COMBO_AIRPLANE_WITH_SINGLES = "AIRPLANE_WITH_SINGLES"
COMBO_AIRPLANE_WITH_PAIRS = "AIRPLANE_WITH_PAIRS"
COMBO_FOUR_WITH_TWO_SINGLES = "FOUR_WITH_TWO_SINGLES"
COMBO_FOUR_WITH_TWO_PAIRS = "FOUR_WITH_TWO_PAIRS"
COMBO_BOMB = "BOMB"
COMBO_LAIZI_BOMB = "LAIZI_BOMB"
COMBO_ROCKET = "ROCKET"

STRAIGHT_MIN_LENGTH = 5
PAIR_STRAIGHT_MIN_PAIRS = 3
AIRPLANE_MIN_GROUPS = 2

ATTACHMENT_NONE = "NONE"
ATTACHMENT_SINGLE = "SINGLE"
ATTACHMENT_PAIR = "PAIR"


class DoudizhuComboRuleConfig(object):
    """斗地主牌型识别配置。"""

    def __init__(
        self,
        enable_laizi: bool = False,
        allow_single_attachment: bool = True,
        laizi_rank_code: Optional[str] = None,
    ) -> None:
        """
        初始化牌型识别配置。

        :param enable_laizi: 是否开启癞子。
        :param allow_single_attachment: 是否允许三带一、飞机带单。
        :param laizi_rank_code: 癞子点数编码。
        """
        self.enableLaizi = enable_laizi
        self.allowSingleAttachment = allow_single_attachment
        self.laiziRankCode = laizi_rank_code


def card_ids(cards: List[DoudizhuCard]) -> List[str]:
    """
    提取牌实例 ID 列表。

    :param cards: 牌列表。
    :return: ID 列表。
    """
    return [card.cardInstanceId for card in cards]


def base_combo_fields(
    cards: List[DoudizhuCard],
    laizis: List[DoudizhuCard],
    naturals: Dict[str, List[DoudizhuCard]],
    laizi_assignments: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    """
    构建 ComboInfo 公共字段片段。

    :param cards: 全部牌。
    :param laizis: 癞子牌。
    :param naturals: 自然牌分组。
    :param laizi_assignments: 癞子归一分配。
    :return: 公共字段字典。
    """
    natural_count = sum(len(group) for group in naturals.values())
    laizi_count = len(laizis)
    assignments = laizi_assignments or {}
    return {
        "cardInstanceIds": card_ids(cards),
        "cardCount": len(cards),
        "isLaiziCombo": laizi_count > 0,
        "naturalCardCount": natural_count,
        "laiziCardCount": laizi_count,
        "laiziUsage": build_laizi_usage(laizis, assignments),
    }
