"""策略回合生命周期与状态投影抽象。"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.modules.strategy_turn.schemas import (
    ActionOutcome,
    AdvanceOutcome,
    GameStateProjection,
    InitialStateOutcome,
    ResolvedGameAction,
    StrategyTurnRuntimeRule,
    TerminalDirective,
)


class GameLifecycleEngine(ABC):
    """只负责对局状态生命周期的游戏引擎。"""

    @abstractmethod
    def build_initial_state(self, runtime_rule: StrategyTurnRuntimeRule) -> InitialStateOutcome:
        """
        构建初始对局状态。

        :param runtime_rule: 运行时规则快照。
        :return: 初始状态结果（含状态、事件与终局标记）。
        """

    @abstractmethod
    def apply_resolved_action(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
    ) -> ActionOutcome:
        """
        应用已解析动作。

        :param state: 当前对局状态。
        :param action: 已解析动作。
        :return: 动作执行结果。
        """

    @abstractmethod
    def advance(self, state: Dict[str, Any]) -> AdvanceOutcome:
        """
        推进无需玩家输入的阶段。

        :param state: 当前对局状态。
        :return: 推进结果（含状态、事件与终局标记）。
        """

    @abstractmethod
    def is_game_over(self, state: Dict[str, Any]) -> bool:
        """
        判断对局是否结束。

        :param state: 当前对局状态。
        :return: 已结束返回 True。
        """

    def build_terminal_directive(
        self,
        state: Dict[str, Any],
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> Optional[TerminalDirective]:
        """
        构建平台级终局指令；默认仅展示后收敛，不做积分结算。

        :param state: 当前对局状态。
        :param runtime_rule: 运行时规则。
        :return: 终局指令；不需要特殊处理时返回展示指令。
        """
        del state, runtime_rule
        return TerminalDirective(
            requiresPlatformSettlement=False,
            displayDurationMs=3000,
        )


class GameStateProjector(ABC):
    """只负责从状态构建玩家可见投影。"""

    @abstractmethod
    def project(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
        current_time_ms: Optional[int] = None,
    ) -> GameStateProjection:
        """
        构建指定视角的状态投影。

        :param state: 当前对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 状态投影。
        """
