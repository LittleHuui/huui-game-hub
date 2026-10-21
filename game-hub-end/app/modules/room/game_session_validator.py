"""房间对局会话校验端口。"""

from typing import Any, Dict, List

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.modules.room.repository import RoomRepository
from app.modules.room.room_member_support import find_member, is_shell_managed


class GameSessionValidator(object):
    """校验房间元信息与成员资格。"""

    def __init__(self, repository: RoomRepository) -> None:
        self._repository = repository

    async def require_meta(self, room_id: str) -> Dict[str, Any]:
        """
        读取房间元信息，不存在时抛业务异常。

        :param room_id: 房间 ID。
        :return: 房间元信息。
        """
        meta = await self._repository.get_meta(str(room_id or "").strip())
        if meta is None:
            raise BizException(ErrorCode.ROOM_NOT_FOUND)
        return meta

    def require_playing_room(self, meta: Dict[str, Any]) -> None:
        """
        校验房间对局已开始。

        :param meta: 房间元信息。
        :return: 无。
        """
        if meta.get("status") != "playing":
            raise BizException(ErrorCode.PARAM_ERROR, message="对局尚未开始")

    async def list_members(self, room_id: str) -> List[Dict[str, Any]]:
        """
        读取房间成员列表。

        :param room_id: 房间 ID。
        :return: 成员列表。
        """
        return await self._repository.list_players(str(room_id or "").strip())

    def require_member(self, members: List[Dict[str, Any]], player_id: str) -> None:
        """
        校验玩家为房间成员。

        :param members: 成员列表。
        :param player_id: 玩家 ID。
        :return: 无。
        """
        if find_member(members, player_id) is None:
            raise BizException(ErrorCode.ROOM_NOT_MEMBER)

    def require_active_human_member(
        self,
        members: List[Dict[str, Any]],
        player_id: str,
    ) -> Dict[str, Any]:
        """
        校验玩家为可操作的真人成员（非 shell、非托管）。

        :param members: 成员列表。
        :param player_id: 玩家 ID。
        :return: 成员对象。
        """
        target_member = find_member(members, player_id)
        if target_member is None:
            raise BizException(ErrorCode.ROOM_NOT_MEMBER)
        if is_shell_managed(target_member):
            raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="请先恢复席位")
        if bool(target_member.get("isManaged")):
            raise BizException(ErrorCode.PLAYER_MANAGED, message="当前为托管状态，请先取消托管")
        return target_member

    def require_readable_member(
        self,
        members: List[Dict[str, Any]],
        player_id: str,
    ) -> None:
        """
        校验玩家为可读对局视图的成员（非 shell）。

        :param members: 成员列表。
        :param player_id: 玩家 ID。
        :return: 无。
        """
        target_member = find_member(members, player_id)
        if target_member is None or is_shell_managed(target_member):
            raise BizException(ErrorCode.ROOM_NOT_MEMBER)
