"""五子棋托管兜底策略。"""

from app.modules.strategy_turn.decision.fallback_policy import FallbackPolicy


class GomokuFallbackPolicy(FallbackPolicy):
    """五子棋私有托管兜底策略。"""

    def choose(self, context, candidates):
        """
        按五子棋保守策略选择兜底候选。

        :param context: 决策上下文。
        :param candidates: 已校验候选列表。
        :return: 兜底候选。
        """
        del context
        for candidate in candidates or []:
            if candidate.actionType == "PLACE_STONE":
                return candidate
        for candidate in candidates or []:
            if candidate.actionType == "REJECT_UNDO":
                return candidate
        return candidates[0] if candidates else None
