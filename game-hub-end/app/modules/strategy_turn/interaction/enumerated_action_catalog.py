"""枚举动作目录抽象。"""

from abc import ABC, abstractmethod
from typing import List

from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.schemas import ResolvedGameAction


class EnumeratedActionCatalog(ABC):
    """列出指定 actionType 的全部合法已解析动作。"""

    @abstractmethod
    def list_actions(
        self,
        context: ActionInteractionContext,
        action_type: str,
    ) -> List[ResolvedGameAction]:
        """
        列出当前状态下指定类型的全部合法动作。

        :param context: 动作交互上下文。
        :param action_type: 动作类型。
        :return: 已解析动作列表。
        """
