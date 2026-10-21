"""斗地主提示为空时的合法出牌存在性核验，不参与自动决策候选排序。"""

from time import monotonic
from typing import Dict, Iterator, List, Optional, Tuple

from app.modules.game_impls.doudizhu.doudizhu_combo_rule import (
    DoudizhuComboRuleConfig,
    recognize_combo,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo

_MAX_HINT_VERIFICATION_PICKS = 50000
_MAX_HINT_VERIFICATION_SECONDS = 0.2


def find_legal_hint_play(
    hand_cards: List[DoudizhuCard],
    combo_config: DoudizhuComboRuleConfig,
    last_play: Optional[DoudizhuComboInfo],
) -> Tuple[Optional[List[DoudizhuCard]], bool]:
    """
    用现有规则核验是否存在合法出牌，仅穷尽后才能确认没有可出的牌。

    :param hand_cards: 当前玩家手牌。
    :param combo_config: 当前牌型规则。
    :param last_play: 待压过的牌型；首出只需寻找单张。
    :return: 首组合法牌及搜索是否完成；预算耗尽返回 ``(None, False)``。
    """
    deadline = monotonic() + _MAX_HINT_VERIFICATION_SECONDS
    groups_by_rank = {}  # type: Dict[Tuple[str, int, bool], List[DoudizhuCard]]
    for card in hand_cards:
        key = (card.rankCode, card.rankValue, card.isJoker)
        groups_by_rank.setdefault(key, []).append(card)
    groups = list(groups_by_rank.values())
    # 现有比较规则只允许同张数牌型、四张炸弹和两张王炸；花色及实例 ID 不影响大小。
    sizes = {1} if last_play is None else {2, 4, int(last_play.cardCount)}
    checked = 0
    for size in sorted(sizes):
        if size <= 0 or size > len(hand_cards):
            continue
        for cards in _iter_rank_selections(groups, size):
            if checked >= _MAX_HINT_VERIFICATION_PICKS or monotonic() >= deadline:
                return None, False
            checked += 1
            combo = recognize_combo(cards, combo_config, last_play)
            if combo is not None:
                return cards, True
    return None, monotonic() < deadline


def _iter_rank_selections(
    groups: List[List[DoudizhuCard]],
    size: int,
) -> Iterator[List[DoudizhuCard]]:
    """
    按同点数牌的数量枚举等价选择，避免重复枚举不同花色和实例组合。

    :param groups: 规则等价的手牌分组。
    :param size: 本次选择张数。
    :return: 覆盖所有点数数量组合的牌组迭代器。
    """
    remaining_counts = [0] * (len(groups) + 1)
    for index in range(len(groups) - 1, -1, -1):
        remaining_counts[index] = remaining_counts[index + 1] + len(groups[index])

    def visit(index: int, needed: int, selected: List[DoudizhuCard]) -> Iterator[List[DoudizhuCard]]:
        """逐组选择张数，并按剩余总张数剪去不可能分支。"""
        if needed == 0:
            yield selected
            return
        if index >= len(groups) or remaining_counts[index] < needed:
            return
        group = groups[index]
        minimum = max(0, needed - remaining_counts[index + 1])
        for count in range(minimum, min(len(group), needed) + 1):
            yield from visit(index + 1, needed - count, selected + group[:count])

    yield from visit(0, size, [])
