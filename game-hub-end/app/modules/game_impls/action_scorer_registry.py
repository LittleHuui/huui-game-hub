"""具体游戏托管动作评分器注册表组装。"""

from app.modules.game_impls.gomoku.gomoku_action_scorer import GomokuActionScorer
from app.modules.game_impls.uno.uno_action_scorer import UnoActionScorer
from app.modules.room.action_scorer import ManagedActionScorerRegistry


def build_managed_action_scorer_registry() -> ManagedActionScorerRegistry:
    """
    组装并注册各游戏托管动作评分器。

    :return: 已注册 UNO 等游戏评分器的 ``ManagedActionScorerRegistry`` 实例。
    """
    registry = ManagedActionScorerRegistry()
    registry.register("uno", UnoActionScorer())
    registry.register("gomoku", GomokuActionScorer())
    return registry
