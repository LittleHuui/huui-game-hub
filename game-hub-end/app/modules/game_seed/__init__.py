"""只能在线游玩的游戏规则种子模块。"""

from app.modules.game_seed.online_game_seed_registry import (
    get_online_game_seed,
    list_online_game_seeds,
    register_online_game_seed,
)
from app.modules.game_seed.schemas import OnlineGameRuleSeed
from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED

__all__ = [
    "OnlineGameRuleSeed",
    "UNO_ONLINE_GAME_RULE_SEED",
    "get_online_game_seed",
    "list_online_game_seeds",
    "register_online_game_seed",
]
