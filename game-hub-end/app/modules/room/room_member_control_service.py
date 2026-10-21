"""房间成员托管与等待中成员管理服务。"""

import logging
from typing import Any, Dict, List, Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock
from app.core.redis.redis_keys import RedisKeys
from app.core.time_utils import now_ms
from app.modules.game_config.module_service import GameModuleService
from app.modules.room.mapper import build_room_response
from app.modules.room.realtime_service import push_room_list_updated, push_room_updated
from app.modules.room.repository import RoomRepository
from app.modules.room.room_game_view_push import RoomGameViewPushPort
from app.modules.room.room_member_support import (
    find_member,
    is_real_human_member,
    is_shell_managed,
    sort_members_by_joined_at,
)
from app.modules.room.room_mutation_commit_service import RoomMutationCommitService
from app.modules.room.room_platform_support import (
    ROOM_ACTION_LOCK_TTL_SECONDS,
    USER_ACTION_LOCK_WAIT_TIMEOUT_MS,
    acquire_user_room_lock,
    append_ai_players,
    count_ai_members,
    game_service_scope,
    is_active_room_member,
    remove_waiting_members,
    require_meta,
    require_playing_room,
    require_room_owner,
    require_waiting_room,
    resolve_effective_room_limits,
    should_cleanup_playing_room,
)
from app.modules.room.room_task_scheduling_service import RoomTaskSchedulingService
from app.modules.room.schemas import RemoveRoomMemberRequest, RoomResponse
from app.modules.user.models import UserAccount

logger = logging.getLogger(__name__)


