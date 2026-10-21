"""斗地主癞子归一化搜索与附带牌分配；同牌型优先最高合法主牌。"""

from typing import Dict, List, Optional, Set, Tuple

from app.modules.game_impls.doudizhu.doudizhu_combo_models import DoudizhuComboRuleConfig
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import (
    is_straight_eligible_rank_value,
    rank_code_for_value,
    rank_value_for_code,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard

def match_fixed_counts(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    required_counts: Dict[Optional[str], int],
    allow_laizi_fill: bool,
) -> Optional[Tuple[str, Dict[str, str]]]:
    """
    匹配单一主牌点数的固定张数（对子、三张等）。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param required_counts: 固定张数要求。
    :param allow_laizi_fill: 是否允许癞子补足。
    :return: ``(主牌点数编码, 癞子分配)`` 或 ``None``。
    """
    del required_counts
    total_cards = sum(len(group) for group in naturals.values()) + len(laizis)
    needed = total_cards
    if len(naturals) > 1 and laizis:
        candidate_ranks = list(naturals.keys())
    elif len(naturals) == 1:
        candidate_ranks = list(naturals.keys())
    else:
        candidate_ranks = []
    if laizis and config.enableLaizi and allow_laizi_fill:
        for value in range(3, 16):
            code = rank_code_for_value(value)
            if code not in candidate_ranks:
                candidate_ranks.append(code)
    if not candidate_ranks and laizis and config.enableLaizi:
        for value in range(3, 16):
            candidate_ranks.append(rank_code_for_value(value))
    for rank_code in sorted(candidate_ranks, key=rank_value_for_code, reverse=True):
        natural_count = len(naturals.get(rank_code, []))
        other_count = sum(
            len(group)
            for code, group in naturals.items()
            if code != rank_code
        )
        if other_count > 0:
            continue
        laizi_needed = needed - natural_count
        if laizi_needed < 0:
            continue
        if laizi_needed == 0 and natural_count == needed:
            return rank_code, {}
        if laizi_needed > 0 and len(laizis) == laizi_needed and config.enableLaizi:
            assignments = {
                card.cardInstanceId: rank_code for card in laizis
            }
            return rank_code, assignments
    if len(naturals) == 1 and not laizis:
        rank_code, group = next(iter(naturals.items()))
        if len(group) == needed:
            return rank_code, {}
    return None


def match_two_rank_counts(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    main_count: int,
    attach_count: int,
) -> Optional[Tuple[str, Dict[str, str]]]:
    """
    匹配主牌与附带牌两种张数（三带一、三带一对）。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param main_count: 主牌张数。
    :param attach_count: 附带牌张数。
    :return: ``(主牌点数编码, 癞子分配)`` 或 ``None``。
    """
    rank_codes = list(naturals.keys())
    if config.enableLaizi and laizis:
        for value in range(3, 16):
            code = rank_code_for_value(value)
            if code not in rank_codes:
                rank_codes.append(code)
    rank_codes.sort(key=rank_value_for_code, reverse=True)
    for main_rank in rank_codes:
        for attach_rank in rank_codes:
            if attach_rank == main_rank:
                continue
            assignment = solve_two_rank_counts(
                naturals,
                laizis,
                config,
                main_rank,
                main_count,
                attach_rank,
                attach_count,
            )
            if assignment is not None:
                return main_rank, assignment
    return None


def solve_two_rank_counts(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    main_rank: str,
    main_count: int,
    attach_rank: str,
    attach_count: int,
) -> Optional[Dict[str, str]]:
    """
    求解主牌与附带牌的双点数癞子分配。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param main_rank: 主牌点数编码。
    :param main_count: 主牌目标张数。
    :param attach_rank: 附带牌点数编码。
    :param attach_count: 附带牌目标张数。
    :return: 癞子分配字典或 ``None``。
    """
    main_natural = len(naturals.get(main_rank, []))
    attach_natural = len(naturals.get(attach_rank, []))
    other_cards = sum(
        len(group)
        for code, group in naturals.items()
        if code not in (main_rank, attach_rank)
    )
    if other_cards > 0:
        return None
    if main_natural > main_count or attach_natural > attach_count:
        return None
    main_need = main_count - main_natural
    attach_need = attach_count - attach_natural
    if main_need < 0 or attach_need < 0:
        return None
    if main_need + attach_need != len(laizis):
        return None
    if main_need > 0 or attach_need > 0:
        if not config.enableLaizi:
            return None
    assignments = {}
    laizi_index = 0
    for _ in range(main_need):
        assignments[laizis[laizi_index].cardInstanceId] = main_rank
        laizi_index += 1
    for _ in range(attach_need):
        assignments[laizis[laizi_index].cardInstanceId] = attach_rank
        laizi_index += 1
    return assignments


def match_consecutive_singles(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    length: int,
) -> Optional[Tuple[int, Dict[str, str]]]:
    """
    匹配连续单张顺子。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param length: 顺子长度。
    :return: ``(最高主牌值, 癞子分配)`` 或 ``None``。
    """
    for start in range(15 - length, 2, -1):
        end = start + length - 1
        needed_values = list(range(start, end + 1))
        assignment = solve_consecutive_requirements(
            naturals,
            laizis,
            config,
            needed_values,
            per_rank_count=1,
        )
        if assignment is not None:
            return end, assignment
    return None


def match_consecutive_pairs(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    pair_count: int,
) -> Optional[Tuple[int, Dict[str, str]]]:
    """
    匹配连续对子连对。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param pair_count: 连对的对数。
    :return: ``(最高主牌值, 癞子分配)`` 或 ``None``。
    """
    for start in range(15 - pair_count, 2, -1):
        end = start + pair_count - 1
        if end > 14:
            break
        needed_values = list(range(start, end + 1))
        assignment = solve_consecutive_requirements(
            naturals,
            laizis,
            config,
            needed_values,
            per_rank_count=2,
        )
        if assignment is not None:
            return end, assignment
    return None


def match_consecutive_triples(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    group_count: int,
) -> Optional[Tuple[int, Dict[str, str]]]:
    """
    匹配连续三张飞机主体。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param group_count: 飞机连续组数。
    :return: ``(最高主牌值, 癞子分配)`` 或 ``None``。
    """
    for start in range(15 - group_count, 2, -1):
        end = start + group_count - 1
        if end > 14:
            break
        needed_values = list(range(start, end + 1))
        assignment = solve_consecutive_requirements(
            naturals,
            laizis,
            config,
            needed_values,
            per_rank_count=3,
        )
        if assignment is not None:
            return end, assignment
    return None


def solve_consecutive_requirements(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    needed_values: List[int],
    per_rank_count: int,
) -> Optional[Dict[str, str]]:
    """
    求解连续点数各取固定张数的癞子分配。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param needed_values: 连续点数值列表。
    :param per_rank_count: 每个点数需要的张数。
    :return: 癞子分配字典或 ``None``。
    """
    allowed_codes = {rank_code_for_value(value) for value in needed_values}
    for code, group in naturals.items():
        if code not in allowed_codes:
            return None
        if not is_straight_eligible_rank_value(rank_value_for_code(code)):
            return None
        if len(group) > per_rank_count:
            return None
    laizi_needed = 0
    for value in needed_values:
        code = rank_code_for_value(value)
        natural_count = len(naturals.get(code, []))
        if natural_count > per_rank_count:
            return None
        laizi_needed += per_rank_count - natural_count
    if laizi_needed != len(laizis):
        return None
    if laizi_needed > 0 and not config.enableLaizi:
        return None
    assignments = {}
    remaining_laizis = list(laizis)
    for value in needed_values:
        code = rank_code_for_value(value)
        natural_count = len(naturals.get(code, []))
        fill_count = per_rank_count - natural_count
        for _ in range(fill_count):
            if not remaining_laizis:
                return None
            laizi_card = remaining_laizis.pop(0)
            assignments[laizi_card.cardInstanceId] = code
    if remaining_laizis:
        return None
    return assignments


def match_airplane_with_attachments(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    group_count: int,
    attachment_size: int,
    joker_single_count: int = 0,
) -> Optional[Tuple[int, Dict[str, str]]]:
    """
    匹配飞机带单或飞机带对。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param group_count: 飞机连续组数。
    :param attachment_size: 每组附带张数（1 或 2）。
    :param joker_single_count: 已作为单张附件消费的王牌数量。
    :return: ``(最高主牌值, 癞子分配)`` 或 ``None``。
    """
    if joker_single_count > 0 and attachment_size != 1:
        return None
    if joker_single_count > group_count:
        return None
    for start in range(15 - group_count, 2, -1):
        end = start + group_count - 1
        if end > 14:
            break
        body_values = list(range(start, end + 1))
        body_codes = {rank_code_for_value(value) for value in body_values}
        body_naturals = {
            code: list(group)
            for code, group in naturals.items()
            if code in body_codes
        }
        attach_naturals = {
            code: list(group)
            for code, group in naturals.items()
            if code not in body_codes
        }
        for body_laizi_count in range(0, len(laizis) + 1):
            body_laizis = laizis[:body_laizi_count]
            remaining_laizis = laizis[body_laizi_count:]
            body_assignment = solve_consecutive_requirements(
                body_naturals,
                body_laizis,
                config,
                body_values,
                per_rank_count=3,
            )
            if body_assignment is None:
                continue
            body_leftover = []
            for code in body_codes:
                group = list(naturals.get(code, []))
                assigned_as_body = min(len(group), 3)
                body_leftover.extend(group[assigned_as_body:])
            attach_pool = []
            for group in attach_naturals.values():
                attach_pool.extend(group)
            attach_pool.extend(body_leftover)
            attach_need = group_count * attachment_size - joker_single_count
            if len(attach_pool) + len(remaining_laizis) != attach_need:
                continue
            attach_assignment = assign_attachments(
                attach_pool,
                remaining_laizis,
                config,
                attachment_size,
                group_count - joker_single_count if attachment_size == 1 else group_count,
                forbidden_codes=body_codes,
            )
            if attach_assignment is None:
                continue
            body_assignment.update(attach_assignment)
            return end, body_assignment
    return None


def attachment_eligible_rank_codes(forbidden_codes: Set[str]) -> List[str]:
    """
    列出可作为附带对子的合法点数编码（3 至 A，排除禁止集合）。

    :param forbidden_codes: 禁止使用的点数编码集合。
    :return: 按点数值升序的合法点数编码列表。
    """
    eligible = []
    for value in range(3, 15):
        code = rank_code_for_value(value)
        if code not in forbidden_codes:
            eligible.append(code)
    return eligible


def assign_pair_attachments(
    natural_cards: List[DoudizhuCard],
    laizi_cards: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    pair_count: int,
    forbidden_codes: Set[str],
) -> Optional[Dict[str, str]]:
    """
    为若干附带对子分配癞子（飞机带对、四带二对共用）。

    :param natural_cards: 自然附带牌。
    :param laizi_cards: 可用癞子。
    :param config: 规则配置。
    :param pair_count: 目标对子数。
    :param forbidden_codes: 禁止作为附带点数的编码集合。
    :return: 癞子分配或 ``None``。
    """
    total_needed = pair_count * 2
    pool = list(natural_cards)
    if len(pool) > total_needed:
        return None
    laizi_needed = total_needed - len(pool)
    if laizi_needed != len(laizi_cards):
        return None
    if laizi_needed > 0 and not config.enableLaizi:
        return None
    groups = {}  # type: Dict[str, List[DoudizhuCard]]
    for card in pool:
        if card.rankCode in forbidden_codes:
            return None
        group = groups.setdefault(card.rankCode, [])
        if len(group) >= 2:
            return None
        group.append(card)
    complete_pairs = [code for code, cards in groups.items() if len(cards) == 2]
    partial_singles = [code for code, cards in groups.items() if len(cards) == 1]
    if len(complete_pairs) > pair_count:
        return None
    pairs_from_structure = len(complete_pairs) + len(partial_singles)
    remaining_pair_slots = pair_count - pairs_from_structure
    if remaining_pair_slots < 0:
        return None
    if len(laizi_cards) != len(partial_singles) + remaining_pair_slots * 2:
        return None
    assignments = {}
    remaining_laizis = list(laizi_cards)
    for code in partial_singles:
        if not remaining_laizis:
            return None
        assignments[remaining_laizis[0].cardInstanceId] = code
        remaining_laizis.pop(0)
    used_ranks = set(forbidden_codes) | set(complete_pairs) | set(partial_singles)
    eligible = attachment_eligible_rank_codes(used_ranks)
    rank_index = 0
    while remaining_laizis:
        if len(remaining_laizis) < 2:
            return None
        if rank_index >= len(eligible):
            return None
        rank_code = eligible[rank_index]
        rank_index += 1
        assignments[remaining_laizis[0].cardInstanceId] = rank_code
        assignments[remaining_laizis[1].cardInstanceId] = rank_code
        remaining_laizis = remaining_laizis[2:]
    return assignments


def assign_attachments(
    natural_attach_cards: List[DoudizhuCard],
    laizi_cards: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    attachment_size: int,
    attachment_group_count: int,
    forbidden_codes: Set[str],
) -> Optional[Dict[str, str]]:
    """
    为飞机附带牌分配癞子并校验结构。

    :param natural_attach_cards: 自然附带牌。
    :param laizi_cards: 可用癞子。
    :param config: 规则配置。
    :param attachment_size: 每组附带张数。
    :param attachment_group_count: 附带组数。
    :param forbidden_codes: 禁止作为附带的主牌点数。
    :return: 癞子分配或 ``None``。
    """
    total_needed = attachment_group_count * attachment_size
    pool = list(natural_attach_cards)
    if len(pool) > total_needed:
        return None
    laizi_needed = total_needed - len(pool)
    if laizi_needed != len(laizi_cards):
        return None
    if laizi_needed > 0 and not config.enableLaizi:
        return None
    if attachment_size == 1:
        if laizi_cards:
            assignments = {}
            fallback = natural_attach_cards[0].rankCode if natural_attach_cards else "3"
            for card in laizi_cards:
                assignments[card.cardInstanceId] = fallback
            return assignments
        return {}
    if attachment_size == 2:
        return assign_pair_attachments(
            pool,
            laizi_cards,
            config,
            attachment_group_count,
            forbidden_codes,
        )
    return None


def match_four_with_attachments(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    single_attachments: int,
    pair_attachments: int,
    joker_single_count: int = 0,
) -> Optional[Tuple[str, Dict[str, str]]]:
    """
    匹配四带二单或四带二对。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param single_attachments: 单张附带数量。
    :param pair_attachments: 对子附带数量。
    :param joker_single_count: 已作为单张附件消费的王牌数量。
    :return: ``(四张主牌点数编码, 癞子分配)`` 或 ``None``。
    """
    if joker_single_count > single_attachments or pair_attachments > 0 and joker_single_count > 0:
        return None
    rank_codes = list(naturals.keys())
    if config.enableLaizi and laizis:
        for value in range(3, 16):
            code = rank_code_for_value(value)
            if code not in rank_codes:
                rank_codes.append(code)
    rank_codes.sort(key=rank_value_for_code, reverse=True)
    for main_rank in rank_codes:
        assignment = solve_four_with_attachments_for_main(
            naturals,
            laizis,
            config,
            main_rank,
            single_attachments,
            pair_attachments,
            joker_single_count,
        )
        if assignment is not None:
            return main_rank, assignment
    return None


def solve_four_with_attachments_for_main(
    naturals: Dict[str, List[DoudizhuCard]],
    laizis: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    main_rank: str,
    single_attachments: int,
    pair_attachments: int,
    joker_single_count: int,
) -> Optional[Dict[str, str]]:
    """
    以指定主牌点数求解四带附带牌。

    :param naturals: 自然牌分组。
    :param laizis: 癞子牌。
    :param config: 规则配置。
    :param main_rank: 四张主牌点数编码。
    :param single_attachments: 单张附带数量。
    :param pair_attachments: 对子附带数量。
    :param joker_single_count: 已作为单张附件消费的王牌数量。
    :return: 癞子分配或 ``None``。
    """
    main_natural = len(naturals.get(main_rank, []))
    if main_natural > 4:
        return None
    main_laizi_need = 4 - main_natural
    attach_cards = []
    for code, group in naturals.items():
        if code == main_rank:
            continue
        attach_cards.extend(group)
    attach_needed = single_attachments + pair_attachments * 2 - joker_single_count
    if attach_needed < 0:
        return None
    if len(attach_cards) > attach_needed:
        return None
    total_laizi = len(laizis)
    attach_laizi_need = attach_needed - len(attach_cards)
    if main_laizi_need + attach_laizi_need != total_laizi:
        return None
    if (main_laizi_need > 0 or attach_laizi_need > 0) and not config.enableLaizi:
        if main_laizi_need > 0 or attach_laizi_need > 0:
            return None
    assignments = {}
    laizi_index = 0
    for _ in range(main_laizi_need):
        assignments[laizis[laizi_index].cardInstanceId] = main_rank
        laizi_index += 1
    remaining_laizis = laizis[laizi_index:]
    if single_attachments == 2 and pair_attachments == 0:
        expected_single_attachments = single_attachments - joker_single_count
        if len(attach_cards) + len(remaining_laizis) != expected_single_attachments:
            return None
        for card in remaining_laizis:
            assignments[card.cardInstanceId] = attach_cards[0].rankCode if attach_cards else "3"
        return assignments
    if single_attachments == 0 and pair_attachments == 2:
        attach_assignment = assign_two_pairs_attachment(
            attach_cards,
            remaining_laizis,
            config,
            forbidden_code=main_rank,
        )
        if attach_assignment is None:
            return None
        assignments.update(attach_assignment)
        return assignments
    return None


def assign_two_pairs_attachment(
    natural_cards: List[DoudizhuCard],
    laizi_cards: List[DoudizhuCard],
    config: DoudizhuComboRuleConfig,
    forbidden_code: str,
) -> Optional[Dict[str, str]]:
    """
    为四带二对分配附带对子癞子。

    :param natural_cards: 自然附带牌。
    :param laizi_cards: 癞子牌。
    :param config: 规则配置。
    :param forbidden_code: 禁止使用的四张主牌点数。
    :return: 癞子分配或 ``None``。
    """
    return assign_pair_attachments(
        natural_cards,
        laizi_cards,
        config,
        2,
        {forbidden_code},
    )
