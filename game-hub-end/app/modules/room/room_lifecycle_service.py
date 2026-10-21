"""房间生命周期编排：创建、查询、加入、配置与开局。"""

import logging
from typing import List, Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.id_utils import generate_server_id
from app.core.lock.distributed_lock import RedisDistributedLock
from app.core.time_utils import now_ms
from app.modules.game_config.module_service import GameModuleService
from app.modules.room.game_presentation_service import GamePresentationService
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.mapper import build_room_response
from app.modules.room.realtime_service import (
    build_views_for_members,
    collect_human_player_ids,
    push_game_view_updated,
    push_room_list_updated,
    push_room_updated,
)
from app.modules.room.repository import RoomRepository
from app.modules.room.room_game_commit_service import RoomGameCommitService
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
    assert_can_create_room,
    build_member,
    build_room_list_item,
    build_runtime_rule,
    commit_room_meta_version,
    game_service_scope,
    is_active_room_member,
    merge_room_config,
    remove_waiting_members,
    require_member,
    require_meta,
    require_room_owner,
    require_waiting_room,
    resolve_effective_room_limits,
)
from app.modules.room.schemas import (
    CreateRoomRequest,
    MyActiveRoomResponse,
    RoomListItemResponse,
    RoomResponse,
    UpdateRoomConfigRequest,
)
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService
from app.modules.strategy_turn.schemas import GameView, StartGameCommand
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.models import UserAccount

logger = logging.getLogger(__name__)


