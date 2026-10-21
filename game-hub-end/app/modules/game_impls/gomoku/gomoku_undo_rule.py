"""五子棋悔棋规则。"""

from typing import Any, Dict, Optional

from app.modules.game_impls.gomoku.gomoku_board_rule import (
    append_move,
    find_last_effective_place_move,
    find_last_move_by_player,
    has_undo_stone_for_target,
)
from app.modules.game_impls.gomoku.gomoku_constants import (
    MOVE_UNDO_REJECT,
    PHASE_FINISHED,
)


def is_undo_enabled(state: Dict[str, Any]) -> bool:
    """
    判断房间是否开启悔棋。

    :param state: 对局状态。
    :return: 开启为 ``True``。
    """
    if "enableUndo" in state:
        return bool(state.get("enableUndo", True))
    room_config = state.get("roomConfig") or {}
    return bool(room_config.get("enableUndo", True))


def is_undo_request_expired(
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
    return expires_at > 0 and now >= expires_at


def clear_expired_undo_request(
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
    if not is_undo_request_expired(undo_request, now):
        return
    append_move(
        state,
        {
            "moveType": MOVE_UNDO_REJECT,
            "playerId": undo_request.get("targetPlayerId"),
            "targetMoveId": undo_request.get("targetMoveId"),
            "reason": "EXPIRED",
            "createdAt": now,
        },
    )
    state["undoRequest"] = None


def get_active_undo_request(
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
    if is_undo_request_expired(undo_request, now):
        return None
    return undo_request


def can_request_undo(
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
    if not is_undo_enabled(state):
        return False
    if state.get("phase") == PHASE_FINISHED:
        return False
    if state.get("winnerPlayerId"):
        return False
    if active_undo is not None:
        return False
    last_place = find_last_effective_place_move(state.get("moves") or [])
    if last_place is None:
        return False
    if last_place.get("playerId") != player_id:
        return False
    if state.get("currentPlayerId") == player_id:
        return False
    if has_undo_stone_for_target(state.get("moves") or [], last_place["moveId"]):
        return False
    last_own_move = find_last_move_by_player(state.get("moves") or [], player_id)
    last_own_move_type = str(last_own_move.get("moveType") or "") if last_own_move else ""
    if last_own_move_type.startswith("UNDO_"):
        return False
    return True


def can_handle_undo(
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
    if not is_undo_enabled(state):
        return False
    if not active_undo:
        return False
    return active_undo.get("targetPlayerId") == player_id
