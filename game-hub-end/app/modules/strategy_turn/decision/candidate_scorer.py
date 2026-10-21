"""动作候选评分接口。"""

from abc import ABC, abstractmethod
from typing import List

from app.modules.strategy_turn.schemas import (
    ActionCandidate,
    ActionDecisionContext,
    CandidateScore,
)


class CandidateScorer(ABC):
    """游戏私有候选评分器接口。"""

    @abstractmethod
    def score_candidates(
        self,
        context: ActionDecisionContext,
        candidates: List[ActionCandidate],
    ) -> List[CandidateScore]:
        """
        对候选动作评分。

        :param context: 决策上下文。
        :param candidates: 候选动作列表。
        :return: 评分列表。
        """
