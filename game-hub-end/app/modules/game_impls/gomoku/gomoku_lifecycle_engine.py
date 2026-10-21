"""五子棋生命周期引擎。"""

from typing import Any, Dict

from app.modules.game_impls.gomoku.gomoku_action_executor import GomokuActionExecutor
from app.modules.game_impls.gomoku.gomoku_state_factory import GomokuStateFactory
from app.modules.game_impls.gomoku.gomoku_turn_progression import GomokuTurnProgression
from app.modules.strategy_turn.lifecycle import GameLifecycleEngine
from app.modules.strategy_turn.schemas import (
    ActionOutcome,
    AdvanceOutcome,
    InitialStateOutcome,
    ResolvedGameAction,
    StrategyTurnRuntimeRule,
)


class GomokuLifecycleEngine(GameLifecycleEngine):
    """五子棋对局生命周期。"""

    def __init__(
        self,
        state_factory: GomokuStateFactory = None,
        action_executor: GomokuActionExecutor = None,
        turn_progression: GomokuTurnProgression = None,
    ) -> None:
        """
        初始化生命周期引擎。

        :param state_factory: 开局状态工厂，可空则使用默认实例。
        :param action_executor: 动作执行器，可空则使用默认实例。
        :param turn_progression: 回合推进器，可空则使用默认实例。
        :return: 无。
        """
        self._state_factory = state_factory or GomokuStateFactory()
        self._action_executor = action_executor or GomokuActionExecutor()
        self._turn_progression = turn_progression or GomokuTurnProgression()

    def build_initial_state(self, runtime_rule: StrategyTurnRuntimeRule) -> InitialStateOutcome:
        """
        构建五子棋初始对局状态。

        :param runtime_rule: 运行时规则快照。
        :return: 初始状态结果。
        """
        state = self._state_factory.build_initial_state(runtime_rule)
        return InitialStateOutcome(
            state=state,
            events=[],
            gameOver=self._turn_progression.is_game_over(state),
        )

    def apply_resolved_action(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
    ) -> ActionOutcome:
        """
        应用已解析五子棋动作。

        :param state: 当前对局状态。
        :param action: 已解析动作。
        :return: 动作执行结果。
        """
        new_state, events = self._action_executor.apply_resolved_action(state, action)
        return ActionOutcome(
            resolvedAction=action,
            state=new_state,
            events=events,
            gameOver=self._turn_progression.is_game_over(new_state),
        )

    def advance(self, state: Dict[str, Any]) -> AdvanceOutcome:
        """
        五子棋无额外推进逻辑，返回状态副本。

        :param state: 当前对局状态。
        :return: 推进结果。
        """
        new_state, events = self._turn_progression.advance(state)
        return AdvanceOutcome(
            state=new_state,
            events=events,
            gameOver=self._turn_progression.is_game_over(new_state),
        )

    def is_game_over(self, state: Dict[str, Any]) -> bool:
        """
        判断五子棋对局是否结束。

        :param state: 当前对局状态。
        :return: 已结束返回 True。
        """
        return self._turn_progression.is_game_over(state)
