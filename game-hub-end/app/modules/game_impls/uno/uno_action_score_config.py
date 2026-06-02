"""UNO 托管动作评分参数（集中配置，便于人工调参）。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnoActionScoreConfig(object):
    """UNO 托管出牌各场景分值权重。"""

    # 直接出完最后一张牌，最高优先级
    immediate_finish: float = 10000.0

    # 待摸牌惩罚下叠加 +4 的收益
    pending_stack_wild_draw4: float = 4200.0

    # 待摸牌惩罚下叠加 +2 的收益
    pending_stack_draw_two: float = 5000.0

    # 待摸牌惩罚下无法叠加时选择摸牌
    pending_draw: float = 1000.0

    # 下家手牌较少时，用 +4 打击下家（再乘以威胁倍率）
    threat_next_wild_draw4: float = 1800.0

    # 下家手牌较少时，用禁用牌跳过下家
    threat_next_disable: float = 1500.0

    # 下家手牌较少时，用 +2 打击下家
    threat_next_draw_two: float = 1500.0

    # 下家手牌较少时，使用万能牌换色
    threat_next_wild: float = 450.0

    # 对手剩余 1 张牌时的威胁倍率，属于强威胁
    threat_multiplier_hand_1: float = 1.0

    # 对手剩余 2 张牌时的威胁倍率，属于中高威胁
    threat_multiplier_hand_2: float = 0.45

    # 对手剩余 3 张牌时的威胁倍率，属于轻度威胁
    threat_multiplier_hand_3: float = 0.18

    # 反转后避开手牌更少的下家（乘以威胁倍率差）
    reverse_avoids_one_card_next: float = 1450.0

    # 反转后把机会给手牌更少的玩家（乘以威胁倍率差）
    reverse_to_one_card_player_penalty: float = -900.0

    # 出完后自己只剩 1 张时，普通数字牌收益
    self_uno_number: float = 900.0

    # 出完后自己只剩 1 张时，普通功能牌收益
    self_uno_action_card: float = 700.0

    # 出完后自己只剩 1 张时，万能牌收益
    self_uno_wild: float = 300.0

    # 出完后自己只剩 1 张时，+4 收益，较低以避免浪费
    self_uno_wild_draw4: float = 100.0

    # 万能牌选择自己手牌最多颜色（低权重，仅影响选色）
    choose_most_color: float = 60.0

    # 万能牌选择自己手牌第二多颜色
    choose_second_color: float = 30.0

    # 万能牌选择自己没有的颜色
    choose_missing_color_penalty: float = -300.0

    # 普通场景打数字牌
    normal_number: float = 180.0

    # 普通场景打反转牌
    normal_reverse: float = 140.0

    # 普通场景打禁用牌
    normal_disable: float = 150.0

    # 普通场景打 +2
    normal_draw_two: float = 160.0

    # 普通场景打万能牌
    normal_wild: float = 80.0

    # 普通场景打 +4，默认低于 +2，避免浪费
    normal_wild_draw4: float = 60.0

    # 数字牌出牌收益，表示普通场景应尽快打掉数字牌
    number_discard_value: float = 220.0

    # 数字牌匹配当前点数的收益，例如红5上出蓝5，可以切换到自己的优势色
    number_match_value: float = 260.0

    # 数字牌颜色等于当前颜色的收益
    number_match_current_color: float = 120.0

    # 打出数字牌后，剩余手牌仍有同色牌的基础收益
    number_keep_color_chain: float = 180.0

    # 打出数字牌后，剩余同色牌每多一张的收益
    number_same_color_remaining_each: float = 80.0

    # 打出数字牌后，该颜色是自己剩余手牌最多颜色的收益
    number_switch_to_best_color: float = 320.0

    # 手牌较少阈值。手牌较少时更重视自己出牌效率
    low_hand_count_threshold: int = 4

    # 手牌较少时，打数字牌的额外收益
    low_hand_number_bonus: float = 300.0

    # 手牌较少时，打普通功能牌的惩罚，尽量保留功能牌
    low_hand_action_card_penalty: float = -180.0

    # 手牌较多阈值。手牌较多时可以更积极压制对手
    high_hand_count_threshold: int = 6

    # 手牌较多且对手低手牌时，威胁倍率额外提升
    high_hand_threat_multiplier_bonus: float = 0.25

    # 超过该分数的数字牌视为优秀数字牌，WILD / +4 应额外保留
    good_number_threshold: float = 500.0

    # 有优秀数字牌可出时，打出 WILD 的额外惩罚
    wild_when_good_number_playable_penalty: float = -500.0

    # 有优秀数字牌可出时，打出 +4 的额外惩罚
    wild_draw4_when_good_number_playable_penalty: float = -800.0

    # 普通场景有数字牌可出时，打出 WILD 的惩罚，避免过早浪费
    wild_when_number_playable_penalty: float = -500.0

    # 普通场景有数字牌可出时，打出 +4 的惩罚，避免过早浪费
    wild_draw4_when_number_playable_penalty: float = -800.0

    # 随机扰动下限，避免托管/AI 在相近局面下总是同一选择
    random_jitter_min: float = -25.0

    # 随机扰动上限，只允许小幅影响相近分数动作
    random_jitter_max: float = 25.0

    # 有牌可出时主动摸牌惩罚
    draw_when_playable_penalty: float = -1000.0

    # 无牌可出时摸牌收益
    draw_when_no_playable: float = 1000.0

    # PASS 低优先级
    pass_turn: float = -2000.0


UNO_ACTION_SCORE_CONFIG = UnoActionScoreConfig()
