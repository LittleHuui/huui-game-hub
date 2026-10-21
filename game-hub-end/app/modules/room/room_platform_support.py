"""房间平台层共享工具：锁、校验、成员与配置辅助。"""

from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.database import session_scope
from app.core.id_utils import generate_server_id
from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock
from app.core.redis.redis_keys import RedisKeys
from app.core.time_utils import now_ms
from app.modules.game_config.deps import build_game_module_service
from app.modules.game_config.module_service import GameModuleService
from app.modules.game_seed.schemas import OnlineGameRuleSeed, resolve_room_config_defaults
from app.modules.room.repository import RoomRepository
from app.modules.room.room_member_support import (
    find_member,
    has_real_human_member,
    is_shell_managed,
)
from app.modules.room.room_mutation_commit_service import RoomMutationCommitService
from app.modules.room.schemas import RoomListItemResponse
from app.modules.strategy_turn.schemas import RuntimeSnapshot, StrategyTurnRuntimeRule
from app.modules.user.models import UserAccount

ROOM_ACTION_LOCK_TTL_SECONDS = 8
USER_ACTION_LOCK_WAIT_TIMEOUT_MS = 1200
MANAGED_ACTION_LOCK_WAIT_TIMEOUT_MS = 0

SHELL_MANAGED_REASONS = frozenset({"presenceTimeout", "leave"})
ACTIVE_MANAGED_REASONS = frozenset({"manual", "turnTimeout"})


async def acquire_user_room_lock(
    lock_service: RedisDistributedLock,
    room_id: str,
    player_id: str,
):
    """
    获取用户房间动作锁。

    :param lock_service: 分布式锁服务。
    :param room_id: 房间 ID。
    :param player_id: 玩家 ID。
    :return: 锁句柄。
    :raises BizException: 锁超时时抛出。
    """
    lock_key = RedisKeys.room_lock(room_id.strip())
    owner_hint = "user:{0}".format(player_id.strip())
    try:
        return await lock_service.acquire(
            lock_key,
            ttl_seconds=ROOM_ACTION_LOCK_TTL_SECONDS,
            wait_timeout_ms=USER_ACTION_LOCK_WAIT_TIMEOUT_MS,
            owner_hint=owner_hint,
        )
    except LockAcquireError:
        raise BizException(ErrorCode.SYSTEM_ERROR, message="房间操作处理中，请稍后重试")


async def acquire_managed_room_lock(
    lock_service: RedisDistributedLock,
    room_id: str,
    task_id: str,
):
    """
    获取托管任务房间动作锁。

    :param lock_service: 分布式锁服务。
    :param room_id: 房间 ID。
    :param task_id: 托管任务 ID。
    :return: 锁句柄。
    :raises LockAcquireError: 锁获取失败。
    """
    lock_key = RedisKeys.room_lock(room_id.strip())
    owner_hint = "managed:{0}".format(task_id.strip())
    return await lock_service.acquire(
        lock_key,
        ttl_seconds=ROOM_ACTION_LOCK_TTL_SECONDS,
        wait_timeout_ms=MANAGED_ACTION_LOCK_WAIT_TIMEOUT_MS,
        owner_hint=owner_hint,
    )


async def acquire_auto_advance_room_lock(
    lock_service: RedisDistributedLock,
    room_id: str,
    task_id: str,
):
    """
    获取自动推进任务房间动作锁。

    :param lock_service: 分布式锁服务。
    :param room_id: 房间 ID。
    :param task_id: 自动推进任务 ID。
    :return: 锁句柄。
    :raises LockAcquireError: 锁获取失败。
    """
    lock_key = RedisKeys.room_lock(room_id.strip())
    owner_hint = "autoAdvance:{0}".format(task_id.strip())
    return await lock_service.acquire(
        lock_key,
        ttl_seconds=ROOM_ACTION_LOCK_TTL_SECONDS,
        wait_timeout_ms=MANAGED_ACTION_LOCK_WAIT_TIMEOUT_MS,
        owner_hint=owner_hint,
    )


