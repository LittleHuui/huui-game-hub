"""五子棋棋盘与流水辅助规则。"""

from typing import Any, Dict, List, Optional, Tuple

from app.common.exceptions import ValidationException
from app.modules.game_impls.gomoku.gomoku_constants import (
    MOVE_PLACE_STONE,
    MOVE_TIMEOUT_PLACE_STONE,
    MOVE_UNDO_REJECT,
    MOVE_UNDO_STONE,
)


def empty_cells(board: List[List[Any]]) -> List[Tuple[int, int]]:
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


def find_last_effective_place_move(moves: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    查找最后一条有效落子记录。

    :param moves: 流水列表。
    :return: 落子记录或 ``None``。
    """
    undone_move_ids = {
        item.get("targetMoveId")
        for item in moves
        if item.get("moveType") == MOVE_UNDO_STONE
    }
    for item in reversed(moves):
        if item.get("moveType") not in (MOVE_PLACE_STONE, MOVE_TIMEOUT_PLACE_STONE):
            continue
        if item.get("moveId") in undone_move_ids:
            continue
        return item
    return None


def has_undo_stone_for_target(moves: List[Dict[str, Any]], target_move_id: str) -> bool:
    """
    判断目标落子是否已被悔掉。

    :param moves: 流水列表。
    :param target_move_id: 目标 moveId。
    :return: 已悔为 ``True``。
    """
    for item in moves:
        if (
            item.get("moveType") == MOVE_UNDO_STONE
            and item.get("targetMoveId") == target_move_id
        ):
            return True
    return False


def find_last_move_by_player(
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


def find_move_by_id(
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


def opponent_player_id(state: Dict[str, Any], player_id: str) -> str:
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


def stone_for_player(state: Dict[str, Any], player_id: str) -> Optional[str]:
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


def switch_turn(state: Dict[str, Any]) -> None:
    """
    切换当前回合玩家与棋子颜色。

    :param state: 对局状态。
    :return: 无。
    """
    current_id = state.get("currentPlayerId")
    opponent_id = opponent_player_id(state, current_id)
    state["currentPlayerId"] = opponent_id
    state["currentStone"] = stone_for_player(state, opponent_id)


def reset_turn_clock(state: Dict[str, Any], current_time: int) -> None:
    """
    重置回合倒计时。

    :param state: 对局状态。
    :param current_time: 当前毫秒时间戳。
    :return: 无。
    """
    timeout_seconds = int(state.get("turnTimeoutSeconds") or 30)
    state["currentTurnStartedAt"] = current_time
    state["currentTurnDeadlineAt"] = current_time + timeout_seconds * 1000


def append_move(state: Dict[str, Any], move_data: Dict[str, Any]) -> Dict[str, Any]:
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


def append_undo_reject_move(
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
    append_move(
        state,
        {
            "moveType": MOVE_UNDO_REJECT,
            "playerId": player_id,
            "targetMoveId": undo_request.get("targetMoveId"),
            "createdAt": current_time,
        },
    )


def public_undo_request(undo_request: Any) -> Optional[Dict[str, Any]]:
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
