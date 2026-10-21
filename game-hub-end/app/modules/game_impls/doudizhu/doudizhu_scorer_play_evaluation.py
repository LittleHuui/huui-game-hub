"""斗地主 PLAY 与 PASS 的统一候选后局面评分。"""

from typing import List

from app.modules.game_impls.doudizhu.doudizhu_action_score_config import DoudizhuActionScoreConfig
from app.modules.game_impls.doudizhu.doudizhu_scorer_hand_cost import DoudizhuHandCostEvaluator
from app.modules.game_impls.doudizhu.doudizhu_scorer_position import DoudizhuPositionEvaluator, project_scoring_position
from app.modules.game_impls.doudizhu.doudizhu_scorer_support import DoudizhuScoreContext
from app.modules.strategy_turn.schemas import ActionCandidate, CandidateScore


class DoudizhuPlayScorer(object):
    """用同一组归一化局面特征比较全部合法出牌与过牌候选。"""

    def __init__(self, config: DoudizhuActionScoreConfig) -> None:
        """初始化只读评分服务，不持有跨对局缓存。"""
        self._config = config
        self._position_evaluator = DoudizhuPositionEvaluator(config)

    def score_candidates(
        self,
        context: DoudizhuScoreContext,
        candidates: List[ActionCandidate],
        lightweight: bool = False,
    ) -> List[CandidateScore]:
        """计算 Q=-wC*C*(1-A)+wK*K+wA*A-wE*E。

        本阵营越接近获得收尾机会，本人减少剩余手牌成本的边际收益越小。
        因此成本连续乘以 (1-A)，避免局部减牌收益压过全队的收尾机会；
        同一公式用于地主、农民和轻量兜底，终局收益高于全部普通局面。
        """
        positions = []
        for candidate in sorted(candidates, key=lambda item: item.candidateId):
            position = project_scoring_position(context, candidate.normalizedAction)
            if position is not None:
                positions.append((candidate, position))
        if not positions:
            return []
        known_groups = None
        if context.last_play is None:
            known_groups = []
            for _, position in positions:
                remaining_ids = {card.cardInstanceId for card in position.remaining_hand}
                played = [card for card in context.hand_cards if card.cardInstanceId not in remaining_ids]
                if position.last_play is not None and played:
                    known_groups.append((position.last_play, played))
        hand_evaluator = DoudizhuHandCostEvaluator(
            context.hand_cards, context.combo_config, self._config,
            lightweight=lightweight, known_groups=known_groups,
        )
        hand_evaluator.prepare([position.remaining_hand for _, position in positions])
        divisor = (1.0 + self._config.weak_group_cost) * len(context.hand_cards)
        results = []
        for candidate, position in positions:
            if position.won:
                results.append(CandidateScore(candidateId=candidate.candidateId, score=self._config.terminal_win_score, reason="terminalWin"))
                continue
            cost = min(1.0, hand_evaluator.cost(position.remaining_hand) / divisor)
            control = hand_evaluator.control(position.remaining_hand)
            alliance, opponent = self._position_evaluator.opportunities(context, position)
            cfg = self._config
            effective_cost = cost * (1.0 - alliance)
            score = (
                -cfg.remaining_cost_weight * effective_cost + cfg.control_weight * control
                + cfg.alliance_opportunity_weight * alliance - cfg.opponent_opportunity_weight * opponent
            )
            reason = "position:C={:.6f},K={:.6f},A={:.6f},E={:.6f},effectiveCost={:.6f}".format(
                cost, control, alliance, opponent, effective_cost,
            )
            results.append(CandidateScore(candidateId=candidate.candidateId, score=score, reason=reason))
        return results
