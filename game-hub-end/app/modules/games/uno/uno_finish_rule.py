"""UNO 结束判定规则。"""

from typing import Any, Dict, List

from app.core.time_utils import now_ms
from app.modules.games.uno.schemas import UnoRankingItem, UnoRuntimeState

_FINISH_MODE_FIRST_FINISH = "FIRST_FINISH"
_FINISH_MODE_UNTIL_REAL_PLAYER_COUNT = "UNTIL_REAL_PLAYER_COUNT"
_SEAT_PLAYING = "PLAYING"
_SEAT_SPECTATING = "SPECTATING"


def count_remaining_real_playing_players(state: UnoRuntimeState) -> int:
    """
    统计仍在 PLAYING 座位且非 AI 的真人玩家数量。

    :param state: 运行时状态。
    :return: 真人玩家数。
    """
    count = 0
    for player_id in state.playerIds:
        player_state = state.players.get(player_id)
        if player_state is None:
            continue
        if player_state.seatStatus != _SEAT_PLAYING:
            continue
        if player_state.isAi:
            continue
        count += 1
    return count


def _has_real_player_ranked(state: UnoRuntimeState) -> bool:
    """
    判断是否已有真人玩家完赛入榜。

    :param state: 运行时状态。
    :return: 已有为 ``True``。
    """
    for item in state.rankings:
        player_state = state.players.get(item.playerId)
        if player_state is None:
            continue
        if not player_state.isAi:
            return True
    return False


def should_finish_game(state: UnoRuntimeState, room_config: Dict[str, Any]) -> bool:
    """
    根据房间 ``finishMode`` 判断是否应结束对局。

    :param state: 运行时状态。
    :param room_config: 房间玩法配置。
    :return: 应结束为 ``True``。
    """
    finish_mode = str(room_config.get("finishMode", _FINISH_MODE_UNTIL_REAL_PLAYER_COUNT)).strip()
    if finish_mode == _FINISH_MODE_FIRST_FINISH:
        return _has_real_player_ranked(state)
    if not state.rankings:
        return False
    remaining_to_end = room_config.get("remainingRealPlayerCountToEnd", 1)
    try:
        threshold = int(remaining_to_end)
    except (TypeError, ValueError):
        threshold = 1
    if threshold < 1:
        threshold = 1
    remaining = count_remaining_real_playing_players(state)
    return remaining <= threshold


def mark_player_finished(
    state: UnoRuntimeState,
    player_id: str,
    finished_at: int,
) -> UnoRankingItem:
    """
    玩家出完手牌后写入名次并转为旁观。

    :param state: 运行时状态。
    :param player_id: 玩家 ID。
    :param finished_at: 完成时间，Unix 毫秒。
    :return: 名次记录。
    """
    normalized_id = str(player_id).strip()
    player_state = state.players.get(normalized_id)
    if player_state is None:
        raise ValueError("player not found: {0}".format(normalized_id))
    player_state.isFinished = True
    player_state.seatStatus = _SEAT_SPECTATING
    rank = len(state.rankings) + 1
    player_state.finishRank = rank
    ranking_item = UnoRankingItem(
        playerId=normalized_id,
        rank=rank,
        finishedAt=finished_at,
    )
    state.rankings.append(ranking_item)
    return ranking_item


def sync_game_over_phase(state: UnoRuntimeState, room_config: Dict[str, Any]) -> bool:
    """
    根据结束条件同步 ``phase`` 字段。

    :param state: 运行时状态。
    :param room_config: 房间玩法配置。
    :return: 对局已结束为 ``True``。
    """
    if should_finish_game(state, room_config):
        fill_remaining_rankings_by_hand_count(state, now_ms())
        state.phase = "finished"
        return True
    state.phase = "playing"
    return False


def fill_remaining_rankings_by_hand_count(
    state: UnoRuntimeState,
    finished_at: int,
) -> List[UnoRankingItem]:
    """
    提前结束时按剩余手牌数量补齐未名次玩家的排名。

    :param state: 运行时状态。
    :param finished_at: 完成时间，Unix 毫秒。
    :return: 新写入的名次列表。
    """
    ranked_ids = set()
    for item in state.rankings:
        ranked_ids.add(item.playerId)
    seat_order = {}
    for index, player_id in enumerate(state.playerIds):
        seat_order[player_id] = index
    unfinished = []
    for player_id in state.playerIds:
        player_state = state.players.get(player_id)
        if player_state is None:
            continue
        if player_state.isFinished or player_id in ranked_ids:
            continue
        unfinished.append((player_id, len(player_state.handCards), seat_order.get(player_id, 0)))
    unfinished.sort(key=lambda item: (item[1], item[2]))
    created = []
    for player_id, _hand_count, _seat_index in unfinished:
        created.append(mark_player_finished(state, player_id, finished_at))
    return created
