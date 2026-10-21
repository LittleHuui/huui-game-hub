"""斗地主牌型与花色常量。"""

from typing import Dict, Tuple

# 四种花色编码与展示文案
DOUDIZHU_SUITS: Tuple[str, ...] = ("SPADE", "HEART", "CLUB", "DIAMOND")
DOUDIZHU_SUIT_LABELS: Dict[str, str] = {
    "SPADE": "黑桃",
    "HEART": "红桃",
    "CLUB": "梅花",
    "DIAMOND": "方块",
}

# 普通牌点数：rankCode、展示标签、rankValue
DOUDIZHU_RANK_SPECS: Tuple[Tuple[str, str, int], ...] = (
    ("3", "3", 3),
    ("4", "4", 4),
    ("5", "5", 5),
    ("6", "6", 6),
    ("7", "7", 7),
    ("8", "8", 8),
    ("9", "9", 9),
    ("10", "10", 10),
    ("J", "J", 11),
    ("Q", "Q", 12),
    ("K", "K", 13),
    ("A", "A", 14),
    ("2", "2", 15),
)

# 大小王定义
DOUDIZHU_JOKER_SPECS: Tuple[Tuple[str, str, str, int, str], ...] = (
    ("small_joker", "small_joker", "小王", 16, "BLACK"),
    ("big_joker", "big_joker", "大王", 17, "RED"),
)

# 花色对应的展示颜色
DOUDIZHU_SUIT_DISPLAY_COLORS: Dict[str, str] = {
    "SPADE": "BLACK",
    "HEART": "RED",
    "CLUB": "BLACK",
    "DIAMOND": "RED",
}

# 固定玩家人数
DOUDIZHU_PLAYER_COUNT = 3

# 单套牌总张数
DOUDIZHU_SINGLE_DECK_CARD_COUNT = 54

# 动作类型
ACTION_SHOW_CARDS = "SHOW_CARDS"
ACTION_SKIP_SHOW_CARDS = "SKIP_SHOW_CARDS"
ACTION_CALL_LANDLORD = "CALL_LANDLORD"
ACTION_PASS_CALL = "PASS_CALL"
ACTION_ROB_LANDLORD = "ROB_LANDLORD"
ACTION_PASS_ROB = "PASS_ROB"
ACTION_DOUBLE = "DOUBLE"
ACTION_PASS_DOUBLE = "PASS_DOUBLE"
ACTION_PLAY_CARDS = "PLAY_CARDS"
ACTION_PASS = "PASS"

# 对局阶段
PHASE_DEALING = "dealing"
PHASE_LAIZI_REVEAL = "laizi_reveal"
PHASE_SHOWING = "showing"
PHASE_CALLING = "calling"
PHASE_ROBBING = "robbing"
PHASE_LANDLORD_CONFIRM = "landlord_confirm"
PHASE_DOUBLING = "doubling"
PHASE_PLAYING = "playing"
PHASE_SETTLEMENT = "settlement"
PHASE_FINISHED = "finished"

# 角色与春天类型
ROLE_LANDLORD = "LANDLORD"
ROLE_FARMER = "FARMER"
WINNER_LANDLORD = "landlord"
WINNER_FARMER = "farmer"
SPRING = "SPRING"
ANTI_SPRING = "ANTI_SPRING"
