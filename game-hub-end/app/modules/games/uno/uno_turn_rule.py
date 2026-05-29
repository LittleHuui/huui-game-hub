"""UNO 回合推进规则。"""

from typing import List

from app.core.time_utils import now_ms
from app.modules.games.uno.schemas import UnoRuntimeState

DEFAULT_TURN_TIMEOUT_SECONDS = 60

_SEAT_PLAYING = "PLAYING"
_SEAT_LEFT = "LEFT"


def get_player_index(state: UnoRuntimeState, player_id: str) -> int:
    """
    获取玩家在座位列表中的下标。

    :param state: 运行时状态。
    :param player_id: 玩家 ID。
    :return: 下标；不存在时为 ``-1``。
    """
    normalized = str(player_id).strip()
    for index, current_id in enumerate(state.playerIds):
        if current_id == normalized:
            return index
    return -1


def is_player_turn(state: UnoRuntimeState, player_id: str) -> bool:
    """
    判断是否为指定玩家的回合。

    :param state: 运行时状态。
    :param player_id: 玩家 ID。
    :return: 是则为 ``True``。
    """
    return state.currentPlayerId == str(player_id).strip()


def count_active_players(state: UnoRuntimeState) -> int:
    """
    统计仍在对局中可参与回合轮转的玩家数量（不含 LEFT / 已完赛）。

    :param state: 运行时状态。
    :return: 活跃玩家数。
    """
    count = 0
    for player_id in state.playerIds:
        player_state = state.players.get(player_id)
        if player_state is None:
            continue
        if player_state.seatStatus == _SEAT_LEFT:
            continue
        if player_state.isFinished:
            continue
        count += 1
    return count


def _is_turn_eligible(state: UnoRuntimeState, player_id: str) -> bool:
    """
    判断玩家是否可成为下一位回合持有者。

    :param state: 运行时状态。
    :param player_id: 玩家 ID。
    :return: 可参与回合为 ``True``。
    """
    player_state = state.players.get(player_id)
    if player_state is None:
        return False
    if player_state.seatStatus != _SEAT_PLAYING:
        return False
    if player_state.isFinished:
        return False
    return True


def _find_next_turn_player_id(state: UnoRuntimeState, step: int = 1) -> str:
    """
    按 ``playerIds`` 座位顺序从当前玩家位置起找下一位可行动玩家。

    :param state: 运行时状态。
    :param step: 推进步数（1 表示下一位可行动玩家）。
    :return: 下一位玩家 ID。
    """
    if not state.playerIds or step < 1:
        return state.currentPlayerId
    total = len(state.playerIds)
    current_index = get_player_index(state, state.currentPlayerId)
    if current_index < 0:
        current_index = 0
    direction = state.playDirection if state.playDirection in (-1, 1) else 1
    offset = 0
    passed = 0
    while passed < step:
        offset += 1
        if offset > total:
            return state.currentPlayerId
        next_index = (current_index + direction * offset) % total
        next_id = state.playerIds[next_index]
        if _is_turn_eligible(state, next_id):
            passed += 1
            if passed == step:
                return next_id
    return state.currentPlayerId


def peek_next_active_player(state: UnoRuntimeState, step: int = 1) -> str:
    """
    按座位顺序预览下一位仍在对局中的玩家，不修改 ``currentPlayerId``。

    :param state: 运行时状态。
    :param step: 预览步数（1 表示下一位）。
    :return: 预览到的玩家 ID。
    """
    return _find_next_turn_player_id(state, step)


def stamp_turn_clock(
    state: UnoRuntimeState,
    turn_timeout_seconds: int = DEFAULT_TURN_TIMEOUT_SECONDS,
) -> None:
    """
    记录当前回合开始与截止时间。

    :param state: 运行时状态。
    :param turn_timeout_seconds: 回合超时时长（秒）。
    :return: 无。
    """
    timeout = max(1, int(turn_timeout_seconds))
    started_at = now_ms()
    state.turnTimeoutSeconds = timeout
    state.currentTurnStartedAt = started_at
    state.currentTurnDeadlineAt = started_at + timeout * 1000


def advance_turn(state: UnoRuntimeState, step: int = 1) -> str:
    """
    按座位顺序推进回合并更新 ``currentPlayerId``。

    :param state: 运行时状态。
    :param step: 推进步数。
    :return: 新的当前玩家 ID。
    """
    previous_player_id = state.currentPlayerId
    next_player_id = _find_next_turn_player_id(state, step)
    state.currentPlayerId = next_player_id
    if next_player_id != previous_player_id:
        stamp_turn_clock(state, state.turnTimeoutSeconds)
    return next_player_id


def _active_player_ids(state: UnoRuntimeState) -> List[str]:
    """
    返回仍在对局中且座位为 PLAYING 的玩家 ID 列表（按座位顺序）。

    :param state: 运行时状态。
    :return: 玩家 ID 列表。
    """
    active_ids = []
    for player_id in state.playerIds:
        if _is_turn_eligible(state, player_id):
            active_ids.append(player_id)
    return active_ids
