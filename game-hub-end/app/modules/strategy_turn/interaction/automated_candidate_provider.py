"""自动决策候选 Provider 接口。"""

from abc import ABC, abstractmethod
from typing import List

from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.schemas import ActionCandidate


class AutomatedCandidateProvider(ABC):
    """为托管与 AI 生成完整或预算内候选动作。"""

    @abstractmethod
    def list_candidates(
        self,
        context: ActionInteractionContext,
    ) -> List[ActionCandidate]:
        """
        列出自动决策候选。

        :param context: 动作交互上下文。
        :return: 候选动作列表。
        """
