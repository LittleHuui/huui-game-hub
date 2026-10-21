"""斗地主托管动作评分参数（集中配置，便于人工调参）。"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class DoudizhuActionScoreConfig(object):
    """斗地主托管各阶段与出牌场景分值权重。"""

    # --- 明牌 ---
    show_when_strong: float = 500.0
    skip_when_weak: float = 500.0
    show_threshold: float = 180.0
    show_strength_weight: float = 0.5
    show_weak_penalty_ratio: float = 0.3
    skip_strong_penalty_ratio: float = 0.3

    # --- 经典叫分：各档位的强度门槛与风险惩罚，仅影响 AI 偏好 ---
    bid_strength_thresholds: Tuple[float, float, float] = (140.0, 240.0, 360.0)
    bid_preferred_score: float = 500.0
    bid_distance_penalty: float = 150.0
    bid_overreach_penalty: float = 600.0

    # --- 旧版在途局叫地主 ---
    call_when_strong: float = 450.0
    pass_call_when_weak: float = 450.0
    call_threshold: float = 200.0
    call_when_all_others_passed: float = 1000.0
    call_strength_weight: float = 0.4
    call_weak_penalty_ratio: float = 0.4
    pass_call_strong_penalty_ratio: float = 0.25

    # --- 抢地主 ---
    rob_when_very_strong: float = 550.0
    pass_rob_when_moderate: float = 500.0
    rob_threshold: float = 360.0
    rob_strength_weight: float = 0.5
    rob_weak_penalty_ratio: float = 0.5
    pass_rob_strong_penalty_ratio: float = 0.2

    # --- 加倍 ---
    double_when_strong: float = 350.0
    pass_double_when_weak: float = 350.0
    double_threshold: float = 230.0
    double_landlord_bonus: float = 80.0
    double_farmer_vs_weak_landlord: float = 120.0
    double_farmer_bonus_ratio: float = 0.5
    double_strength_weight: float = 0.35
    double_weak_penalty_ratio: float = 0.4
    pass_double_strong_penalty_ratio: float = 0.25

    # --- 候选后局面：各特征归一到 0～1，终局收益独立于普通局面 ---
    remaining_cost_weight: float = 0.45
    control_weight: float = 0.10
    alliance_opportunity_weight: float = 0.25
    opponent_opportunity_weight: float = 0.20
    terminal_win_score: float = 2.0
    weak_group_cost: float = 0.20
    finish_distance_scale: float = 4.0
    response_order_decay: float = 0.80
    ordinary_response_weight: float = 1.0
    bomb_response_weight: float = 0.06
    rocket_response_weight: float = 0.02

    # --- 本次决策共享的手牌拆分预算，不改变合法候选集合 ---
    decomposition_state_budget: int = 1200
    decomposition_transition_budget: int = 24000

    # --- 不重复占用实体牌的控制资源估值 ---
    control_rank_a: float = 0.08
    control_rank2: float = 0.22
    control_small_joker: float = 0.45
    control_big_joker: float = 0.55
    control_bomb: float = 1.0
    control_rocket: float = 1.5
    control_scale: float = 2.5

    # --- 手牌强度评估 ---
    strength_rocket: float = 160.0
    strength_bomb_each: float = 85.0
    strength_rank2_each: float = 28.0
    strength_rank_a_each: float = 16.0
    strength_laizi_each: float = 22.0
    strength_long_straight: float = 45.0
    strength_airplane_body: float = 55.0
    strength_pair_count_bonus: float = 8.0
    strength_singleton_small_penalty: float = -9.0
    strength_fragment_penalty: float = -25.0


DOUDIZHU_ACTION_SCORE_CONFIG = DoudizhuActionScoreConfig()
