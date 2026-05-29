"""只能在线游玩的游戏规则种子注册表。"""

from typing import Dict, List

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.modules.game_seed.schemas import OnlineGameRuleSeed
from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED

_REGISTRY = {}  # type: Dict[str, OnlineGameRuleSeed]


def register_online_game_seed(seed: OnlineGameRuleSeed) -> None:
    """
    注册在线游戏规则种子。

    :param seed: 规则种子实例。
    """
    _REGISTRY[seed.gameCode] = seed


def get_online_game_seed(game_code: str) -> OnlineGameRuleSeed:
    """
    按 ``gameCode`` 获取在线游戏规则种子。

    :param game_code: 游戏编码。
    :return: 规则种子。
    :raises BizException: 未注册时抛出。
    """
    normalized = str(game_code).strip()
    seed = _REGISTRY.get(normalized)
    if seed is None:
        raise BizException(ErrorCode.GAME_RULE_DEFINITION_NOT_FOUND)
    return seed


def list_online_game_seeds() -> List[OnlineGameRuleSeed]:
    """
    列出全部已注册的在线游戏规则种子。

    :return: 规则种子列表。
    """
    return list(_REGISTRY.values())


def _register_builtin_seeds() -> None:
    """注册内置在线游戏规则种子。"""
    register_online_game_seed(UNO_ONLINE_GAME_RULE_SEED)


_register_builtin_seeds()
