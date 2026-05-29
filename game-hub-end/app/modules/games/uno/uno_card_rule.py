"""UNO 牌型规则基类。"""

from abc import ABC, abstractmethod
from typing import Any, Dict

from app.modules.games.uno.schemas import UnoCard, UnoRuleContext


class UnoCardRule(ABC):
    """单种牌型的出牌与效果规则。"""

    rule_key: str = ""

    @abstractmethod
    def can_play(self, context: UnoRuleContext, card: UnoCard) -> bool:
        """
        判断指定牌在当前上下文是否可出。

        :param context: 规则上下文。
        :param card: 待出牌。
        :return: 可出为 ``True``。
        """

    @abstractmethod
    def apply_effect(
        self,
        context: UnoRuleContext,
        card: UnoCard,
        action: Dict[str, Any],
    ) -> None:
        """
        应用出牌效果并更新 ``context.runtimeState``。

        :param context: 规则上下文。
        :param card: 已出的牌。
        :param action: 玩家提交的操作载荷。
        """
