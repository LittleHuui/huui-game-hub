"""房间模块业务编排。"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.database import session_scope
from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock, distributed_lock
from app.core.redis.redis_keys import RedisKeys
from app.core.id_utils import generate_server_id
from app.core.time_utils import now_ms
from app.modules.game.deps import build_game_module_service
from app.modules.game.module_service import GameModuleService
from app.modules.game_seed.schemas import OnlineGameRuleSeed, resolve_room_config_defaults
from app.modules.room.managed_action_selector import ManagedActionSelector
from app.modules.room.managed_task_service import (
    MANAGED_TURN_DELAY_MS,
    ManagedTaskSubmitResult,
    ManagedTurnTask,
    ManagedTurnTaskService,
)
from app.modules.room.mapper import build_room_response
from app.modules.room.realtime_service import (
    build_views_for_members,
    collect_human_player_ids,
    push_game_view_updated,
    push_room_list_updated,
    push_room_updated,
)
from app.modules.room.repository import RoomRepository
from app.modules.room.schemas import (
    CreateRoomRequest,
    MyActiveRoomResponse,
    RemoveRoomMemberRequest,
    RoomActionRequest,
    RoomLeaveResponse,
    RoomListItemResponse,
    RoomResponse,
    UpdateRoomConfigRequest,
)
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService
from app.modules.strategy_turn.schemas import (
    ApplyActionCommand,
    GameAction,
    GameEvent,
    GameView,
    RuntimeSnapshot,
    StartGameCommand,
    StrategyTurnRuntimeRule,
)
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.models import UserAccount

logger = logging.getLogger(__name__)


class RoomModuleService(object):
    """房间业务服务。"""

    ROOM_ACTION_LOCK_TTL_SECONDS = 8
    USER_ACTION_LOCK_WAIT_TIMEOUT_MS = 1200
    MANAGED_ACTION_LOCK_WAIT_TIMEOUT_MS = 0

    def __init__(
        self,
        repository: RoomRepository,
        lock_service: RedisDistributedLock,
        game_service: Optional[GameModuleService],
        runtime_service: StrategyTurnRuntimeService,
        account_service: Optional[UserAccountEntityService],
        managed_task_service: ManagedTurnTaskService,
        managed_action_selector: ManagedActionSelector,
    ) -> None:
        """
        初始化房间业务服务。

        :param repository: 房间 Redis 仓库。
        :param lock_service: 房间锁服务。
        :param game_service: 游戏模块服务。
        :param runtime_service: 策略回合制运行时服务。
        :param account_service: 用户账号实体服务。
        """
        self._repository = repository
        self._lock_service = lock_service
        self._game_service = game_service
        self._runtime_service = runtime_service
        self._account_service = account_service
        self._managed_task_service = managed_task_service
        self._managed_action_selector = managed_action_selector

    @contextmanager
    def _game_service_scope(self) -> Generator[GameModuleService, None, None]:
        """
        获取游戏模块服务：请求级注入优先，否则使用短生命周期数据库会话。

        :yield: ``GameModuleService`` 实例。
        """
        if self._game_service is not None:
            yield self._game_service
            return
        with session_scope() as db:
            yield build_game_module_service(db)

    SHELL_MANAGED_REASONS = frozenset({"timeout", "leave"})

    async def mark_member_shell_managed(self, room_id: str, player_id: str, reason: str) -> bool:
        """
        将成员标记为 shell 托管并同步房间状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 托管原因（timeout / leave）。
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
                ttl_seconds=self.ROOM_ACTION_LOCK_TTL_SECONDS,
                wait_timeout_ms=self.USER_ACTION_LOCK_WAIT_TIMEOUT_MS,
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
            target = self._find_member(members, normalized_player_id)
            if target is None:
                return True
            if self._is_shell_managed(target):
                await self.create_current_player_managed_task_if_needed(
                    normalized_room_id,
                    normalized_reason,
                )
                return True
            current_time = now_ms()
            target["isManaged"] = True
            target["managedMode"] = "shell"
            target["managedReason"] = normalized_reason
            target["managedAt"] = current_time
            target["onlineState"] = "managed"
            target["updatedAt"] = current_time
            await self._repository.save_player(normalized_room_id, normalized_player_id, target)
            await self._repository.delete_player_room(normalized_player_id)

            game_code = str(meta.get("gameCode", "")).strip()
            await self._repository.save_managed_shell_room_index(
                normalized_player_id,
                game_code,
                normalized_room_id,
            )
            owner_id = str(meta.get("ownerPlayerId", "")).strip()
            if owner_id == normalized_player_id:
                human_members = [
                    item
                    for item in self._sort_members_by_joined_at(members)
                    if self._is_real_human_member(item)
                    and str(item.get("playerId", "")).strip() != normalized_player_id
                ]
                if human_members:
                    new_owner = human_members[0]
                    new_owner_id = str(new_owner.get("playerId", "")).strip()
                    meta["ownerPlayerId"] = new_owner_id
                    meta["ownerNickname"] = str(new_owner.get("nickname", new_owner_id)).strip()
            meta["updatedAt"] = current_time
            await self._repository.save_meta(normalized_room_id, meta)

            version = await self._bump_version(normalized_room_id)
            refreshed_members = await self._repository.list_players(normalized_room_id)
            if not self._has_real_human_member(refreshed_members):
                await self._clear_managed_shell_indexes(game_code, refreshed_members)
                await self._repository.delete_room_cascade(
                    normalized_room_id,
                    game_code,
                    [str(item.get("playerId", "")).strip() for item in refreshed_members],
                )
                await push_room_list_updated(game_code)
                return True

            room_response = self._build_room_response(meta, refreshed_members, version)
            await push_room_updated(room_response)
            # 列表项 memberCount 不含 shell，标记 shell 后需刷新列表。
            await push_room_list_updated(game_code)
            await self.push_current_game_view_if_playing(
                normalized_room_id,
                meta,
                refreshed_members,
                version,
            )

            await self.create_current_player_managed_task_if_needed(
                normalized_room_id,
                normalized_reason,
            )
            return True

    async def create_room(self, account: UserAccount, request: CreateRoomRequest) -> RoomResponse:
        """
        创建房间并写入房主、版本号与玩家房间索引。

        :param account: 当前用户账号（房主）。
        :param request: 创建房间请求。
        :return: 房间详情。
        """
        game_code = request.gameCode.strip()
        if not game_code:
            raise BizException(ErrorCode.PARAM_ERROR, message="gameCode 不能为空")
        mode = request.mode.strip()
        if not mode:
            raise BizException(ErrorCode.PARAM_ERROR, message="mode 不能为空")
        owner_player_id = account.server_id.strip()
        if not owner_player_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="当前用户 ID 无效")
        await self._assert_can_create_room(owner_player_id)

        with self._game_service_scope() as game_service:
            definition = game_service.get_game_rule_definition(game_code)
        room_rule = definition.roomRule
        expire_seconds = request.expireSeconds
        if expire_seconds is None:
            expire_seconds = int(room_rule.defaultExpireSeconds)
        if expire_seconds <= 0:
            raise BizException(ErrorCode.PARAM_ERROR, message="expireSeconds 必须大于 0")

        room_config = self._merge_room_config(definition, request.roomConfig)
        ai_count = 0
        max_players = int(room_rule.maxPlayers)
        current_time = now_ms()
        room_id = generate_server_id("room")
        member = self._build_member(owner_player_id, account, current_time)
        owner_nickname = str(member.get("nickname", owner_player_id))
        room_name = str(request.roomName or "").strip()
        if not room_name:
            room_name = "房间-{0}".format(room_id[-6:])
        meta = {
            "roomId": room_id,
            "roomName": room_name,
            "gameCode": game_code,
            "mode": mode,
            "ownerPlayerId": owner_player_id,
            "ownerNickname": owner_nickname,
            "maxPlayers": max_players,
            "aiCount": ai_count,
            "allowAi": bool(room_rule.allowAi),
            "maxAiCount": int(room_rule.maxAiCount),
            "roomConfig": room_config,
            "ruleVersion": definition.ruleVersion,
            "status": "waiting",
            "createdAt": current_time,
            "updatedAt": current_time,
        }

        if not await self._repository.save_meta(room_id, meta, expire_seconds):
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息写入失败")
        if not await self._repository.save_player(room_id, owner_player_id, member, expire_seconds):
            await self._repository.delete_meta(room_id)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员写入失败")
        if not await self._repository.save_version(room_id, 1, expire_seconds):
            await self._rollback_create_room(room_id, owner_player_id, game_code)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间版本写入失败")
        if not await self._repository.save_player_room(owner_player_id, room_id, expire_seconds):
            await self._rollback_create_room(room_id, owner_player_id, game_code)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="玩家房间索引写入失败")
        if not await self._repository.add_game_room_index(game_code, room_id, expire_seconds):
            await self._rollback_create_room(room_id, owner_player_id, game_code)
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间列表索引写入失败")

        members = [member]
        room_response = self._build_room_response(meta, members, 1)
        await push_room_list_updated(game_code)
        return room_response

    async def list_rooms(self, game_code: str) -> List[RoomListItemResponse]:
        """
        按游戏编码查询房间列表。

        :param game_code: 游戏编码。
        :return: 房间列表项。
        """
        normalized_code = game_code.strip()
        if not normalized_code:
            raise BizException(ErrorCode.PARAM_ERROR, message="gameCode 不能为空")
        with self._game_service_scope() as game_service:
            game_service.get_game_rule_definition(normalized_code)
        room_ids = await self._repository.list_game_room_ids(normalized_code)
        items = []
        for room_id in room_ids:
            meta = await self._repository.get_meta(room_id)
            if meta is None:
                await self._repository.remove_game_room_index(normalized_code, room_id)
                await self._repository.remove_playing_room(room_id)
                continue
            if str(meta.get("gameCode", "")).strip() != normalized_code:
                await self._repository.remove_game_room_index(normalized_code, room_id)
                continue
            members = await self._repository.list_players(room_id)
            await self._cleanup_invalid_player_room_indexes(room_id, members)
            room_status = str(meta.get("status", "")).strip()
            if room_status == "waiting":
                cleaned_waiting_members = []
                for member in members:
                    if self._is_shell_managed(member):
                        stale_player_id = str(member.get("playerId", "")).strip()
                        if stale_player_id:
                            await self._repository.delete_player(room_id, stale_player_id)
                            await self._repository.delete_player_room(stale_player_id)
                            await self._repository.delete_managed_shell_room_index(
                                stale_player_id,
                                normalized_code,
                            )
                        continue
                    cleaned_waiting_members.append(member)
                members_changed = len(cleaned_waiting_members) != len(members)
                if members_changed:
                    members = cleaned_waiting_members
                    meta["updatedAt"] = now_ms()
                    await self._repository.save_meta(room_id, meta)
                    version = await self._bump_version(room_id)
                if not self._has_real_human_member(members):
                    member_player_ids = []
                    for member in members:
                        member_id = str(member.get("playerId", "")).strip()
                        if member_id:
                            member_player_ids.append(member_id)
                    await self._clear_managed_shell_indexes(normalized_code, members)
                    await self._repository.delete_room_cascade(
                        room_id,
                        normalized_code,
                        member_player_ids,
                    )
                    await push_room_list_updated(normalized_code)
                    continue
                if members_changed:
                    room_response = self._build_room_response(meta, members, version)
                    await push_room_updated(room_response)
            if not members:
                await self._repository.delete_room_cascade(room_id, normalized_code, [])
                continue
            items.append(
                (
                    int(meta.get("createdAt", 0)),
                    self._build_room_list_item(meta, members),
                )
            )
        items.sort(key=lambda pair: pair[0], reverse=True)
        return [pair[1] for pair in items]

    async def _cleanup_invalid_player_room_indexes(
        self,
        room_id: str,
        members: List[Dict[str, Any]],
    ) -> None:
        """
        清理成员中失效的 player-room 索引（仅 Redis 索引维护）。

        :param room_id: 当前房间 ID。
        :param members: 房间成员列表。
        :return: 无。
        """
        for member in members:
            player_id = str(member.get("playerId", "")).strip()
            if not player_id:
                continue
            indexed_room_id = await self._repository.get_player_room(player_id)
            if not indexed_room_id:
                continue
            if indexed_room_id == room_id:
                continue
            indexed_meta = await self._repository.get_meta(indexed_room_id)
            if indexed_meta is None:
                await self._repository.delete_player_room(player_id)

    async def get_room(self, room_id: str) -> RoomResponse:
        """
        查询房间详情。

        :param room_id: 房间 ID。
        :return: 房间详情。
        """
        meta = await self._require_meta(room_id)
        members = await self._repository.list_players(room_id)
        version = await self._repository.get_version(room_id)
        if version is None:
            version = 0
        return self._build_room_response(meta, members, version)

    async def get_my_active_room(
        self,
        account: UserAccount,
    ) -> MyActiveRoomResponse:
        """
        查询当前用户活跃房间（跨游戏）。

        :param account: 当前用户账号。
        :return: 活跃房间响应；无活跃房间时 ``room`` 为 ``None``。
        """
        player_id = account.server_id.strip()
        if not player_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="当前用户 ID 无效")

        room_id = await self._repository.get_player_room(player_id)
        if not room_id:
            return MyActiveRoomResponse(room=None)

        meta = await self._repository.get_meta(room_id)
        if meta is None:
            await self._repository.delete_player_room(player_id)
            return MyActiveRoomResponse(room=None)

        members = await self._repository.list_players(room_id)
        member = self._find_member(members, player_id)
        if member is None or self._is_shell_managed(member):
            await self._repository.delete_player_room(player_id)
            return MyActiveRoomResponse(room=None)

        status = str(meta.get("status", "")).strip()
        if status not in ("waiting", "playing"):
            return MyActiveRoomResponse(room=None)

        version = await self._repository.get_version(room_id)
        if version is None:
            version = 0
        return MyActiveRoomResponse(
            room=self._build_room_response(meta, members, version),
        )

    async def join_room(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        加入房间。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 更新后的房间详情。
        """
        player_id = account.server_id
        async with await self._acquire_user_room_lock(room_id, player_id):
            meta = await self._require_meta(room_id)
            game_code = str(meta.get("gameCode", "")).strip()
            with self._game_service_scope() as game_service:
                game_service.get_game_rule_definition(game_code)
            members = await self._repository.list_players(room_id)
            existing = self._find_member(members, player_id)
            self._require_waiting_room(meta)
            if existing is not None:
                await self._repository.refresh_room_ttl(room_id)
                version = await self._repository.get_version(room_id)
                if version is None:
                    version = 0
                return self._build_room_response(meta, members, version)
            indexed_room_id = await self._repository.get_player_room(player_id)
            if indexed_room_id and indexed_room_id != room_id:
                indexed_meta = await self._repository.get_meta(indexed_room_id)
                if indexed_meta is None:
                    await self._repository.delete_player_room(player_id)
                else:
                    indexed_members = await self._repository.list_players(indexed_room_id)
                    indexed_member = self._find_member(indexed_members, player_id)
                    if indexed_member is None or self._is_shell_managed(indexed_member):
                        await self._repository.delete_player_room(player_id)
                    else:
                        raise BizException(ErrorCode.PLAYER_ALREADY_IN_ROOM)
            max_players = int(meta.get("maxPlayers", 0))
            active_members = [item for item in members if self._is_active_room_member(item)]
            if len(active_members) >= max_players:
                raise BizException(ErrorCode.ROOM_FULL)
            current_time = now_ms()
            member = self._build_member(player_id, account, current_time)
            if not await self._repository.save_player(room_id, player_id, member):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员写入失败")
            if not await self._repository.save_player_room(player_id, room_id):
                await self._repository.delete_player(room_id, player_id)
                raise BizException(ErrorCode.SYSTEM_ERROR, message="玩家房间索引写入失败")
            meta["updatedAt"] = current_time
            if not await self._repository.save_meta(room_id, meta):
                await self._repository.delete_player_room(player_id)
                await self._repository.delete_player(room_id, player_id)
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            members.append(member)
            version = await self._bump_version(room_id)
            await self._repository.refresh_room_ttl(room_id)
            room_response = self._build_room_response(meta, members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            return room_response

    async def start_managed_mode(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        玩家主动开启在线托管（active）。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 更新后的房间详情。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id.strip()
        async with await self._acquire_user_room_lock(normalized_room_id, player_id):
            meta = await self._require_meta(normalized_room_id)
            self._require_playing_room(meta)
            members = await self._repository.list_players(normalized_room_id)
            target = self._find_member(members, player_id)
            if target is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            if self._is_shell_managed(target):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="请先恢复席位")
            current_time = now_ms()
            target["isManaged"] = True
            target["managedMode"] = "active"
            target["managedReason"] = "manual"
            target["managedAt"] = current_time
            target["updatedAt"] = current_time
            if not await self._repository.save_player(normalized_room_id, player_id, target):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员写入失败")
            meta["updatedAt"] = current_time
            if not await self._repository.save_meta(normalized_room_id, meta):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            refreshed_members = await self._repository.list_players(normalized_room_id)
            room_response = self._build_room_response(meta, refreshed_members, version)
            await push_room_updated(room_response)
            await self.push_current_game_view_if_playing(
                normalized_room_id,
                meta,
                refreshed_members,
                version,
            )
            await self.create_current_player_managed_task_if_needed(
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
        async with await self._acquire_user_room_lock(normalized_room_id, player_id):
            meta = await self._require_meta(normalized_room_id)
            self._require_playing_room(meta)
            members = await self._repository.list_players(normalized_room_id)
            target = self._find_member(members, player_id)
            if target is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            if self._is_shell_managed(target):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="请先恢复席位")
            if str(target.get("managedMode", "")).strip() != "active":
                raise BizException(ErrorCode.PARAM_ERROR, message="当前未处于在线托管")
            current_time = now_ms()
            target["isManaged"] = False
            target["managedMode"] = None
            target["managedReason"] = None
            target["managedAt"] = None
            target["updatedAt"] = current_time
            if not await self._repository.save_player(normalized_room_id, player_id, target):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员写入失败")
            meta["updatedAt"] = current_time
            if not await self._repository.save_meta(normalized_room_id, meta):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            refreshed_members = await self._repository.list_players(normalized_room_id)
            room_response = self._build_room_response(meta, refreshed_members, version)
            await push_room_updated(room_response)
            await self.push_current_game_view_if_playing(
                normalized_room_id,
                meta,
                refreshed_members,
                version,
            )
            await self.create_current_player_managed_task_if_needed(
                normalized_room_id,
                "managedModeStopped",
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
        with self._game_service_scope() as game_service:
            game_service.get_game_rule_definition(normalized_code)
        player_id = account.server_id.strip()
        if not player_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="当前用户 ID 无效")
        room_id = await self._repository.get_managed_shell_room_index(player_id, normalized_code)
        if not room_id:
            return MyActiveRoomResponse(room=None)
        meta = await self._repository.get_meta(room_id)
        if meta is None:
            await self._repository.delete_managed_shell_room_index(player_id, normalized_code)
            return MyActiveRoomResponse(room=None)
        if str(meta.get("gameCode", "")).strip() != normalized_code:
            await self._repository.delete_managed_shell_room_index(player_id, normalized_code)
            return MyActiveRoomResponse(room=None)
        if str(meta.get("status", "")).strip() != "playing":
            await self._repository.delete_managed_shell_room_index(player_id, normalized_code)
            return MyActiveRoomResponse(room=None)
        members = await self._repository.list_players(room_id)
        member = self._find_member(members, player_id)
        if member is None or not self._is_shell_managed(member):
            await self._repository.delete_managed_shell_room_index(player_id, normalized_code)
            return MyActiveRoomResponse(room=None)
        version = await self._repository.get_version(room_id)
        if version is None:
            version = 0
        return MyActiveRoomResponse(room=self._build_room_response(meta, members, version))

    async def rejoin_managed_room(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        恢复对局中托管席位并重建 player_room 索引。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 更新后的房间详情。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id.strip()
        async with await self._acquire_user_room_lock(normalized_room_id, player_id):
            meta = await self._require_meta(normalized_room_id)
            if str(meta.get("status", "")).strip() != "playing":
                raise BizException(ErrorCode.PARAM_ERROR, message="房间不在对局中")
            members = await self._repository.list_players(normalized_room_id)
            target = self._find_member(members, player_id)
            if target is None or not self._is_shell_managed(target):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="当前无可恢复席位")
            indexed_room_id = await self._repository.get_player_room(player_id)
            if indexed_room_id and indexed_room_id != normalized_room_id:
                raise BizException(ErrorCode.PLAYER_ALREADY_IN_ROOM)
            if indexed_room_id == normalized_room_id:
                logger.warning(
                    "rejoin_managed_room cleared stale active player_room index, roomId=%s playerId=%s",
                    normalized_room_id,
                    player_id,
                )
                await self._repository.delete_player_room(player_id)
            current_time = now_ms()
            target["isManaged"] = False
            target["managedMode"] = None
            target["managedReason"] = None
            target["managedAt"] = None
            target["onlineState"] = "online"
            target["updatedAt"] = current_time
            if not await self._repository.save_player(normalized_room_id, player_id, target):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员写入失败")
            if not await self._repository.save_player_room(player_id, normalized_room_id):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="玩家房间索引写入失败")
            game_code = str(meta.get("gameCode", "")).strip()
            await self._repository.delete_managed_shell_room_index(player_id, game_code)
            meta["updatedAt"] = current_time
            if not await self._repository.save_meta(normalized_room_id, meta):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            refreshed_members = await self._repository.list_players(normalized_room_id)
            room_response = self._build_room_response(meta, refreshed_members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            await self.push_current_game_view_if_playing(
                normalized_room_id,
                meta,
                refreshed_members,
                version,
            )
            await self.create_current_player_managed_task_if_needed(
                normalized_room_id,
                "rejoinManagedRoom",
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
        async with await self._acquire_user_room_lock(normalized_room_id, player_id):
            meta = await self._require_meta(normalized_room_id)
            self._require_waiting_room(meta)
            self._require_room_owner(meta, player_id)
            game_code = str(meta.get("gameCode", "")).strip()
            with self._game_service_scope() as game_service:
                definition = game_service.get_game_rule_definition(game_code)
            room_rule = definition.roomRule
            _, allow_ai, max_ai_count = self._resolve_effective_room_limits(meta, room_rule)
            if not allow_ai:
                raise BizException(ErrorCode.PARAM_ERROR, message="当前玩法不允许 AI 玩家")
            members = await self._repository.list_players(normalized_room_id)
            current_ai_count = self._count_ai_members(members)
            if current_ai_count + 1 > max_ai_count:
                raise BizException(ErrorCode.PARAM_ERROR, message="AI 玩家数量已达上限")
            max_players = int(meta.get("maxPlayers", 0))
            active_members = [item for item in members if self._is_active_room_member(item)]
            if len(active_members) >= max_players:
                raise BizException(ErrorCode.ROOM_FULL)
            updated_members = await self._append_ai_players(normalized_room_id, meta, members, 1)
            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = self._build_room_response(meta, updated_members, version)
            await push_room_updated(room_response)
            game_code = str(meta.get("gameCode", "")).strip()
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
        async with await self._acquire_user_room_lock(normalized_room_id, owner_player_id):
            meta = await self._require_meta(normalized_room_id)
            self._require_waiting_room(meta)
            self._require_room_owner(meta, owner_player_id)
            members = await self._repository.list_players(normalized_room_id)
            target_member = self._find_member(members, target_player_id)
            if target_member is None or self._is_shell_managed(target_member):
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            remaining_members = await self._remove_waiting_members(
                normalized_room_id,
                meta,
                members,
                [target_player_id],
            )
            current_time = now_ms()
            meta["updatedAt"] = current_time
            if not await self._repository.save_meta(normalized_room_id, meta):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = self._build_room_response(meta, remaining_members, version)
            await push_room_updated(room_response)
            game_code = str(meta.get("gameCode", "")).strip()
            await push_room_list_updated(game_code)
            return room_response

    async def update_room_config(
        self,
        account: UserAccount,
        room_id: str,
        request: UpdateRoomConfigRequest,
    ) -> RoomResponse:
        """
        房主在等待中的房间内更新人数上限与玩法配置。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :param request: 更新配置请求。
        :return: 更新后的房间详情。
        """
        normalized_room_id = room_id.strip()
        owner_player_id = account.server_id.strip()
        async with await self._acquire_user_room_lock(normalized_room_id, owner_player_id):
            meta = await self._require_meta(normalized_room_id)
            self._require_waiting_room(meta)
            self._require_room_owner(meta, owner_player_id)
            game_code = str(meta.get("gameCode", "")).strip()
            with self._game_service_scope() as game_service:
                definition = game_service.get_game_rule_definition(game_code)
            room_rule = definition.roomRule
            members = await self._repository.list_players(normalized_room_id)
            active_members = [item for item in members if self._is_active_room_member(item)]
            human_count = sum(1 for item in active_members if self._is_real_human_member(item))

            if request.roomConfig is not None:
                merged_config = self._merge_room_config(definition, request.roomConfig)
                existing_config = meta.get("roomConfig")
                if isinstance(existing_config, dict):
                    next_config = dict(existing_config)
                    next_config.update(merged_config)
                else:
                    next_config = merged_config
                meta["roomConfig"] = next_config

            next_max_players, _, _ = self._resolve_effective_room_limits(meta, room_rule)
            if request.maxPlayers is not None:
                next_max_players = int(request.maxPlayers)
                if next_max_players < int(room_rule.minPlayers):
                    raise BizException(ErrorCode.PARAM_ERROR, message="人数上限低于玩法最小人数")
                if next_max_players > int(room_rule.maxPlayers):
                    raise BizException(ErrorCode.PARAM_ERROR, message="人数上限超过玩法允许范围")
                if human_count > next_max_players:
                    raise BizException(
                        ErrorCode.PARAM_ERROR,
                        message="当前真人玩家数已超过新的人数上限",
                    )
                meta["maxPlayers"] = next_max_players

            remove_player_ids = []
            active_count = len(active_members)
            if active_count > next_max_players:
                ai_members = self._sort_members_by_joined_at(
                    [item for item in active_members if bool(item.get("isAi"))]
                )
                need_remove = active_count - next_max_players
                for member in ai_members[-need_remove:]:
                    member_id = str(member.get("playerId", "")).strip()
                    if member_id:
                        remove_player_ids.append(member_id)
                if active_count - len(remove_player_ids) > next_max_players:
                    raise BizException(
                        ErrorCode.PARAM_ERROR,
                        message="人数上限不足以容纳当前成员",
                    )

            remaining_members = members
            if remove_player_ids:
                remaining_members = await self._remove_waiting_members(
                    normalized_room_id,
                    meta,
                    members,
                    remove_player_ids,
                )

            current_time = now_ms()
            meta["updatedAt"] = current_time
            if not await self._repository.save_meta(normalized_room_id, meta):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = self._build_room_response(meta, remaining_members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            return room_response

    async def leave_room(self, account: UserAccount, room_id: str) -> RoomLeaveResponse:
        """
        离开房间（``waiting`` / ``playing`` 状态允许）。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 离开结果；房间解散时 ``room`` 为 ``None``。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id
        async with await self._acquire_user_room_lock(normalized_room_id, player_id):
            meta = await self._require_meta(normalized_room_id)
            room_status = str(meta.get("status", "")).strip()
            if room_status not in ("waiting", "playing"):
                raise BizException(ErrorCode.ROOM_ALREADY_STARTED)
            game_code = str(meta.get("gameCode", "")).strip()
            owner_player_id = str(meta.get("ownerPlayerId", "")).strip()
            members_before = self._sort_members_by_joined_at(
                await self._repository.list_players(normalized_room_id)
            )
            if self._find_member(members_before, player_id) is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            member_player_ids = []
            for member in members_before:
                member_id = str(member.get("playerId", "")).strip()
                if member_id:
                    member_player_ids.append(member_id)

            current_time = now_ms()
            leaving_member = self._find_member(members_before, player_id)
            if room_status == "playing":
                managed_member = dict(leaving_member or {})
                managed_member["isManaged"] = True
                managed_member["managedMode"] = "shell"
                managed_member["managedReason"] = "leave"
                managed_member["managedAt"] = current_time
                managed_member["onlineState"] = "managed"
                managed_member["updatedAt"] = current_time
                if not await self._repository.save_player(normalized_room_id, player_id, managed_member):
                    raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员写入失败")
                await self._repository.delete_player_room(player_id)
                await self._repository.save_managed_shell_room_index(
                    player_id,
                    game_code,
                    normalized_room_id,
                )
            else:
                await self._repository.delete_player(normalized_room_id, player_id)
                await self._repository.delete_player_room(player_id)

            if room_status == "playing":
                remaining_members = self._sort_members_by_joined_at(await self._repository.list_players(normalized_room_id))
            else:
                remaining_members = self._sort_members_by_joined_at(
                    [
                        member
                        for member in members_before
                        if str(member.get("playerId", "")).strip() != player_id
                    ]
                )

            if not self._has_real_human_member(remaining_members):
                await self._clear_managed_shell_indexes(game_code, remaining_members)
                await self._repository.delete_room_cascade(
                    normalized_room_id,
                    game_code,
                    member_player_ids,
                )
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
                    item for item in self._sort_members_by_joined_at(remaining_members)
                    if self._is_real_human_member(item)
                ]
                if not human_members:
                    await self._clear_managed_shell_indexes(game_code, remaining_members)
                    await self._repository.delete_room_cascade(
                        normalized_room_id,
                        game_code,
                        member_player_ids,
                    )
                    await push_room_list_updated(game_code)
                    return RoomLeaveResponse(
                        roomId=normalized_room_id,
                        gameCode=game_code,
                        dissolved=True,
                        room=None,
                    )
                new_owner = human_members[0]
                new_owner_id = str(new_owner.get("playerId", "")).strip()
                meta["ownerPlayerId"] = new_owner_id
                meta["ownerNickname"] = str(new_owner.get("nickname", new_owner_id)).strip()

            if not await self._repository.save_meta(normalized_room_id, meta):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")

            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = self._build_room_response(meta, remaining_members, version)
            await push_room_updated(room_response)
            # waiting 删成员、playing 转 shell 后列表 memberCount 可能变化。
            await push_room_list_updated(game_code)
            if room_status == "playing":
                await self.push_current_game_view_if_playing(
                    normalized_room_id,
                    meta,
                    remaining_members,
                    version,
                )
                await self.create_current_player_managed_task_if_needed(
                    normalized_room_id,
                    "leave",
                )
            return RoomLeaveResponse(
                roomId=normalized_room_id,
                gameCode=game_code,
                dissolved=False,
                room=room_response,
            )

    async def push_current_game_view_if_playing(
        self,
        room_id: str,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        version: int,
    ) -> None:
        """
        对局进行中时推送当前 GameView（同步版本与成员状态，可无新 events）。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 成员列表。
        :param version: bump 后的房间版本号。
        :return: 无。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return
        if str(meta.get("status", "")).strip() != "playing":
            return
        try:
            snapshot = await self._load_runtime_snapshot(normalized_room_id)
        except BizException:
            logger.warning(
                "push_current_game_view_if_playing runtime missing, roomId=%s",
                normalized_room_id,
            )
            return
        room_response = self._build_room_response(meta, members, version)
        player_ids = collect_human_player_ids(room_response.members)
        views = build_views_for_members(
            self._enrich_game_view,
            snapshot,
            version,
            [],
            player_ids,
        )
        await push_game_view_updated(normalized_room_id, views, room_response.members)

    async def start_room_game(self, account: UserAccount, room_id: str) -> GameView:
        """
        在 ``waiting`` 房间中开始策略回合制对局。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 当前玩家的对局视图。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id
        async with await self._acquire_user_room_lock(normalized_room_id, player_id):
            meta = await self._require_meta(normalized_room_id)
            self._require_waiting_room(meta)
            self._require_room_owner(meta, player_id)
            all_members = await self._repository.list_players(normalized_room_id)
            game_code = str(meta.get("gameCode", "")).strip()
            shell_members = [item for item in all_members if self._is_shell_managed(item)]
            if shell_members:
                for shell_member in shell_members:
                    stale_id = str(shell_member.get("playerId", "")).strip()
                    if not stale_id:
                        continue
                    await self._repository.delete_managed_shell_room_index(stale_id, game_code)
                    await self._repository.delete_player(normalized_room_id, stale_id)
                    await self._repository.delete_player_room(stale_id)
                all_members = await self._repository.list_players(normalized_room_id)
            members = [item for item in all_members if self._is_active_room_member(item)]
            self._require_member(members, player_id)

            with self._game_service_scope() as game_service:
                definition = game_service.get_game_rule_definition(game_code)
            min_players = int(definition.roomRule.minPlayers)
            if len(members) < min_players:
                raise BizException(ErrorCode.PARAM_ERROR, message="玩家人数不足，无法开始")

            runtime_rule = self._build_runtime_rule(meta, members, definition)
            start_result = self._runtime_service.start_game(
                StartGameCommand(
                    gameCode=game_code,
                    runtimeRule=runtime_rule,
                    roomId=normalized_room_id,
                )
            )
            snapshot = start_result.snapshot
            await self._save_runtime_snapshot(normalized_room_id, snapshot)

            current_time = now_ms()
            meta["status"] = "playing"
            meta["updatedAt"] = current_time
            if not await self._repository.save_meta(normalized_room_id, meta):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            await self._repository.add_playing_room(normalized_room_id)
            version = await self._bump_version(normalized_room_id)
            await self._repository.refresh_room_ttl(normalized_room_id)
            if version is None:
                version = 0
            frame_events = self._filter_game_view_events(start_result.newEvents)
            starter_view = self._enrich_game_view(
                snapshot,
                player_id,
                version,
                frame_events,
            )
            room_response = self._build_room_response(meta, members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            player_ids = collect_human_player_ids(room_response.members)
            views = build_views_for_members(
                self._enrich_game_view,
                snapshot,
                version,
                frame_events,
                player_ids,
            )
            await push_game_view_updated(normalized_room_id, views, room_response.members)
            await self.create_current_player_managed_task_if_needed(
                normalized_room_id,
                "roomGameStarted",
            )
            return starter_view

    async def view_room_game(self, account: UserAccount, room_id: str) -> GameView:
        """
        查询当前玩家在房间对局中的视图，不推进对局。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 当前玩家的对局视图。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id
        meta = await self._require_meta(normalized_room_id)
        self._require_match_room(meta)
        members = await self._repository.list_players(normalized_room_id)
        target_member = self._find_member(members, player_id)
        if target_member is None:
            raise BizException(ErrorCode.ROOM_NOT_MEMBER)
        if self._is_shell_managed(target_member):
            raise BizException(ErrorCode.ROOM_NOT_MEMBER, message="请先恢复席位")
        snapshot = await self._load_runtime_snapshot(normalized_room_id)
        version = await self._repository.get_version(normalized_room_id)
        if version is None:
            version = 0
        return self._enrich_game_view(snapshot, player_id, version, [])

    async def apply_room_action(
        self,
        account: UserAccount,
        room_id: str,
        request: RoomActionRequest,
    ) -> GameView:
        """
        提交玩家操作并保存更新后的运行时快照。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :param request: 操作请求。
        :return: 当前玩家的对局视图。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id
        async with await self._acquire_user_room_lock(normalized_room_id, player_id):
            meta = await self._require_meta(normalized_room_id)
            self._require_playing_room(meta)
            members = await self._repository.list_players(normalized_room_id)
            target_member = self._find_member(members, player_id)
            if target_member is None:
                raise BizException(ErrorCode.ROOM_NOT_MEMBER)
            if bool(target_member.get("isManaged")):
                raise BizException(ErrorCode.PLAYER_MANAGED, message="当前为托管状态，请先取消托管")
            current_version = await self._repository.get_version(normalized_room_id)
            if current_version is None:
                current_version = 0
            if int(request.baseVersion) != int(current_version):
                raise BizException(ErrorCode.GAME_VIEW_VERSION_CONFLICT)
            action_id = request.actionId.strip()
            if not action_id:
                raise BizException(ErrorCode.PARAM_ERROR, message="actionId 不能为空")
            client_id = None
            if request.clientSeq is not None:
                client_id = str(request.clientSeq)
            return await self._submit_action_locked(
                room_id=normalized_room_id,
                player_id=player_id,
                action_id=action_id,
                client_id=client_id,
            )

    async def submit_managed_action(self, task: ManagedTurnTask) -> ManagedTaskSubmitResult:
        """
        托管任务入口：锁内校验并提交托管动作。

        :param task: 托管任务。
        :return: 托管任务执行结果。
        """
        normalized_room_id = str(task.roomId or "").strip()
        player_id = str(task.playerId or "").strip()
        try:
            lock_handle = await self._acquire_managed_room_lock(normalized_room_id, task.taskId)
        except LockAcquireError:
            return ManagedTaskSubmitResult(status="pending")
        async with lock_handle:
            meta = await self._repository.get_meta(normalized_room_id)
            if meta is None:
                return ManagedTaskSubmitResult(status="skipped", skipReason="roomNotPlaying")
            if str(meta.get("status", "")).strip() != "playing":
                return ManagedTaskSubmitResult(status="skipped", skipReason="roomNotPlaying")
            current_version = await self._repository.get_version(normalized_room_id)
            if current_version is None:
                current_version = 0
            if int(current_version) != int(task.expectedVersion):
                return ManagedTaskSubmitResult(status="skipped", skipReason="versionChanged")
            snapshot = await self._load_runtime_snapshot(normalized_room_id)
            current_player_id = self._extract_current_player_id(snapshot)
            if current_player_id != str(task.expectedCurrentPlayerId or "").strip():
                return ManagedTaskSubmitResult(status="skipped", skipReason="currentPlayerChanged")
            if current_player_id != player_id:
                return ManagedTaskSubmitResult(status="skipped", skipReason="currentPlayerChanged")
            members = await self._repository.list_players(normalized_room_id)
            target_member = self._find_member(members, player_id)
            if target_member is None:
                return ManagedTaskSubmitResult(status="skipped", skipReason="playerNotManaged")
            if (not bool(target_member.get("isManaged"))) and (not bool(target_member.get("isAi"))):
                return ManagedTaskSubmitResult(status="skipped", skipReason="playerNotManaged")
            view = self._runtime_service.build_view(snapshot, player_id)
            legal_actions = list(view.legalActions or [])
            if not legal_actions:
                return ManagedTaskSubmitResult(status="skipped", skipReason="noLegalAction")
            try:
                action_id = self._managed_action_selector.select_action_id(
                    view=view,
                    legal_actions=legal_actions,
                    player_context={"roomId": normalized_room_id, "playerId": player_id},
                )
            except Exception:
                logger.exception(
                    "managed action selector failed, roomId=%s taskId=%s playerId=%s",
                    normalized_room_id,
                    task.taskId,
                    player_id,
                )
                return ManagedTaskSubmitResult(status="failed", skipReason="selectorFailed")
            if not action_id:
                return ManagedTaskSubmitResult(status="skipped", skipReason="selectorFailed")
            try:
                await self._submit_action_locked(
                    room_id=normalized_room_id,
                    player_id=player_id,
                    action_id=action_id,
                    client_id=None,
                )
            except Exception:
                logger.exception(
                    "managed action submit failed, roomId=%s taskId=%s playerId=%s",
                    normalized_room_id,
                    task.taskId,
                    player_id,
                )
                return ManagedTaskSubmitResult(status="failed", skipReason="submitFailed")
            return ManagedTaskSubmitResult(status="done")

    async def create_managed_turn_task(self, room_id: str, player_id: str, reason: str) -> Optional[ManagedTurnTask]:
        """
        创建托管回合任务（后端内部）。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 创建原因。
        :return: 创建的任务，未创建返回 ``None``。
        """
        normalized_room_id = room_id.strip()
        normalized_player_id = player_id.strip()
        meta = await self._repository.get_meta(normalized_room_id)
        if meta is None:
            return None
        if str(meta.get("status", "")).strip() != "playing":
            return None
        snapshot = await self._load_runtime_snapshot(normalized_room_id)
        current_player_id = self._extract_current_player_id(snapshot)
        if current_player_id != normalized_player_id:
            return None
        members = await self._repository.list_players(normalized_room_id)
        target_member = self._find_member(members, normalized_player_id)
        if target_member is None:
            return None
        if (not bool(target_member.get("isManaged"))) and (not bool(target_member.get("isAi"))):
            return None
        current_version = await self._repository.get_version(normalized_room_id)
        if current_version is None:
            current_version = 0
        current_time = now_ms()
        task = ManagedTurnTask(
            taskId=generate_server_id("managed-task"),
            roomId=normalized_room_id,
            gameCode=str(meta.get("gameCode", "")).strip(),
            playerId=normalized_player_id,
            expectedVersion=int(current_version),
            expectedCurrentPlayerId=normalized_player_id,
            executeAfterMs=current_time + MANAGED_TURN_DELAY_MS,
            status="pending",
            createdAt=current_time,
            reason=str(reason or "").strip() or "managedTurn",
            skipReason=None,
            retryCount=0,
        )
        enqueue_result = await self._managed_task_service.enqueue_task(task)
        if enqueue_result.created:
            return task
        if enqueue_result.duplicated:
            logger.debug(
                "create_managed_turn_task dedupe hit, roomId=%s playerId=%s reason=%s",
                normalized_room_id,
                normalized_player_id,
                reason,
            )
            return None
        if enqueue_result.failed:
            logger.warning(
                "create_managed_turn_task enqueue failed, roomId=%s playerId=%s reason=%s",
                normalized_room_id,
                normalized_player_id,
                reason,
            )
        return None

    async def create_current_player_managed_task_if_needed(
        self,
        room_id: str,
        reason: str,
    ) -> None:
        """
        对局进行中且当前行动玩家为托管或 AI 时，按最新房间版本创建托管任务。

        :param room_id: 房间 ID。
        :param reason: 创建原因。
        :return: 无。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_reason = str(reason or "").strip() or "managedTurn"
        if not normalized_room_id:
            return
        meta = await self._repository.get_meta(normalized_room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            return
        try:
            snapshot = await self._load_runtime_snapshot(normalized_room_id)
        except BizException:
            logger.warning(
                "create_current_player_managed_task_if_needed runtime missing, roomId=%s reason=%s",
                normalized_room_id,
                normalized_reason,
            )
            return
        current_player_id = self._extract_current_player_id(snapshot)
        if not current_player_id:
            return
        members = await self._repository.list_players(normalized_room_id)
        target_member = self._find_member(members, current_player_id)
        if target_member is None:
            return
        if (not bool(target_member.get("isManaged"))) and (not bool(target_member.get("isAi"))):
            return
        await self.create_managed_turn_task(
            normalized_room_id,
            current_player_id,
            normalized_reason,
        )

    async def _submit_action_locked(
        self,
        room_id: str,
        player_id: str,
        action_id: str,
        client_id: Optional[str],
    ) -> GameView:
        """
        提交动作核心链路（调用方必须已持有房间动作锁）。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param action_id: 合法动作 ID。
        :param client_id: 客户端操作序号。
        :return: 提交者视角 GameView。
        """
        normalized_room_id = room_id.strip()
        meta = await self._require_meta(normalized_room_id)
        self._require_playing_room(meta)
        members = await self._repository.list_players(normalized_room_id)
        if self._find_member(members, player_id) is None:
            raise BizException(ErrorCode.ROOM_NOT_MEMBER)
        snapshot = await self._load_runtime_snapshot(normalized_room_id)
        action = GameAction(actionId=action_id, playerId=player_id, clientId=client_id)
        apply_result = self._runtime_service.apply_player_action(snapshot, ApplyActionCommand(action=action))
        game_code = str(meta.get("gameCode", "")).strip()
        frame_events = self._filter_game_view_events(apply_result.newEvents)
        final_snapshot = apply_result.snapshot
        if bool(final_snapshot.isGameOver):
            await self._repository.clear_match_runtime(normalized_room_id)
            meta["status"] = "waiting"
            await self._repository.remove_playing_room(normalized_room_id)
            all_members = list(members)
            active_members = [
                member for member in members if not self._is_shell_managed(member)
            ]
            if not self._has_real_human_member(active_members):
                final_version = await self._bump_version(normalized_room_id)
                await self._clear_managed_shell_indexes(game_code, all_members)
                await self._repository.delete_room_cascade(
                    normalized_room_id,
                    game_code,
                    [str(item.get("playerId", "")).strip() for item in all_members],
                )
                await push_room_list_updated(game_code)
                return self._enrich_game_view(
                    final_snapshot,
                    player_id,
                    final_version,
                    frame_events,
                )
            members = active_members
            owner_player_id = str(meta.get("ownerPlayerId", "")).strip()
            owner_member = self._find_member(members, owner_player_id)
            if owner_member is None or not self._is_real_human_member(owner_member):
                human_members = [
                    item for item in self._sort_members_by_joined_at(members)
                    if self._is_real_human_member(item)
                ]
                if human_members:
                    new_owner = human_members[0]
                    meta["ownerPlayerId"] = str(new_owner.get("playerId", "")).strip()
                    meta["ownerNickname"] = str(
                        new_owner.get("nickname", meta["ownerPlayerId"])
                    ).strip()
            for stale_member in await self._repository.list_players(normalized_room_id):
                stale_id = str(stale_member.get("playerId", "")).strip()
                if not stale_id:
                    continue
                if self._find_member(members, stale_id) is None:
                    if self._is_shell_managed(stale_member):
                        await self._repository.delete_managed_shell_room_index(
                            stale_id,
                            game_code,
                        )
                    await self._repository.delete_player(normalized_room_id, stale_id)
                    await self._repository.delete_player_room(stale_id)
        else:
            await self._save_runtime_snapshot(normalized_room_id, final_snapshot)
            meta["status"] = "playing"
        meta["updatedAt"] = now_ms()
        if not await self._repository.save_meta(normalized_room_id, meta):
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
        version = await self._bump_version(normalized_room_id)
        await self._repository.refresh_room_ttl(normalized_room_id)
        actor_view = self._enrich_game_view(final_snapshot, player_id, version, frame_events)
        room_response = self._build_room_response(meta, members, version)
        await push_room_updated(room_response)
        if bool(final_snapshot.isGameOver):
            await push_room_list_updated(game_code)
        player_ids = collect_human_player_ids(room_response.members)
        views = build_views_for_members(
            self._enrich_game_view,
            final_snapshot,
            version,
            frame_events,
            player_ids,
        )
        await push_game_view_updated(normalized_room_id, views, room_response.members)
        if not bool(final_snapshot.isGameOver):
            next_player_id = self._extract_current_player_id(final_snapshot)
            if next_player_id:
                await self.create_managed_turn_task(
                    normalized_room_id,
                    next_player_id,
                    "afterAction",
                )
        return actor_view

    def _filter_game_view_events(self, events: List[GameEvent]) -> List[GameEvent]:
        """
        过滤不应进入 GameView.events 的房间级事件。

        :param events: 原始事件列表。
        :return: 供前端动画播放的事件列表。
        """
        filtered = []
        for event in events or []:
            if str(event.eventType or "").strip() == "gameStarted":
                continue
            filtered.append(event)
        return filtered

    def _enrich_game_view(
        self,
        snapshot: RuntimeSnapshot,
        player_id: str,
        version: int,
        events: List[GameEvent],
    ) -> GameView:
        """
        为房间接口响应补充版本号与待播放事件列表。

        :param snapshot: 运行时快照。
        :param player_id: 视角玩家 ID。
        :param version: 房间版本号。
        :param events: 本帧事件列表。
        :return: 对局视图。
        """
        view = self._runtime_service.build_view(snapshot, player_id)
        room_id = str(snapshot.roomId or "").strip() or None
        return view.model_copy(
            update={
                "roomId": room_id,
                "version": version,
                "events": events,
            },
        )

    async def _rollback_create_room(
        self,
        room_id: str,
        player_id: str,
        game_code: Optional[str] = None,
    ) -> None:
        """
        回滚创建房间已写入的 Redis 数据。

        :param room_id: 房间 ID。
        :param player_id: 房主玩家 ID。
        :param game_code: 游戏编码，用于清理列表索引。
        :return: 无。
        """
        await self._repository.delete_version(room_id)
        await self._repository.delete_player(room_id, player_id)
        await self._repository.delete_meta(room_id)
        await self._repository.delete_player_room(player_id)
        if game_code:
            normalized_code = str(game_code).strip()
            if normalized_code:
                await self._repository.remove_game_room_index(normalized_code, room_id)

    async def _acquire_user_room_lock(self, room_id: str, player_id: str):
        """
        获取用户房间动作锁。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 锁句柄。
        :raises BizException: 锁超时时抛出。
        """
        lock_key = RedisKeys.room_lock(room_id.strip())
        owner_hint = "user:{0}".format(player_id.strip())
        try:
            return await self._lock_service.acquire(
                lock_key,
                ttl_seconds=self.ROOM_ACTION_LOCK_TTL_SECONDS,
                wait_timeout_ms=self.USER_ACTION_LOCK_WAIT_TIMEOUT_MS,
                owner_hint=owner_hint,
            )
        except LockAcquireError:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间操作处理中，请稍后重试")

    async def _acquire_managed_room_lock(self, room_id: str, task_id: str):
        """
        获取托管任务房间动作锁。

        :param room_id: 房间 ID。
        :param task_id: 托管任务 ID。
        :return: 锁句柄。
        :raises LockAcquireError: 锁获取失败。
        """
        lock_key = RedisKeys.room_lock(room_id.strip())
        owner_hint = "managed:{0}".format(task_id.strip())
        return await self._lock_service.acquire(
            lock_key,
            ttl_seconds=self.ROOM_ACTION_LOCK_TTL_SECONDS,
            wait_timeout_ms=self.MANAGED_ACTION_LOCK_WAIT_TIMEOUT_MS,
            owner_hint=owner_hint,
        )

    async def _assert_can_create_room(self, player_id: str) -> None:
        """
        校验玩家当前未处于有效活跃房间。

        :param player_id: 玩家 ID。
        :return: 无。
        """
        indexed_room_id = await self._repository.get_player_room(player_id)
        if not indexed_room_id:
            return
        meta = await self._repository.get_meta(indexed_room_id)
        if meta is None:
            await self._repository.delete_player_room(player_id)
            return
        members = await self._repository.list_players(indexed_room_id)
        member = self._find_member(members, player_id)
        if member is None or self._is_shell_managed(member):
            await self._repository.delete_player_room(player_id)
            return
        raise BizException(ErrorCode.PLAYER_ALREADY_IN_ROOM)

    async def _require_meta(self, room_id: str) -> Dict[str, Any]:
        """
        读取房间元信息，不存在时抛业务异常。

        :param room_id: 房间 ID。
        :return: 房间元信息。
        """
        meta = await self._repository.get_meta(room_id.strip())
        if meta is None:
            raise BizException(ErrorCode.ROOM_NOT_FOUND)
        return meta

    def _require_waiting_room(self, meta: Dict[str, Any]) -> None:
        """
        校验房间尚未开始。

        :param meta: 房间元信息。
        :return: 无。
        :raises BizException: 房间已开始。
        """
        if meta.get("status") != "waiting":
            raise BizException(ErrorCode.ROOM_ALREADY_STARTED)

    def _require_playing_room(self, meta: Dict[str, Any]) -> None:
        """
        校验房间对局已开始。

        :param meta: 房间元信息。
        :return: 无。
        :raises BizException: 对局尚未开始。
        """
        if meta.get("status") != "playing":
            raise BizException(ErrorCode.PARAM_ERROR, message="对局尚未开始")

    def _require_match_room(self, meta: Dict[str, Any]) -> None:
        """
        校验房间处于对局中。

        :param meta: 房间元信息。
        :return: 无。
        :raises BizException: 对局尚未开始。
        """
        status = str(meta.get("status", "")).strip()
        if status != "playing":
            raise BizException(ErrorCode.PARAM_ERROR, message="对局尚未开始")

    def _require_room_owner(self, meta: Dict[str, Any], player_id: str) -> None:
        """
        校验当前用户为房主。

        :param meta: 房间元信息。
        :param player_id: 玩家 ID。
        :return: 无。
        :raises BizException: 非房主时抛出。
        """
        owner_player_id = str(meta.get("ownerPlayerId", "")).strip()
        if owner_player_id != player_id:
            raise BizException(ErrorCode.PARAM_ERROR, message="仅房主可执行该操作")

    def _require_member(
        self,
        members: List[Dict[str, Any]],
        player_id: str,
    ) -> None:
        """
        校验玩家为房间成员。

        :param members: 成员列表。
        :param player_id: 玩家 ID。
        :return: 无。
        :raises BizException: 不在房间中时抛出。
        """
        if self._find_member(members, player_id) is None:
            raise BizException(ErrorCode.ROOM_NOT_MEMBER)

    def _build_runtime_rule(
        self,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        definition: OnlineGameRuleSeed,
    ) -> StrategyTurnRuntimeRule:
        """
        根据房间元信息与成员构造运行时规则。

        :param meta: 房间元信息。
        :param members: 成员列表。
        :param definition: 在线游戏规则种子。
        :return: 运行时规则。
        """
        game_code = str(meta.get("gameCode", "")).strip()
        mode = str(meta.get("mode", "")).strip()
        sorted_members = sorted(members, key=lambda item: int(item.get("joinedAt", 0)))
        player_ids = []
        for member in sorted_members:
            member_id = str(member.get("playerId", "")).strip()
            if member_id:
                player_ids.append(member_id)
        room_config = meta.get("roomConfig")
        if not isinstance(room_config, dict):
            room_config = resolve_room_config_defaults(definition)
        else:
            room_config = dict(room_config)
        ai_player_ids = []
        for member in sorted_members:
            if bool(member.get("isAi")):
                member_id = str(member.get("playerId", "")).strip()
                if member_id:
                    ai_player_ids.append(member_id)
        room_config["aiPlayerIds"] = ai_player_ids
        return StrategyTurnRuntimeRule(
            gameCode=game_code,
            mode=mode,
            playerIds=player_ids,
            config=room_config,
        )

    async def _load_runtime_snapshot(self, room_id: str) -> RuntimeSnapshot:
        """
        从 Redis 加载策略回合制运行时快照。

        :param room_id: 房间 ID。
        :return: 运行时快照。
        :raises BizException: 快照不存在或数据无效。
        """
        runtime_data = await self._repository.get_runtime(room_id)
        if runtime_data is None:
            raise BizException(ErrorCode.PARAM_ERROR, message="对局尚未开始")
        events_raw = await self._repository.get_events(room_id)
        if events_raw is None:
            event_items = []
        elif isinstance(events_raw, list):
            event_items = events_raw
        else:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间事件数据无效")
        event_log = []
        for item in event_items:
            if isinstance(item, dict):
                event_log.append(GameEvent.model_validate(item))
        try:
            return RuntimeSnapshot(
                gameCode=str(runtime_data.get("gameCode", "")).strip(),
                roomId=runtime_data.get("roomId"),
                runtimeRule=StrategyTurnRuntimeRule.model_validate(runtime_data.get("runtimeRule")),
                state=runtime_data.get("runtimeState", {}),
                eventLog=event_log,
                eventSequence=int(runtime_data.get("eventSequence", 0)),
                startedAt=int(runtime_data.get("startedAt", 0)),
                updatedAt=int(runtime_data.get("updatedAt", 0)),
                isGameOver=bool(runtime_data.get("isGameOver", False)),
            )
        except (TypeError, ValueError) as exc:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间运行时数据无效") from exc

    async def _save_runtime_snapshot(self, room_id: str, snapshot: RuntimeSnapshot) -> None:
        """
        将运行时快照拆分写入 Redis。

        :param room_id: 房间 ID。
        :param snapshot: 运行时快照。
        :return: 无。
        :raises BizException: 写入失败时抛出。
        """
        runtime_data = {
            "gameCode": snapshot.gameCode,
            "roomId": snapshot.roomId,
            "runtimeRule": snapshot.runtimeRule.model_dump(),
            "runtimeState": snapshot.state,
            "eventSequence": snapshot.eventSequence,
            "startedAt": snapshot.startedAt,
            "updatedAt": snapshot.updatedAt,
            "isGameOver": snapshot.isGameOver,
        }
        if not await self._repository.save_runtime(room_id, runtime_data):
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间运行时写入失败")
        events = [event.model_dump() for event in snapshot.eventLog]
        if not await self._repository.save_events(room_id, events):
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间事件写入失败")

        public_state_saved = False
        for player_id in snapshot.runtimeRule.playerIds:
            view = self._runtime_service.build_view(snapshot, player_id)
            if not public_state_saved:
                if not await self._repository.save_public_state(room_id, view.publicState):
                    raise BizException(ErrorCode.SYSTEM_ERROR, message="房间公开状态写入失败")
                public_state_saved = True
            if not await self._repository.save_private_state(room_id, player_id, view.privateState):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间私有状态写入失败")
            legal_actions = [action.model_dump() for action in view.legalActions]
            if not await self._repository.save_legal_actions(room_id, player_id, legal_actions):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间合法动作写入失败")

    async def _bump_version(self, room_id: str) -> int:
        """
        将房间版本号递增并写回 Redis。

        :param room_id: 房间 ID。
        :return: 递增后的版本号。
        """
        version = await self._repository.get_version(room_id)
        if version is None:
            version = 0
        next_version = version + 1
        if not await self._repository.save_version(room_id, next_version):
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间版本更新失败")
        return next_version

    def _resolve_effective_room_limits(
        self,
        meta: Dict[str, Any],
        room_rule: Any,
    ) -> tuple:
        """
        解析房间有效人数与 AI 限制（优先使用 meta 覆盖项）。

        :param meta: 房间元信息。
        :param room_rule: 玩法房间规则。
        :return: ``(maxPlayers, allowAi, maxAiCount)`` 元组。
        """
        max_players = int(meta.get("maxPlayers", room_rule.maxPlayers))
        if "allowAi" in meta:
            allow_ai = bool(meta.get("allowAi"))
        else:
            allow_ai = bool(room_rule.allowAi)
        if "maxAiCount" in meta:
            max_ai_count = int(meta.get("maxAiCount"))
        else:
            max_ai_count = int(room_rule.maxAiCount)
        return max_players, allow_ai, max_ai_count

    async def _remove_waiting_members(
        self,
        room_id: str,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        target_player_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """
        在等待中的房间内批量移除成员并同步 AI 元信息。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 当前成员列表。
        :param target_player_ids: 待移除玩家 ID 列表。
        :return: 更新后的成员列表。
        """
        normalized_ids = []
        seen = set()
        for player_id in target_player_ids:
            normalized = str(player_id or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            normalized_ids.append(normalized)
        if not normalized_ids:
            return members
        remaining_members = list(members)
        for target_player_id in normalized_ids:
            target_member = self._find_member(remaining_members, target_player_id)
            if target_member is None or self._is_shell_managed(target_member):
                continue
            if not bool(target_member.get("isAi")):
                await self._repository.delete_player_room(target_player_id)
            if not await self._repository.delete_player(room_id, target_player_id):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员删除失败")
            remaining_members = [
                item
                for item in remaining_members
                if str(item.get("playerId", "")).strip() != target_player_id
            ]
        self._sync_meta_ai_context(meta, remaining_members)
        return remaining_members

    async def _append_ai_players(
        self,
        room_id: str,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        count: int,
        expire_seconds: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        向房间追加指定数量的 AI 成员。

        :param room_id: 房间 ID。
        :param meta: 房间元信息（就地更新 aiCount 与 roomConfig）。
        :param members: 当前成员列表。
        :param count: 追加数量。
        :param expire_seconds: Redis TTL（秒）；未传时仅刷新已有 TTL。
        :return: 更新后的成员列表。
        """
        if count <= 0:
            return members
        original_ai_count = meta.get("aiCount")
        original_updated_at = meta.get("updatedAt")
        room_config = meta.get("roomConfig")
        if isinstance(room_config, dict):
            original_room_config = dict(room_config)
            original_ai_player_ids = list(room_config.get("aiPlayerIds") or [])
        else:
            original_room_config = {}
            original_ai_player_ids = []
        updated_members = list(members)
        added_ai_player_ids = []
        current_time = now_ms()
        try:
            for _ in range(count):
                ai_index = self._count_ai_members(updated_members) + 1
                ai_player_id = generate_server_id("ai")
                ai_member = self._build_ai_member(ai_player_id, ai_index, current_time)
                if expire_seconds is not None:
                    saved = await self._repository.save_player(
                        room_id,
                        ai_player_id,
                        ai_member,
                        expire_seconds,
                    )
                else:
                    saved = await self._repository.save_player(room_id, ai_player_id, ai_member)
                if not saved:
                    raise BizException(ErrorCode.SYSTEM_ERROR, message="AI 成员写入失败")
                added_ai_player_ids.append(ai_player_id)
                updated_members.append(ai_member)
            self._sync_meta_ai_context(meta, updated_members)
            meta["updatedAt"] = current_time
            if expire_seconds is not None:
                saved_meta = await self._repository.save_meta(room_id, meta, expire_seconds)
            else:
                saved_meta = await self._repository.save_meta(room_id, meta)
            if not saved_meta:
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息更新失败")
            return updated_members
        except Exception:
            for ai_player_id in added_ai_player_ids:
                await self._repository.delete_player(room_id, ai_player_id)
            restored_room_config = dict(original_room_config)
            restored_room_config["aiPlayerIds"] = list(original_ai_player_ids)
            meta["roomConfig"] = restored_room_config
            meta["aiCount"] = original_ai_count
            meta["updatedAt"] = original_updated_at
            if expire_seconds is not None:
                await self._repository.save_meta(room_id, meta, expire_seconds)
            else:
                await self._repository.save_meta(room_id, meta)
            raise

    def _count_ai_members(self, members: List[Dict[str, Any]]) -> int:
        """
        统计成员列表中的 AI 数量。

        :param members: 成员列表。
        :return: AI 成员数量。
        """
        total = 0
        for member in members:
            if bool(member.get("isAi")):
                total += 1
        return total

    def _sync_meta_ai_context(
        self,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
    ) -> None:
        """
        根据成员列表同步房间元信息中的 AI 计数与 aiPlayerIds。

        :param meta: 房间元信息。
        :param members: 成员列表。
        :return: 无。
        """
        ai_player_ids = []
        for member in members:
            if not bool(member.get("isAi")):
                continue
            member_id = str(member.get("playerId", "")).strip()
            if member_id:
                ai_player_ids.append(member_id)
        room_config = meta.get("roomConfig")
        if not isinstance(room_config, dict):
            room_config = {}
        else:
            room_config = dict(room_config)
        room_config["aiPlayerIds"] = ai_player_ids
        meta["roomConfig"] = room_config
        meta["aiCount"] = len(ai_player_ids)

    def _build_ai_member(
        self,
        player_id: str,
        ai_index: int,
        joined_at: int,
    ) -> Dict[str, Any]:
        """
        构造 AI 房间成员对象。

        :param player_id: AI 玩家 ID。
        :param ai_index: AI 序号（从 1 起）。
        :param joined_at: 加入时间（毫秒）。
        :return: 成员字典。
        """
        return {
            "playerId": player_id,
            "nickname": "AI {0}".format(ai_index),
            "avatar": None,
            "joinedAt": joined_at,
            "isAi": True,
            "isManaged": True,
            "managedMode": "active",
            "managedReason": "ai",
            "managedAt": joined_at,
            "onlineState": "ai",
        }

    def _build_member(
        self,
        player_id: str,
        account: Optional[UserAccount],
        joined_at: int,
    ) -> Dict[str, Any]:
        """
        构造房间成员对象。

        :param player_id: 玩家 ID。
        :param account: 用户账号，可为空。
        :param joined_at: 加入时间（毫秒）。
        :return: 成员字典。
        """
        if account is not None:
            nickname = account.nickname
            avatar = account.avatar
        else:
            nickname = player_id
            avatar = None
        return {
            "playerId": player_id,
            "nickname": nickname,
            "avatar": avatar,
            "joinedAt": joined_at,
            "isAi": False,
            "isManaged": False,
            "managedMode": None,
            "managedReason": None,
            "managedAt": None,
        }

    def _is_shell_managed(self, member: Dict[str, Any]) -> bool:
        """
        判断成员是否处于空壳托管状态。

        :param member: 成员对象。
        :return: 是否为空壳托管。
        """
        if not bool(member.get("isManaged")):
            return False
        return str(member.get("managedMode", "")).strip() == "shell"

    def _is_active_room_member(self, member: Dict[str, Any]) -> bool:
        """
        判断成员是否为活跃占位成员（非 shell，含真人与 AI）。

        :param member: 成员对象。
        :return: 是否为活跃成员。
        """
        return not self._is_shell_managed(member)

    def _is_real_human_member(self, member: Dict[str, Any]) -> bool:
        """
        判断成员是否为真人真实成员（非 shell、非 AI）。

        :param member: 成员对象。
        :return: 是否为真人真实成员。
        """
        if self._is_shell_managed(member):
            return False
        return not bool(member.get("isAi"))

    def _has_real_human_member(self, members: List[Dict[str, Any]]) -> bool:
        """
        判断成员列表中是否仍有真人真实成员。

        :param members: 成员列表。
        :return: 是否存在真人真实成员。
        """
        for member in members:
            if self._is_real_human_member(member):
                return True
        return False

    async def _clear_managed_shell_indexes(
        self,
        game_code: str,
        members: List[Dict[str, Any]],
    ) -> None:
        """
        清理成员列表中 shell 玩家对应的托管空壳索引。

        :param game_code: 游戏编码。
        :param members: 成员列表。
        :return: 无。
        """
        normalized_code = str(game_code or "").strip()
        if not normalized_code:
            return
        for member in members:
            if not self._is_shell_managed(member):
                continue
            player_id = str(member.get("playerId", "")).strip()
            if not player_id:
                continue
            await self._repository.delete_managed_shell_room_index(player_id, normalized_code)

    def _sort_members_by_joined_at(
        self,
        members: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        按加入时间升序排列成员列表。

        :param members: 成员列表。
        :return: 排序后的新列表。
        """
        return sorted(members, key=lambda item: int(item.get("joinedAt", 0)))

    def _find_member(
        self,
        members: List[Dict[str, Any]],
        player_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        在成员列表中查找指定玩家。

        :param members: 成员列表。
        :param player_id: 玩家 ID。
        :return: 成员对象；未找到时返回 ``None``。
        """
        for member in members:
            if member.get("playerId") == player_id:
                return member
        return None

    def _extract_current_player_id(self, snapshot: RuntimeSnapshot) -> str:
        """
        从运行时快照解析当前行动玩家 ID。

        :param snapshot: 运行时快照。
        :return: 当前行动玩家 ID；不存在时返回空字符串。
        """
        state = snapshot.state if isinstance(snapshot.state, dict) else {}
        return str(state.get("currentPlayerId", "")).strip()

    def _merge_room_config(
        self,
        definition: OnlineGameRuleSeed,
        request_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        将请求中的房间配置与规则种子默认值合并。

        :param definition: 在线游戏规则种子。
        :param request_config: 请求覆盖项。
        :return: 合并后的房间配置。
        """
        merged = resolve_room_config_defaults(definition)
        if not isinstance(request_config, dict):
            return merged
        schema_keys = {field.key for field in definition.roomConfigSchema}
        for key, value in request_config.items():
            if key not in schema_keys:
                continue
            merged[key] = value
        return merged

    def _build_room_list_item(
        self,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
    ) -> RoomListItemResponse:
        """
        组装房间列表项。

        :param meta: 房间元信息。
        :param members: 成员列表。
        :return: 列表项响应。
        """
        owner_player_id = str(meta.get("ownerPlayerId", ""))
        owner_nickname = str(meta.get("ownerNickname", "")).strip()
        if not owner_nickname:
            owner_member = self._find_member(members, owner_player_id)
            if owner_member is not None:
                owner_nickname = str(owner_member.get("nickname", owner_player_id))
            else:
                owner_nickname = owner_player_id
        room_name = str(meta.get("roomName", "")).strip()
        if not room_name:
            room_name = "房间-{0}".format(str(meta.get("roomId", ""))[-6:])
        real_member_count = 0
        for member in members:
            if self._is_active_room_member(member):
                real_member_count += 1
        data = {
            "roomId": meta.get("roomId", ""),
            "roomName": room_name,
            "ownerPlayerId": owner_player_id,
            "ownerNickname": owner_nickname,
            "memberCount": real_member_count,
            "maxPlayers": int(meta.get("maxPlayers", 0)),
            "aiCount": int(meta.get("aiCount", 0)),
            "status": meta.get("status", "waiting"),
            "gameCode": meta.get("gameCode", ""),
            "mode": meta.get("mode", ""),
        }
        return RoomListItemResponse.model_validate(data)

    def _build_room_response(
        self,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        version: int,
    ) -> RoomResponse:
        """
        组装房间详情响应。

        :param meta: 房间元信息。
        :param members: 成员列表。
        :param version: 房间版本号。
        :return: 房间详情响应。
        """
        return build_room_response(meta, members, version)
