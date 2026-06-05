"""五子棋策略回合制规则引擎。"""

import copy
from typing import Any, Dict, List, Optional, Tuple

from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.strategy_turn.rule_engine import StrategyTurnRuleEngine
from app.modules.strategy_turn.schemas import (
    GameAction,
    GameEvent,
    GameView,
    LegalAction,
    StrategyTurnRuntimeRule,
)

_ACTION_PLACE_STONE = "PLACE_STONE"
_ACTION_REQUEST_UNDO = "REQUEST_UNDO"
_ACTION_ACCEPT_UNDO = "ACCEPT_UNDO"
_ACTION_REJECT_UNDO = "REJECT_UNDO"
_ACTION_RESIGN = "RESIGN"
_MOVE_PLACE_STONE = "PLACE_STONE"
_MOVE_UNDO_REQUEST = "UNDO_REQUEST"
_MOVE_UNDO_ACCEPT = "UNDO_ACCEPT"
_MOVE_UNDO_REJECT = "UNDO_REJECT"
_MOVE_UNDO_STONE = "UNDO_STONE"
_MOVE_RESIGN = "RESIGN"
_PHASE_PLAYING = "playing"
_PHASE_FINISHED = "finished"
_STATE_EVENTS_KEY = "lastActionEvents"
_MOVE_TIMEOUT_PLACE_STONE = "TIMEOUT_PLACE_STONE"
_DEFAULT_UNDO_REQUEST_EXPIRE_SECONDS = 30


