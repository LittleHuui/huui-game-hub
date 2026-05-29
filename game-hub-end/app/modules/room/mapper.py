"""房间响应映射。"""

from typing import Any, Dict, List

from app.modules.room.schemas import RoomMemberResponse, RoomResponse

_MEMBER_RESPONSE_FIELDS = frozenset(
    {
        "playerId",
        "nickname",
        "avatar",
        "joinedAt",
        "isAi",
        "isManaged",
        "managedMode",
        "managedReason",
        "managedAt",
    }
)


def _to_member_response(member: Dict[str, Any]) -> RoomMemberResponse:
    """
    将 Redis 成员对象映射为 API 成员响应。

    :param member: 成员字典。
    :return: 成员响应项。
    """
    payload = {
        key: member.get(key)
        for key in _MEMBER_RESPONSE_FIELDS
        if key in member
    }
    return RoomMemberResponse.model_validate(payload)


def build_room_response(meta: Dict[str, Any], members: List[Dict[str, Any]], version: int) -> RoomResponse:
    """
    构造统一房间详情响应。

    :param meta: 房间元信息。
    :param members: 房间成员。
    :param version: 房间版本号。
    :return: 房间详情响应。
    """
    member_items = []
    for member in members:
        if not isinstance(member, dict):
            continue
        try:
            member_items.append(_to_member_response(member))
        except ValueError:
            continue
    member_items.sort(key=lambda item: item.joinedAt)
    real_member_count = 0
    for item in member_items:
        if str(item.managedMode or "").strip() != "shell":
            real_member_count += 1
    owner_player_id = str(meta.get("ownerPlayerId", ""))
    owner_nickname = str(meta.get("ownerNickname", "")).strip()
    if not owner_nickname:
        owner_nickname = owner_player_id
    room_name = str(meta.get("roomName", "")).strip()
    if not room_name:
        room_name = "房间-{0}".format(str(meta.get("roomId", ""))[-6:])
    room_config = meta.get("roomConfig")
    if not isinstance(room_config, dict):
        room_config = {}
    allow_ai = meta.get("allowAi")
    if allow_ai is None:
        allow_ai = True
    max_ai_count = meta.get("maxAiCount")
    if max_ai_count is None:
        max_ai_count = 0
    data = {
        "roomId": meta.get("roomId", ""),
        "roomName": room_name,
        "gameCode": meta.get("gameCode", ""),
        "mode": meta.get("mode", ""),
        "ownerPlayerId": owner_player_id,
        "ownerNickname": owner_nickname,
        "maxPlayers": meta.get("maxPlayers", 0),
        "aiCount": int(meta.get("aiCount", 0)),
        "version": version,
        "status": meta.get("status", "waiting"),
        "memberCount": real_member_count,
        "members": member_items,
        "roomConfig": dict(room_config),
        "allowAi": bool(allow_ai),
        "maxAiCount": int(max_ai_count),
        "createdAt": meta.get("createdAt", 0),
        "updatedAt": meta.get("updatedAt", 0),
    }
    return RoomResponse.model_validate(data)
