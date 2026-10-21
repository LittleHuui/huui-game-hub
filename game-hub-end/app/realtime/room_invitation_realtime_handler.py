"""房间邀请实时 Handler 适配器。"""

from typing import Dict, Optional

from pydantic import ValidationError

from app.core.database import session_scope
from app.core.websocket.schemas import RealtimeHandlerResult, RoomInviteClientPayload
from app.modules.room.repository import RoomRepository
from app.modules.room.room_invitation_service import RoomInvitationService
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.repository import UserAccountRepository


class RoomInvitationRealtimeHandler:
    """将 ``RoomInvitationService`` 适配为房间邀请实时 Handler。"""

    def __init__(self, repository: RoomRepository) -> None:
        """
        初始化房间邀请 Handler。

        :param repository: 房间 Redis 仓库。
        """
        self._repository = repository

    async def handle(
        self,
        sender_service_id: str,
        payload: Dict[str, object],
        request_id: Optional[str],
    ) -> RealtimeHandlerResult:
        """
        校验邀请载荷并构造权威转发结果。

        :param sender_service_id: 邀请方 serviceId。
        :param payload: 客户端邀请载荷。
        :param request_id: 请求 ID（当前未使用，保留签名便于扩展）。
        :return: Handler 标准结果。
        """
        _ = request_id
        try:
            invite_request = RoomInviteClientPayload.model_validate(payload)
        except ValidationError:
            return RealtimeHandlerResult(error_message="邀请参数无效")
        with session_scope() as db:
            account_service = UserAccountEntityService(UserAccountRepository(db))
            invitation_service = RoomInvitationService(self._repository, account_service)
            forward_payload = await invitation_service.build_invitation(
                sender_service_id,
                invite_request,
            )
        return RealtimeHandlerResult(
            forward_service_id=invite_request.targetServiceId.strip(),
            forward_payload=forward_payload,
        )
