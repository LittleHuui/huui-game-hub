"""通用动作候选选择器。"""

import math
from typing import Dict, List, Optional

from app.modules.strategy_turn.schemas import ActionCandidate, CandidateScore
from app.modules.strategy_turn.decision.schemas import CandidateSelectionError


class CandidateSelector(object):
    """只按评分结果选择候选，不理解具体游戏。"""

    def select(
        self,
        candidates: List[ActionCandidate],
        scores: List[CandidateScore],
    ) -> Optional[ActionCandidate]:
        """
        选择最高分候选。

        :param candidates: 候选列表。
        :param scores: 评分列表。
        :return: 选中的候选，无有效评分时返回 None。
        """
        candidate_by_id = {}  # type: Dict[str, ActionCandidate]
        for item in candidates:
            candidate_id = str(item.candidateId or "").strip()
            if not candidate_id or candidate_id in candidate_by_id:
                raise CandidateSelectionError("candidateId 为空或重复")
            candidate_by_id[candidate_id] = item
        best = None  # type: Optional[CandidateScore]
        for score in scores or []:
            candidate_id = str(score.candidateId or "").strip()
            if candidate_id not in candidate_by_id:
                continue
            value = float(score.score)
            if not math.isfinite(value):
                continue
            if best is None or value > float(best.score):
                best = score
        if best is None:
            return None
        selected = candidate_by_id.get(best.candidateId)
        if selected is None:
            raise CandidateSelectionError("Selector 返回候选集合外对象")
        return selected
