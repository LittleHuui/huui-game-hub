"""动作预览 Provider 接口。"""

from abc import ABC, abstractmethod

from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.schemas import ActionPreview, ActionSubmission


class ActionPreviewProvider(ABC):
    """构造动作只读预览接口。"""

    @abstractmethod
    def preview(
        self,
        context: ActionInteractionContext,
        submission: ActionSubmission,
    ) -> ActionPreview:
        """
        预览动作提交。

        :param context: 动作交互上下文。
        :param submission: 外部动作意图。
        :return: 预览结果。
        """
