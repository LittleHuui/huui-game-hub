"""斗地主出牌候选结构化生成（斗地主私有，非公共层）。"""

from typing import Dict, List, Optional, Set, Tuple

from app.modules.game_impls.doudizhu.doudizhu_combo_rule import (
    DoudizhuComboRuleConfig,
    recognize_combo,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import partition_cards
from app.modules.game_impls.doudizhu.doudizhu_play_candidate_strategies import (
    _MAX_CANDIDATES,
    generate_airplane_candidates,
    generate_all_combo_card_sets,
    generate_bomb_candidates,
    generate_follow_combo_card_sets,
    generate_four_with_two_candidates,
    generate_pair_candidates,
    generate_pair_straight_candidates,
    generate_rocket_candidates,
    generate_single_candidates,
    generate_straight_candidates,
    generate_triple_attachment_candidates,
    generate_triple_candidates,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo


def enumerate_play_candidates_structured(
    hand_cards: List[DoudizhuCard],
    combo_config: DoudizhuComboRuleConfig,
    last_play: Optional[DoudizhuComboInfo],
) -> List[Tuple[DoudizhuComboInfo, List[DoudizhuCard]]]:
    """
    结构化生成可出牌型候选。

    :param hand_cards: 手牌列表。
    :param combo_config: 牌型配置。
    :param last_play: 上家出牌；为空表示首出。
    :return: ``(牌型, 牌列表)`` 候选。
    """
    if not hand_cards:
        return []
    ctx = group_cards_for_generation(hand_cards, combo_config)
    raw_sets = []  # type: List[List[DoudizhuCard]]
    if last_play is None:
        generate_all_combo_card_sets(ctx, combo_config, raw_sets)
    else:
        generate_follow_combo_card_sets(ctx, combo_config, last_play, raw_sets)
    candidates = []  # type: List[Tuple[DoudizhuComboInfo, List[DoudizhuCard]]]
    seen_ids = set()  # type: Set[Tuple[str, ...]]
    for cards in raw_sets:
        key = tuple(sorted(card.cardInstanceId for card in cards))
        if key in seen_ids:
            continue
        seen_ids.add(key)
        combo = recognize_combo(cards, combo_config, last_play)
        if combo is None:
            continue
        candidates.append((combo, cards))
        if len(candidates) >= _MAX_CANDIDATES:
            break
    return candidates


def group_cards_for_generation(
    hand_cards: List[DoudizhuCard],
    combo_config: DoudizhuComboRuleConfig,
) -> Dict[str, object]:
    """
    按点数分组并划分王牌、癞子与自然牌。

    :param hand_cards: 手牌列表。
    :param combo_config: 牌型配置。
    :return: 生成上下文。
    """
    jokers, laizis, naturals = partition_cards(
        hand_cards,
        combo_config.laiziRankCode,
        combo_config.enableLaizi,
    )
    return {
        "hand_cards": hand_cards,
        "jokers": jokers,
        "laizis": laizis,
        "naturals": naturals,
        "enable_laizi": combo_config.enableLaizi,
        "allow_single_attachment": combo_config.allowSingleAttachment,
        "laizi_rank_code": combo_config.laiziRankCode,
    }
