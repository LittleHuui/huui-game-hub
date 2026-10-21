"""UNO 生命周期引擎。"""



from typing import Any, Dict



from app.modules.game_impls.uno.uno_action_executor import UnoActionExecutor

from app.modules.game_impls.uno.uno_state_factory import UnoStateFactory

from app.modules.game_impls.uno.uno_turn_progression import UnoTurnProgression

from app.modules.strategy_turn.lifecycle import GameLifecycleEngine

from app.modules.strategy_turn.schemas import (

    ActionOutcome,

    AdvanceOutcome,

    InitialStateOutcome,

    ResolvedGameAction,

    StrategyTurnRuntimeRule,

)





class UnoLifecycleEngine(GameLifecycleEngine):

    """UNO 对局生命周期：开局、应用动作与回合推进。"""



    def __init__(

        self,

        state_factory: UnoStateFactory = None,

        action_executor: UnoActionExecutor = None,

        turn_progression: UnoTurnProgression = None,

    ) -> None:

        """

        初始化生命周期引擎。



        :param state_factory: 开局状态工厂，可空则使用默认实例。

        :param action_executor: 动作执行器，可空则使用默认实例。

        :param turn_progression: 回合推进器，可空则使用默认实例。

        :return: 无。

        """

        self._state_factory = state_factory or UnoStateFactory()

        self._action_executor = action_executor or UnoActionExecutor()

        self._turn_progression = turn_progression or UnoTurnProgression()



    def build_initial_state(self, runtime_rule: StrategyTurnRuntimeRule) -> InitialStateOutcome:

        """

        构建 UNO 初始对局状态。



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

        应用已解析 UNO 动作。



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

        推进 UNO 回合（切换当前玩家等）。



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

        判断 UNO 对局是否结束。



        :param state: 当前对局状态。

        :return: 已结束返回 True。

        """

        return self._turn_progression.is_game_over(state)
