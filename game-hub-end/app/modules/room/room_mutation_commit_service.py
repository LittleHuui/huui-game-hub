"""Room 聚合原子提交编排服务。"""

from typing import Any, Dict, List, Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.id_utils import generate_server_id
from app.modules.room.room_mutation_commit_repository import (
    RoomMutationCommitRepository,
    room_mutation_commit_repository,
)
from app.modules.room.room_mutation_commit_schemas import (
    RoomMemberUpsert,
    RoomMutationCommit,
    RoomMutationCommitResult,
)


class RoomMutationCommitService(object):
    """构建并执行 Room 聚合 CAS 提交。"""

    def __init__(
        self,
        repository: RoomMutationCommitRepository = room_mutation_commit_repository,
    ) -> None:
        """初始化 Room 聚合提交服务。"""
        self._repository = repository

    async def commit(
        self,
        room_id: str,
        expected_room_version: int,
        next_meta: Dict[str, Any],
        member_upserts: Optional[List[Dict[str, Any]]] = None,
        member_deletes: Optional[List[str]] = None,
        ttl_seconds: int = 86400,
        delete_room: bool = False,
        claim_player_id: Optional[str] = None,
    ) -> RoomMutationCommitResult:
        """
        提交 meta、成员和 roomVersion。
        :param room_id: 房间 ID。
        :param expected_room_version: 期望版本；创建时为 -1。
        :param next_meta: 下一版 meta。
        :param member_upserts: 待写入成员。
        :param member_deletes: 待删除成员 ID。
        :param ttl_seconds: 聚合 TTL。
        :param claim_player_id: 与成员写入一并原子占用房间的真人玩家。
        :return: 原子提交结果。
        """
        next_version = 1 if expected_room_version < 0 else int(expected_room_version) + 1
        upserts = []
        for member in member_upserts or []:
            player_id = str(member.get("playerId", "")).strip()
            if player_id:
                upserts.append(RoomMemberUpsert(playerId=player_id, member=member))
        result = await self._repository.commit(
            RoomMutationCommit(
                roomId=room_id,
                expectedRoomVersion=int(expected_room_version),
                nextRoomVersion=next_version,
                nextMeta=next_meta,
                memberUpserts=upserts,
                memberDeletes=list(member_deletes or []),
                ttlSeconds=int(ttl_seconds),
                commitId=generate_server_id("room-mutation"),
                deleteRoom=bool(delete_room),
                claimPlayerId=claim_player_id,
            ),
        )
        if result.status == "VERSION_CONFLICT":
            raise BizException(ErrorCode.GAME_VIEW_VERSION_CONFLICT)
        if result.status == "ROOM_NOT_FOUND":
            raise BizException(ErrorCode.ROOM_NOT_FOUND)
        if result.status == "PLAYER_ALREADY_IN_ROOM":
            raise BizException(ErrorCode.PLAYER_ALREADY_IN_ROOM)
        return result
