"""五子棋动作执行器。"""

import copy
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from app.common.exceptions import ValidationException
from app.core.time_utils import now_ms
from app.modules.game_impls.gomoku.gomoku_board_rule import (
    append_move,
    append_undo_reject_move,
    find_last_effective_place_move,
    find_move_by_id,
    opponent_player_id,
    reset_turn_clock,
    stone_for_player,
    switch_turn,
)
from app.modules.game_impls.gomoku.gomoku_constants import (
    ACTION_ACCEPT_UNDO,
    ACTION_PLACE_STONE,
    ACTION_REJECT_UNDO,
    ACTION_REQUEST_UNDO,
    ACTION_RESIGN,
    BOARD_SIZE,
    WIN_LENGTH,
    DEFAULT_UNDO_REQUEST_EXPIRE_SECONDS,
    MOVE_PLACE_STONE,
    MOVE_RESIGN,
    MOVE_UNDO_ACCEPT,
    MOVE_UNDO_REJECT,
    MOVE_UNDO_REQUEST,
    MOVE_UNDO_STONE,
    PHASE_FINISHED,
)
from app.modules.game_impls.gomoku.gomoku_event_factory import make_action_event
from app.modules.game_impls.gomoku.gomoku_state_codec import dump_state
from app.modules.game_impls.gomoku.gomoku_undo_rule import (
    clear_expired_undo_request,
    is_undo_request_expired,
)
from app.modules.game_impls.gomoku.gomoku_win_rule import has_five_in_row
from app.modules.strategy_turn.schemas import DomainEventDraft, ResolvedGameAction


class GomokuPlacePayload(BaseModel):
    """五子棋落子归一载荷。"""

    model_config = ConfigDict(extra="forbid")
    row: int = Field(ge=0, le=BOARD_SIZE - 1)
    col: int = Field(ge=0, le=BOARD_SIZE - 1)


class GomokuUndoTargetPayload(BaseModel):
    """五子棋悔棋目标归一载荷。"""

    model_config = ConfigDict(extra="forbid")
    targetMoveId: str = Field(min_length=1)


class GomokuUndoDecisionPayload(BaseModel):
    """五子棋悔棋决策归一载荷。"""

    model_config = ConfigDict(extra="forbid")
    undoRequestId: Optional[str] = None


class GomokuEmptyPayload(BaseModel):
    """五子棋无参数动作归一载荷。"""

    model_config = ConfigDict(extra="forbid")


