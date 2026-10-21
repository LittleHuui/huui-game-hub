"""动作 Offer Provider 接口。"""

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.schemas import ActionOffer


class ActionOfferProvider(ABC):
    """构建动作 Offer 的接口。"""

    @abstractmethod
    def build_offer(self, context: ActionInteractionContext) -> Optional[ActionOffer]:
        """
        构建动作 Offer。

        :param context: 动作交互上下文。
        :return: 动作 Offer；当前不可操作时返回 None。
        """
