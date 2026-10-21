"""真人动作提示 Provider 合同。"""

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.schemas import HintSuggestionPage


class HintSuggestionProvider(ABC):
    """仅向真人玩家返回公开提示，不暴露内部候选。"""

    @abstractmethod
    def list_page(
        self,
        context: ActionInteractionContext,
        cursor: Optional[str],
        page_size: int,
    ) -> HintSuggestionPage:
        """
        返回公开提示分页。
        :param context: 动作交互上下文。
        :param cursor: 分页游标。
        :param page_size: 页面大小。
        :return: 公开提示分页。
        """
