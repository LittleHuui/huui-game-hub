"""UNO 托管兜底策略。"""

from app.modules.game_impls.uno.uno_constants import UNO_ACTION_TYPES
from app.modules.strategy_turn.decision.fallback_policy import FallbackPolicy


class UnoFallbackPolicy(FallbackPolicy):
    """UNO 私有托管兜底策略。"""

    def choose(self, context, candidates):
        """
        按 UNO 保守策略选择兜底候选。

        :param context: 决策上下文。
        :param candidates: 已校验候选列表。
        :return: 兜底候选。
        """
        del context
        for action_type in UNO_ACTION_TYPES:
            for candidate in candidates or []:
                if candidate.actionType == action_type:
                    return candidate
        return None
