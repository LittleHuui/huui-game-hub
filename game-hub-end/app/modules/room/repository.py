"""房间 Redis 读写。"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_errors import RedisOperationError
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.room_membership_index_bindings import prepare_member_index_bindings
from app.modules.room.room_membership_index_lua import (
    DELETE_OWNED_MEMBERSHIP_LUA,
    LIST_MEMBERSHIP_CANDIDATES_LUA,
    MEMBERSHIP_FACTS_LUA,
    REBUILD_MEMBERSHIP_LUA,
    RESOLVE_MEMBERSHIP_LUA,
)
from app.modules.room.task_errors import TaskTemporaryInfrastructureError, TaskTemporaryReason

ROOM_EXPIRE_SECONDS = 86400
logger = logging.getLogger(__name__)

_READ_ROOM_SNAPSHOT_LUA = """
local meta = redis.call('GET', KEYS[1])
if not meta then return {} end
return {meta, redis.call('HVALS', KEYS[2]), redis.call('GET', KEYS[3]) or ''}
"""

_ADD_GAME_ROOM_INDEX_LUA = """
redis.call('SADD', KEYS[1], ARGV[1])
local ttl = redis.call('TTL', KEYS[1])
local requested = tonumber(ARGV[2])
if ttl < requested then redis.call('EXPIRE', KEYS[1], requested) end
return 1
"""

_REFRESH_ROOM_TTL_LUA = MEMBERSHIP_FACTS_LUA + """
local rawMeta = redis.call('GET', KEYS[1])
if not rawMeta then return 'MISSING' end
local meta = decodeObject(rawMeta)
if not meta or meta.roomId ~= ARGV[1] then return 'INVALID' end
local gameCode = meta.gameCode
if gameCode == nil or gameCode == cjson.null then gameCode = '' end
if gameCode ~= ARGV[3] then return 'CHANGED' end
local bindings = cjson.decode(ARGV[4])
if not hasCompleteMemberBindings(KEYS[2], bindings) then return 'CHANGED' end
local ttl = tonumber(ARGV[2])
for index = 1, 7 do redis.call('EXPIRE', KEYS[index], ttl) end
if gameCode ~= '' then
  redis.call('SADD', KEYS[8], ARGV[1])
  if redis.call('TTL', KEYS[8]) < ttl then redis.call('EXPIRE', KEYS[8], ttl) end