class GomokuRuleEngine(StrategyTurnRuleEngine):
    """五子棋规则引擎。"""

    def build_initial_state(
        self,
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> Dict[str, Any]:
        """
        根据运行时规则构建初始对局状态。

        :param runtime_rule: 运行时规则。
        :return: 对局状态字典。
        """
        current_time = now_ms()
        player_ids = list(runtime_rule.playerIds)
        if len(player_ids) != 2:
            raise ValidationException("五子棋需要且仅需要 2 名玩家")
        config = dict(runtime_rule.config or {})
        board_size = self._read_int_config(config, "boardSize", 15)
        win_length = self._read_int_config(config, "winLength", 5)
        turn_timeout_seconds = self._read_int_config(config, "turnTimeoutSeconds", 30)
        undo_request_expire_seconds = self._read_int_config(
            config,
            "undoRequestExpireSeconds",
            _DEFAULT_UNDO_REQUEST_EXPIRE_SECONDS,
        )
        if board_size < 5:
            raise ValidationException("五子棋棋盘尺寸不能小于 5")
        if board_size > 30:
            raise ValidationException("五子棋棋盘尺寸不能大于 30")
        if win_length < 3:
            raise ValidationException("五子棋连子长度不能小于 3")
        if win_length > board_size:
            raise ValidationException("五子棋连子长度不能大于棋盘尺寸")
        if turn_timeout_seconds < 10:
            raise ValidationException("五子棋回合时间不能小于 10 秒")
        if turn_timeout_seconds > 120:
            raise ValidationException("五子棋回合时间不能大于 120 秒")
        if undo_request_expire_seconds < 10:
            raise ValidationException("五子棋悔棋请求有效时间不能小于 10 秒")
        if undo_request_expire_seconds > 120:
            raise ValidationException("五子棋悔棋请求有效时间不能大于 120 秒")
        state = {
            "phase": _PHASE_PLAYING,
            "boardSize": board_size,
            "winLength": win_length,
            "turnTimeoutSeconds": turn_timeout_seconds,
            "undoRequestExpireSeconds": undo_request_expire_seconds,
            "board": [[None for _ in range(board_size)] for _ in range(board_size)],
            "players": [
                {"playerId": player_ids[0], "seatIndex": 0, "stone": "BLACK"},
                {"playerId": player_ids[1], "seatIndex": 1, "stone": "WHITE"},
            ],
            "currentPlayerId": player_ids[0],
            "currentStone": "BLACK",
            "moves": [],
            "lastPlaceMoveId": None,
            "lastPlaceRow": None,
            "lastPlaceCol": None,
            "undoRequest": None,
            "winnerPlayerId": None,
            "winnerStone": None,
            "finishReason": None,
            "currentTurnStartedAt": current_time,
            "currentTurnDeadlineAt": current_time + turn_timeout_seconds * 1000,
            "roomConfig": config,
            "enableUndo": self._read_bool_config(config, "enableUndo", True),
            "moveCounter": 0,
        }
        return state

    def _now_ms(self) -> int:
        """
        获取当前毫秒时间戳。

        :return: 毫秒时间戳。
        """
        return now_ms()

    def _read_int_config(
        self,
        config: Dict[str, Any],
        key: str,
        default: int,
    ) -> int:
        """
        安全读取整数配置项。

        :param config: 房间配置。
        :param key: 配置键。
        :param default: 默认值。
        :return: 整数值。
        """
        raw_value = config.get(key, default)
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            raise ValidationException("五子棋配置 {0} 必须是数字".format(key))

    def _read_bool_config(
        self,
        config: Dict[str, Any],
        key: str,
        default: bool,
    ) -> bool:
        """
        安全读取布尔配置项。

        :param config: 房间配置。
        :param key: 配置键。
        :param default: 默认值。
        :return: 布尔值。
        """
        value = config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("true", "1", "yes", "on"):
                return True
            if normalized in ("false", "0", "no", "off"):
                return False
        raise ValidationException("五子棋配置 {0} 必须是布尔值".format(key))

    def _is_undo_request_expired(
        self,
        undo_request: Any,
        now: int,
    ) -> bool:
        """
        判断悔棋申请是否已过期。

        :param undo_request: 悔棋申请字典。
        :param now: 当前毫秒时间戳。
        :return: 已过期为 ``True``。
        """
        if not undo_request:
            return False
        expires_at = int(undo_request.get("expiresAt") or 0)
        return expires_at > 0 and now > expires_at

    def _clear_expired_undo_request(
        self,
        state: Dict[str, Any],
        now: int,
    ) -> None:
        """
        清理已过期的悔棋申请并追加拒绝流水。

        :param state: 对局状态。
        :param now: 当前毫秒时间戳。
        :return: 无。
        """
        undo_request = state.get("undoRequest")
        if not self._is_undo_request_expired(undo_request, now):
            return
        _append_move(
            state,
            {
                "moveType": _MOVE_UNDO_REJECT,
                "playerId": undo_request.get("targetPlayerId"),
                "targetMoveId": undo_request.get("targetMoveId"),
                "reason": "EXPIRED",
                "createdAt": now,
            },
        )
        state["undoRequest"] = None

    def _get_active_undo_request(
        self,
        state: Dict[str, Any],
        now: int,
    ) -> Optional[Dict[str, Any]]:
        """
        只读获取未过期的悔棋申请，不修改 state。

        :param state: 对局状态。
        :param now: 当前毫秒时间戳。
        :return: 有效悔棋申请或 ``None``。
        """
        undo_request = state.get("undoRequest")
        if not undo_request:
            return None
        if self._is_undo_request_expired(undo_request, now):
            return None
        return undo_request

    def list_legal_actions(
        self,
        state: Dict[str, Any],
        player_id: str,
    ) -> List[LegalAction]:
        """
        列出指定玩家可执行的合法操作。

        :param state: 当前对局状态。
        :param player_id: 玩家 ID。
        :return: 合法操作列表。
        """
        now = self._now_ms()
        active_undo = self._get_active_undo_request(state, now)
        normalized_id = str(player_id).strip()
        if state.get("phase") == _PHASE_FINISHED:
            return []
        if state.get("winnerPlayerId"):
            return []
        actions: List[LegalAction] = []
        if state.get("currentPlayerId") == normalized_id:
            for row, col in _empty_cells(state.get("board") or []):
                actions.append(
                    LegalAction(
                        actionType=_ACTION_PLACE_STONE,
                        actionId="PLACE_STONE:{0}:{1}".format(row, col),
                        playerId=normalized_id,
                        payload={"row": row, "col": col},
                        selection={
                            "type": "BOARD_CELL",
                            "config": {"row": row, "col": col},
                        },
                    )
                )
            actions.append(
                LegalAction(
                    actionType=_ACTION_RESIGN,
                    actionId=_ACTION_RESIGN,
                    playerId=normalized_id,
                    payload={},
                    selection={"type": "ACTION_BUTTON", "config": {"name": "resign"}},
                )
            )
        if _can_request_undo(state, normalized_id, active_undo):
            actions.append(
                LegalAction(
                    actionType=_ACTION_REQUEST_UNDO,
                    actionId=_ACTION_REQUEST_UNDO,
                    playerId=normalized_id,
                    payload={},
                    selection={
                        "type": "ACTION_BUTTON",
                        "config": {"name": "requestUndo"},
                    },
                )
            )
        if _can_handle_undo(state, normalized_id, active_undo):
            target_move_id = str(active_undo.get("targetMoveId") or "") if active_undo else ""
            actions.append(
                LegalAction(
                    actionType=_ACTION_ACCEPT_UNDO,
                    actionId=_ACTION_ACCEPT_UNDO,
                    playerId=normalized_id,
                    payload={"targetMoveId": target_move_id},
                    selection={
                        "type": "ACTION_BUTTON",
                        "config": {"name": "acceptUndo"},
                    },
                )
            )
            actions.append(
                LegalAction(
                    actionType=_ACTION_REJECT_UNDO,
                    actionId=_ACTION_REJECT_UNDO,
                    playerId=normalized_id,
                    payload={"targetMoveId": target_move_id},
                    selection={
                        "type": "ACTION_BUTTON",
                        "config": {"name": "rejectUndo"},
                    },
                )
            )
        return actions

    def apply_action(
        self,
        state: Dict[str, Any],
        action: GameAction,
    ) -> Dict[str, Any]:
        """
        校验并应用玩家操作。

        :param state: 当前对局状态。
        :param action: 玩家提交的操作。
        :return: 更新后的对局状态。
        """
        working = copy.deepcopy(state)
        now = self._now_ms()
        action_id = str(action.actionId).strip()
        if action_id in (_ACTION_ACCEPT_UNDO, _ACTION_REJECT_UNDO):
            if self._is_undo_request_expired(working.get("undoRequest"), now):
                raise ValidationException("悔棋请求已失效")
        else:
            self._clear_expired_undo_request(working, now)
        legal_actions = self.list_legal_actions(working, action.playerId)
        matched = _find_by_action_id(legal_actions, action.actionId)
        if matched is None:
            if action_id in (_ACTION_ACCEPT_UNDO, _ACTION_REJECT_UNDO) and not working.get(
                "undoRequest"
            ):
                raise ValidationException("悔棋请求已失效")
            raise ValidationException("非法操作")
        if matched.actionType == _ACTION_PLACE_STONE:
            return self._apply_place_stone(working, matched)
        if matched.actionType == _ACTION_REQUEST_UNDO:
            return self._apply_request_undo(working, matched)
        if matched.actionType == _ACTION_ACCEPT_UNDO:
            return self._apply_accept_undo(working, matched)
        if matched.actionType == _ACTION_REJECT_UNDO:
            return self._apply_reject_undo(working, matched)
        if matched.actionType == _ACTION_RESIGN:
            return self._apply_resign(working, matched)
        raise ValidationException("不支持的操作")

    def advance(
        self,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        五子棋在 ``apply_action`` 内已完成回合切换，此处无需额外推进。

        :param state: 当前对局状态。
        :return: 原状态副本。
        """
        next_state = copy.deepcopy(state)
        next_state[_STATE_EVENTS_KEY] = []
        return next_state

    def build_view(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
    ) -> GameView:
        """
        构建玩家可见对局视图。

        :param state: 当前对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 对局视图。
        """
        now = self._now_ms()
        active_undo = self._get_active_undo_request(state, now)
        viewer_id = str(viewer_player_id).strip()
        return GameView(
            gameCode="gomoku",
            viewerPlayerId=viewer_id,
            phase=str(state.get("phase") or _PHASE_PLAYING),
            currentPlayerId=state.get("currentPlayerId"),
            legalActions=self.list_legal_actions(state, viewer_id),
            publicState={
                "players": state.get("players") or [],
                "currentPlayerId": state.get("currentPlayerId"),
                "gameState": {
                    "boardSize": state.get("boardSize"),
                    "winLength": state.get("winLength"),
                    "board": state.get("board") or [],
                    "lastPlaceMoveId": state.get("lastPlaceMoveId"),
                    "lastPlaceRow": state.get("lastPlaceRow"),
                    "lastPlaceCol": state.get("lastPlaceCol"),
                    "lastMove": _find_last_effective_place_move(state.get("moves") or []),
                    "movesCount": len(state.get("moves") or []),
                    "undoRequest": _public_undo_request(active_undo),
                    "winnerPlayerId": state.get("winnerPlayerId"),
                    "winnerStone": state.get("winnerStone"),
                    "finishReason": state.get("finishReason"),
                    "currentTurnStartedAt": state.get("currentTurnStartedAt"),
                    "currentTurnDeadlineAt": state.get("currentTurnDeadlineAt"),
                },
            },
            privateState={},
            isGameOver=self.is_game_over(state),
            version=0,
            events=[],
        )

    def is_game_over(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        判断对局是否已结束。

        :param state: 当前对局状态。
        :return: 已结束为 ``True``。
        """
        return state.get("phase") == _PHASE_FINISHED or bool(state.get("winnerPlayerId"))

    def _apply_place_stone(
        self,
        state: Dict[str, Any],
        action: LegalAction,
    ) -> Dict[str, Any]:
        """
        应用落子操作。

        :param state: 当前状态。
        :param action: 合法落子操作。
        :return: 更新后的状态。
        """
        current_time = now_ms()
        row = int(action.payload["row"])
        col = int(action.payload["col"])
        player_id = action.playerId
        if state.get("currentPlayerId") != player_id:
            raise ValidationException("未轮到当前玩家")
        board = state.get("board") or []
        if board[row][col] is not None:
            raise ValidationException("该位置已有棋子")
        if state.get("undoRequest") is not None:
            _append_undo_reject_move(state, player_id, current_time)
            state["undoRequest"] = None
        stone = state.get("currentStone")
        move = _append_move(
            state,
            {
                "moveType": _MOVE_PLACE_STONE,
                "playerId": player_id,
                "row": row,
                "col": col,
                "stone": stone,
                "createdAt": current_time,
            },
        )
        board[row][col] = stone
        state["lastPlaceMoveId"] = move["moveId"]
        state["lastPlaceRow"] = row
        state["lastPlaceCol"] = col
        win_length = int(state.get("winLength") or 5)
        if _has_five_in_row(board, row, col, stone, win_length):
            state["phase"] = _PHASE_FINISHED
            state["winnerPlayerId"] = player_id
            state["winnerStone"] = stone
            state["finishReason"] = "FIVE_IN_ROW"
        else:
            _switch_turn(state)
            _reset_turn_clock(state, current_time)
        self._record_action_events(
            state,
            "gomoku.place_stone",
            player_id,
            {"row": row, "col": col, "stone": stone, "moveId": move["moveId"]},
        )
        return state

    def _apply_request_undo(
        self,
        state: Dict[str, Any],
        action: LegalAction,
    ) -> Dict[str, Any]:
        """
        申请悔棋。

        :param state: 当前状态。
        :param action: 合法悔棋申请操作。
        :return: 更新后的状态。
        """
        current_time = now_ms()
        player_id = action.playerId
        last_place = _find_last_effective_place_move(state.get("moves") or [])
        if last_place is None:
            raise ValidationException("没有可悔的落子")
        opponent_id = _opponent_player_id(state, player_id)
        expire_seconds = int(
            state.get("undoRequestExpireSeconds") or _DEFAULT_UNDO_REQUEST_EXPIRE_SECONDS
        )
        request_id = "undo_{0}".format(current_time)
        state["undoRequest"] = {
            "requestId": request_id,
            "requesterPlayerId": player_id,
            "targetPlayerId": opponent_id,
            "targetMoveId": last_place["moveId"],
            "requestedAt": current_time,
            "expiresAt": current_time + expire_seconds * 1000,
        }
        _append_move(
            state,
            {
                "moveType": _MOVE_UNDO_REQUEST,
                "playerId": player_id,
                "targetMoveId": last_place["moveId"],
                "createdAt": current_time,
            },
        )
        self._record_action_events(
            state,
            "gomoku.undo.requested",
            player_id,
            {"targetMoveId": last_place["moveId"], "requestId": request_id},
        )
        return state

    def _apply_accept_undo(
        self,
        state: Dict[str, Any],
        action: LegalAction,
    ) -> Dict[str, Any]:
        """
        同意悔棋。

        :param state: 当前状态。
        :param action: 合法同意悔棋操作。
        :return: 更新后的状态。
        """
        current_time = self._now_ms()
        undo_request = state.get("undoRequest")
        if not undo_request:
            raise ValidationException("悔棋请求已失效")
        if undo_request.get("targetPlayerId") != action.playerId:
            raise ValidationException("无权处理该悔棋申请")
        target = _find_move_by_id(state.get("moves") or [], undo_request["targetMoveId"])
        if target is None:
            raise ValidationException("悔棋目标不存在")
        board = state.get("board") or []
        row = int(target["row"])
        col = int(target["col"])
        board[row][col] = None
        _append_move(
            state,
            {
                "moveType": _MOVE_UNDO_ACCEPT,
                "playerId": action.playerId,
                "targetMoveId": target["moveId"],
                "createdAt": current_time,
            },
        )
        _append_move(
            state,
            {
                "moveType": _MOVE_UNDO_STONE,
                "playerId": undo_request["requesterPlayerId"],
                "targetMoveId": target["moveId"],
                "row": row,
                "col": col,
                "stone": target["stone"],
                "createdAt": current_time,
            },
        )
        state["currentPlayerId"] = undo_request["requesterPlayerId"]
        state["currentStone"] = target["stone"]
        state["undoRequest"] = None
        latest_place = _find_last_effective_place_move(state.get("moves") or [])
        if latest_place is not None:
            state["lastPlaceMoveId"] = latest_place.get("moveId")
            state["lastPlaceRow"] = latest_place.get("row")
            state["lastPlaceCol"] = latest_place.get("col")
        else:
            state["lastPlaceMoveId"] = None
            state["lastPlaceRow"] = None
            state["lastPlaceCol"] = None
        _reset_turn_clock(state, current_time)
        self._record_action_events(
            state,
            "gomoku.undo.accepted",
            action.playerId,
            {"targetMoveId": target["moveId"]},
        )
        return state

    def _apply_reject_undo(
        self,
        state: Dict[str, Any],
        action: LegalAction,
    ) -> Dict[str, Any]:
        """
        拒绝悔棋。

        :param state: 当前状态。
        :param action: 合法拒绝悔棋操作。
        :return: 更新后的状态。
        """
        current_time = self._now_ms()
        undo_request = state.get("undoRequest")
        if not undo_request:
            raise ValidationException("悔棋请求已失效")
        if undo_request.get("targetPlayerId") != action.playerId:
            raise ValidationException("无权处理该悔棋申请")
        _append_move(
            state,
            {
                "moveType": _MOVE_UNDO_REJECT,
                "playerId": action.playerId,
                "targetMoveId": undo_request["targetMoveId"],
                "createdAt": current_time,
            },
        )
        state["undoRequest"] = None
        self._record_action_events(
            state,
            "gomoku.undo.rejected",
            action.playerId,
            {},
        )
        return state

    def _apply_resign(
        self,
        state: Dict[str, Any],
        action: LegalAction,
    ) -> Dict[str, Any]:
        """
        认输并结束对局。

        :param state: 当前状态。
        :param action: 合法认输操作。
        :return: 更新后的状态。
        """
        current_time = now_ms()
        player_id = action.playerId
        winner_id = _opponent_player_id(state, player_id)
        winner_stone = _stone_for_player(state, winner_id)
        _append_move(
            state,
            {
                "moveType": _MOVE_RESIGN,
                "playerId": player_id,
                "createdAt": current_time,
            },
        )
        state["phase"] = _PHASE_FINISHED
        state["winnerPlayerId"] = winner_id
        state["winnerStone"] = winner_stone
        state["finishReason"] = "RESIGN"
        state["undoRequest"] = None
        self._record_action_events(
            state,
            "gomoku.resign",
            player_id,
            {"winnerPlayerId": winner_id},
        )
        return state

    def _record_action_events(
        self,
        state: Dict[str, Any],
        event_type: str,
        player_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """
        写入 ``lastActionEvents`` 供运行时提取。

        :param state: 对局状态。
        :param event_type: 事件类型。
        :param player_id: 玩家 ID。
        :param payload: 事件载荷。
        :return: 无。
        """
        sequence = int(state.get("eventSequence") or 0)
        event = GameEvent(
            eventType=event_type,
            sequence=sequence,
            playerId=player_id,
            payload=payload,
            createdAt=now_ms(),
        )
        state[_STATE_EVENTS_KEY] = [event.model_dump()]
        state["eventSequence"] = sequence + 1


def _find_by_action_id(
    legal_actions: List[LegalAction],
    action_id: str,
) -> Optional[LegalAction]:
    """
    按 actionId 查找合法操作。

    :param legal_actions: 合法操作列表。
    :param action_id: 操作 ID。
    :return: 匹配项或 ``None``。
    """
    normalized = str(action_id).strip()
    for item in legal_actions:
        if item.actionId == normalized:
            return item
    return None


def _empty_cells(board: List[List[Any]]) -> List[Tuple[int, int]]:
    """
    枚举空格子坐标。

    :param board: 棋盘。
    :return: (row, col) 列表。
    """
    cells = []
    for row_index, row in enumerate(board):
        for col_index, cell in enumerate(row):
            if cell is None:
                cells.append((row_index, col_index))
    return cells


def _find_last_effective_place_move(moves: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    查找最后一条有效落子记录。

    :param moves: 流水列表。
    :return: 落子记录或 ``None``。
    """
    undone_move_ids = {
        item.get("targetMoveId")
        for item in moves
        if item.get("moveType") == _MOVE_UNDO_STONE
    }
    for item in reversed(moves):
        if item.get("moveType") not in (_MOVE_PLACE_STONE, _MOVE_TIMEOUT_PLACE_STONE):
            continue
        if item.get("moveId") in undone_move_ids:
            continue
        return item
    return None


def _has_undo_stone_for_target(moves: List[Dict[str, Any]], target_move_id: str) -> bool:
    """
    判断目标落子是否已被悔掉。

    :param moves: 流水列表。
    :param target_move_id: 目标 moveId。
    :return: 已悔为 ``True``。
    """
    for item in moves:
        if (
            item.get("moveType") == _MOVE_UNDO_STONE
            and item.get("targetMoveId") == target_move_id
        ):
            return True
    return False


def _find_last_move_by_player(
    moves: List[Dict[str, Any]],
    player_id: str,
) -> Optional[Dict[str, Any]]:
    """
    查找玩家最后一条流水。

    :param moves: 流水列表。
    :param player_id: 玩家 ID。
    :return: 流水或 ``None``。
    """
    for item in reversed(moves):
        if item.get("playerId") == player_id:
            return item
    return None


def _find_move_by_id(
    moves: List[Dict[str, Any]],
    move_id: str,
) -> Optional[Dict[str, Any]]:
    """
    按 moveId 查找流水。

    :param moves: 流水列表。
    :param move_id: moveId。
    :return: 流水或 ``None``。
    """
    for item in moves:
        if item.get("moveId") == move_id:
            return item
    return None


def _is_undo_enabled(state: Dict[str, Any]) -> bool:
    """
    判断房间是否开启悔棋。

    :param state: 对局状态。
    :return: 开启为 ``True``。
    """
    if "enableUndo" in state:
        return bool(state.get("enableUndo", True))
    room_config = state.get("roomConfig") or {}
    return bool(room_config.get("enableUndo", True))


def _can_request_undo(
    state: Dict[str, Any],
    player_id: str,
    active_undo: Optional[Dict[str, Any]],
) -> bool:
    """
    判断是否可申请悔棋。

    :param state: 对局状态。
    :param player_id: 玩家 ID。
    :param active_undo: 未过期的悔棋申请，只读。
    :return: 可申请为 ``True``。
    """
    if not _is_undo_enabled(state):
        return False
    if state.get("phase") == _PHASE_FINISHED:
        return False
    if state.get("winnerPlayerId"):
        return False
    if active_undo is not None:
        return False
    last_place = _find_last_effective_place_move(state.get("moves") or [])
    if last_place is None:
        return False
    if last_place.get("playerId") != player_id:
        return False
    if state.get("currentPlayerId") == player_id:
        return False
    if _has_undo_stone_for_target(state.get("moves") or [], last_place["moveId"]):
        return False
    last_own_move = _find_last_move_by_player(state.get("moves") or [], player_id)
    last_own_move_type = str(last_own_move.get("moveType") or "") if last_own_move else ""
    if last_own_move_type.startswith("UNDO_"):
        return False
    return True


def _can_handle_undo(
    state: Dict[str, Any],
    player_id: str,
    active_undo: Optional[Dict[str, Any]],
) -> bool:
    """
    判断是否为悔棋申请的处理方。

    :param state: 对局状态。
    :param player_id: 玩家 ID。
    :param active_undo: 未过期的悔棋申请，只读。
    :return: 可处理为 ``True``。
    """
    if not _is_undo_enabled(state):
        return False
    if not active_undo:
        return False
    return active_undo.get("targetPlayerId") == player_id


def _opponent_player_id(state: Dict[str, Any], player_id: str) -> str:
    """
    获取对手玩家 ID。

    :param state: 对局状态。
    :param player_id: 当前玩家 ID。
    :return: 对手 ID。
    """
    for item in state.get("players") or []:
        if item.get("playerId") != player_id:
            return str(item.get("playerId"))
    raise ValidationException("找不到对手玩家")


def _stone_for_player(state: Dict[str, Any], player_id: str) -> Optional[str]:
    """
    获取玩家执子颜色。

    :param state: 对局状态。
    :param player_id: 玩家 ID。
    :return: 棋子颜色。
    """
    for item in state.get("players") or []:
        if item.get("playerId") == player_id:
            return item.get("stone")
    return None


def _switch_turn(state: Dict[str, Any]) -> None:
    """
    切换当前回合玩家与棋子颜色。

    :param state: 对局状态。
    :return: 无。
    """
    current_id = state.get("currentPlayerId")
    opponent_id = _opponent_player_id(state, current_id)
    state["currentPlayerId"] = opponent_id
    state["currentStone"] = _stone_for_player(state, opponent_id)


def _reset_turn_clock(state: Dict[str, Any], current_time: int) -> None:
    """
    重置回合倒计时。

    :param state: 对局状态。
    :param current_time: 当前毫秒时间戳。
    :return: 无。
    """
    timeout_seconds = int(state.get("turnTimeoutSeconds") or 30)
    state["currentTurnStartedAt"] = current_time
    state["currentTurnDeadlineAt"] = current_time + timeout_seconds * 1000


def _append_move(state: Dict[str, Any], move_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    追加一条不可变流水。

    :param state: 对局状态。
    :param move_data: 流水字段。
    :return: 完整流水记录。
    """
    move_counter = int(state.get("moveCounter") or 0) + 1
    state["moveCounter"] = move_counter
    move_no = len(state.get("moves") or []) + 1
    move = dict(move_data)
    move["moveId"] = "move_{0}".format(move_counter)
    move["moveNo"] = move_no
    moves = list(state.get("moves") or [])
    moves.append(move)
    state["moves"] = moves
    return move


def _append_undo_reject_move(
    state: Dict[str, Any],
    player_id: str,
    current_time: int,
) -> None:
    """
    因落子而隐式拒绝悔棋时追加流水。

    :param state: 对局状态。
    :param player_id: 拒绝方玩家 ID。
    :param current_time: 时间戳。
    :return: 无。
    """
    undo_request = state.get("undoRequest")
    if not isinstance(undo_request, dict):
        return
    _append_move(
        state,
        {
            "moveType": _MOVE_UNDO_REJECT,
            "playerId": player_id,
            "targetMoveId": undo_request.get("targetMoveId"),
            "createdAt": current_time,
        },
    )


def _public_undo_request(undo_request: Any) -> Optional[Dict[str, Any]]:
    """
    构建对外可见的悔棋申请摘要。

    :param undo_request: 内部悔棋申请。
    :return: 公开字段或 ``None``。
    """
    if not isinstance(undo_request, dict):
        return None
    return {
        "requestId": undo_request.get("requestId"),
        "requesterPlayerId": undo_request.get("requesterPlayerId"),
        "targetPlayerId": undo_request.get("targetPlayerId"),
        "targetMoveId": undo_request.get("targetMoveId"),
        "requestedAt": undo_request.get("requestedAt"),
        "expiresAt": undo_request.get("expiresAt"),
    }


def _has_five_in_row(
    board: List[List[Any]],
    row: int,
    col: int,
    stone: str,
    win_length: int,
) -> bool:
    """
    判断落子后是否形成五连。

    :param board: 棋盘。
    :param row: 行。
    :param col: 列。
    :param stone: 棋子颜色。
    :param win_length: 连子长度。
    :return: 成五为 ``True``。
    """
    for delta_row, delta_col in ((1, 0), (0, 1), (1, 1), (1, -1)):
        count = 1
        count += _count_same(board, row, col, delta_row, delta_col, stone)
        count += _count_same(board, row, col, -delta_row, -delta_col, stone)
        if count >= win_length:
            return True
    return False


def _count_same(
    board: List[List[Any]],
    row: int,
    col: int,
    delta_row: int,
    delta_col: int,
    stone: str,
) -> int:
    """
    沿方向统计同色连续棋子数（不含起点）。

    :param board: 棋盘。
    :param row: 起点行。
    :param col: 起点列。
    :param delta_row: 行增量。
    :param delta_col: 列增量。
    :param stone: 棋子颜色。
    :return: 连续数量。
    """
    total = 0
    board_size = len(board)
    next_row = row + delta_row
    next_col = col + delta_col
    while (
        0 <= next_row < board_size
        and 0 <= next_col < board_size
        and board[next_row][next_col] == stone
    ):
        total += 1
        next_row += delta_row
        next_col += delta_col
    return total
