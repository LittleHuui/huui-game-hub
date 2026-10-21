"""动作提交解析接口。"""

from abc import ABC, abstractmethod

from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.schemas import ActionSubmission, ResolvedGameAction


class ActionSubmissionResolver(ABC):
    """将外部动作意图解析为已校验动作的接口。"""

    @abstractmethod
    def resolve(
        self,
        context: ActionInteractionContext,
        submission: ActionSubmission,
    ) -> ResolvedGameAction:
        """
        解析动作提交。

        :param context: 动作交互上下文。
        :param submission: 外部动作意图。
        :return: 已解析动作。
        """
