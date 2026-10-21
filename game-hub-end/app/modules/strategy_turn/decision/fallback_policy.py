"""游戏私有兜底策略接口。"""

from abc import ABC, abstractmethod
from typing import List, Optional

from app.modules.strategy_turn.schemas import ActionCandidate, ActionDecisionContext


class FallbackPolicy(ABC):
    """从已校验候选中选择兜底动作。"""

    @abstractmethod
    def choose(
        self,
        context: ActionDecisionContext,
        candidates: List[ActionCandidate],
    ) -> Optional[ActionCandidate]:
        """
        选择兜底候选。

        :param context: 决策上下文。
        :param candidates: 已校验候选列表。
        :return: 兜底候选。
        """
