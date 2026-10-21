"""斗地主出牌候选生成策略（按牌型枚举牌组）。"""

from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from app.modules.game_impls.doudizhu.doudizhu_combo_rule import (
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
    can_beat,
    recognize_combo,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import (
    partition_cards,
    rank_code_for_value,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo

_STRAIGHT_MIN_LENGTH = 5
_PAIR_STRAIGHT_MIN_PAIRS = 3
_AIRPLANE_MIN_GROUPS = 2
_MAX_CANDIDATES = 1000
_MAX_ATTACHMENT_VARIANTS = 4
_MAX_SMALL_COMBO_PICKS = 8

_BOMB_TYPES = frozenset([COMBO_BOMB, COMBO_LAIZI_BOMB, COMBO_ROCKET])


def append_card_set(
    collector: List[List[DoudizhuCard]],
    cards: List[DoudizhuCard],
) -> None:
    """
    向收集器追加一组候选牌（去重实例 ID）。

    :param collector: 候选牌组列表。
    :param cards: 待追加牌组。
    :return: 无。
    """
    if not cards:
        return
    if len(collector) >= _MAX_CANDIDATES:
        return
    collector.append(list(cards))


def sort_cards_for_pick(cards: List[DoudizhuCard]) -> List[DoudizhuCard]:
    """
    按点数、花色、实例 ID 排序，便于规范化选牌。

    :param cards: 待排序牌列表。
    :return: 排序后的牌列表。
    """
    return sorted(
        cards,
        key=lambda card: (card.rankValue, card.suitCode or "", card.cardInstanceId),
    )


def generate_all_combo_card_sets(
    ctx: Dict[str, object],
    combo_config: DoudizhuComboRuleConfig,
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    首出场景：生成全部牌型候选牌组。

    :param ctx: 生成上下文。
    :param combo_config: 牌型配置。
    :param collector: 输出收集器。
    :return: 无。
    """
    generate_rocket_candidates(ctx, collector)
    generate_bomb_candidates(ctx, collector)
    generate_four_with_two_candidates(ctx, combo_config, collector)
    generate_airplane_candidates(ctx, combo_config, collector)
    generate_pair_straight_candidates(ctx, collector)
    generate_straight_candidates(ctx, collector)
    generate_triple_attachment_candidates(ctx, combo_config, collector)
    generate_triple_candidates(ctx, collector)
    generate_pair_candidates(ctx, collector)
    generate_single_candidates(ctx, collector)
    append_card_set(collector, list(ctx["hand_cards"]))


def generate_follow_combo_card_sets(
    ctx: Dict[str, object],
    combo_config: DoudizhuComboRuleConfig,
    last_play: DoudizhuComboInfo,
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    压牌场景：仅生成可压过上家的同型候选及炸弹、王炸。

    :param ctx: 生成上下文。
    :param combo_config: 牌型配置。
    :param last_play: 上家牌型。
    :param collector: 输出收集器。
    :return: 无。
    """
    generate_rocket_candidates(ctx, collector)
    generate_bomb_candidates(ctx, collector)
    target_type = last_play.comboType
    if target_type == COMBO_SINGLE:
        generate_single_candidates(ctx, collector)
    elif target_type == COMBO_PAIR:
        generate_pair_candidates(ctx, collector)
    elif target_type == COMBO_TRIPLE:
        generate_triple_candidates(ctx, collector)
    elif target_type == COMBO_TRIPLE_WITH_SINGLE and combo_config.allowSingleAttachment:
        generate_triple_attachment_candidates(ctx, combo_config, collector)
    elif target_type == COMBO_TRIPLE_WITH_PAIR:
        generate_triple_attachment_candidates(ctx, combo_config, collector)
    elif target_type == COMBO_STRAIGHT:
        generate_straight_candidates(ctx, collector, fixed_length=last_play.chainLength)
    elif target_type == COMBO_PAIR_STRAIGHT:
        generate_pair_straight_candidates(ctx, collector, fixed_pairs=last_play.chainLength)
    elif target_type == COMBO_AIRPLANE:
        generate_airplane_candidates(ctx, combo_config, collector, fixed_groups=last_play.chainLength)
    elif target_type == COMBO_AIRPLANE_WITH_SINGLES and combo_config.allowSingleAttachment:
        generate_airplane_candidates(
            ctx,
            combo_config,
            collector,
            fixed_groups=last_play.chainLength,
            with_singles=True,
        )
    elif target_type == COMBO_AIRPLANE_WITH_PAIRS:
        generate_airplane_candidates(
            ctx,
            combo_config,
            collector,
            fixed_groups=last_play.chainLength,
            with_pairs=True,
        )
    elif target_type == COMBO_FOUR_WITH_TWO_SINGLES:
        generate_four_with_two_candidates(ctx, combo_config, collector, singles_only=True)
    elif target_type == COMBO_FOUR_WITH_TWO_PAIRS:
        generate_four_with_two_candidates(ctx, combo_config, collector, pairs_only=True)
    hand_size = len(ctx["hand_cards"])
    if hand_size > 0:
        full_hand = list(ctx["hand_cards"])
        combo = recognize_combo(full_hand, combo_config)
        if combo is not None and can_beat(combo, last_play):
            append_card_set(collector, full_hand)


def generate_single_candidates(
    ctx: Dict[str, object],
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    生成单张候选。

    :param ctx: 生成上下文。
    :param collector: 输出收集器。
    :return: 无。
    """
    for card in ctx["hand_cards"]:
        append_card_set(collector, [card])


def ways_pick_from_rank(
    ctx: Dict[str, object],
    rank_code: str,
    count: int,
    used_ids: Optional[Set[str]] = None,
) -> List[List[DoudizhuCard]]:
    """
    从指定点数自然牌与癞子中选取固定张数组合。

    :param ctx: 生成上下文。
    :param rank_code: 点数编码。
    :param count: 目标张数。
    :param used_ids: 已占用实例 ID。
    :return: 牌组列表。
    """
    used = used_ids or set()
    naturals = [
        card
        for card in (ctx["naturals"].get(rank_code) or [])
        if card.cardInstanceId not in used
    ]
    available_laizis = [
        card for card in ctx["laizis"] if card.cardInstanceId not in used
    ]
    results = []  # type: List[List[DoudizhuCard]]
    if len(naturals) >= count:
        picks = list(combinations(naturals, count))
        if len(picks) > _MAX_SMALL_COMBO_PICKS:
            picks = [tuple(sort_cards_for_pick(naturals)[:count])]
        for picked in picks:
            results.append(list(picked))
        return results
    need_laizi = count - len(naturals)
    if need_laizi < 0 or need_laizi > len(available_laizis):
        return []
    if not ctx["enable_laizi"] and need_laizi > 0:
        return []
    if need_laizi == 0 and len(naturals) == count:
        return [list(naturals)]
    laizi_picks = list(combinations(available_laizis, need_laizi))
    if len(laizi_picks) > _MAX_SMALL_COMBO_PICKS:
        laizi_picks = [tuple(sort_cards_for_pick(available_laizis)[:need_laizi])]
    for laizi_pick in laizi_picks:
        results.append(list(naturals) + list(laizi_pick))
    return results


def generate_pair_candidates(
    ctx: Dict[str, object],
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    生成对子候选。

    :param ctx: 生成上下文。
    :param collector: 输出收集器。
    :return: 无。
    """
    rank_codes = all_rank_codes(ctx)
    for rank_code in rank_codes:
        for picked in ways_pick_from_rank(ctx, rank_code, 2):
            append_card_set(collector, picked)


def generate_triple_candidates(
    ctx: Dict[str, object],
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    生成三张候选。

    :param ctx: 生成上下文。
    :param collector: 输出收集器。
    :return: 无。
    """
    rank_codes = all_rank_codes(ctx)
    for rank_code in rank_codes:
        for picked in ways_pick_from_rank(ctx, rank_code, 3):
            append_card_set(collector, picked)


def pick_canonical_singles(
    ctx: Dict[str, object],
    count: int,
    used_ids: Set[str],
    exclude_ranks: Optional[Set[str]] = None,
) -> Optional[List[DoudizhuCard]]:
    """
    从剩余手牌中按小牌优先选取若干单张附件。

    :param ctx: 生成上下文。
    :param count: 目标单张数。
    :param used_ids: 已占用实例 ID。
    :param exclude_ranks: 排除的点数编码。
    :return: 选中的牌列表；不足时返回 ``None``。
    """
    exclude = exclude_ranks or set()
    pool = [
        card
        for card in ctx["hand_cards"]
        if card.cardInstanceId not in used_ids and card.rankCode not in exclude
    ]
    if len(pool) < count:
        return None
    return sort_cards_for_pick(pool)[:count]


def pair_ranks_available(
    ctx: Dict[str, object],
    used_ids: Set[str],
    exclude_ranks: Optional[Set[str]] = None,
) -> List[str]:
    """
    列出剩余手牌中可组成对子的点数（按点数值升序）。

    :param ctx: 生成上下文。
    :param used_ids: 已占用实例 ID。
    :param exclude_ranks: 排除的点数编码。
    :return: 点数编码列表。
    """
    exclude = exclude_ranks or set()
    rank_codes = all_rank_codes(ctx)
    available = []
    for rank_code in rank_codes:
        if rank_code in exclude:
            continue
        picks = ways_pick_from_rank(ctx, rank_code, 2, used_ids)
        if picks:
            available.append(rank_code)
    available.sort(key=lambda code: rank_value_for_rank(ctx, code))
    return available


def rank_value_for_rank(ctx: Dict[str, object], rank_code: str) -> int:
    """
    获取上下文中某点数的排序值。

    :param ctx: 生成上下文。
    :param rank_code: 点数编码。
    :return: 点数值。
    """
    naturals = ctx["naturals"] or {}
    group = naturals.get(rank_code) or []
    if group:
        return group[0].rankValue
    if rank_code == str(ctx.get("laizi_rank_code") or ""):
        laizis = ctx["laizis"] or []
        if laizis:
            return laizis[0].rankValue
    return 0


def pick_canonical_pairs(
    ctx: Dict[str, object],
    pair_count: int,
    used_ids: Set[str],
    exclude_ranks: Optional[Set[str]] = None,
) -> Optional[List[DoudizhuCard]]:
    """
    按小牌优先选取若干对子作为附件。

    :param ctx: 生成上下文。
    :param pair_count: 目标对子数。
    :param used_ids: 已占用实例 ID。
    :param exclude_ranks: 排除的点数编码。
    :return: 选中的牌列表；不足时返回 ``None``。
    """
    ranks = pair_ranks_available(ctx, used_ids, exclude_ranks)
    if len(ranks) < pair_count:
        return None
    picked_cards = []
    working_used = set(used_ids)
    for rank_code in ranks[:pair_count]:
        pair_pick = ways_pick_from_rank(ctx, rank_code, 2, working_used)
        if not pair_pick:
            return None
        cards = pair_pick[0]
        picked_cards.extend(cards)
        working_used.update(card.cardInstanceId for card in cards)
    return picked_cards


def append_attachment_combos(
    collector: List[List[DoudizhuCard]],
    ctx: Dict[str, object],
    body_cards: List[DoudizhuCard],
    combo_config: DoudizhuComboRuleConfig,
    attach_count: int,
    per_attach: int,
) -> None:
    """
    向收集器追加带附件牌型的有限规范化候选。

    :param collector: 输出收集器。
    :param ctx: 生成上下文。
    :param body_cards: 主体牌列表。
    :param combo_config: 牌型配置。
    :param attach_count: 附件组数。
    :param per_attach: 每组张数（1 或 2）。
    :return: 无。
    """
    used = {card.cardInstanceId for card in body_cards}
    body_ranks = {card.rankCode for card in body_cards}
    variants = []  # type: List[List[DoudizhuCard]]
    if per_attach == 1:
        canonical = pick_canonical_singles(ctx, attach_count, used, body_ranks)
        if canonical is not None:
            variants.append(canonical)
        rank_codes = [
            code for code in all_rank_codes(ctx)
            if code not in body_ranks
        ]
        rank_codes.sort(key=lambda code: rank_value_for_rank(ctx, code))
        variant_count = 0
        for start_index in range(len(rank_codes)):
            if variant_count >= _MAX_ATTACHMENT_VARIANTS:
                break
            if start_index + attach_count > len(rank_codes):
                break
            chosen_ranks = rank_codes[start_index:start_index + attach_count]
            if len(set(chosen_ranks)) < attach_count:
                continue
            attach_cards = []
            working_used = set(used)
            valid = True
            for rank_code in chosen_ranks:
                picks = ways_pick_from_rank(ctx, rank_code, 1, working_used)
                if not picks:
                    valid = False
                    break
                attach_cards.extend(picks[0])
                working_used.update(card.cardInstanceId for card in picks[0])
            if valid and attach_cards:
                variants.append(attach_cards)
                variant_count += 1
    else:
        canonical = pick_canonical_pairs(ctx, attach_count, used, body_ranks)
        if canonical is not None:
            variants.append(canonical)
        ranks = pair_ranks_available(ctx, used, body_ranks)
        variant_count = 0
        for start_index in range(len(ranks)):
            if variant_count >= _MAX_ATTACHMENT_VARIANTS:
                break
            if start_index + attach_count > len(ranks):
                break
            chosen_ranks = ranks[start_index:start_index + attach_count]
            attach_cards = []
            working_used = set(used)
            valid = True
            for rank_code in chosen_ranks:
                picks = ways_pick_from_rank(ctx, rank_code, 2, working_used)
                if not picks:
                    valid = False
                    break
                attach_cards.extend(picks[0])
                working_used.update(card.cardInstanceId for card in picks[0])
            if valid and attach_cards:
                variants.append(attach_cards)
                variant_count += 1
    seen = set()  # type: Set[Tuple[str, ...]]
    for attach_cards in variants:
        key = tuple(sorted(card.cardInstanceId for card in attach_cards))
        if key in seen:
            continue
        seen.add(key)
        cards = body_cards + attach_cards
        if recognize_combo(cards, combo_config) is not None:
            append_card_set(collector, cards)


def generate_triple_attachment_candidates(
    ctx: Dict[str, object],
    combo_config: DoudizhuComboRuleConfig,
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    生成三带一、三带一对候选。

    :param ctx: 生成上下文。
    :param combo_config: 牌型配置。
    :param collector: 输出收集器。
    :return: 无。
    """
    rank_codes = all_rank_codes(ctx)
    for main_rank in rank_codes:
        for main_cards in ways_pick_from_rank(ctx, main_rank, 3):
            used = {card.cardInstanceId for card in main_cards}
            exclude = {main_rank}
            if combo_config.allowSingleAttachment:
                singles = pick_canonical_singles(ctx, 1, used, exclude)
                if singles is not None:
                    cards = main_cards + singles
                    if recognize_combo(cards, combo_config) is not None:
                        append_card_set(collector, cards)
                rank_codes_attach = [
                    code for code in rank_codes
                    if code not in exclude
                ]
                rank_codes_attach.sort(key=lambda code: rank_value_for_rank(ctx, code))
                for attach_rank in rank_codes_attach[:_MAX_ATTACHMENT_VARIANTS]:
                    for attach_cards in ways_pick_from_rank(ctx, attach_rank, 1, used):
                        append_card_set(collector, main_cards + attach_cards)
            pairs = pick_canonical_pairs(ctx, 1, used, exclude)
            if pairs is not None:
                cards = main_cards + pairs
                if recognize_combo(cards, combo_config) is not None:
                    append_card_set(collector, cards)
            pair_ranks = pair_ranks_available(ctx, used, exclude)
            for attach_rank in pair_ranks[:_MAX_ATTACHMENT_VARIANTS]:
                for attach_cards in ways_pick_from_rank(ctx, attach_rank, 2, used):
                    append_card_set(collector, main_cards + attach_cards)


def enumerate_consecutive_picks(
    ctx: Dict[str, object],
    values: List[int],
    per_rank: int,
) -> List[List[DoudizhuCard]]:
    """
    枚举连续点数各取固定张数的牌组。

    :param ctx: 生成上下文。
    :param values: 连续点数值。
    :param per_rank: 每点张数。
    :return: 牌组列表。
    """
    if not values:
        return [[]]
    first_value = values[0]
    if first_value > 14:
        return []
    first_code = rank_code_for_value(first_value)
    rest_values = values[1:]
    results = []  # type: List[List[DoudizhuCard]]
    first_picks = ways_pick_from_rank(ctx, first_code, per_rank)
    if len(first_picks) > _MAX_SMALL_COMBO_PICKS:
        first_picks = first_picks[:_MAX_SMALL_COMBO_PICKS]
    for first_pick in first_picks:
        used = {card.cardInstanceId for card in first_pick}
        sub_ctx = with_used_cards(ctx, used)
        for rest_pick in enumerate_consecutive_picks(sub_ctx, rest_values, per_rank):
            results.append(first_pick + rest_pick)
            if len(results) >= _MAX_SMALL_COMBO_PICKS:
                return results
    return results


def with_used_cards(
    ctx: Dict[str, object],
    used_ids: Set[str],
) -> Dict[str, object]:
    """
    构造排除已用牌后的上下文副本。

    :param ctx: 原上下文。
    :param used_ids: 已用实例 ID。
    :return: 新上下文。
    """
    hand_cards = [card for card in ctx["hand_cards"] if card.cardInstanceId not in used_ids]
    jokers = [card for card in ctx["jokers"] if card.cardInstanceId not in used_ids]
    laizis = [card for card in ctx["laizis"] if card.cardInstanceId not in used_ids]
    naturals = {}  # type: Dict[str, List[DoudizhuCard]]
    for rank_code, group in (ctx["naturals"] or {}).items():
        filtered = [card for card in group if card.cardInstanceId not in used_ids]
        if filtered:
            naturals[rank_code] = filtered
    return {
        "hand_cards": hand_cards,
        "jokers": jokers,
        "laizis": laizis,
        "naturals": naturals,
        "enable_laizi": ctx["enable_laizi"],
        "allow_single_attachment": ctx["allow_single_attachment"],
        "laizi_rank_code": ctx["laizi_rank_code"],
    }


def generate_straight_candidates(
    ctx: Dict[str, object],
    collector: List[List[DoudizhuCard]],
    fixed_length: Optional[int] = None,
) -> None:
    """
    生成顺子候选。

    :param ctx: 生成上下文。
    :param collector: 输出收集器。
    :param fixed_length: 固定长度（压牌时）。
    :return: 无。
    """
    hand_size = len(ctx["hand_cards"])
    if fixed_length is not None:
        lengths = [fixed_length]
    else:
        max_len = min(12, hand_size)
        lengths = list(range(_STRAIGHT_MIN_LENGTH, max_len + 1))
    for length in lengths:
        for start in range(3, 15 - length + 1):
            end = start + length - 1
            if end > 14:
                break
            values = list(range(start, end + 1))
            for picked in enumerate_consecutive_picks(ctx, values, 1):
                if len(picked) == length:
                    append_card_set(collector, picked)


def generate_pair_straight_candidates(
    ctx: Dict[str, object],
    collector: List[List[DoudizhuCard]],
    fixed_pairs: Optional[int] = None,
) -> None:
    """
    生成连对候选。

    :param ctx: 生成上下文。
    :param collector: 输出收集器。
    :param fixed_pairs: 固定对数（压牌时）。
    :return: 无。
    """
    hand_size = len(ctx["hand_cards"]) // 2
    if fixed_pairs is not None:
        pair_counts = [fixed_pairs]
    else:
        max_pairs = min(10, hand_size)
        pair_counts = list(range(_PAIR_STRAIGHT_MIN_PAIRS, max_pairs + 1))
    for pair_count in pair_counts:
        for start in range(3, 15 - pair_count + 1):
            end = start + pair_count - 1
            if end > 14:
                break
            values = list(range(start, end + 1))
            for picked in enumerate_consecutive_picks(ctx, values, 2):
                if len(picked) == pair_count * 2:
                    append_card_set(collector, picked)


def generate_airplane_candidates(
    ctx: Dict[str, object],
    combo_config: DoudizhuComboRuleConfig,
    collector: List[List[DoudizhuCard]],
    fixed_groups: Optional[int] = None,
    with_singles: bool = False,
    with_pairs: bool = False,
) -> None:
    """
    生成飞机、飞机带单、飞机带对候选。

    :param ctx: 生成上下文。
    :param combo_config: 牌型配置。
    :param collector: 输出收集器。
    :param fixed_groups: 固定连续组数（压牌时）。
    :param with_singles: 是否仅生成带单。
    :param with_pairs: 是否仅生成带对。
    :return: 无。
    """
    hand_size = len(ctx["hand_cards"]) // 3
    if fixed_groups is not None:
        group_counts = [fixed_groups]
    else:
        max_groups = min(6, hand_size)
        group_counts = list(range(_AIRPLANE_MIN_GROUPS, max_groups + 1))
    for group_count in group_counts:
        for start in range(3, 15 - group_count + 1):
            end = start + group_count - 1
            if end > 14:
                break
            values = list(range(start, end + 1))
            for body_cards in enumerate_consecutive_picks(ctx, values, 3):
                if len(body_cards) != group_count * 3:
                    continue
                if with_singles:
                    if combo_config.allowSingleAttachment:
                        append_attachment_combos(
                            collector,
                            ctx,
                            body_cards,
                            combo_config,
                            group_count,
                            1,
                        )
                    continue
                if with_pairs:
                    append_attachment_combos(
                        collector,
                        ctx,
                        body_cards,
                        combo_config,
                        group_count,
                        2,
                    )
                    continue
                append_card_set(collector, body_cards)
                if combo_config.allowSingleAttachment:
                    append_attachment_combos(
                        collector,
                        ctx,
                        body_cards,
                        combo_config,
                        group_count,
                        1,
                    )
                append_attachment_combos(
                    collector,
                    ctx,
                    body_cards,
                    combo_config,
                    group_count,
                    2,
                )


def generate_four_with_two_candidates(
    ctx: Dict[str, object],
    combo_config: DoudizhuComboRuleConfig,
    collector: List[List[DoudizhuCard]],
    singles_only: bool = False,
    pairs_only: bool = False,
) -> None:
    """
    生成四带二单、四带二对候选。

    :param ctx: 生成上下文。
    :param combo_config: 牌型配置。
    :param collector: 输出收集器。
    :param singles_only: 仅四带二单。
    :param pairs_only: 仅四带二对。
    :return: 无。
    """
    rank_codes = all_rank_codes(ctx)
    for main_rank in rank_codes:
        for main_cards in ways_pick_from_rank(ctx, main_rank, 4):
            used = {card.cardInstanceId for card in main_cards}
            exclude = {main_rank}
            if not pairs_only:
                canonical = pick_canonical_singles(ctx, 2, used, exclude)
                if canonical is not None:
                    cards = main_cards + canonical
                    if recognize_combo(cards, combo_config) is not None:
                        append_card_set(collector, cards)
                rank_codes_attach = [
                    code for code in rank_codes
                    if code not in exclude
                ]
                rank_codes_attach.sort(key=lambda code: rank_value_for_rank(ctx, code))
                variant_count = 0
                for index_a in range(len(rank_codes_attach)):
                    if variant_count >= _MAX_ATTACHMENT_VARIANTS:
                        break
                    for index_b in range(index_a + 1, len(rank_codes_attach)):
                        if variant_count >= _MAX_ATTACHMENT_VARIANTS:
                            break
                        r1 = rank_codes_attach[index_a]
                        r2 = rank_codes_attach[index_b]
                        picks_a = ways_pick_from_rank(ctx, r1, 1, used)
                        if not picks_a:
                            continue
                        u1 = used | {card.cardInstanceId for card in picks_a[0]}
                        picks_b = ways_pick_from_rank(ctx, r2, 1, u1)
                        if not picks_b:
                            continue
                        attach = picks_a[0] + picks_b[0]
                        cards = main_cards + attach
                        if recognize_combo(cards, combo_config) is not None:
                            append_card_set(collector, cards)
                        variant_count += 1
            if not singles_only:
                canonical_pairs = pick_canonical_pairs(ctx, 2, used, exclude)
                if canonical_pairs is not None:
                    cards = main_cards + canonical_pairs
                    if recognize_combo(cards, combo_config) is not None:
                        append_card_set(collector, cards)
                pair_ranks = pair_ranks_available(ctx, used, exclude)
                variant_count = 0
                for start_index in range(len(pair_ranks)):
                    if variant_count >= _MAX_ATTACHMENT_VARIANTS:
                        break
                    if start_index + 2 > len(pair_ranks):
                        break
                    chosen = pair_ranks[start_index:start_index + 2]
                    attach_cards = []
                    working_used = set(used)
                    valid = True
                    for rank_code in chosen:
                        picks = ways_pick_from_rank(ctx, rank_code, 2, working_used)
                        if not picks:
                            valid = False
                            break
                        attach_cards.extend(picks[0])
                        working_used.update(card.cardInstanceId for card in picks[0])
                    if valid and attach_cards:
                        cards = main_cards + attach_cards
                        if recognize_combo(cards, combo_config) is not None:
                            append_card_set(collector, cards)
                            variant_count += 1


def generate_bomb_candidates(
    ctx: Dict[str, object],
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    生成炸弹与癞子炸弹候选。

    :param ctx: 生成上下文。
    :param collector: 输出收集器。
    :return: 无。
    """
    rank_codes = all_rank_codes(ctx)
    laizi_rank = ctx.get("laizi_rank_code")
    if ctx["enable_laizi"] and laizi_rank and not (ctx["naturals"].get(laizi_rank) or []):
        if laizi_rank not in rank_codes:
            rank_codes.append(laizi_rank)
    for rank_code in rank_codes:
        for picked in ways_pick_from_rank(ctx, rank_code, 4):
            append_card_set(collector, picked)


def generate_rocket_candidates(
    ctx: Dict[str, object],
    collector: List[List[DoudizhuCard]],
) -> None:
    """
    生成王炸候选。

    :param ctx: 生成上下文。
    :param collector: 输出收集器。
    :return: 无。
    """
    jokers = ctx["jokers"]
    if len(jokers) == 2:
        ranks = {card.rankCode for card in jokers}
        if ranks == {"small_joker", "big_joker"}:
            append_card_set(collector, list(jokers))


def all_rank_codes(ctx: Dict[str, object]) -> List[str]:
    """
    收集手牌中实际出现的点数编码（含癞子点数）。

    :param ctx: 生成上下文。
    :return: 点数编码列表。
    """
    codes = list((ctx["naturals"] or {}).keys())
    if ctx["enable_laizi"] and ctx.get("laizi_rank_code"):
        laizi_code = str(ctx["laizi_rank_code"])
        if laizi_code not in codes:
            codes.append(laizi_code)
    return codes
