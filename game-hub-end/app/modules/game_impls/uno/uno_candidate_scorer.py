"""UNO 托管候选评分器。"""

from typing import List, Optional

from app.modules.game_impls.uno.uno_action_score_config import UNO_ACTION_SCORE_CONFIG, UnoActionScoreConfig
from app.modules.game_impls.uno.uno_scorer_context import UnoFeatureExtractor
from app.modules.game_impls.uno.uno_scorer_evaluation import UnoActionEvaluator
from app.modules.strategy_turn.decision.candidate_scorer import CandidateScorer
from app.modules.strategy_turn.schemas import ActionCandidate, ActionDecisionContext, CandidateScore


class UnoCandidateScorer(CandidateScorer):
    """UNO 托管候选评分实现。"""

    def __init__(self, config: Optional[UnoActionScoreConfig] = None) -> None:
        """组装共享同一权重配置的特征提取与评分器。"""
        resolved = config or UNO_ACTION_SCORE_CONFIG
        self._feature_extractor = UnoFeatureExtractor(resolved)
        self._evaluator = UnoActionEvaluator(resolved, self._feature_extractor)

    def score_candidates(
        self,
        context: ActionDecisionContext,
        candidates: List[ActionCandidate],
    ) -> List[CandidateScore]:
        """
        对 UNO 候选动作评分。

        :param context: 决策上下文。
        :param candidates: 候选动作列表。
        :return: 评分列表。
        """
        score_context = self._feature_extractor.build_context(context, candidates)
        if score_context is None:
            return []
        results = []
        for candidate in candidates:
            feature = self._feature_extractor.build_action_feature(score_context, candidate)
            score, reason = self._evaluator.score_action(score_context, feature)
            candidate_id = str(candidate.candidateId or "").strip()
            if not candidate_id:
                continue
            results.append(CandidateScore(candidateId=candidate_id, score=score, reason=reason))
        return results
