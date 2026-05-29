"""房间实时推送（WebSocket）。"""

from typing import Dict, List

from app.core.websocket.message_dispatcher import broadcast, send_to_user
from app.core.websocket.message_types import MessageType
from app.modules.room.schemas import RoomMemberResponse, RoomResponse
from app.modules.strategy_turn.schemas import GameEvent, GameView, RuntimeSnapshot


async def push_room_list_updated(game_code: str) -> None:
    """
    通知在线客户端刷新指定游戏的房间列表。

    :param game_code: 游戏编码。
    :return: 无。
    """
    normalized_code = str(game_code or "").strip()
    if not normalized_code:
        return
    await broadcast(MessageType.ROOM_LIST_UPDATED, {"gameCode": normalized_code})


async def push_room_updated(room: RoomResponse) -> None:
    """
    向房间内非 AI 成员推送房间更新。

    :param room: 房间详情。
    :return: 无。
    """
    payload = {
        "roomId": room.roomId,
        "room": room.model_dump(),
        "version": room.version,
    }
    for member in room.members:
        if member.isAi:
            continue
        if str(member.managedMode or "").strip().lower() == "shell":
            continue
        await send_to_user(member.playerId, MessageType.ROOM_UPDATED, payload)


async def push_game_view_updated(
    room_id: str,
    views_by_player: Dict[str, GameView],
    members: List[RoomMemberResponse],
) -> None:
    """
    向各玩家推送个性化 GameView 更新。

    :param room_id: 房间 ID。
    :param views_by_player: 玩家 ID 到视图的映射。
    :param members: 房间成员列表，用于过滤推送目标。
    :return: 无。
    """
    normalized_room_id = room_id.strip()
    if not normalized_room_id:
        return
    pushable_ids = set(collect_human_player_ids(members))
    for player_id, view in views_by_player.items():
        normalized_player_id = str(player_id).strip()
        if not normalized_player_id or normalized_player_id not in pushable_ids:
            continue
        payload = {
            "roomId": normalized_room_id,
            "gameView": view.model_dump(),
        }
        await send_to_user(normalized_player_id, MessageType.GAME_VIEW_UPDATED, payload)


def collect_human_player_ids(members: List[RoomMemberResponse]) -> List[str]:
    """
    提取房间内需要接收 GameView 的真人玩家 ID 列表。

    :param members: 房间成员列表。
    :return: 玩家 ID 列表。
    """
    player_ids = []
    for member in members:
        if member.isAi:
            continue
        if str(member.managedMode or "").strip().lower() == "shell":
            continue
        player_id = str(member.playerId).strip()
        if player_id:
            player_ids.append(player_id)
    return player_ids


def build_views_for_members(
    enrich_view,
    snapshot: RuntimeSnapshot,
    version: int,
    events: List[GameEvent],
    player_ids: List[str],
) -> Dict[str, GameView]:
    """
    为多名玩家构造 GameView 映射。

    :param enrich_view: 组装视图的回调。
    :param snapshot: 运行时快照。
    :param version: 房间版本号。
    :param events: 本帧待播放事件。
    :param player_ids: 玩家 ID 列表。
    :return: 玩家 ID 到视图的映射。
    """
    views = {}
    for player_id in player_ids:
        views[player_id] = enrich_view(snapshot, player_id, version, events)
    return views
