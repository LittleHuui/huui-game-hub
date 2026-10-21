"""斗地主私有托管兜底，使用有限成本的同方向局面评价。"""

from typing import List, Optional

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import DOUDIZHU_ACTION_SCORE_CONFIG, DoudizhuActionScoreConfig
from app.modules.game_impls.doudizhu.doudizhu_constants import (
    ACTION_PASS_CALL, ACTION_PASS_DOUBLE, ACTION_PASS_ROB, ACTION_SKIP_SHOW_CARDS,
    PHASE_CALLING, PHASE_DOUBLING, PHASE_PLAYING, PHASE_ROBBING, PHASE_SHOWING,
)
from app.modules.game_impls.doudizhu.doudizhu_scorer_hand_features import DoudizhuHandStrengthEvaluator
from app.modules.game_impls.doudizhu.doudizhu_scorer_play_evaluation import DoudizhuPlayScorer
from app.modules.game_impls.doudizhu.doudizhu_scorer_support import build_score_context
from app.modules.strategy_turn.decision.fallback_policy import FallbackPolicy
from app.modules.strategy_turn.schemas import ActionCandidate, ActionDecisionContext


class DoudizhuFallbackPolicy(FallbackPolicy):
    """评分搜索不可用时只用简单合法拆分，不重试完整枚举或搜索。"""

    def __init__(self, config: Optional[DoudizhuActionScoreConfig] = None) -> None:
        """复用斗地主局面权重与阶段手牌特征。"""
        resolved = config or DOUDIZHU_ACTION_SCORE_CONFIG
        self._hand_evaluator = DoudizhuHandStrengthEvaluator(resolved)
        self._play_scorer = DoudizhuPlayScorer(resolved)

    def choose(self, context: ActionDecisionContext, candidates: List[ActionCandidate]) -> Optional[ActionCandidate]:
        """在已校验候选中选择确定性兜底动作，出牌与过牌接受同一局面比较。"""
        if not candidates:
            return None
        state = context.state if isinstance(context.state, dict) else {}
        phase = str(state.get("phase") or "").strip()
        ordered = sorted(candidates, key=lambda item: item.candidateId)
        if phase == PHASE_PLAYING:
            score_context = build_score_context(state, context.playerId, self._hand_evaluator)
            if score_context is None:
                return None
            scores = self._play_scorer.score_candidates(score_context, ordered, lightweight=True)
            if not scores:
                return None
            best = min(scores, key=lambda item: (-item.score, item.candidateId))
            return next(item for item in ordered if item.candidateId == best.candidateId)
        conservative = {
            PHASE_SHOWING: ACTION_SKIP_SHOW_CARDS,
            PHASE_CALLING: ACTION_PASS_CALL,
            PHASE_ROBBING: ACTION_PASS_ROB,
            PHASE_DOUBLING: ACTION_PASS_DOUBLE,
        }.get(phase)
        for candidate in ordered:
            if candidate.actionType == conservative:
                return candidate
        return ordered[0]
