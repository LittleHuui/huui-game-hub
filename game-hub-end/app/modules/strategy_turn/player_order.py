"""座位顺序与活跃玩家遍历工具。"""

from typing import Any, Dict, List, Optional


def _normalize_direction(direction: int) -> int:
    """
    将方向规范为 1 或 -1。

    :param direction: 原始方向值。
    :return: ``1`` 或 ``-1``。
    """
    return 1 if int(direction) >= 0 else -1


def _is_active_player(player: Dict[str, Any]) -> bool:
    """
    判断玩家是否仍在对局中活跃。

    :param player: 玩家摘要字典。
    :return: 是否活跃。
    """
    player_id = str(player.get("playerId") or "").strip()
    if not player_id:
        return False
    if str(player.get("seatStatus") or "").strip() != "PLAYING":
        return False
    if bool(player.get("isFinished")):
        return False
    return True


def _find_player_index(players: List[Dict[str, Any]], current_player_id: str) -> Optional[int]:
    """
    在座位列表中定位当前玩家下标。

    :param players: 按座位顺序排列的玩家列表。
    :param current_player_id: 当前玩家 ID。
    :return: 下标，未找到时返回 ``None``。
    """
    normalized_id = str(current_player_id or "").strip()
    if not normalized_id:
        return None
    for index, player in enumerate(players):
        if str(player.get("playerId") or "").strip() == normalized_id:
            return index
    return None


def get_next_active_player(
    players: List[Dict[str, Any]],
    current_player_id: str,
    direction: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    按出牌方向查找下一位活跃玩家。

    :param players: 按座位顺序排列的玩家列表。
    :param current_player_id: 当前玩家 ID。
    :param direction: 出牌方向，>=0 为顺时针，<0 为逆时针。
    :return: 下一位活跃玩家摘要，找不到时返回 ``None``。
    """
    normalized_direction = _normalize_direction(direction)
    current_index = _find_player_index(players, current_player_id)
    if current_index is None:
        return None
    normalized_current_id = str(current_player_id or "").strip()
    total = len(players)
    if total <= 1:
        return None
    for step in range(1, total):
        candidate_index = (current_index + step * normalized_direction) % total
        candidate = players[candidate_index]
        if not _is_active_player(candidate):
            continue
        candidate_id = str(candidate.get("playerId") or "").strip()
        if candidate_id and candidate_id != normalized_current_id:
            return candidate
    return None


def get_previous_active_player(
    players: List[Dict[str, Any]],
    current_player_id: str,
    direction: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    按出牌方向查找上一位活跃玩家。

    :param players: 按座位顺序排列的玩家列表。
    :param current_player_id: 当前玩家 ID。
    :param direction: 出牌方向，>=0 为顺时针，<0 为逆时针。
    :return: 上一位活跃玩家摘要，找不到时返回 ``None``。
    """
    return get_next_active_player(players, current_player_id, -_normalize_direction(direction))


def get_next_active_player_after_reverse(
    players: List[Dict[str, Any]],
    current_player_id: str,
    direction: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    反转牌生效后，按反向查找下一位活跃玩家。

    :param players: 按座位顺序排列的玩家列表。
    :param current_player_id: 当前玩家 ID。
    :param direction: 反转前的出牌方向。
    :return: 反转后下一位活跃玩家摘要，找不到时返回 ``None``。
    """
    return get_next_active_player(players, current_player_id, -_normalize_direction(direction))
