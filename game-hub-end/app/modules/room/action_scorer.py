"""托管动作评分通用接口与注册表。"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from app.modules.strategy_turn.schemas import GameView, LegalAction


@dataclass
class ActionScore:
    """单个合法动作的评分结果。"""

    actionId: str
    score: float
    reason: str = ""


class ManagedActionScorer(object):
    """托管动作评分器基类，仅返回评分，不执行动作。"""

    def score_actions(
        self,
        *,
        game_code: str,
        game_view: GameView,
        legal_actions: List[LegalAction],
        player_id: str,
    ) -> List[ActionScore]:
        """
        对合法动作列表评分。

        :param game_code: 游戏编码。
        :param game_view: 当前玩家视角 GameView。
        :param legal_actions: 合法动作列表。
        :param player_id: 当前行动玩家 ID。
        :return: 评分列表，无评分时返回空列表。
        """
        del game_code
        del game_view
        del legal_actions
        del player_id
        return []


class ManagedActionScorerRegistry(object):
    """按 gameCode 注册与查找托管动作评分器。"""

    def __init__(self) -> None:
        self._scorers: Dict[str, ManagedActionScorer] = {}

    def register(self, game_code: str, scorer: ManagedActionScorer) -> None:
        """
        注册指定游戏的评分器。

        :param game_code: 游戏编码。
        :param scorer: 评分器实例。
        :return: 无。
        """
        normalized = str(game_code or "").strip()
        if not normalized:
            return
        self._scorers[normalized] = scorer

    def get(self, game_code: str) -> Optional[ManagedActionScorer]:
        """
        获取已注册的评分器。

        :param game_code: 游戏编码。
        :return: 评分器实例，未注册时返回 ``None``。
        """
        normalized = str(game_code or "").strip()
        if not normalized:
            return None
        return self._scorers.get(normalized)