class RoomLifecycleService(object):
    """房间创建、列表、加入、配置与开局服务。"""

    def __init__(
        self,
        repository: RoomRepository,
        lock_service: RedisDistributedLock,
        game_service: Optional[GameModuleService],
        runtime_service: StrategyTurnRuntimeService,
        account_service: Optional[UserAccountEntityService],
        state_reader: GameStateReader,
        commit_service: RoomGameCommitService,
        room_mutation_commit_service: RoomMutationCommitService,
        presentation_service: GamePresentationService,
    ) -> None:
        """
        初始化房间生命周期服务。

        :param repository: 房间 Redis 仓库。
        :param lock_service: 分布式锁服务。
        :param game_service: 游戏模块服务；后台可为 ``None``。
        :param runtime_service: 策略回合制运行时服务。
        :param account_service: 用户账号实体服务；后台可为 ``None``。
        :param state_reader: 运行时读取端口。
        :param commit_service: 对局原子提交服务。
        :param room_mutation_commit_service: 房间变更提交服务。
        :param presentation_service: 对局展示服务。
        """
        self._repository = repository
        self._lock_service = lock_service
        self._game_service = game_service
        self._runtime_service = runtime_service
        self._account_service = account_service
        self._state_reader = state_reader
        self._commit_service = commit_service
        self._room_mutation_commit_service = room_mutation_commit_service
        self._presentation_service = presentation_service

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
        await assert_can_create_room(self._repository, owner_player_id)

        with game_service_scope(self._game_service) as resolved_game_service:
            definition = resolved_game_service.get_game_rule_definition(game_code)
        room_rule = definition.roomRule
        expire_seconds = request.expireSeconds
        if expire_seconds is None:
            expire_seconds = int(room_rule.defaultExpireSeconds)
        if expire_seconds <= 0:
            raise BizException(ErrorCode.PARAM_ERROR, message="expireSeconds 必须大于 0")

        room_config = merge_room_config(definition, request.roomConfig)
        ai_count = 0
        max_players = int(room_rule.maxPlayers)
        current_time = now_ms()
        room_id = generate_server_id("room")
        member = build_member(owner_player_id, account, current_time)
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

        await self._room_mutation_commit_service.commit(
            room_id=room_id,
            expected_room_version=-1,
            next_meta=meta,
            member_upserts=[member],
            ttl_seconds=expire_seconds,
            claim_player_id=owner_player_id,
        )

        members = [member]
        room_response = build_room_response(meta, members, 1)
        try:
            await push_room_list_updated(game_code)
        except Exception:
            logger.exception("create room list push failed, roomId=%s", room_id)
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
        with game_service_scope(self._game_service) as resolved_game_service:
            resolved_game_service.get_game_rule_definition(normalized_code)
        room_ids = await self._repository.list_game_room_ids(normalized_code)
        items = []
        for room_id in room_ids:
            async with await acquire_user_room_lock(self._lock_service, room_id, "room-list"):
                meta = await self._repository.get_meta(room_id)
                if meta is None:
                    await self._repository.remove_game_room_index(normalized_code, room_id)
                    await self._repository.remove_playing_room(room_id)
                    continue
                if str(meta.get("gameCode", "")).strip() != normalized_code:
                    await self._repository.remove_game_room_index(normalized_code, room_id)
                    continue
                members = await self._repository.list_players(room_id)
                version = int(await self._repository.get_room_version(room_id) or 0)
                room_status = str(meta.get("status", "")).strip()
                if room_status == "waiting":
                    cleaned_waiting_members = []
                    stale_player_ids = []
                    for member in members:
                        if is_shell_managed(member):
                            stale_player_id = str(member.get("playerId", "")).strip()
                            if stale_player_id:
                                stale_player_ids.append(stale_player_id)
                            continue
                        cleaned_waiting_members.append(member)
                    members_changed = len(cleaned_waiting_members) != len(members)
                    if members_changed:
                        members = cleaned_waiting_members
                        meta["updatedAt"] = now_ms()
                        current_version = int(
                            await self._repository.get_room_version(room_id) or 0
                        )
                        result = await self._room_mutation_commit_service.commit(
                            room_id,
                            current_version,
                            meta,
                            member_deletes=stale_player_ids,
                        )
                        version = int(result.committedRoomVersion or 0)
                    if not has_real_human_member(members):
                        await self._room_mutation_commit_service.commit(
                            room_id,
                            int(version),
                            meta,
                            delete_room=True,
                        )
                        await self._repository.remove_game_room_index(normalized_code, room_id)
                        await push_room_list_updated(normalized_code)
                        continue
                    if members_changed:
                        room_response = build_room_response(meta, members, version)
                        await push_room_updated(room_response)
                if not members:
                    current_version = int(await self._repository.get_room_version(room_id) or 0)
                    await self._room_mutation_commit_service.commit(
                        room_id,
                        current_version,
                        meta,
                        delete_room=True,
                    )
                    await self._repository.remove_game_room_index(normalized_code, room_id)
                    continue
                items.append(
                    (
                        int(meta.get("createdAt", 0)),
                        build_room_list_item(meta, members),
                    )
                )
        items.sort(key=lambda pair: pair[0], reverse=True)
        return [pair[1] for pair in items]

    async def get_room(self, room_id: str) -> RoomResponse:
        """
        查询房间详情。

        :param room_id: 房间 ID。
        :return: 房间详情。
        """
        meta = await require_meta(self._repository, room_id)
        members = await self._repository.list_players(room_id)
        version = await self._repository.get_room_version(room_id)
        if version is None:
            version = 0
        return build_room_response(meta, members, version)

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

        membership = await self._repository.get_active_membership(player_id)
        if membership is None:
            return MyActiveRoomResponse(room=None)
        return MyActiveRoomResponse(
            room=build_room_response(
                membership["meta"], membership["members"], membership["roomVersion"],
            ),
        )

    async def join_room(self, account: UserAccount, room_id: str) -> RoomResponse:
        """
        加入房间。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 更新后的房间详情。
        """
        player_id = account.server_id
        async with await acquire_user_room_lock(
            self._lock_service,
            room_id,
            player_id,
        ):
            meta = await require_meta(self._repository, room_id)
            game_code = str(meta.get("gameCode", "")).strip()
            with game_service_scope(self._game_service) as resolved_game_service:
                resolved_game_service.get_game_rule_definition(game_code)
            members = await self._repository.list_players(room_id)
            existing = find_member(members, player_id)
            require_waiting_room(meta)
            membership = await self._repository.get_active_membership(player_id)
            if membership is not None and membership["meta"]["roomId"] != room_id:
                raise BizException(ErrorCode.PLAYER_ALREADY_IN_ROOM)
            if existing is not None and membership is not None:
                await self._repository.refresh_room_ttl(room_id)
                version = await self._repository.get_room_version(room_id)
                if version is None:
                    version = 0
                return build_room_response(meta, members, version)
            max_players = int(meta.get("maxPlayers", 0))
            active_members = [item for item in members if is_active_room_member(item)]
            if existing is None and len(active_members) >= max_players:
                raise BizException(ErrorCode.ROOM_FULL)
            current_time = now_ms()
            member = existing if existing is not None and not is_shell_managed(existing) else build_member(
                player_id, account, current_time,
            )
            meta["updatedAt"] = current_time
            current_version = int(await self._repository.get_room_version(room_id) or 0)
            result = await self._room_mutation_commit_service.commit(
                room_id,
                current_version,
                meta,
                member_upserts=[member],
                claim_player_id=player_id,
            )
            members = [item for item in members if item.get("playerId") != player_id] + [member]
            version = int(result.committedRoomVersion or 0)
            try:
                await self._repository.refresh_room_ttl(room_id)
            except Exception:
                logger.exception(
                    "join room derived index update failed, roomId=%s playerId=%s",
                    room_id,
                    player_id,
                )
            room_response = build_room_response(meta, members, version)
            try:
                await push_room_updated(room_response)
                await push_room_list_updated(game_code)
            except Exception:
                logger.exception("join room push failed, roomId=%s", room_id)
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
        async with await acquire_user_room_lock(
            self._lock_service,
            normalized_room_id,
            owner_player_id,
        ):
            meta = await require_meta(self._repository, normalized_room_id)
            require_waiting_room(meta)
            require_room_owner(meta, owner_player_id)
            game_code = str(meta.get("gameCode", "")).strip()
            with game_service_scope(self._game_service) as resolved_game_service:
                definition = resolved_game_service.get_game_rule_definition(game_code)
            room_rule = definition.roomRule
            members = await self._repository.list_players(normalized_room_id)
            active_members = [item for item in members if is_active_room_member(item)]
            human_count = sum(1 for item in active_members if is_real_human_member(item))

            if request.roomConfig is not None:
                merged_config = merge_room_config(definition, request.roomConfig)
                existing_config = meta.get("roomConfig")
                if isinstance(existing_config, dict):
                    next_config = dict(existing_config)
                    next_config.update(merged_config)
                else:
                    next_config = merged_config
                meta["roomConfig"] = next_config

            next_max_players, _, _ = resolve_effective_room_limits(meta, room_rule)
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
                ai_members = sort_members_by_joined_at(
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

            current_time = now_ms()
            meta["updatedAt"] = current_time
            remaining_members = members
            if remove_player_ids:
                remaining_members = await remove_waiting_members(
                    self._repository,
                    self._room_mutation_commit_service,
                    normalized_room_id,
                    meta,
                    members,
                    remove_player_ids,
                )
                version = int(await self._repository.get_room_version(normalized_room_id) or 0)
            else:
                version = await commit_room_meta_version(
                    self._repository,
                    self._room_mutation_commit_service,
                    normalized_room_id,
                    meta,
                )
            await self._repository.refresh_room_ttl(normalized_room_id)
            room_response = build_room_response(meta, remaining_members, version)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
            return room_response

    async def start_room_game(self, account: UserAccount, room_id: str) -> GameView:
        """
        在 ``waiting`` 房间中开始策略回合制对局。

        :param account: 当前用户账号。
        :param room_id: 房间 ID。
        :return: 当前玩家的对局视图。
        """
        normalized_room_id = room_id.strip()
        player_id = account.server_id
        async with await acquire_user_room_lock(
            self._lock_service,
            normalized_room_id,
            player_id,
        ):
            meta = await require_meta(self._repository, normalized_room_id)
            require_waiting_room(meta)
            require_room_owner(meta, player_id)
            all_members = await self._repository.list_players(normalized_room_id)
            game_code = str(meta.get("gameCode", "")).strip()
            shell_members = [item for item in all_members if is_shell_managed(item)]
            shell_member_ids = [
                str(item.get("playerId", "")).strip()
                for item in shell_members
                if str(item.get("playerId", "")).strip()
            ]
            members = [item for item in all_members if is_active_room_member(item)]
            require_member(members, player_id)

            reset_managed_time = now_ms()
            for member in members:
                if bool(member.get("isAi")):
                    continue
                managed_changed = False
                if bool(member.get("isManaged")):
                    member["isManaged"] = False
                    managed_changed = True
                if member.get("managedMode") is not None:
                    member["managedMode"] = None
                    managed_changed = True
                if member.get("managedReason") is not None:
                    member["managedReason"] = None
                    managed_changed = True
                if member.get("managedAt") is not None:
                    member["managedAt"] = None
                    managed_changed = True
                if managed_changed:
                    member["updatedAt"] = reset_managed_time

            with game_service_scope(self._game_service) as resolved_game_service:
                definition = resolved_game_service.get_game_rule_definition(game_code)
            min_players = int(definition.roomRule.minPlayers)
            if len(members) < min_players:
                raise BizException(ErrorCode.PARAM_ERROR, message="玩家人数不足，无法开始")

            runtime_rule = build_runtime_rule(meta, members, definition)
            start_result = self._runtime_service.start_game(
                StartGameCommand(
                    gameCode=game_code,
                    runtimeRule=runtime_rule,
                    roomId=normalized_room_id,
                )
            )
            snapshot = start_result.snapshot
            current_version = await self._repository.get_game_version(normalized_room_id)
            if current_version is None:
                current_version = 0
            current_room_version = await self._repository.get_room_version(normalized_room_id)
            if current_room_version is None:
                current_room_version = 0
            current_time = now_ms()
            meta["status"] = "playing"
            meta["updatedAt"] = current_time
            commit_result = await self._commit_service.commit_state_change(
                room_id=normalized_room_id,
                expected_version=int(current_version),
                next_snapshot=snapshot,
                next_room_meta=meta,
                outbox_reason="roomGameStarted",
                committed_at=current_time,
                expected_room_version=int(current_room_version),
                next_room_version=int(current_room_version) + 1,
                member_upserts={
                    str(member.get("playerId", "")).strip(): member
                    for member in members
                    if str(member.get("playerId", "")).strip()
                },
                member_deletes=shell_member_ids,
            )
            game_version = int(commit_result.committedVersion or (int(current_version) + 1))
            room_version = int(current_room_version) + 1
            stamped_snapshot = snapshot.model_copy(update={"commitVersion": game_version})
            try:
                await self._repository.add_playing_room(normalized_room_id)
                await self._repository.refresh_room_ttl(normalized_room_id)
            except Exception:
                logger.exception(
                    "start game derived index update failed, roomId=%s",
                    normalized_room_id,
                )
            frame_events = self._presentation_service.filter_game_view_events(start_result.newEvents)
            starter_view = self._presentation_service.enrich_game_view(
                stamped_snapshot,
                player_id,
                game_version,
                frame_events,
            )
            room_response = build_room_response(meta, members, room_version)
            try:
                await push_room_updated(room_response)
                await push_room_list_updated(game_code)
                player_ids = collect_human_player_ids(room_response.members)
                views = build_views_for_members(
                    self._presentation_service.enrich_game_view,
                    stamped_snapshot,
                    game_version,
                    frame_events,
                    player_ids,
                )
                await push_game_view_updated(normalized_room_id, views, room_response.members)
            except Exception:
                logger.exception(
                    "start game presentation failed after commit, roomId=%s",
                    normalized_room_id,
                )
            return starter_view