class RoomMemberControlService(object):
    """房间成员托管、等待中 AI 与成员移除编排。"""

    SHELL_MANAGED_REASONS = frozenset({"presenceTimeout", "leave"})
    ACTIVE_MANAGED_REASONS = frozenset({"manual", "turnTimeout"})

    def __init__(
        self,
        repository: RoomRepository,
        lock_service: RedisDistributedLock,
        game_service: Optional[GameModuleService],
        room_mutation_commit_service: RoomMutationCommitService,
        task_scheduling_service: RoomTaskSchedulingService,
        game_view_push: RoomGameViewPushPort,
    ) -> None:
        """
        初始化房间成员控制服务。

        :param repository: 房间 Redis 仓库。
        :param lock_service: 分布式锁服务。
        :param game_service: 游戏模块服务；后台可为 ``None``。
        :param room_mutation_commit_service: 房间变更提交服务。
        :param task_scheduling_service: 托管与自动推进任务调度服务。
        :param game_view_push: 对局进行中 GameView 推送端口。
        """
        self._repository = repository
        self._lock_service = lock_service
        self._game_service = game_service
        self._room_mutation_commit_service = room_mutation_commit_service
        self._task_scheduling_service = task_scheduling_service
        self._game_view_push = game_view_push

    async def mark_member_active_managed(self, room_id: str, player_id: str, reason: str) -> bool:
        """
        将成员标记为 active 托管并同步房间状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 托管原因（manual / turnTimeout）。
        :return: 是否成功标记或房间已无需处理；锁冲突等临时失败返回 ``False``。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        normalized_reason = str(reason or "").strip()
        if not normalized_room_id or not normalized_player_id:
            return False
        if normalized_reason not in self.ACTIVE_MANAGED_REASONS:
            return False
        lock_key = RedisKeys.room_lock(normalized_room_id)
        try:
            lock_handle = await self._lock_service.acquire(
                lock_key,
                ttl_seconds=ROOM_ACTION_LOCK_TTL_SECONDS,
                wait_timeout_ms=USER_ACTION_LOCK_WAIT_TIMEOUT_MS,
                owner_hint="active:{0}".format(normalized_player_id),
            )
        except LockAcquireError:
            logger.warning(
                "mark_member_active_managed lock conflict, roomId=%s playerId=%s reason=%s",
                normalized_room_id,
                normalized_player_id,
                normalized_reason,
            )
            return False
        async with lock_handle:
            meta = await self._repository.get_meta(normalized_room_id)
            if meta is None or str(meta.get("status", "")).strip() != "playing":
                return True
            members = await self._repository.list_players(normalized_room_id)
            target = find_member(members, normalized_player_id)
            if target is None:
                return True
            if bool(target.get("isAi")):
                return True
            if is_shell_managed(target):
                return True
            if str(target.get("managedMode", "")).strip() == "active":
                await self._task_scheduling_service.create_current_player_managed_task_if_needed(
                    normalized_room_id,
                    "turnTimeoutManaged" if normalized_reason == "turnTimeout" else normalized_reason,
                )
                return True
            await self._mark_member_active_managed_locked(
                normalized_room_id,
                meta,
                members,
                normalized_player_id,
                normalized_reason,
            )
            await self._task_scheduling_service.create_current_player_managed_task_if_needed(
                normalized_room_id,
                "turnTimeoutManaged" if normalized_reason == "turnTimeout" else normalized_reason,
            )
            return True

    async def mark_member_shell_managed(self, room_id: str, player_id: str, reason: str) -> bool:
        """
        将成员标记为 shell 托管并同步房间状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 托管原因（presenceTimeout / leave）。
        :return: 是否成功标记或房间已无需处理；锁冲突等临时失败返回 ``False``。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        normalized_reason = str(reason or "").strip()
        if not normalized_room_id or not normalized_player_id:
            return False
        if normalized_reason not in self.SHELL_MANAGED_REASONS:
            return False
        lock_key = RedisKeys.room_lock(normalized_room_id)
        try:
            lock_handle = await self._lock_service.acquire(
                lock_key,
                ttl_seconds=ROOM_ACTION_LOCK_TTL_SECONDS,
                wait_timeout_ms=USER_ACTION_LOCK_WAIT_TIMEOUT_MS,
                owner_hint="shell:{0}".format(normalized_player_id),
            )
        except LockAcquireError:
            logger.warning(
                "mark_member_shell_managed lock conflict, roomId=%s playerId=%s reason=%s",
                normalized_room_id,
                normalized_player_id,
                normalized_reason,
            )
            return False
        async with lock_handle:
            meta = await self._repository.get_meta(normalized_room_id)
            if meta is None or str(meta.get("status", "")).strip() != "playing":
                return True
            members = await self._repository.list_players(normalized_room_id)
            target = find_member(members, normalized_player_id)
            if target is None:
                return True
            if is_shell_managed(target):
                await self._task_scheduling_service.create_current_player_managed_task_if_needed(
                    normalized_room_id,
                    normalized_reason,
                )
                return True
            if bool(target.get("isAi")):
                return True
            current_time = now_ms()
            marked = await self.apply_shell_managed_in_lock(
                normalized_room_id,
                meta,
                members,
                normalized_player_id,
                normalized_reason,
                current_time,
            )
            if marked is None:
                return True

            game_code = str(meta.get("gameCode", "")).strip()
            owner_id = str(meta.get("ownerPlayerId", "")).strip()
            if owner_id == normalized_player_id:
                human_members = [
                    item
                    for item in sort_members_by_joined_at(members)
                    if is_real_human_member(item)
                    and str(item.get("playerId", "")).strip() != normalized_player_id
                ]
                if human_members:
                    new_owner = human_members[0]
                    new_owner_id = str(new_owner.get("playerId", "")).strip()
                    meta["ownerPlayerId"] = new_owner_id
                    meta["ownerNickname"] = str(new_owner.get("nickname", new_owner_id)).strip()
            meta["updatedAt"] = current_time
            current_version = await self._repository.get_room_version(normalized_room_id)
            result = await self._room_mutation_commit_service.commit(
                normalized_room_id,
                int(current_version or 0),
                meta,
                member_upserts=[marked],
            )
            version = int(result.committedRoomVersion or 0)
            refreshed_members = await self._repository.list_players(normalized_room_id)
            if should_cleanup_playing_room(refreshed_members):
                await self._room_mutation_commit_service.commit(
                    normalized_room_id,
                    version,
                    meta,
                    delete_room=True,
                )
                await self._repository.remove_game_room_index(game_code, normalized_room_id)
                await self._repository.remove_playing_room(normalized_room_id)
                await push_room_list_updated(game_code)
                return True

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
                normalized_reason,
            )
            return True

    async def start_managed_mode(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        玩家主动开启在线托管（active）。

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
            require_playing_room(meta)
            members = await self._repository.list_players(normalized_room_id)
            target = find_member(members, player_id)
            if target is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            if is_shell_managed(target):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="请先恢复席位")
            room_response = await self._mark_member_active_managed_locked(
                normalized_room_id,
                meta,
                members,
                player_id,
                "manual",
            )
            await self._task_scheduling_service.create_current_player_managed_task_if_needed(
                normalized_room_id,
                "managedModeStarted",
            )
            return room_response

    async def stop_managed_mode(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        玩家主动取消在线托管（active）。

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
            require_playing_room(meta)
            members = await self._repository.list_players(normalized_room_id)
            target = find_member(members, player_id)
            if target is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            if is_shell_managed(target):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="请先恢复席位")
            if str(target.get("managedMode", "")).strip() != "active":
                raise BizException(ErrorCode.PARAM_ERROR, message="当前未处于在线托管")
            current_time = now_ms()
            target["isManaged"] = False
            target["managedMode"] = None
            target["managedReason"] = None
            target["managedAt"] = None
            target["updatedAt"] = current_time
            meta["updatedAt"] = current_time
            current_version = int(await self._repository.get_room_version(normalized_room_id) or 0)
            result = await self._room_mutation_commit_service.commit(
                normalized_room_id,
                current_version,
                meta,
                member_upserts=[target],
            )
            version = int(result.committedRoomVersion or 0)
            await self._repository.refresh_room_ttl(normalized_room_id)
            refreshed_members = await self._repository.list_players(normalized_room_id)
            room_response = build_room_response(meta, refreshed_members, version)
            await push_room_updated(room_response)
            await self._game_view_push.push_current_game_view_if_playing(
                normalized_room_id,
                meta,
                refreshed_members,
                version,
            )
            await self._task_scheduling_service.create_current_player_managed_task_if_needed(
                normalized_room_id,
                "managedModeStopped",
            )
            return room_response

    async def add_room_ai(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        在等待中的房间内添加一名平台代管 AI 玩家（仅房主可操作）。

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
            require_waiting_room(meta)
            require_room_owner(meta, player_id)
            game_code = str(meta.get("gameCode", "")).strip()
            with game_service_scope(self._game_service) as resolved_game_service:
                definition = resolved_game_service.get_game_rule_definition(game_code)
            room_rule = definition.roomRule
            _, allow_ai, max_ai_count = resolve_effective_room_limits(meta, room_rule)
            if not allow_ai:
                raise BizException(ErrorCode.PARAM_ERROR, message="当前玩法不允许 AI 玩家")
            members = await self._repository.list_players(normalized_room_id)
            current_ai_count = count_ai_members(members)
            if current_ai_count + 1 > max_ai_count:
                raise BizException(ErrorCode.PARAM_ERROR, message="AI 玩家数量已达上限")
            max_players = int(meta.get("maxPlayers", 0))
            active_members = [item for item in members if is_active_room_member(item)]
            if len(active_members) >= max_players:
                raise BizException(ErrorCode.ROOM_FULL)
            updated_members = await append_ai_players(
                self._repository,
                self._room_mutation_commit_service,
                normalized_room_id,
                meta,
                members,
                1,
            )
            version = int(await self._repository.get_room_version(normalized_room_id) or 0)
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = build_room_response(meta, updated_members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            return room_response

    async def remove_room_member(
        self,
        account: UserAccount,
        room_id: str,
        request: RemoveRoomMemberRequest,
    ) -> RoomResponse:
        """
        房主在等待中的房间内移除指定成员（真人或 AI）。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :param request: 移除成员请求。
        :return: 更新后的房间详情。
        """
        normalized_room_id = room_id.strip()
        owner_player_id = account.server_id.strip()
        target_player_id = request.targetPlayerId.strip()
        if not target_player_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="targetPlayerId 不能为空")
        if target_player_id == owner_player_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="不能移除自己")
        async with await acquire_user_room_lock(
            self._lock_service,
            normalized_room_id,
            owner_player_id,
        ):
            meta = await require_meta(self._repository, normalized_room_id)
            require_waiting_room(meta)
            require_room_owner(meta, owner_player_id)
            members = await self._repository.list_players(normalized_room_id)
            target_member = find_member(members, target_player_id)
            if target_member is None or is_shell_managed(target_member):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            current_time = now_ms()
            meta["updatedAt"] = current_time
            remaining_members = await remove_waiting_members(
                self._repository,
                self._room_mutation_commit_service,
                normalized_room_id,
                meta,
                members,
                [target_player_id],
            )
            version = int(await self._repository.get_room_version(normalized_room_id) or 0)
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = build_room_response(meta, remaining_members, version)
            await push_room_updated(room_response)
            game_code = str(meta.get("gameCode", "")).strip()
            await push_room_list_updated(game_code)
            return room_response

    async def apply_shell_managed_in_lock(
        self,
        room_id: str,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        player_id: str,
        reason: str,
        current_time: int,
    ) -> Optional[Dict[str, Any]]:
        """
        在房间锁内构造 shell 成员变化，由调用方随元信息一起原子提交。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 房间成员列表。
        :param player_id: 玩家 ID。
        :param reason: 托管原因（presenceTimeout / leave）。
        :param current_time: 当前时间戳（毫秒）。
        :return: 更新后的成员；未找到或 AI 时返回 ``None``。
        """
        target = find_member(members, player_id)
        if target is None:
            return None
        if bool(target.get("isAi")):
            return None
        target["isManaged"] = True
        target["managedMode"] = "shell"
        target["managedReason"] = reason
        target["managedAt"] = current_time
        target["onlineState"] = "managed"
        target["updatedAt"] = current_time
        return target

    async def _mark_member_active_managed_locked(
        self,
        room_id: str,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        player_id: str,
        reason: str,
    ) -> RoomResponse:
        """
        在已持有房间锁的上下文中将成员标记为 active 托管并推送房间更新。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 房间成员列表。
        :param player_id: 玩家 ID。
        :param reason: 托管原因（manual / turnTimeout）。
        :return: 更新后的房间详情。
        """
        current_time = now_ms()
        target = find_member(members, player_id)
        member_upserts = []
        if target is not None:
            target["isManaged"] = True
            target["managedMode"] = "active"
            target["managedReason"] = reason
            target["managedAt"] = current_time
            target["updatedAt"] = current_time
            member_upserts.append(target)
        meta["updatedAt"] = current_time
        current_version = await self._repository.get_room_version(room_id)
        result = await self._room_mutation_commit_service.commit(
            room_id,
            int(current_version or 0),
            meta,
            member_upserts=member_upserts,
        )
        version = int(result.committedRoomVersion or 0)
        await self._repository.refresh_room_ttl(room_id)
        refreshed_members = await self._repository.list_players(room_id)
        room_response = build_room_response(meta, refreshed_members, version)
        await push_room_updated(room_response)
        await self._game_view_push.push_current_game_view_if_playing(
            room_id,
            meta,
            refreshed_members,
            version,
        )
        return room_response
