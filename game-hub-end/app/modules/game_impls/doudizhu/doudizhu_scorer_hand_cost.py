"""斗地主剩余手牌的有限预算拆分与非重叠控制资源评价。

使用规则模块产生的合法组合池，在点数计数上计算
D(H) = min(1 + weak_group_cost * (1 - strength(g)) + D(H - g))。
所有候选先获得完整合法拆分的成本上界，再共享状态和转移预算优化。
组合池与搜索均有界，因此结果是估计成本，不承诺精确最少手数。
"""

from collections import deque
from dataclasses import dataclass
from math import exp
from typing import Dict, List, Optional, Sequence, Tuple

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import DoudizhuActionScoreConfig
from app.modules.game_impls.doudizhu.doudizhu_combo_rule import DoudizhuComboRuleConfig, recognize_combo
from app.modules.game_impls.doudizhu.doudizhu_play_candidate_generator import group_cards_for_generation
from app.modules.game_impls.doudizhu.doudizhu_play_candidate_strategies import generate_all_combo_card_sets
from app.modules.game_impls.doudizhu.doudizhu_scorer_combo_features import combo_strength
from app.modules.game_impls.doudizhu.schemas import DoudizhuCard, DoudizhuComboInfo

HandCounts = Tuple[int, ...]


@dataclass(frozen=True)
class HandGroup(object):
    """一个合法牌组消耗的实体点数及拆分成本。"""

    counts: HandCounts
    cost: float
    control: float