async def require_meta(repository: RoomRepository, room_id: str) -> Dict[str, Any]:
    """
    读取房间元信息，不存在时抛业务异常。

    :param repository: 房间 Redis 仓库。
    :param room_id: 房间 ID。
    :return: 房间元信息。
    """
    meta = await repository.get_meta(room_id.strip())
    if meta is None:
        raise BizException(ErrorCode.ROOM_NOT_FOUND)
    return meta


def require_waiting_room(meta: Dict[str, Any]) -> None:
    """
    校验房间尚未开始。

    :param meta: 房间元信息。
    :return: 无。
    :raises BizException: 房间已开始。
    """
    if meta.get("status") != "waiting":
        raise BizException(ErrorCode.ROOM_ALREADY_STARTED)


def require_playing_room(meta: Dict[str, Any]) -> None:
    """
    校验房间对局已开始。

    :param meta: 房间元信息。
    :return: 无。
    :raises BizException: 对局尚未开始。
    """
    if meta.get("status") != "playing":
        raise BizException(ErrorCode.PARAM_ERROR, message="对局尚未开始")


def require_match_room(meta: Dict[str, Any]) -> None:
    """
    校验房间处于对局中。

    :param meta: 房间元信息。
    :return: 无。
    :raises BizException: 对局尚未开始。
    """
    status = str(meta.get("status", "")).strip()
    if status != "playing":
        raise BizException(ErrorCode.PARAM_ERROR, message="对局尚未开始")


def require_room_owner(meta: Dict[str, Any], player_id: str) -> None:
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


def require_member(members: List[Dict[str, Any]], player_id: str) -> None:
    """
    校验玩家为房间成员。

    :param members: 成员列表。
    :param player_id: 玩家 ID。
    :return: 无。
    :raises BizException: 不在房间中时抛出。
    """
    if find_member(members, player_id) is None:
        raise BizException(ErrorCode.ROOM_NOT_MEMBER)


async def assert_can_create_room(repository: RoomRepository, player_id: str) -> None:
    """
    校验玩家当前未处于有效活跃房间。

    :param repository: 房间 Redis 仓库。
    :param player_id: 玩家 ID。
    :return: 无。
    """
    if await repository.get_active_membership(player_id) is not None:
        raise BizException(ErrorCode.PLAYER_ALREADY_IN_ROOM)


def is_active_room_member(member: Dict[str, Any]) -> bool:
    """
    判断成员是否为活跃占位成员（非 shell，含真人与 AI）。

    :param member: 成员对象。
    :return: 是否为活跃成员。
    """
    return not is_shell_managed(member)


def has_rejoinable_shell_human_member(members: List[Dict[str, Any]]) -> bool:
    """
    判断成员列表中是否仍有可重新加入的 shell 托管真人席位。

    :param members: 成员列表。
    :return: 是否存在可重连的 shell 托管真人。
    """
    for member in members:
        if bool(member.get("isAi")):
            continue
        if is_shell_managed(member):
            return True
    return False


def should_cleanup_playing_room(members: List[Dict[str, Any]]) -> bool:
    """
    判断 playing 房间是否应清理（无在线真人且无 shell 可重连真人）。

    :param members: 房间成员列表。
    :return: 是否应删除房间。
    """
    has_real_human = has_real_human_member(members)
    has_shell_human = has_rejoinable_shell_human_member(members)
    return not has_real_human and not has_shell_human


