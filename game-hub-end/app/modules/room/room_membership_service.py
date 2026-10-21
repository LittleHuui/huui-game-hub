"""房间成员进出与托管席位恢复编排。"""

import logging

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.lock.distributed_lock import RedisDistributedLock
from app.core.time_utils import now_ms
from app.modules.game_config.module_service import GameModuleService
from app.modules.room.game_presentation_service import GamePresentationService
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.mapper import build_room_response
from app.modules.room.realtime_service import (
    push_room_list_updated,
    push_room_updated,
)
from app.modules.room.room_game_view_push import RoomGameViewPushPort
from app.modules.room.repository import RoomRepository
from app.modules.room.room_member_control_service import RoomMemberControlService
from app.modules.room.room_member_support import (
    find_member,
    has_real_human_member,
    is_real_human_member,
    is_shell_managed,
    sort_members_by_joined_at,
)
from app.modules.room.room_mutation_commit_service import RoomMutationCommitService
from app.modules.room.room_platform_support import (
    acquire_user_room_lock,
    game_service_scope,
    require_meta,
    should_cleanup_playing_room,
)
from app.modules.room.room_task_scheduling_service import RoomTaskSchedulingService
from app.modules.room.schemas import MyActiveRoomResponse, RoomLeaveResponse, RoomResponse
from app.modules.user.models import UserAccount

logger = logging.getLogger(__name__)