class DoudizhuHandCostEvaluator(object):
    """本次决策内共享合法组合与手牌状态缓存。"""

    def __init__(
        self,
        hand: List[DoudizhuCard],
        combo_config: DoudizhuComboRuleConfig,
        config: DoudizhuActionScoreConfig,
        lightweight: bool = False,
        known_groups: Optional[List[Tuple[DoudizhuComboInfo, List[DoudizhuCard]]]] = None,
    ) -> None:
        """建立一次性组合池；轻量模式只识别同点数组和王牌。"""
        self._config = config
        self._lightweight = lightweight
        ordered = sorted(hand, key=lambda card: (card.rankValue, card.rankCode, card.cardInstanceId))
        self._ranks = sorted({(card.rankValue, card.rankCode) for card in ordered})
        self._rank_indexes = {code: index for index, (_, code) in enumerate(self._ranks)}
        self._empty = tuple(0 for _ in self._ranks)
        self._single_costs = [0.0 for _ in self._ranks]
        self._single_controls = [self._single_control(code) for _, code in self._ranks]
        pool = {}  # type: Dict[HandCounts, HandGroup]
        raw_groups = []  # type: List[Tuple[DoudizhuComboInfo, List[DoudizhuCard]]]
        if not lightweight:
            raw_groups.extend(
                known_groups if known_groups is not None
                else self._generate_groups(ordered, combo_config)
            )
        by_rank = {}  # type: Dict[str, List[DoudizhuCard]]
        for card in ordered:
            by_rank.setdefault(card.rankCode, []).append(card)
        simple_groups = []
        for cards in by_rank.values():
            for count in range(1, len(cards) + 1):
                simple_groups.append(cards[:count])
        simple_groups.append([card for card in ordered if card.isJoker])
        for cards in simple_groups:
            combo = recognize_combo(cards, combo_config)
            if combo is not None:
                raw_groups.append((combo, cards))
        for combo, cards in raw_groups:
            counts = self.signature(cards)
            cost = 1.0 + config.weak_group_cost * (1.0 - combo_strength(combo))
            control = config.control_rocket if combo.isRocket else (config.control_bomb if combo.isBomb else 0.0)
            prior = pool.get(counts)
            pool[counts] = HandGroup(counts, min(cost, prior.cost) if prior else cost, max(control, prior.control) if prior else control)
            if len(cards) == 1:
                self._single_costs[self._rank_indexes[cards[0].rankCode]] = cost
        self._groups = sorted(pool.values(), key=lambda group: (group.cost / sum(group.counts), -sum(group.counts), group.counts))
        self._groups_by_rank = [
            [group for group in self._groups if group.counts[index]]
            for index in range(len(self._ranks))
        ]
        self._costs = {self._empty: 0.0}  # type: Dict[HandCounts, float]
        self._control_cache = {}  # type: Dict[HandCounts, float]
        self._control_groups = sorted(
            (group for group in self._groups if group.control > self._single_control_total(group.counts)),
            key=lambda group: (-(group.control - self._single_control_total(group.counts)), group.counts),
        )
        self.expanded_states = 0
        self.visited_transitions = 0

    def signature(self, cards: Sequence[DoudizhuCard]) -> HandCounts:
        """将实体牌转换为点数计数，花色与输入顺序不影响估值。"""
        counts = [0 for _ in self._ranks]
        for card in cards:
            counts[self._rank_indexes[card.rankCode]] += 1
        return tuple(counts)

    def _generate_groups(
        self,
        hand: List[DoudizhuCard],
        combo_config: DoudizhuComboRuleConfig,
    ) -> List[Tuple[DoudizhuComboInfo, List[DoudizhuCard]]]:
        """复用规则枚举，先按实体点数去重再识别，避免重复计算花色排列。"""
        raw_sets = []  # type: List[List[DoudizhuCard]]
        generate_all_combo_card_sets(group_cards_for_generation(hand, combo_config), combo_config, raw_sets)
        seen = set()
        groups = []
        for cards in raw_sets:
            signature = self.signature(cards)
            if signature in seen:
                continue
            seen.add(signature)
            combo = recognize_combo(cards, combo_config)
            if combo is not None:
                groups.append((combo, cards))
        return groups

    def prepare(self, remaining_hands: List[List[DoudizhuCard]]) -> None:
        """先覆盖所有候选，再以稳定广度顺序共享预算构建拆分有向无环图。"""
        roots = sorted({self.signature(hand) for hand in remaining_hands}, key=lambda key: (sum(key), key))
        for root in roots:
            self._costs[root] = self._greedy_cost(root)
        if self._lightweight:
            return
        queue = deque(roots)
        discovered = set(roots)
        edges = {}  # type: Dict[HandCounts, List[Tuple[float, HandCounts]]]
        cfg = self._config
        while queue and self.expanded_states < cfg.decomposition_state_budget:
            if self.visited_transitions >= cfg.decomposition_transition_budget:
                break
            current = queue.popleft()
            if not any(current):
                continue
            self.expanded_states += 1
            pivot = next(index for index, count in enumerate(current) if count)
            branches = []
            for group in self._groups_by_rank[pivot]:
                if self.visited_transitions >= cfg.decomposition_transition_budget:
                    break
                self.visited_transitions += 1
                child = self._subtract(current, group.counts)
                if child is None:
                    continue
                branches.append((group.cost, child))
                if child not in discovered:
                    discovered.add(child)
                    self._costs[child] = self._greedy_cost(child)
                    queue.append(child)
            edges[current] = branches
        for current in sorted(edges, key=lambda key: (sum(key), key)):
            self._costs[current] = min(
                [self._costs[current]]
                + [cost + self._costs[child] for cost, child in edges[current]]
            )

    def cost(self, cards: List[DoudizhuCard]) -> float:
        """读取当前决策共享搜索得到的完整拆分成本。"""
        return self._costs[self.signature(cards)]

    def control(self, cards: List[DoudizhuCard]) -> float:
        """用互不重叠的控制组合和剩余单牌估值，王炸不重复计为两张王。"""
        remaining = self.signature(cards)
        signature = remaining
        if signature in self._control_cache:
            return self._control_cache[signature]
        value = 0.0
        for group in self._control_groups:
            child = self._subtract(remaining, group.counts)
            if child is not None:
                value += group.control
                remaining = child
        value += self._single_control_total(remaining)
        result = 1.0 - exp(-value / self._config.control_scale)
        self._control_cache[signature] = result
        return result

    def _greedy_cost(self, counts: HandCounts) -> float:
        """构造有效完整拆分作为搜索上界，单张组确保组合池截断仍可覆盖。"""
        remaining = counts
        total = 0.0
        while any(remaining):
            pivot = next(index for index, count in enumerate(remaining) if count)
            for group in self._groups_by_rank[pivot]:
                child = self._subtract(remaining, group.counts)
                if child is None:
                    continue
                total += group.cost
                remaining = child
                break
            else:
                return total + sum(count * cost for count, cost in zip(remaining, self._single_costs))
        return total

    @staticmethod
    def _subtract(counts: HandCounts, removed: HandCounts) -> Optional[HandCounts]:
        """扣除实体点数，牌数不足时不形成拆分分支。"""
        result = []
        for count, take in zip(counts, removed):
            if take > count:
                return None
            result.append(count - take)
        return tuple(result)

    def _single_control(self, rank_code: str) -> float:
        """读取单张高牌的控制资源权重。"""
        return {
            "A": self._config.control_rank_a,
            "2": self._config.control_rank2,
            "small_joker": self._config.control_small_joker,
            "big_joker": self._config.control_big_joker,
        }.get(rank_code, 0.0)

    def _single_control_total(self, counts: HandCounts) -> float:
        """计算尚未被控制组合占用的单张资源。"""
        return sum(count * value for count, value in zip(counts, self._single_controls))