end
renewOwnedMemberIndexes(KEYS[1], KEYS[2], ARGV[1], bindings)
return 'REFRESHED'
"""


class RoomRepository(object):
    """房间临时态 Redis 仓库。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        """
        初始化房间仓库。

        :param redis: Redis 工具。
        """
        self._redis = redis

    async def save_meta(
        self,
        room_id: str,
        meta: Dict[str, Any],
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间元信息。

        :param room_id: 房间 ID。
        :param meta: 房间元信息对象。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_json(
            RedisKeys.room_meta(room_id),
            meta,
            self._expire_seconds(expire_seconds),
        )

    async def get_meta(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        读取房间元信息。

        :param room_id: 房间 ID。
        :return: 房间元信息；不存在时返回 ``None``。
        """
        return self._as_dict(await self._redis.get_json(RedisKeys.room_meta(room_id)))

    async def read_room_snapshot(
        self, room_id: str,
    ) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]], int]]:
        """原子读取详情事实与版本，避免终局提交夹在多次读取之间。"""
        raw = await self._redis.eval_raw(
            _READ_ROOM_SNAPSHOT_LUA, 3,
            [RedisKeys.room_meta(room_id), RedisKeys.room_players(room_id),
             RedisKeys.room_room_version(room_id)], [],
        )
        if raw == []:
            return None
        try:
            if not isinstance(raw, (list, tuple)) or len(raw) != 3:
                raise ValueError("invalid room snapshot")
            meta = json.loads(raw[0])
            if not isinstance(meta, dict) or meta.get("roomId") != room_id:
                raise ValueError("invalid room meta")
            if not isinstance(raw[1], (list, tuple)):
                raise ValueError("invalid room members")
            members = [json.loads(item) for item in raw[1]]
            if any(not isinstance(member, dict) for member in members):
                raise ValueError("invalid room member")
            version = int(raw[2])
            if version < 1:
                raise ValueError("invalid room version")
            return meta, members, version
        except (TypeError, ValueError) as exc:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间详情快照无效，请重试") from exc

    async def get_meta_for_task(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        任务路径读取房间元信息；Redis 失败时抛 ``TaskTemporaryInfrastructureError``。

        :param room_id: 房间 ID。
        :return: 房间元信息；不存在时返回 ``None``。
        :raises TaskTemporaryInfrastructureError: Redis 暂时不可用时抛出。
        """
        try:
            return self._as_dict(
                await self._redis.get_json_strict(RedisKeys.room_meta(room_id)),
            )
        except RedisOperationError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_UNAVAILABLE, cause=exc)

    async def get_game_version_for_task(self, room_id: str) -> Optional[int]:
        """
        任务路径读取对局版本；Redis 失败时抛 ``TaskTemporaryInfrastructureError``。

        :param room_id: 房间 ID。
        :return: 对局版本号；不存在或格式非法时返回 ``None``。
        :raises TaskTemporaryInfrastructureError: Redis 暂时不可用时抛出。
        """
        try:
            value = await self._redis.get_string_strict(RedisKeys.room_game_version(room_id))
        except RedisOperationError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_UNAVAILABLE, cause=exc)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def get_room_version_for_task(self, room_id: str) -> Optional[int]:
        """
        任务路径读取房间元数据版本；Redis 失败时抛 ``TaskTemporaryInfrastructureError``。

        :param room_id: 房间 ID。
        :return: 房间元数据版本号；不存在或格式非法时返回 ``None``。
        :raises TaskTemporaryInfrastructureError: Redis 暂时不可用时抛出。
        """
        try:
            value = await self._redis.get_string_strict(RedisKeys.room_room_version(room_id))
        except RedisOperationError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_UNAVAILABLE, cause=exc)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def list_players_for_task(self, room_id: str) -> List[Dict[str, Any]]:
        """
        任务路径读取房间全部玩家；Redis 失败时抛 ``TaskTemporaryInfrastructureError``。

        :param room_id: 房间 ID。
        :return: 玩家对象列表。
        :raises TaskTemporaryInfrastructureError: Redis 暂时不可用时抛出。
        """
        try:
            players_map = await self._redis.hgetall_json_strict(RedisKeys.room_players(room_id))
        except RedisOperationError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_UNAVAILABLE, cause=exc)
        players = []
        for value in players_map.values():
            player = self._as_dict(value)
            if player is not None:
                players.append(player)
        return players

    async def delete_meta(self, room_id: str) -> bool:
        """
        删除房间元信息。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_meta(room_id))

    async def save_player(
        self,
        room_id: str,
        player_id: str,
        player: Dict[str, Any],
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间玩家。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param player: 玩家对象。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.hset_json(
            RedisKeys.room_players(room_id),
            player_id,
            player,
            self._expire_seconds(expire_seconds),
        )

    async def get_player(self, room_id: str, player_id: str) -> Optional[Dict[str, Any]]:
        """
        读取单个房间玩家。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 玩家对象；不存在时返回 ``None``。
        """
        return self._as_dict(
            await self._redis.hget_json(RedisKeys.room_players(room_id), player_id)
        )

    async def delete_player(self, room_id: str, player_id: str) -> bool:
        """
        删除房间玩家。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 是否删除成功。
        """
        return await self._redis.hdel(RedisKeys.room_players(room_id), player_id)

    async def list_players(self, room_id: str) -> List[Dict[str, Any]]:
        """
        读取房间全部玩家。

        :param room_id: 房间 ID。
        :return: 玩家对象列表。
        """
        players_map = await self._redis.hgetall_json(RedisKeys.room_players(room_id))
        players = []
        for value in players_map.values():
            player = self._as_dict(value)
            if player is not None:
                players.append(player)
        return players

    async def save_runtime(
        self,
        room_id: str,
        runtime: Dict[str, Any],
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间运行期数据。

        :param room_id: 房间 ID。
        :param runtime: 运行期对象。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_json(
            RedisKeys.room_runtime(room_id),
            runtime,
            self._expire_seconds(expire_seconds),
        )

    async def get_runtime(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        读取房间运行期数据。

        :param room_id: 房间 ID。
        :return: 运行期对象；不存在时返回 ``None``。
        """
        return self._as_dict(await self._redis.get_json(RedisKeys.room_runtime(room_id)))

    async def get_runtime_for_task(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        任务路径读取房间运行期数据；Redis 失败时抛 ``TaskTemporaryInfrastructureError``。

        :param room_id: 房间 ID。
        :return: 运行期对象；不存在时返回 ``None``。
        :raises TaskTemporaryInfrastructureError: Redis 暂时不可用时抛出。
        """
        try:
            return self._as_dict(
                await self._redis.get_json_strict(RedisKeys.room_runtime(room_id)),
            )
        except RedisOperationError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.REDIS_UNAVAILABLE, cause=exc)

    async def delete_runtime(self, room_id: str) -> bool:
        """
        删除房间运行期数据。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_runtime(room_id))

    async def save_events(
        self,
        room_id: str,
        events: Any,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间事件。

        :param room_id: 房间 ID。
        :param events: 事件数据。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_json(
            RedisKeys.room_events(room_id),
            events,
            self._expire_seconds(expire_seconds),
        )

    async def get_events(self, room_id: str) -> Optional[Any]:
        """
        读取房间事件。

        :param room_id: 房间 ID。
        :return: 事件数据；不存在时返回 ``None``。
        """
        return await self._redis.get_json(RedisKeys.room_events(room_id))

    async def delete_events(self, room_id: str) -> bool:
        """
        删除房间事件。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_events(room_id))

    async def save_presence_state(
        self,
        room_id: str,
        player_id: str,
        state: Dict[str, Any],
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间玩家探活状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param state: 探活状态对象。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.hset_json(
            RedisKeys.room_presence(room_id),
            player_id,
            state,
            self._expire_seconds(expire_seconds),
        )

    async def get_presence_state(self, room_id: str, player_id: str) -> Optional[Dict[str, Any]]:
        """
        读取房间玩家探活状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 探活状态；不存在时返回 ``None``。
        """
        return self._as_dict(
            await self._redis.hget_json(RedisKeys.room_presence(room_id), player_id)
        )

    async def list_presence_states(self, room_id: str) -> Dict[str, Dict[str, Any]]:
        """
        读取房间全部玩家探活状态。

        :param room_id: 房间 ID。
        :return: ``player_id -> state`` 映射。
        """
        raw = await self._redis.hgetall_json(RedisKeys.room_presence(room_id))
        result = {}
        for player_id, value in raw.items():
            state = self._as_dict(value)
            if state is not None:
                result[str(player_id)] = state
        return result

    async def delete_presence_state(self, room_id: str, player_id: str) -> bool:
        """
        删除房间玩家探活状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 是否删除成功。
        """
        return await self._redis.hdel(RedisKeys.room_presence(room_id), player_id)

    async def delete_presence(self, room_id: str) -> bool:
        """
        删除房间探活 hash。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_presence(room_id))

    async def clear_match_runtime(self, room_id: str) -> None:
        """
        清理房间对局运行时相关 Redis 数据，保留成员与元信息。

        :param room_id: 房间 ID。
        :return: 无。
        """
        await self.delete_runtime(room_id)
        await self.delete_events(room_id)
        await self.delete_presence(room_id)

    async def save_game_version(
        self,
        room_id: str,
        version: int,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入对局版本号。

        :param room_id: 房间 ID。
        :param version: 对局版本号。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_string(
            RedisKeys.room_game_version(room_id),
            str(version),
            self._expire_seconds(expire_seconds),
        )

    async def get_game_version(self, room_id: str) -> Optional[int]:
        """
        读取对局版本号。

        :param room_id: 房间 ID。
        :return: 对局版本号；不存在或格式非法时返回 ``None``。
        """
        value = await self._redis.get_string(RedisKeys.room_game_version(room_id))
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def save_room_version(
        self,
        room_id: str,
        version: int,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间元数据版本号。

        :param room_id: 房间 ID。
        :param version: 房间元数据版本号。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_string(
            RedisKeys.room_room_version(room_id),
            str(version),
            self._expire_seconds(expire_seconds),
        )

    async def get_room_version(self, room_id: str) -> Optional[int]:
        """
        读取房间元数据版本号。

        :param room_id: 房间 ID。
        :return: 房间元数据版本号；不存在或格式非法时返回 ``None``。
        """
        value = await self._redis.get_string(RedisKeys.room_room_version(room_id))
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def get_runtime_and_version_consistent(
        self,
        room_id: str,
        max_retry: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """
        读取版本一致的运行时快照与房间版本。

        :param room_id: 房间 ID。
        :param max_retry: 最大重试次数。
        :return: 包含 runtime 与 version 的字典；运行期不存在时返回 ``None``。
        """
        retry_count = max(1, int(max_retry))
        last_runtime = None
        for _index in range(retry_count):
            version_before = await self.get_game_version(room_id)
            runtime = await self.get_runtime(room_id)
            version_after = await self.get_game_version(room_id)
            if runtime is None:
                return None
            if version_before == version_after:
                return {
                    "runtime": runtime,
                    "version": int(version_after or 0),
                }
            last_runtime = runtime
        if last_runtime is None:
            return None
        raise BizException(
            ErrorCode.SYSTEM_ERROR,
            message="运行时与版本号不一致，请重试",
        )

    async def delete_version(self, room_id: str) -> bool:
        """
        删除房间全部版本号 key。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        game_deleted = await self._redis.delete(RedisKeys.room_game_version(room_id))
        room_deleted = await self._redis.delete(RedisKeys.room_room_version(room_id))
        return bool(game_deleted or room_deleted)

    async def save_player_room(
        self,
        player_id: str,
        room_id: str,
        game_code: str,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        核对房间成员事实后重建索引，不覆盖其他房间的占用。

        :param player_id: 玩家 ID。
        :param room_id: 房间 ID。
        :param game_code: 房间游戏编码。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._rebuild_membership_index(
            RedisKeys.player_room(player_id), player_id, room_id, "active", game_code,
            self._expire_seconds(expire_seconds),
        )

    async def get_player_room(self, player_id: str) -> Optional[str]:
        """
        读取玩家当前房间索引。

        :param player_id: 玩家 ID。
        :return: 房间 ID；不存在时返回 ``None``。
        """
        return await self._redis.get_string_strict(RedisKeys.player_room(player_id))

    async def delete_player_room(self, player_id: str, expected_room_id: str) -> bool:
        """
        仅在索引仍属于指定房间时原子删除。

        :param player_id: 玩家 ID。
        :param expected_room_id: 本次清理所属的房间 ID。
        :return: 是否删除成功。
        """
        return bool(await self._redis.eval_raw(
            DELETE_OWNED_MEMBERSHIP_LUA, 1,
            [RedisKeys.player_room(player_id)], [expected_room_id],
        ))

    async def get_active_membership(self, player_id: str) -> Optional[Dict[str, Any]]:
        """原子读取有效活跃成员事实，并收敛已失效的所属索引。"""
        return await self._resolve_membership_index(
            RedisKeys.player_room(player_id), player_id, "active", "",
        )

    async def get_shell_membership(
        self, player_id: str, game_code: str,
    ) -> Optional[Dict[str, Any]]:
        """原子读取指定游戏中的有效托管席位事实。"""
        return await self._resolve_membership_index(
            RedisKeys.player_managed_shell_room(player_id, game_code),
            player_id, "shell", game_code,
        )

    async def _resolve_membership_index(
        self, index_key: str, player_id: str, kind: str, game_code: str,
    ) -> Optional[Dict[str, Any]]:
        """索引切换时有限重读，避免用旧房间快照清理新占用。"""
        for _attempt in range(3):
            room_id = await self._redis.get_string_strict(index_key)
            if not room_id:
                return None
            keys = [index_key, RedisKeys.room_meta(room_id), RedisKeys.room_players(room_id),
                    RedisKeys.room_room_version(room_id)]
            raw = await self._redis.eval_raw(
                RESOLVE_MEMBERSHIP_LUA, len(keys), keys, [room_id, player_id, kind, game_code],
            )
            result = json.loads(raw)
            if result["status"] == "ACTIVE":
                return result
            if result["status"] == "STALE":
                return None
            if result["status"] != "CHANGED":
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员状态不完整，请稍后重试")
        raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员状态正在变化，请稍后重试")

    async def _rebuild_membership_index(
        self, index_key: str, player_id: str, room_id: str,
        kind: str, game_code: str, expire_seconds: int,
    ) -> bool:
        """重建时同时核对当前成员事实和索引归属。"""
        counterpart_key = (
            RedisKeys.player_room(player_id) if kind == "shell"
            else RedisKeys.player_managed_shell_room(player_id, game_code)
        )
        keys = [index_key, RedisKeys.room_meta(room_id), RedisKeys.room_players(room_id), counterpart_key]
        return bool(await self._redis.eval_raw(
            REBUILD_MEMBERSHIP_LUA, len(keys), keys,
            [room_id, player_id, kind, game_code, str(expire_seconds)],
        ))

    async def save_managed_shell_room_index(
        self,
        player_id: str,
        game_code: str,
        room_id: str,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入玩家托管空壳房间索引。

        :param player_id: 玩家 ID。
        :param game_code: 游戏编码。
        :param room_id: 房间 ID。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._rebuild_membership_index(
            RedisKeys.player_managed_shell_room(player_id, game_code), player_id,
            room_id, "shell", game_code,
            self._expire_seconds(expire_seconds),
        )

    async def get_managed_shell_room_index(self, player_id: str, game_code: str) -> Optional[str]:
        """
        读取玩家托管空壳房间索引。

        :param player_id: 玩家 ID。
        :param game_code: 游戏编码。
        :return: 房间 ID；不存在时返回 ``None``。
        """
        return await self._redis.get_string(
            RedisKeys.player_managed_shell_room(player_id, game_code),
        )

    async def delete_managed_shell_room_index(
        self, player_id: str, game_code: str, expected_room_id: str,
    ) -> bool:
        """
        删除玩家托管空壳房间索引。

        :param player_id: 玩家 ID。
        :param game_code: 游戏编码。
        :param expected_room_id: 本次清理所属的房间 ID。
        :return: 是否删除成功。
        """
        return bool(await self._redis.eval_raw(
            DELETE_OWNED_MEMBERSHIP_LUA, 1,
            [RedisKeys.player_managed_shell_room(player_id, game_code)], [expected_room_id],
        ))

    async def add_game_room_index(
        self,
        game_code: str,
        room_id: str,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        将房间 ID 写入按游戏编码索引的集合。

        :param game_code: 游戏编码。
        :param room_id: 房间 ID。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return bool(await self._redis.eval_raw(
            _ADD_GAME_ROOM_INDEX_LUA, 1, [RedisKeys.game_rooms(game_code)],
            [room_id, str(self._expire_seconds(expire_seconds))],
        ))

    async def list_game_room_ids(self, game_code: str) -> List[str]:
        """
        读取某游戏下已索引的房间 ID 列表。

        :param game_code: 游戏编码。
        :return: 房间 ID 列表。
        """
        members = await self._redis.smembers(RedisKeys.game_rooms(game_code))
        return sorted(members)

    async def remove_game_room_index(self, game_code: str, room_id: str) -> bool:
        """
        从按游戏编码索引的集合中移除房间 ID。

        :param game_code: 游戏编码。
        :param room_id: 房间 ID。
        :return: 是否移除成功。
        """
        return await self._redis.srem(RedisKeys.game_rooms(game_code), room_id)

    async def add_playing_room(self, room_id: str, expire_seconds: Optional[int] = None) -> bool:
        """
        将房间写入对局中房间集合。

        :param room_id: 房间 ID。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.sadd(
            RedisKeys.playing_rooms(),
            room_id,
            self._expire_seconds(expire_seconds),
        )

    async def remove_playing_room(self, room_id: str) -> bool:
        """
        将房间从对局中房间集合移除。

        :param room_id: 房间 ID。
        :return: 是否移除成功。
        """
        return await self._redis.srem(RedisKeys.playing_rooms(), room_id)

    async def list_playing_room_ids(self) -> List[str]:
        """
        读取对局中房间集合。

        :return: 房间 ID 列表。
        """
        members = await self._redis.smembers(RedisKeys.playing_rooms())
        return sorted(members)

    async def rebuild_playing_room_index(self) -> int:
        """
        从权威 Room meta 扫描重建 playing-room 派生索引。
        :return: 重建的 playing 房间数量。
        """
        keys = await self._redis.scan_keys(RedisKeys.room_meta_pattern())
        rebuilt = 0
        for key in keys:
            meta = self._as_dict(await self._redis.get_json(key))
            if meta is None or str(meta.get("status", "")).strip() != "playing":
                continue
            room_id = str(meta.get("roomId", "")).strip()
            if room_id and await self.add_playing_room(room_id):
                rebuilt += 1
        return rebuilt

    async def rebuild_member_derived_indexes(self) -> int:
        """
        从 Room 主事实扫描重建 player-room 与 managed-shell 派生索引。

        :return: 同步的索引条目数量。
        """
        keys = await self._redis.scan_keys(RedisKeys.room_meta_pattern())
        rebuilt = 0
        active_candidates = {}  # type: Dict[str, List[Tuple[str, str]]]
        shell_candidates = {}  # type: Dict[Tuple[str, str], List[str]]
        for key in keys:
            meta = self._as_dict(await self._redis.get_json(key))
            if meta is None:
                continue
            room_id = str(meta.get("roomId", "")).strip()
            if not room_id:
                continue
            raw_candidates = await self._redis.eval_raw(
                LIST_MEMBERSHIP_CANDIDATES_LUA, 2,
                [RedisKeys.room_meta(room_id), RedisKeys.room_players(room_id)], [room_id],
            )
            candidate_snapshot = json.loads(raw_candidates)
            if candidate_snapshot["status"] == "STALE":
                continue
            if candidate_snapshot["status"] != "ACTIVE":
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员事实损坏，不能重建索引")
            game_code = candidate_snapshot["gameCode"]
            if game_code:
                await self.add_game_room_index(game_code, room_id)
            for member in candidate_snapshot["members"]:
                player_id = member["playerId"]
                if member["kind"] == "SHELL":
                    shell_candidates.setdefault((player_id, game_code), []).append(room_id)
                else:
                    active_candidates.setdefault(player_id, []).append((room_id, game_code))
        for player_id, candidates in active_candidates.items():
            membership = await self.get_active_membership(player_id)
            if membership is not None:
                meta = membership["meta"]
                rebuilt += int(await self.save_player_room(player_id, meta["roomId"], meta["gameCode"]))
            elif len(candidates) == 1:
                room_id, game_code = candidates[0]
                rebuilt += int(await self.save_player_room(player_id, room_id, game_code))
            else:
                logger.error("ambiguous active membership, playerId=%s roomIds=%s", player_id,
                             [item[0] for item in candidates])
        for (player_id, game_code), candidates in shell_candidates.items():
            membership = await self.get_shell_membership(player_id, game_code)
            if membership is not None:
                room_id = membership["meta"]["roomId"]
                rebuilt += int(await self.save_managed_shell_room_index(player_id, game_code, room_id))
            elif len(candidates) == 1:
                rebuilt += int(await self.save_managed_shell_room_index(player_id, game_code, candidates[0]))
            else:
                logger.error("ambiguous shell membership, playerId=%s gameCode=%s roomIds=%s",
                             player_id, game_code, candidates)
        return rebuilt

    async def delete_players_hash(self, room_id: str) -> bool:
        """
        删除房间玩家 hash。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_players(room_id))

    async def delete_room_cascade(
        self,
        room_id: str,
        game_code: str,
        member_player_ids: List[str],
    ) -> None:
        """
        集中删除房间全部 Redis 数据与相关索引。

        :param room_id: 房间 ID。
        :param game_code: 游戏编码。
        :param member_player_ids: 曾属于该房间的玩家 ID 列表（含离开者）。
        :return: 无。
        """
        await self.delete_meta(room_id)
        await self.delete_players_hash(room_id)
        await self.delete_runtime(room_id)
        await self.delete_events(room_id)
        await self.delete_presence(room_id)
        await self.delete_version(room_id)
        await self.remove_playing_room(room_id)
        normalized_code = str(game_code).strip()
        if normalized_code:
            await self.remove_game_room_index(normalized_code, room_id)
        for player_id in member_player_ids:
            normalized_player_id = str(player_id).strip()
            if normalized_player_id:
                await self.delete_player_room(normalized_player_id, room_id)

    async def refresh_room_ttl(self, room_id: str, expire_seconds: Optional[int] = None) -> None:
        """
        原子刷新房间事实与已有成员归属；预绑定变化时有限重读。

        :param room_id: 房间 ID。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 无。
        """
        expire = self._expire_seconds(expire_seconds)
        for _attempt in range(3):
            meta = await self._redis.get_json_strict(RedisKeys.room_meta(room_id))
            if meta is None:
                return
            if not isinstance(meta, dict):
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息损坏，不能续期")
            game_code = str(meta.get("gameCode") or "").strip()
            keys = [
                RedisKeys.room_meta(room_id),
                RedisKeys.room_players(room_id),
                RedisKeys.room_runtime(room_id),
                RedisKeys.room_events(room_id),
                RedisKeys.room_presence(room_id),
                RedisKeys.room_game_version(room_id),
                RedisKeys.room_room_version(room_id),
                RedisKeys.game_rooms(game_code) if game_code else RedisKeys.room_meta(room_id),
            ]
            bindings = await prepare_member_index_bindings(self._redis, keys, room_id, game_code, [])
            result = await self._redis.eval_raw(
                _REFRESH_ROOM_TTL_LUA, len(keys), keys, [room_id, str(expire), game_code, bindings],
            )
            if isinstance(result, bytes):
                result = result.decode("utf-8")
            if result in ("MISSING", "REFRESHED"):
                return
            if result != "CHANGED":
                raise BizException(ErrorCode.SYSTEM_ERROR, message="房间元信息损坏，不能续期")
        raise BizException(ErrorCode.SYSTEM_ERROR, message="房间成员状态正在变化，请稍后重试")

    def _expire_seconds(self, expire_seconds: Optional[int]) -> int:
        """
        解析房间 key 过期秒数。

        :param expire_seconds: 调用方传入的过期秒数。
        :return: 实际使用的过期秒数。
        """
        if expire_seconds is None:
            return ROOM_EXPIRE_SECONDS
        return expire_seconds

    def _as_dict(self, value: Any) -> Optional[Dict[str, Any]]:
        """
        将 Redis 返回值约束为字典。

        :param value: Redis 反序列化结果。
        :return: 字典；类型不匹配时返回 ``None``。
        """
        if isinstance(value, dict):
            return value
        return None