class RoomMembershipService(object):
    """房间离开、托管席位恢复与对局视图同步推送。"""

    def __init__(
        self,
        repository: RoomRepository,
        lock_service: RedisDistributedLock,
        game_service: GameModuleService,
        room_mutation_commit_service: RoomMutationCommitService,
        state_reader: GameStateReader,
        presentation_service: GamePresentationService,
        member_control_service: RoomMemberControlService,
        task_scheduling_service: RoomTaskSchedulingService,
    ) -> None:
        """
        初始化房间成员服务。

        :param repository: 房间 Redis 仓库。
        :param lock_service: 分布式锁服务。
        :param game_service: 游戏模块服务。
        :param room_mutation_commit_service: 房间变更提交服务。
        :param state_reader: 运行时读取端口。
        :param presentation_service: 对局展示服务。
        :param member_control_service: 成员托管控制服务。
        :param task_scheduling_service: 托管与自动推进任务调度服务。
        """
        self._repository = repository
        self._lock_service = lock_service
        self._game_service = game_service
        self._room_mutation_commit_service = room_mutation_commit_service
        self._game_view_push = RoomGameViewPushPort(repository, state_reader, presentation_service)
        self._member_control_service = member_control_service
        self._task_scheduling_service = task_scheduling_service

    async def leave_room(self, account: UserAccount, room_id: str) -> RoomLeaveResponse:
        """
        离开房间（``waiting`` / ``playing`` 状态允许）。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 离开结果；房间解散时 ``room`` 为 ``None``。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id
        async with await acquire_user_room_lock(
            self._lock_service,
            normalized_room_id,
            player_id,
        ):
            meta = await require_meta(self._repository, normalized_room_id)
            room_status = str(meta.get("status", "")).strip()
            if room_status not in ("waiting", "playing"):
                raise BizException(ErrorCode.ROOM_ALREADY_STARTED)
            game_code = str(meta.get("gameCode", "")).strip()
            owner_player_id = str(meta.get("ownerPlayerId", "")).strip()
            members_before = sort_members_by_joined_at(
                await self._repository.list_players(normalized_room_id)
            )
            if find_member(members_before, player_id) is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)

            current_time = now_ms()
            marked_member = None
            if room_status == "playing":
                marked_member = await self._member_control_service.apply_shell_managed_in_lock(
                    normalized_room_id,
                    meta,
                    members_before,
                    player_id,
                    "leave",
                    current_time,
                )

            if room_status == "playing":
                refreshed_members = await self._repository.list_players(normalized_room_id)
                if marked_member is not None and find_member(refreshed_members, player_id) is not None:
                    remaining_members = sort_members_by_joined_at(
                        [
                            marked_member
                            if str(member.get("playerId", "")).strip() == player_id
                            else member
                            for member in refreshed_members
                        ]
                    )
                else:
                    remaining_members = sort_members_by_joined_at(refreshed_members)
            else:
                remaining_members = sort_members_by_joined_at(
                    [
                        member
                        for member in members_before
                        if str(member.get("playerId", "")).strip() != player_id
                    ]
                )

            if room_status == "waiting":
                if not remaining_members or not has_real_human_member(remaining_members):
                    current_version = int(
                        await self._repository.get_room_version(normalized_room_id) or 0
                    )
                    await self._room_mutation_commit_service.commit(
                        normalized_room_id,
                        current_version,
                        meta,
                        member_deletes=[player_id],
                        delete_room=True,
                    )
                    await self._repository.remove_game_room_index(game_code, normalized_room_id)
                    await push_room_list_updated(game_code)
                    return RoomLeaveResponse(
                        roomId=normalized_room_id,
                        gameCode=game_code,
                        dissolved=True,
                        room=None,
                    )
            elif room_status == "playing":
                if should_cleanup_playing_room(remaining_members):
                    current_version = int(
                        await self._repository.get_room_version(normalized_room_id) or 0
                    )
                    await self._room_mutation_commit_service.commit(
                        normalized_room_id,
                        current_version,
                        meta,
                        delete_room=True,
                    )
                    await self._repository.remove_game_room_index(game_code, normalized_room_id)
                    await self._repository.remove_playing_room(normalized_room_id)
                    await push_room_list_updated(game_code)
                    return RoomLeaveResponse(
                        roomId=normalized_room_id,
                        gameCode=game_code,
                        dissolved=True,
                        room=None,
                    )

            meta["updatedAt"] = current_time
            if owner_player_id == player_id:
                human_members = [
                    item for item in sort_members_by_joined_at(remaining_members)
                    if is_real_human_member(item)
                ]
                if human_members:
                    new_owner = human_members[0]
                    new_owner_id = str(new_owner.get("playerId", "")).strip()
                    meta["ownerPlayerId"] = new_owner_id
                    meta["ownerNickname"] = str(
                        new_owner.get("nickname", new_owner_id)
                    ).strip()

            current_version = int(
                await self._repository.get_room_version(normalized_room_id) or 0
            )
            result = await self._room_mutation_commit_service.commit(
                normalized_room_id,
                current_version,
                meta,
                member_upserts=[marked_member] if marked_member is not None else [],
                member_deletes=[player_id] if room_status == "waiting" else [],
            )
            version = int(result.committedRoomVersion or 0)
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = build_room_response(meta, remaining_members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            if room_status == "playing":
                await self._game_view_push.push_current_game_view_if_playing(
                    normalized_room_id,
                    meta,
                    remaining_members,
                    version,
                )
                await self._task_scheduling_service.create_current_player_managed_task_if_needed(
                    normalized_room_id,
                    "leave",
                )
            return RoomLeaveResponse(
                roomId=normalized_room_id,
                gameCode=game_code,
                dissolved=False,
                room=room_response,
            )

    async def rejoin_managed_room(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        恢复对局中托管席位并重建 player_room 索引。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 更新后的房间详情。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id.strip()
        async with await acquire_user_room_lock(
            self._lock_service,
            normalized_room_id,
            player_id,
        ):
            meta = await require_meta(self._repository, normalized_room_id)
            if str(meta.get("status", "")).strip() != "playing":
                raise BizException(ErrorCode.PARAM_ERROR, message="房间不在对局中")
            members = await self._repository.list_players(normalized_room_id)
            target = find_member(members, player_id)
            if target is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="当前无可恢复席位")
            if bool(target.get("isAi")):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="当前无可恢复席位")
            if not is_shell_managed(target):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="当前无可恢复席位")
            membership = await self._repository.get_active_membership(player_id)
            if membership is not None and membership["meta"]["roomId"] != normalized_room_id:
                raise BizException(ErrorCode.PLAYER_ALREADY_IN_ROOM)
            current_time = now_ms()
            target["isManaged"] = False
            target["managedMode"] = None
            target["managedReason"] = None
            target["managedAt"] = None
            target["onlineState"] = "online"
            target["updatedAt"] = current_time
            game_code = str(meta.get("gameCode", "")).strip()
            meta["updatedAt"] = current_time
            current_version = int(await self._repository.get_room_version(normalized_room_id) or 0)
            result = await self._room_mutation_commit_service.commit(
                normalized_room_id,
                current_version,
                meta,
                member_upserts=[target],
                claim_player_id=player_id,
            )
            version = int(result.committedRoomVersion or 0)
            await self._repository.refresh_room_ttl(normalized_room_id)
            refreshed_members = await self._repository.list_players(normalized_room_id)
            room_response = build_room_response(meta, refreshed_members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            await self._game_view_push.push_current_game_view_if_playing(
                normalized_room_id,
                meta,
                refreshed_members,
                version,
            )
            await self._task_scheduling_service.create_current_player_managed_task_if_needed(
                normalized_room_id,
                "rejoinManagedRoom",
            )
            return room_response

    async def get_my_managed_shell_room(
        self,
        account: UserAccount,
        game_code: str,
    ) -> MyActiveRoomResponse:
        """
        查询当前用户在指定游戏中的托管空壳房间。

        :param account: 当前用户账号。
        :param game_code: 游戏编码。
        :return: 托管空壳房间响应。
        """
        normalized_code = game_code.strip()
        if not normalized_code:
            raise BizException(ErrorCode.PARAM_ERROR, message="gameCode 不能为空")
        with game_service_scope(self._game_service) as resolved_game_service:
            resolved_game_service.get_game_rule_definition(normalized_code)
        player_id = account.server_id.strip()
        if not player_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="当前用户 ID 无效")
        membership = await self._repository.get_shell_membership(player_id, normalized_code)
        if membership is None:
            return MyActiveRoomResponse(room=None)
        return MyActiveRoomResponse(room=build_room_response(
            membership["meta"], membership["members"], membership["roomVersion"],
        ))
