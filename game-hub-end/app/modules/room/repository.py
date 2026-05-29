"""房间 Redis 读写。"""

from typing import Any, Dict, List, Optional

from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys

ROOM_EXPIRE_SECONDS = 86400


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

    async def delete_runtime(self, room_id: str) -> bool:
        """
        删除房间运行期数据。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_runtime(room_id))

    async def save_public_state(
        self,
        room_id: str,
        state: Dict[str, Any],
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间公开状态。

        :param room_id: 房间 ID。
        :param state: 公开状态对象。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_json(
            RedisKeys.room_public_state(room_id),
            state,
            self._expire_seconds(expire_seconds),
        )

    async def get_public_state(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        读取房间公开状态。

        :param room_id: 房间 ID。
        :return: 公开状态对象；不存在时返回 ``None``。
        """
        return self._as_dict(await self._redis.get_json(RedisKeys.room_public_state(room_id)))

    async def delete_public_state(self, room_id: str) -> bool:
        """
        删除房间公开状态。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_public_state(room_id))

    async def save_private_state(
        self,
        room_id: str,
        player_id: str,
        state: Dict[str, Any],
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间玩家私有状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param state: 私有状态对象。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_json(
            RedisKeys.room_private_state(room_id, player_id),
            state,
            self._expire_seconds(expire_seconds),
        )

    async def get_private_state(self, room_id: str, player_id: str) -> Optional[Dict[str, Any]]:
        """
        读取房间玩家私有状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 私有状态对象；不存在时返回 ``None``。
        """
        return self._as_dict(
            await self._redis.get_json(RedisKeys.room_private_state(room_id, player_id))
        )

    async def delete_private_state(self, room_id: str, player_id: str) -> bool:
        """
        删除房间玩家私有状态。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_private_state(room_id, player_id))

    async def save_legal_actions(
        self,
        room_id: str,
        player_id: str,
        actions: Any,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间玩家合法动作。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param actions: 合法动作数据。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_json(
            RedisKeys.room_legal_actions(room_id, player_id),
            actions,
            self._expire_seconds(expire_seconds),
        )

    async def get_legal_actions(self, room_id: str, player_id: str) -> Optional[Any]:
        """
        读取房间玩家合法动作。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 合法动作数据；不存在时返回 ``None``。
        """
        return await self._redis.get_json(RedisKeys.room_legal_actions(room_id, player_id))

    async def delete_legal_actions(self, room_id: str, player_id: str) -> bool:
        """
        删除房间玩家合法动作。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_legal_actions(room_id, player_id))

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
        await self.delete_public_state(room_id)
        await self.delete_events(room_id)
        await self.delete_presence(room_id)
        for pattern in (
            RedisKeys.room_private_state_pattern(room_id),
            RedisKeys.room_legal_actions_pattern(room_id),
        ):
            keys = await self._redis.scan_keys(pattern)
            for key in keys:
                await self._redis.delete(key)

    async def save_version(
        self,
        room_id: str,
        version: int,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入房间版本号。

        :param room_id: 房间 ID。
        :param version: 版本号。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_string(
            RedisKeys.room_version(room_id),
            str(version),
            self._expire_seconds(expire_seconds),
        )

    async def get_version(self, room_id: str) -> Optional[int]:
        """
        读取房间版本号。

        :param room_id: 房间 ID。
        :return: 版本号；不存在或格式非法时返回 ``None``。
        """
        value = await self._redis.get_string(RedisKeys.room_version(room_id))
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def delete_version(self, room_id: str) -> bool:
        """
        删除房间版本号。

        :param room_id: 房间 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.room_version(room_id))

    async def save_player_room(
        self,
        player_id: str,
        room_id: str,
        expire_seconds: Optional[int] = None,
    ) -> bool:
        """
        写入玩家当前房间索引。

        :param player_id: 玩家 ID。
        :param room_id: 房间 ID。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 是否写入成功。
        """
        return await self._redis.set_string(
            RedisKeys.player_room(player_id),
            room_id,
            self._expire_seconds(expire_seconds),
        )

    async def get_player_room(self, player_id: str) -> Optional[str]:
        """
        读取玩家当前房间索引。

        :param player_id: 玩家 ID。
        :return: 房间 ID；不存在时返回 ``None``。
        """
        return await self._redis.get_string(RedisKeys.player_room(player_id))

    async def delete_player_room(self, player_id: str) -> bool:
        """
        删除玩家当前房间索引。

        :param player_id: 玩家 ID。
        :return: 是否删除成功。
        """
        return await self._redis.delete(RedisKeys.player_room(player_id))

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
        return await self._redis.set_string(
            RedisKeys.player_managed_shell_room(player_id, game_code),
            room_id,
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

    async def delete_managed_shell_room_index(self, player_id: str, game_code: str) -> bool:
        """
        删除玩家托管空壳房间索引。

        :param player_id: 玩家 ID。
        :param game_code: 游戏编码。
        :return: 是否删除成功。
        """
        return await self._redis.delete(
            RedisKeys.player_managed_shell_room(player_id, game_code),
        )

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
        return await self._redis.sadd(
            RedisKeys.game_rooms(game_code),
            room_id,
            self._expire_seconds(expire_seconds),
        )

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
        await self.delete_public_state(room_id)
        await self.delete_events(room_id)
        await self.delete_presence(room_id)
        await self.delete_version(room_id)
        await self.remove_playing_room(room_id)
        for pattern in (
            RedisKeys.room_private_state_pattern(room_id),
            RedisKeys.room_legal_actions_pattern(room_id),
        ):
            keys = await self._redis.scan_keys(pattern)
            for key in keys:
                await self._redis.delete(key)
        normalized_code = str(game_code).strip()
        if normalized_code:
            await self.remove_game_room_index(normalized_code, room_id)
        for player_id in member_player_ids:
            normalized_player_id = str(player_id).strip()
            if normalized_player_id:
                await self.delete_player_room(normalized_player_id)

    async def refresh_room_ttl(self, room_id: str, expire_seconds: Optional[int] = None) -> None:
        """
        刷新房间相关 key 的过期时间。

        :param room_id: 房间 ID。
        :param expire_seconds: 过期秒数，默认 86400。
        :return: 无。
        """
        expire = self._expire_seconds(expire_seconds)
        fixed_keys = [
            RedisKeys.room_meta(room_id),
            RedisKeys.room_players(room_id),
            RedisKeys.room_runtime(room_id),
            RedisKeys.room_public_state(room_id),
            RedisKeys.room_events(room_id),
            RedisKeys.room_presence(room_id),
            RedisKeys.room_version(room_id),
        ]
        for key in fixed_keys:
            await self._redis.expire(key, expire)
        patterns = [
            RedisKeys.room_private_state_pattern(room_id),
            RedisKeys.room_legal_actions_pattern(room_id),
        ]
        for pattern in patterns:
            keys = await self._redis.scan_keys(pattern)
            for key in keys:
                await self._redis.expire(key, expire)

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
