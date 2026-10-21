"""房间邀请校验与权威载荷构造。"""

from typing import Any, Dict

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.websocket.schemas import RoomInviteClientPayload, RoomInviteForwardPayload
from app.modules.room.repository import RoomRepository
from app.modules.room.room_member_support import find_member
from app.modules.room.room_platform_support import is_active_room_member
from app.modules.user.entity_service import UserAccountEntityService


class RoomInvitationService(object):
    """房间邀请应用服务：校验权限并构造权威邀请载荷。"""

    def __init__(
        self,
        repository: RoomRepository,
        account_service: UserAccountEntityService,
    ) -> None:
        """
        初始化房间邀请服务。

        :param repository: 房间 Redis 仓库。
        :param account_service: 用户账号实体服务。
        """
        self._repository = repository
        self._account_service = account_service

    async def build_invitation(
        self,
        sender_service_id: str,
        request: RoomInviteClientPayload,
    ) -> Dict[str, str]:
        """
        校验邀请请求并构造服务端权威邀请载荷。

        :param sender_service_id: 邀请方 serviceId。
        :param request: 客户端邀请请求。
        :return: 可转发给目标用户的邀请载荷。
        :raises BizException: 校验失败时抛出业务异常。
        """
        sender_id = str(sender_service_id or "").strip()
        if not sender_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="邀请方无效")

        target_service_id = request.targetServiceId.strip()
        if not target_service_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="缺少被邀请用户")
        if target_service_id == sender_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="不能邀请自己")

        target_account = self._account_service.get_by_server_id(
            target_service_id,
            active_only=True,
        )
        if target_account is None:
            raise BizException(ErrorCode.USER_NOT_FOUND)
        if target_account.status != "normal":
            raise BizException(ErrorCode.USER_DISABLED)

        room_id = request.roomId.strip()
        meta = await self._repository.get_meta(room_id)
        if meta is None:
            raise BizException(ErrorCode.ROOM_NOT_FOUND)

        room_status = str(meta.get("status", "")).strip()
        if room_status not in ("waiting", "playing"):
            raise BizException(ErrorCode.ROOM_NOT_FOUND)
        if room_status != "waiting":
            raise BizException(ErrorCode.ROOM_ALREADY_STARTED)

        members = await self._repository.list_players(room_id)
        sender_member = find_member(members, sender_id)
        if sender_member is None or not is_active_room_member(sender_member):
            raise BizException(ErrorCode.ROOM_NOT_MEMBER)

        target_member = find_member(members, target_service_id)
        if target_member is not None and is_active_room_member(target_member):
            raise BizException(ErrorCode.ROOM_ALREADY_JOINED)

        membership = await self._repository.get_active_membership(target_service_id)
        if membership is not None and membership["meta"]["roomId"] == room_id:
            raise BizException(ErrorCode.ROOM_ALREADY_JOINED)

        max_players = int(meta.get("maxPlayers", 0))
        active_members = [item for item in members if is_active_room_member(item)]
        if max_players > 0 and len(active_members) >= max_players:
            raise BizException(ErrorCode.ROOM_FULL)

        inviter_nickname = self._resolve_inviter_nickname(
            sender_member,
            sender_id,
        )
        forward_payload = RoomInviteForwardPayload(
            roomId=room_id,
            roomName=str(meta.get("roomName", "")).strip() or room_id,
            gameCode=str(meta.get("gameCode", "")).strip(),
            inviterPlayerId=sender_id,
            inviterNickname=inviter_nickname,
        )
        return forward_payload.model_dump()

    def _resolve_inviter_nickname(
        self,
        sender_member: Dict[str, Any],
        sender_id: str,
    ) -> str:
        """
        从房间成员或用户账号解析邀请方昵称。

        :param sender_member: 邀请方成员对象。
        :param sender_id: 邀请方 serviceId。
        :return: 邀请方展示昵称。
        """
        member_nickname = str(sender_member.get("nickname", "")).strip()
        if member_nickname:
            return member_nickname
        account = self._account_service.get_by_server_id(sender_id, active_only=True)
        if account is not None:
            account_nickname = str(account.nickname or "").strip()
            if account_nickname:
                return account_nickname
        return sender_id