def build_member(
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


def build_ai_member(
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


def count_ai_members(members: List[Dict[str, Any]]) -> int:
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


def sync_meta_ai_context(
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


def merge_room_config(
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


def resolve_effective_room_limits(
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


def build_runtime_rule(
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
    room_config = resolve_room_config_defaults(definition)
    room_config_from_meta = meta.get("roomConfig")
    if isinstance(room_config_from_meta, dict):
        room_config.update(room_config_from_meta)
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


def build_room_list_item(
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
        owner_member = find_member(members, owner_player_id)
        if owner_member is not None:
            owner_nickname = str(owner_member.get("nickname", owner_player_id))
        else:
            owner_nickname = owner_player_id
    room_name = str(meta.get("roomName", "")).strip()
    if not room_name:
        room_name = "房间-{0}".format(str(meta.get("roomId", ""))[-6:])
    real_member_count = 0
    for member in members:
        if is_active_room_member(member):
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


def extract_current_player_id(snapshot: RuntimeSnapshot) -> str:
    """
    从运行时快照解析当前行动玩家 ID。

    :param snapshot: 运行时快照。
    :return: 当前行动玩家 ID；不存在时返回空字符串。
    """
    state = snapshot.state if isinstance(snapshot.state, dict) else {}
    return str(state.get("currentPlayerId", "")).strip()


@contextmanager
def game_service_scope(
    game_service: Optional[GameModuleService],
) -> Generator[GameModuleService, None, None]:
    """
    获取游戏模块服务：请求级注入优先，否则使用短生命周期数据库会话。

    :param game_service: 已注入的游戏模块服务，可为空。
    :yield: ``GameModuleService`` 实例。
    """
    if game_service is not None:
        yield game_service
        return
    with session_scope() as db:
        yield build_game_module_service(db)


async def commit_room_meta_version(
    repository: RoomRepository,
    room_mutation_commit_service: RoomMutationCommitService,
    room_id: str,
    meta: Dict[str, Any],
) -> int:
    """
    通过 RoomMutationCommit 原子更新 meta 与 roomVersion。

    :param repository: 房间 Redis 仓库。
    :param room_mutation_commit_service: 房间变更提交服务。
    :param room_id: 房间 ID。
    :param meta: 下一版房间元数据。
    :return: 已提交版本。
    """
    version = int(await repository.get_room_version(room_id) or 0)
    result = await room_mutation_commit_service.commit(
        room_id,
        version,
        meta,
    )
    return int(result.committedRoomVersion or 0)


async def remove_waiting_members(
    repository: RoomRepository,
    room_mutation_commit_service: RoomMutationCommitService,
    room_id: str,
    meta: Dict[str, Any],
    members: List[Dict[str, Any]],
    target_player_ids: List[str],
) -> List[Dict[str, Any]]:
    """
    在等待中的房间内批量移除成员并同步 AI 元信息。

    :param repository: 房间 Redis 仓库。
    :param room_mutation_commit_service: 房间变更提交服务。
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
        target_member = find_member(remaining_members, target_player_id)
        if target_member is None or is_shell_managed(target_member):
            continue
        remaining_members = [
            item
            for item in remaining_members
            if str(item.get("playerId", "")).strip() != target_player_id
        ]
    sync_meta_ai_context(meta, remaining_members)
    version = int(await repository.get_room_version(room_id) or 0)
    await room_mutation_commit_service.commit(
        room_id,
        version,
        meta,
        member_deletes=normalized_ids,
    )
    return remaining_members


async def append_ai_players(
    repository: RoomRepository,
    room_mutation_commit_service: RoomMutationCommitService,
    room_id: str,
    meta: Dict[str, Any],
    members: List[Dict[str, Any]],
    count: int,
    expire_seconds: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    向房间追加指定数量的 AI 成员。

    :param repository: 房间 Redis 仓库。
    :param room_mutation_commit_service: 房间变更提交服务。
    :param room_id: 房间 ID。
    :param meta: 房间元信息（就地更新 aiCount 与 roomConfig）。
    :param members: 当前成员列表。
    :param count: 追加数量。
    :param expire_seconds: Redis TTL（秒）；未传时仅刷新已有 TTL。
    :return: 更新后的成员列表。
    """
    if count <= 0:
        return members
    updated_members = list(members)
    added_members = []
    current_time = now_ms()
    for _ in range(count):
        ai_index = count_ai_members(updated_members) + 1
        ai_player_id = generate_server_id("ai")
        ai_member = build_ai_member(ai_player_id, ai_index, current_time)
        added_members.append(ai_member)
        updated_members.append(ai_member)
    sync_meta_ai_context(meta, updated_members)
    meta["updatedAt"] = current_time
    version = int(await repository.get_room_version(room_id) or 0)
    await room_mutation_commit_service.commit(
        room_id,
        version,
        meta,
        member_upserts=added_members,
        ttl_seconds=int(expire_seconds or 86400),
    )
    return updated_members
