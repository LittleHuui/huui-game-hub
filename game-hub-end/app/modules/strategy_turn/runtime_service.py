"""策略回合制平台运行时编排服务。"""

from typing import Any, Dict, List

from app.common.exceptions import ValidationException
from app.core.clock import Clock, system_clock
from app.core.config import settings
from app.modules.strategy_turn.game_module import StrategyTurnGameModuleRegistry
from app.modules.strategy_turn.lifecycle import GameLifecycleEngine
from app.modules.strategy_turn.schemas import (
    ApplyActionCommand,
    ApplyActionResult,
    DomainEventDraft,
    GameEvent,
    InitialStateOutcome,
    ResolvedGameAction,
    RuntimeSnapshot,
    StartGameCommand,
    StartGameResult,
)


class StrategyTurnRuntimeService(object):
    """策略回合制运行时编排骨架；不访问 Redis、DB 或 WebSocket。"""

    def __init__(
        self,
        module_registry: StrategyTurnGameModuleRegistry,
        clock: Clock = system_clock,
        event_log_limit: int = settings.RUNTIME_EVENT_LOG_LIMIT,
    ) -> None:
        """
        初始化运行时服务。

        :param module_registry: 游戏模块注册表。
        :return: 无。
        """
        self._module_registry = module_registry
        self._clock = clock
        self._event_log_limit = max(1, int(event_log_limit))

    def start_game(self, command: StartGameCommand) -> StartGameResult:
        """
        根据运行时规则初始化对局并返回首帧快照。

        :param command: 开始对局命令。
        :return: 开始对局结果。
        """
        game_code = self._normalize_game_code(command.gameCode)
        runtime_rule = command.runtimeRule
        if runtime_rule.gameCode != game_code:
            raise ValidationException("runtimeRule.gameCode 与 command.gameCode 不一致")
        engine = self._require_lifecycle_engine(game_code)
        initial_outcome = engine.build_initial_state(runtime_rule)
        current_time = self._clock.now_ms()
        initial_events = self._materialize_events(list(initial_outcome.events or []), 0)
        event_sequence = len(initial_events)
        snapshot = RuntimeSnapshot(
            gameCode=game_code,
            roomId=command.roomId,
            runtimeRule=runtime_rule,
            state=dict(initial_outcome.state or {}),
            eventLog=initial_events,
            eventSequence=event_sequence,
            startedAt=current_time,
            updatedAt=current_time,
            isGameOver=self._resolve_game_over(engine, initial_outcome.gameOver, initial_outcome.state),
        )
        return StartGameResult(snapshot=snapshot, newEvents=initial_events)

    def apply_resolved_action(
        self,
        snapshot: RuntimeSnapshot,
        command: ApplyActionCommand,
    ) -> ApplyActionResult:
        """
        应用已解析玩家操作，推进生命周期引擎后返回更新快照。

        :param snapshot: 当前运行时快照。
        :param command: 玩家操作命令。
        :return: 应用操作结果。
        """
        if snapshot.isGameOver:
            raise ValidationException("对局已结束，无法继续提交操作")
        game_code = self._normalize_game_code(snapshot.gameCode)
        engine = self._require_lifecycle_engine(game_code)
        action = command.action
        self._validate_action_player(snapshot, action)

        base_state = dict(snapshot.state or {})
        action_outcome = engine.apply_resolved_action(base_state, action)
        state_after_action = action_outcome.state
        engine_events = self._materialize_events(
            list(action_outcome.events or []),
            snapshot.eventSequence,
        )
        next_sequence = snapshot.eventSequence + len(engine_events)

        if self._state_has_pending_phase_auto_advance(state_after_action):
            advance_events = []
            final_sequence = next_sequence
            state_after_advance = state_after_action
            is_game_over = self._resolve_game_over(
                engine,
                action_outcome.gameOver,
                state_after_advance,
            )
        else:
            advance_outcome = engine.advance(state_after_action)
            state_after_advance = advance_outcome.state
            advance_events = self._materialize_events(
                list(advance_outcome.events or []),
                next_sequence,
            )
            final_sequence = next_sequence + len(advance_events)
            is_game_over = self._resolve_game_over(
                engine,
                advance_outcome.gameOver,
                state_after_advance,
            )

        merged_events = engine_events + advance_events
        current_time = self._clock.now_ms()
        terminal_directive = None
        if is_game_over:
            terminal_directive = engine.build_terminal_directive(
                dict(state_after_advance or {}),
                snapshot.runtimeRule,
            )
        updated_snapshot = snapshot.model_copy(
            update={
                "state": dict(state_after_advance or {}),
                "updatedAt": current_time,
                "isGameOver": is_game_over,
                "eventLog": self._trim_event_log(
                    list(snapshot.eventLog) + merged_events,
                ),
                "eventSequence": final_sequence,
                "terminalDirective": terminal_directive,
            },
        )
        return ApplyActionResult(snapshot=updated_snapshot, newEvents=merged_events)

    def advance_snapshot(self, snapshot: RuntimeSnapshot) -> ApplyActionResult:
        """
        无玩家动作地推进生命周期引擎并合并显式事件。

        :param snapshot: 当前运行时快照。
        :return: 推进后的快照与本次新事件。
        """
        if snapshot.isGameOver:
            raise ValidationException("对局已结束，无法继续推进")
        game_code = self._normalize_game_code(snapshot.gameCode)
        engine = self._require_lifecycle_engine(game_code)
        base_state = dict(snapshot.state or {})
        advance_outcome = engine.advance(base_state)
        advance_events = self._materialize_events(
            list(advance_outcome.events or []),
            snapshot.eventSequence,
        )
        final_sequence = snapshot.eventSequence + len(advance_events)
        current_time = self._clock.now_ms()
        is_game_over = self._resolve_game_over(
            engine,
            advance_outcome.gameOver,
            advance_outcome.state,
        )
        terminal_directive = None
        if is_game_over:
            terminal_directive = engine.build_terminal_directive(
                dict(advance_outcome.state or {}),
                snapshot.runtimeRule,
            )
        updated_snapshot = snapshot.model_copy(
            update={
                "state": dict(advance_outcome.state or {}),
                "updatedAt": current_time,
                "isGameOver": is_game_over,
                "eventLog": self._trim_event_log(
                    list(snapshot.eventLog) + advance_events,
                ),
                "eventSequence": final_sequence,
                "terminalDirective": terminal_directive,
            },
        )
        return ApplyActionResult(snapshot=updated_snapshot, newEvents=advance_events)

    def _require_lifecycle_engine(self, game_code: str) -> GameLifecycleEngine:
        """
        获取已注册生命周期引擎。

        :param game_code: 游戏编码。
        :return: 生命周期引擎实例。
        """
        return self._module_registry.require(game_code).lifecycleEngine

    def _materialize_events(
        self,
        drafts: List[DomainEventDraft],
        start_sequence: int,
    ) -> List[GameEvent]:
        """
        将领域事件草稿转为带序号与时间戳的最终事件。

        :param drafts: 事件草稿列表。
        :param start_sequence: 起始序号。
        :return: 最终事件列表。
        """
        events = []
        sequence = int(start_sequence)
        current_time = self._clock.now_ms()
        for draft in drafts or []:
            events.append(
                GameEvent(
                    eventType=str(draft.eventType),
                    sequence=sequence,
                    playerId=draft.playerId,
                    payload=dict(draft.payload or {}),
                    createdAt=current_time,
                )
            )
            sequence = sequence + 1
        return events

    def _trim_event_log(self, events: List[GameEvent]) -> List[GameEvent]:
        """
        仅保留 Runtime 配置允许的最近事件。
        :param events: 完整候选事件列表。
        :return: 裁剪后的最近事件。
        """
        if len(events) <= self._event_log_limit:
            return events
        return events[-self._event_log_limit:]

    def _normalize_game_code(self, game_code: str) -> str:
        """
        规范化游戏编码。

        :param game_code: 原始游戏编码。
        :return: 去空白后的编码。
        :raises ValidationException: 为空时抛出。
        """
        normalized = str(game_code).strip()
        if not normalized:
            raise ValidationException("gameCode 不能为空")
        return normalized

    def _validate_action_player(
        self,
        snapshot: RuntimeSnapshot,
        action: ResolvedGameAction,
    ) -> None:
        """
        校验操作提交者是否在对局玩家列表中。

        :param snapshot: 当前快照。
        :param action: 玩家操作。
        :raises ValidationException: 玩家不在列表中时抛出。
        """
        player_id = str(action.playerId or "").strip()
        if not player_id:
            raise ValidationException("action.playerId 不能为空")
        action_id = str(action.actionId or "").strip()
        if not action_id:
            raise ValidationException("action.actionId 不能为空")
        if player_id not in snapshot.runtimeRule.playerIds:
            raise ValidationException("action.playerId 不在对局玩家列表中")

    def _resolve_game_over(
        self,
        engine: GameLifecycleEngine,
        outcome_game_over: bool,
        state: Dict[str, Any],
    ) -> bool:
        """
        综合生命周期结果与引擎判断确定终局标记。

        :param engine: 生命周期引擎。
        :param outcome_game_over: 生命周期结果中的终局标记。
        :param state: 当前对局状态。
        :return: 是否已终局。
        """
        if bool(outcome_game_over):
            return True
        return bool(engine.is_game_over(state or {}))

    def _state_has_pending_phase_auto_advance(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        判断状态是否声明了待定时器触发的阶段自动推进。

        :param state: 对局状态。
        :return: 存在且启用时为 ``True``。
        """
        phase_auto_advance = state.get("phaseAutoAdvance")
        if not isinstance(phase_auto_advance, dict):
            return False
        return bool(phase_auto_advance.get("enabled"))