class GomokuActionExecutor(object):
    """五子棋已解析动作执行器。"""

    def apply_resolved_action(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        校验并应用已解析动作。

        :param state: 当前对局状态。
        :param action: 已解析动作。
        :return: (新状态, 事件草稿列表)。
        """
        working = copy.deepcopy(state)
        now = now_ms()
        action_type = str(action.actionType or "").strip()
        if action_type in (ACTION_ACCEPT_UNDO, ACTION_REJECT_UNDO):
            if is_undo_request_expired(working.get("undoRequest"), now):
                raise ValidationException("悔棋请求已失效")
        else:
            clear_expired_undo_request(working, now)
        if action_type == ACTION_PLACE_STONE:
            return self._apply_place_stone(working, action, now)
        if action_type == ACTION_REQUEST_UNDO:
            return self._apply_request_undo(working, action, now)
        if action_type == ACTION_ACCEPT_UNDO:
            if not working.get("undoRequest"):
                raise ValidationException("悔棋请求已失效")
            return self._apply_accept_undo(working, action, now)
        if action_type == ACTION_REJECT_UNDO:
            if not working.get("undoRequest"):
                raise ValidationException("悔棋请求已失效")
            return self._apply_reject_undo(working, action, now)
        if action_type == ACTION_RESIGN:
            return self._apply_resign(working, action, now)
        raise ValidationException("非法操作")

    def _apply_place_stone(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        current_time: int,
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        应用落子操作。

        :param state: 当前状态。
        :param action: 合法落子操作。
        :return: (更新后的状态, 事件草稿列表)。
        """
        payload = GomokuPlacePayload.model_validate(action.payload or {})
        row = payload.row
        col = payload.col
        player_id = str(action.playerId or "").strip()
        if state.get("currentPlayerId") != player_id:
            raise ValidationException("未轮到当前玩家")
        board = state.get("board") or []
        if board[row][col] is not None:
            raise ValidationException("该位置已有棋子")
        if state.get("undoRequest") is not None:
            append_undo_reject_move(state, player_id, current_time)
            state["undoRequest"] = None
        stone = state.get("currentStone")
        move = append_move(
            state,
            {
                "moveType": MOVE_PLACE_STONE,
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
        win_length = int(state.get("winLength") or WIN_LENGTH)
        if has_five_in_row(board, row, col, stone, win_length):
            state["phase"] = PHASE_FINISHED
            state["winnerPlayerId"] = player_id
            state["winnerStone"] = stone
            state["finishReason"] = "FIVE_IN_ROW"
        else:
            switch_turn(state)
            reset_turn_clock(state, current_time)
        events = make_action_event(
            "gomoku.place_stone",
            player_id,
            {"row": row, "col": col, "stone": stone, "moveId": move["moveId"]},
        )
        return dump_state(state), events

    def _apply_request_undo(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        current_time: int,
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        申请悔棋。

        :param state: 当前状态。
        :param action: 合法悔棋申请操作。
        :return: (更新后的状态, 事件草稿列表)。
        """
        player_id = str(action.playerId or "").strip()
        payload = GomokuUndoTargetPayload.model_validate(action.payload or {})
        last_place = find_last_effective_place_move(state.get("moves") or [])
        if last_place is None:
            raise ValidationException("没有可悔的落子")
        if payload.targetMoveId != str(last_place.get("moveId") or ""):
            raise ValidationException("悔棋目标已变化")
        opponent_id = opponent_player_id(state, player_id)
        expire_seconds = int(
            state.get("undoRequestExpireSeconds") or DEFAULT_UNDO_REQUEST_EXPIRE_SECONDS
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
        append_move(
            state,
            {
                "moveType": MOVE_UNDO_REQUEST,
                "playerId": player_id,
                "targetMoveId": last_place["moveId"],
                "createdAt": current_time,
            },
        )
        events = make_action_event(
            "gomoku.undo.requested",
            player_id,
            {"targetMoveId": last_place["moveId"], "requestId": request_id},
        )
        return dump_state(state), events

    def _apply_accept_undo(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        current_time: int,
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        同意悔棋。

        :param state: 当前状态。
        :param action: 已解析动作。
        :return: (更新后的状态, 事件草稿列表)。
        """
        undo_request = state.get("undoRequest")
        if not undo_request:
            raise ValidationException("悔棋请求已失效")
        payload = GomokuUndoDecisionPayload.model_validate(action.payload or {})
        request_id = str(payload.undoRequestId or "").strip()
        if request_id and request_id != str(undo_request.get("requestId") or ""):
            raise ValidationException("悔棋请求已失效")
        if undo_request.get("targetPlayerId") != str(action.playerId or "").strip():
            raise ValidationException("无权处理该悔棋申请")
        target = find_move_by_id(state.get("moves") or [], undo_request["targetMoveId"])
        if target is None:
            raise ValidationException("悔棋目标不存在")
        board = state.get("board") or []
        row = int(target["row"])
        col = int(target["col"])
        board[row][col] = None
        append_move(
            state,
            {
                "moveType": MOVE_UNDO_ACCEPT,
                "playerId": action.playerId,
                "targetMoveId": target["moveId"],
                "createdAt": current_time,
            },
        )
        append_move(
            state,
            {
                "moveType": MOVE_UNDO_STONE,
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
        latest_place = find_last_effective_place_move(state.get("moves") or [])
        if latest_place is not None:
            state["lastPlaceMoveId"] = latest_place.get("moveId")
            state["lastPlaceRow"] = latest_place.get("row")
            state["lastPlaceCol"] = latest_place.get("col")
        else:
            state["lastPlaceMoveId"] = None
            state["lastPlaceRow"] = None
            state["lastPlaceCol"] = None
        reset_turn_clock(state, current_time)
        events = make_action_event(
            "gomoku.undo.accepted",
            action.playerId,
            {"targetMoveId": target["moveId"]},
        )
        return dump_state(state), events

    def _apply_reject_undo(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        current_time: int,
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        拒绝悔棋。

        :param state: 当前状态。
        :param action: 已解析动作。
        :return: (更新后的状态, 事件草稿列表)。
        """
        undo_request = state.get("undoRequest")
        if not undo_request:
            raise ValidationException("悔棋请求已失效")
        payload = GomokuUndoDecisionPayload.model_validate(action.payload or {})
        request_id = str(payload.undoRequestId or "").strip()
        if request_id and request_id != str(undo_request.get("requestId") or ""):
            raise ValidationException("悔棋请求已失效")
        if undo_request.get("targetPlayerId") != str(action.playerId or "").strip():
            raise ValidationException("无权处理该悔棋申请")
        append_move(
            state,
            {
                "moveType": MOVE_UNDO_REJECT,
                "playerId": action.playerId,
                "targetMoveId": undo_request["targetMoveId"],
                "createdAt": current_time,
            },
        )
        state["undoRequest"] = None
        events = make_action_event(
            "gomoku.undo.rejected",
            action.playerId,
            {},
        )
        return dump_state(state), events

    def _apply_resign(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        current_time: int,
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        认输并结束对局。

        :param state: 当前状态。
        :param action: 已解析动作。
        :return: (更新后的状态, 事件草稿列表)。
        """
        GomokuEmptyPayload.model_validate(action.payload or {})
        player_id = str(action.playerId or "").strip()
        winner_id = opponent_player_id(state, player_id)
        winner_stone = stone_for_player(state, winner_id)
        append_move(
            state,
            {
                "moveType": MOVE_RESIGN,
                "playerId": player_id,
                "createdAt": current_time,
            },
        )
        state["phase"] = PHASE_FINISHED
        state["winnerPlayerId"] = winner_id
        state["winnerStone"] = winner_stone
        state["finishReason"] = "RESIGN"
        state["undoRequest"] = None
        events = make_action_event(
            "gomoku.resign",
            player_id,
            {"winnerPlayerId": winner_id},
        )
        return dump_state(state), events
