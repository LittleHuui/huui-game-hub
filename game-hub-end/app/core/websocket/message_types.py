"""WebSocket 消息类型集中定义。"""

from enum import Enum


class MessageType(str, Enum):
    """平台实时通道消息类型。"""

    ONLINE_PING = "online.ping"
    ONLINE_PONG = "online.pong"
    SYSTEM_NOTICE = "system.notice"
    ROOM_INVITE = "room.invite"
    ROOM_INVITE_ACCEPTED = "room.inviteAccepted"
    ROOM_INVITE_REJECTED = "room.inviteRejected"
    ROOM_UPDATED = "roomUpdated"
    ROOM_LIST_UPDATED = "room.list.updated"
    GAME_VIEW_UPDATED = "gameViewUpdated"
    ROOM_PRESENCE_PING = "room.presence.ping"
    ROOM_PRESENCE_PONG = "room.presence.pong"
    ERROR = "error"
