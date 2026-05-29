"""策略回合制规则引擎抽象。"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.modules.strategy_turn.schemas import (
    GameAction,
    GameView,
    LegalAction,
    StrategyTurnRuntimeRule,
)


class StrategyTurnRuleEngine(ABC):
    """策略回合制游戏规则引擎基类；具体游戏实现子类并注册到 ``rule_engine_registry``。"""

    @abstractmethod
    def build_initial_state(
        self,
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> Dict[str, Any]:
        """
        根据运行时规则构建初始对局状态。

        :param runtime_rule: 合并后的运行时规则。
        :return: 对局状态字典，由具体规则引擎定义结构。
        """

    @abstractmethod
    def list_legal_actions(
        self,
        state: Dict[str, Any],
        player_id: str,
    ) -> List[LegalAction]:
        """
        列出指定玩家在当回合可执行的合法操作。

        :param state: 当前对局状态。
        :param player_id: 待查询玩家 ID。
        :return: 合法操作列表。
        """

    @abstractmethod
    def apply_action(
        self,
        state: Dict[str, Any],
        action: GameAction,
    ) -> Dict[str, Any]:
        """
        校验并应用玩家操作，返回更新后的对局状态。

        :param state: 当前对局状态。
        :param action: 玩家提交的操作。
        :return: 应用操作后的对局状态。
        """

    @abstractmethod
    def advance(
        self,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        推进回合或阶段（如自动结算、轮到下一位等），不依赖玩家显式操作。

        :param state: 当前对局状态。
        :return: 推进后的对局状态。
        """

    @abstractmethod
    def build_view(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
    ) -> GameView:
        """
        为指定玩家构建可见对局视图（含合法操作与私有信息）。

        :param state: 当前对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 玩家视图。
        """

    @abstractmethod
    def is_game_over(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        判断对局是否已结束。

        :param state: 当前对局状态。
        :return: 已结束为 ``True``，否则为 ``False``。
        """


class StubStrategyTurnRuleEngine(StrategyTurnRuleEngine):
    """占位规则引擎：仅完成注册，玩法方法尚未实现。"""

    def build_initial_state(
        self,
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> Dict[str, Any]:
        """
        占位：规则引擎尚未实现。

        :param runtime_rule: 运行时规则。
        :return: 不返回。
        :raises NotImplementedError: 始终抛出。
        """
        raise NotImplementedError("策略回合规则引擎尚未实现")

    def list_legal_actions(
        self,
        state: Dict[str, Any],
        player_id: str,
    ) -> List[LegalAction]:
        """
        占位：规则引擎尚未实现。

        :param state: 当前对局状态。
        :param player_id: 玩家 ID。
        :return: 不返回。
        :raises NotImplementedError: 始终抛出。
        """
        raise NotImplementedError("策略回合规则引擎尚未实现")

    def apply_action(
        self,
        state: Dict[str, Any],
        action: GameAction,
    ) -> Dict[str, Any]:
        """
        占位：规则引擎尚未实现。

        :param state: 当前对局状态。
        :param action: 玩家操作。
        :return: 不返回。
        :raises NotImplementedError: 始终抛出。
        """
        raise NotImplementedError("策略回合规则引擎尚未实现")

    def advance(
        self,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        占位：规则引擎尚未实现。

        :param state: 当前对局状态。
        :return: 不返回。
        :raises NotImplementedError: 始终抛出。
        """
        raise NotImplementedError("策略回合规则引擎尚未实现")

    def build_view(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
    ) -> GameView:
        """
        占位：规则引擎尚未实现。

        :param state: 当前对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 不返回。
        :raises NotImplementedError: 始终抛出。
        """
        raise NotImplementedError("策略回合规则引擎尚未实现")

    def is_game_over(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        占位：规则引擎尚未实现。

        :param state: 当前对局状态。
        :return: 不返回。
        :raises NotImplementedError: 始终抛出。
        """
        raise NotImplementedError("策略回合规则引擎尚未实现")
