"""只能在线游玩的游戏规则种子注册表。"""

from types import MappingProxyType
from typing import Iterable, List, Mapping

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.modules.game_seed.schemas import OnlineGameRuleSeed
from app.modules.game_seed.doudizhu_seed import DOUDIZHU_ONLINE_GAME_RULE_SEED
from app.modules.game_seed.gomoku_seed import GOMOKU_ONLINE_GAME_RULE_SEED
from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED


def _build_seed_registry(seeds: Iterable[OnlineGameRuleSeed]) -> Mapping[str, OnlineGameRuleSeed]:
    """启动时复制并注册种子，拒绝重复编码并冻结注册映射。"""
    registry = {}
    for seed in seeds:
        if seed.gameCode in registry:
            raise ValueError("重复的在线游戏规则种子: {0}".format(seed.gameCode))
        registry[seed.gameCode] = seed.model_copy(deep=True)
    return MappingProxyType(registry)


_REGISTRY = _build_seed_registry((
    UNO_ONLINE_GAME_RULE_SEED,
    GOMOKU_ONLINE_GAME_RULE_SEED,
    DOUDIZHU_ONLINE_GAME_RULE_SEED,
))


def get_online_game_seed(game_code: str) -> OnlineGameRuleSeed:
    """
    按 gameCode 获取种子的独立副本，避免调用方修改注册事实。

    :param game_code: 游戏编码。
    :return: 规则种子。
    :raises BizException: 未注册时抛出。
    """
    normalized = str(game_code).strip()
    seed = _REGISTRY.get(normalized)
    if seed is None:
        raise BizException(ErrorCode.GAME_RULE_DEFINITION_NOT_FOUND)
    return seed.model_copy(deep=True)


def list_online_game_seeds() -> List[OnlineGameRuleSeed]:
    """
    按注册顺序返回全部规则种子的独立副本。

    :return: 规则种子列表。
    """
    return [seed.model_copy(deep=True) for seed in _REGISTRY.values()]
