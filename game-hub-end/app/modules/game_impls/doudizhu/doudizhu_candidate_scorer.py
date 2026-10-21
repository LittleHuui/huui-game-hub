"""斗地主候选动作评分器。"""

from typing import List, Optional

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import (
    DOUDIZHU_ACTION_SCORE_CONFIG,
    DoudizhuActionScoreConfig,
)
from app.modules.game_impls.doudizhu.doudizhu_scorer_hand_features import DoudizhuHandStrengthEvaluator
from app.modules.game_impls.doudizhu.doudizhu_scorer_phase_evaluation import DoudizhuPhaseScorer
from app.modules.game_impls.doudizhu.doudizhu_scorer_play_evaluation import DoudizhuPlayScorer
from app.modules.game_impls.doudizhu.doudizhu_constants import (
    ACTION_CALL_LANDLORD,
    ACTION_DOUBLE,
    ACTION_PASS_CALL,
    ACTION_PASS_DOUBLE,
    ACTION_PASS_ROB,
    ACTION_ROB_LANDLORD,
    ACTION_SHOW_CARDS,
    ACTION_SKIP_SHOW_CARDS,
    PHASE_PLAYING,
)
from app.modules.game_impls.doudizhu.doudizhu_scorer_support import build_score_context
from app.modules.strategy_turn.decision.candidate_scorer import CandidateScorer
from app.modules.strategy_turn.schemas import (
    ActionCandidate,
    ActionDecisionContext,
    CandidateScore,
    ResolvedGameAction,
)


class DoudizhuCandidateScorer(CandidateScorer):
    """斗地主候选动作评分实现。"""

    def __init__(self, config: Optional[DoudizhuActionScoreConfig] = None) -> None:
        """组装斗地主私有阶段评分器与出牌局面评分器。"""
        resolved = config or DOUDIZHU_ACTION_SCORE_CONFIG
        self._config = resolved
        self._hand_evaluator = DoudizhuHandStrengthEvaluator(resolved)
        self._phase_scorer = DoudizhuPhaseScorer(resolved)
        self._play_scorer = DoudizhuPlayScorer(resolved)

    def _build_context(self, state, player_id):
        """
        从运行时状态构建只读评分上下文。

        :param state: 对局状态。
        :param player_id: 玩家 ID。
        :return: 评分上下文或 ``None``。
        """
        return build_score_context(state, player_id, self._hand_evaluator)

    def score_candidates(
        self,
        context: ActionDecisionContext,
        candidates: List[ActionCandidate],
    ) -> List[CandidateScore]:
        """
        对斗地主候选动作评分。

        :param context: 决策上下文。
        :param candidates: 候选动作列表。
        :return: 评分列表。
        """
        score_context = build_score_context(
            context.state if isinstance(context.state, dict) else {},
            context.playerId,
            self._hand_evaluator,
        )
        if score_context is None:
            return []
        if score_context.phase == PHASE_PLAYING:
            return self._play_scorer.score_candidates(score_context, candidates)
        results = []
        for candidate in sorted(candidates, key=lambda item: item.candidateId):
            score, reason = self._score_phase_action(score_context, candidate.normalizedAction)
            results.append(CandidateScore(candidateId=candidate.candidateId, score=score, reason=reason))
        return results

    def _score_phase_action(
        self,
        context,
        action: ResolvedGameAction,
    ):
        """按动作类型分发评分。"""
        action_type = str(action.actionType or "").strip()
        if action_type == ACTION_SHOW_CARDS:
            return self._phase_scorer.score_showing_action(context, action, prefer_show=True)
        if action_type == ACTION_SKIP_SHOW_CARDS:
            return self._phase_scorer.score_showing_action(context, action, prefer_show=False)
        if action_type == ACTION_CALL_LANDLORD:
            return self._phase_scorer.score_calling_action(context, action, prefer_call=True)
        if action_type == ACTION_PASS_CALL:
            return self._phase_scorer.score_calling_action(context, action, prefer_call=False)
        if action_type == ACTION_ROB_LANDLORD:
            return self._phase_scorer.score_robbing_action(context, action, prefer_rob=True)
        if action_type == ACTION_PASS_ROB:
            return self._phase_scorer.score_robbing_action(context, action, prefer_rob=False)
        if action_type == ACTION_DOUBLE:
            return self._phase_scorer.score_doubling_action(context, action, prefer_double=True)
        if action_type == ACTION_PASS_DOUBLE:
            return self._phase_scorer.score_doubling_action(context, action, prefer_double=False)
        return 0.0, action_type
