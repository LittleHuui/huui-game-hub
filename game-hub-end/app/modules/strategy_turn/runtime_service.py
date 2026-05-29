"""策略回合制平台运行时编排服务。"""

from typing import Any, Dict, List, Optional, Tuple

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException, ValidationException
from app.core.time_utils import now_ms
from app.modules.strategy_turn.rule_engine import StrategyTurnRuleEngine
from app.modules.strategy_turn.rule_engine_registry import get_rule_engine
from app.modules.strategy_turn.schemas import (
    ApplyActionCommand,
    ApplyActionResult,
    GameAction,
    GameEvent,
    GameView,
    RuntimeSnapshot,
    StartGameCommand,
    StartGameResult,
)


class StrategyTurnRuntimeService(object):
    """策略回合制运行时编排骨架；不访问 Redis、DB 或 WebSocket。"""

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
        engine = self._require_engine(game_code)
        state = engine.build_initial_state(runtime_rule)
        current_time = now_ms()
        snapshot = RuntimeSnapshot(
            gameCode=game_code,
            roomId=command.roomId,
            runtimeRule=runtime_rule,
            state=state,
            eventLog=[],
            eventSequence=0,
            startedAt=current_time,
            updatedAt=current_time,
            isGameOver=engine.is_game_over(state),
        )
        return StartGameResult(snapshot=snapshot, newEvents=[])

    def apply_player_action(
        self,
        snapshot: RuntimeSnapshot,
        command: ApplyActionCommand,
    ) -> ApplyActionResult:
        """
        校验并应用玩家操作，推进规则引擎后返回更新快照。

        :param snapshot: 当前运行时快照。
        :param command: 玩家操作命令。
        :return: 应用操作结果。
        """
        if snapshot.isGameOver:
            raise ValidationException("对局已结束，无法继续提交操作")
        game_code = self._normalize_game_code(snapshot.gameCode)
        engine = self._require_engine(game_code)
        action = command.action
        self._validate_action_player(snapshot, action)

        base_state = dict(snapshot.state or {})
        base_state["eventSequence"] = snapshot.eventSequence

        state_after_action = engine.apply_action(base_state, action)
        engine_events, next_sequence = self._extract_engine_events(
            snapshot.gameCode,
            state_after_action,
            snapshot.eventSequence,
        )

        state_after_advance = engine.advance(
            self._attach_event_sequence(state_after_action, next_sequence),
        )
        advance_events, final_sequence = self._extract_engine_events(
            snapshot.gameCode,
            state_after_advance,
            next_sequence,
        )

        merged_events = engine_events + advance_events
        cleaned_state = dict(state_after_advance or {})
        cleaned_state.pop("lastActionEvents", None)

        current_time = now_ms()
        updated_snapshot = snapshot.model_copy(
            update={
                "state": cleaned_state,
                "updatedAt": current_time,
                "isGameOver": engine.is_game_over(cleaned_state),
                "eventLog": list(snapshot.eventLog) + merged_events,
                "eventSequence": final_sequence,
            },
        )
        return ApplyActionResult(snapshot=updated_snapshot, newEvents=merged_events)

    def build_view(
        self,
        snapshot: RuntimeSnapshot,
        viewer_player_id: str,
    ) -> GameView:
        """
        为指定玩家构建对局视图。

        :param snapshot: 当前运行时快照。
        :param viewer_player_id: 视角玩家 ID。
        :return: 玩家视图。
        """
        game_code = self._normalize_game_code(snapshot.gameCode)
        normalized_viewer_id = str(viewer_player_id).strip()
        if not normalized_viewer_id:
            raise ValidationException("viewerPlayerId 不能为空")
        if normalized_viewer_id not in snapshot.runtimeRule.playerIds:
            raise ValidationException("viewerPlayerId 不在对局玩家列表中")
        engine = self._require_engine(game_code)
        view = engine.build_view(snapshot.state, normalized_viewer_id)
        return view.model_copy(
            update={
                "roomId": snapshot.roomId,
                "gameCode": game_code,
                "isGameOver": snapshot.isGameOver,
            },
        )

    def _require_engine(self, game_code: str) -> StrategyTurnRuleEngine:
        """
        获取已注册规则引擎。

        :param game_code: 游戏编码。
        :return: 规则引擎实例。
        :raises BizException: 未注册时抛出。
        """
        engine = get_rule_engine(game_code)
        if engine is None:
            raise BizException(ErrorCode.GAME_RULE_DEFINITION_NOT_FOUND)
        return engine

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
        action: GameAction,
    ) -> None:
        """
        校验操作提交者是否在对局玩家列表中。

        :param snapshot: 当前快照。
        :param action: 玩家操作。
        :raises ValidationException: 玩家不在列表中时抛出。
        """
        player_id = str(action.playerId).strip()
        if not player_id:
            raise ValidationException("action.playerId 不能为空")
        action_id = str(action.actionId).strip()
        if not action_id:
            raise ValidationException("action.actionId 不能为空")
        if player_id not in snapshot.runtimeRule.playerIds:
            raise ValidationException("action.playerId 不在对局玩家列表中")

    def _attach_event_sequence(
        self,
        state: Dict[str, Any],
        event_sequence: int,
    ) -> Dict[str, Any]:
        """
        在状态字典中附加 ``eventSequence``，供具体规则引擎读取。

        :param state: 对局状态。
        :param event_sequence: 当前事件序号。
        :return: 新状态字典。
        """
        attached = dict(state or {})
        attached["eventSequence"] = int(event_sequence)
        return attached

    def _extract_engine_events(
        self,
        game_code: str,
        state: Dict[str, Any],
        start_sequence: int,
    ) -> Tuple[List[GameEvent], int]:
        """
        从规则引擎状态中提取本次产生的事件列表并返回新的事件序号。

        :param game_code: 游戏编码（预留按需做差异化处理）。
        :param state: 规则引擎返回的对局状态。
        :param start_sequence: 当前事件起始序号。
        :return: ``(事件列表, 下一条事件序号)``。
        """
        raw_events = state.get("lastActionEvents")
        events: List[GameEvent] = []
        if isinstance(raw_events, list):
            for item in raw_events:
                if isinstance(item, dict):
                    events.append(GameEvent.model_validate(item))
        next_sequence = int(start_sequence) + len(events)
        return events, next_sequence

    def _append_event(
        self,
        snapshot: RuntimeSnapshot,
        event_type: str,
        player_id: Optional[str],
        payload: Dict[str, Any],
    ) -> Tuple[RuntimeSnapshot, List[GameEvent]]:
        """
        向快照追加一条事件并返回更新后的快照与新事件列表。

        :param snapshot: 当前快照。
        :param event_type: 事件类型。
        :param player_id: 关联玩家 ID，可空。
        :param payload: 事件载荷。
        :return: ``(更新快照, 新事件列表)``。
        """
        event = GameEvent(
            eventType=event_type,
            sequence=snapshot.eventSequence,
            playerId=player_id,
            payload=payload,
            createdAt=now_ms(),
        )
        event_log = list(snapshot.eventLog)
        event_log.append(event)
        updated_snapshot = snapshot.model_copy(
            update={
                "eventLog": event_log,
                "eventSequence": snapshot.eventSequence + 1,
            },
        )
        return updated_snapshot, [event]
