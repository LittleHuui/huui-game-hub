"""五子棋对局状态编解码与房间配置解析。"""

from typing import Any, Dict

from app.modules.game_impls.gomoku.gomoku_board_rule import (
    find_last_effective_place_move,
    public_undo_request,
)
from app.modules.game_impls.gomoku.gomoku_undo_rule import get_active_undo_request
from app.core.time_utils import now_ms


def parse_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    校验游戏状态不包含框架事件字段，并复制状态字典。

    :param state: 原始状态字典。
    :return: 通过校验的状态字典副本。
    """
    if "lastActionEvents" in state or "eventSequence" in state:
        raise ValueError("五子棋 state 不允许包含框架事件字段")
    return dict(state)


def dump_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    校验并复制对局状态，拒绝框架事件字段。

    :param state: 对局状态。
    :return: 状态字典副本。
    """
    return parse_state(state)


def resolve_room_config_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    从状态字典解析房间配置。

    :param state: 对局状态字典。
    :return: 房间配置字典。
    """
    room_config = state.get("roomConfig")
    if isinstance(room_config, dict):
        return dict(room_config)
    return {}


def build_public_game_state(
    state: Dict[str, Any],
    current_time_ms: int = None,
) -> Dict[str, Any]:
    """
    构建对外可见的棋局状态摘要。

    :param state: 对局状态。
    :return: 公开棋局字段。
    """
    now = int(current_time_ms) if current_time_ms is not None else now_ms()
    active_undo = get_active_undo_request(state, now)
    return {
        "boardSize": state.get("boardSize"),
        "winLength": state.get("winLength"),
        "board": state.get("board") or [],
        "lastPlaceMoveId": state.get("lastPlaceMoveId"),
        "lastPlaceRow": state.get("lastPlaceRow"),
        "lastPlaceCol": state.get("lastPlaceCol"),
        "lastMove": find_last_effective_place_move(state.get("moves") or []),
        "movesCount": len(state.get("moves") or []),
        "undoRequest": public_undo_request(active_undo),
        "winnerPlayerId": state.get("winnerPlayerId"),
        "winnerStone": state.get("winnerStone"),
        "finishReason": state.get("finishReason"),
        "currentTurnStartedAt": state.get("currentTurnStartedAt"),
        "currentTurnDeadlineAt": state.get("currentTurnDeadlineAt"),
    }
