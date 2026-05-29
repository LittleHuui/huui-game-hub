"""Redis 异步客户端工具封装。"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Set

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis.redis_constants import TimeUnit

logger = logging.getLogger(__name__)


class RedisClient(object):
    """面向业务层的 Redis 数据结构操作工具。"""

    def __init__(self, client: Optional[Redis] = None) -> None:
        """
        初始化 Redis 工具。

        :param client: 可选底层 Redis client，便于测试注入。
        """
        self._client = client or Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=settings.REDIS_DECODE_RESPONSES,
        )

    async def set_string(self, key: str, value: str, expire: int, unit: TimeUnit = TimeUnit.SECONDS) -> bool:
        """
        写入字符串并设置过期时间。

        :param key: Redis key。
        :param value: 字符串值。
        :param expire: 过期时间，必须显式传入。
        :param unit: 过期时间单位，默认秒。
        :return: 是否写入成功。
        """
        try:
            return bool(await self._client.set(key, value, ex=self._to_seconds(expire, unit)))
        except (RedisError, ValueError):
            logger.exception("Redis set_string failed, key=%s", key)
            return False

    async def set_string_if_absent(
        self,
        key: str,
        value: str,
        expire: int,
        unit: TimeUnit = TimeUnit.SECONDS,
    ) -> bool:
        """
        仅在 key 不存在时写入字符串并设置过期时间。

        :param key: Redis key。
        :param value: 字符串值。
        :param expire: 过期时间，必须显式传入。
        :param unit: 过期时间单位，默认秒。
        :return: 是否写入成功。
        """
        try:
            return bool(
                await self._client.set(
                    key,
                    value,
                    nx=True,
                    ex=self._to_seconds(expire, unit),
                )
            )
        except (RedisError, ValueError):
            logger.exception("Redis set_string_if_absent failed, key=%s", key)
            return False

    async def get_string(self, key: str) -> Optional[str]:
        """
        读取字符串。

        :param key: Redis key。
        :return: 字符串值；不存在或 Redis 不可用时返回 ``None``。
        """
        try:
            return await self._client.get(key)
        except RedisError:
            logger.exception("Redis get_string failed, key=%s", key)
            return None

    async def set_json(
        self,
        key: str,
        value: Any,
        expire: int,
        unit: TimeUnit = TimeUnit.SECONDS,
    ) -> bool:
        """
        写入 JSON 对象并设置过期时间。

        :param key: Redis key。
        :param value: 可 JSON 序列化对象。
        :param expire: 过期时间，必须显式传入。
        :param unit: 过期时间单位，默认秒。
        :return: 是否写入成功。
        """
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            logger.exception("Redis set_json encode failed, key=%s", key)
            return False
        return await self.set_string(key, text, expire, unit)

    async def get_json(self, key: str) -> Optional[Any]:
        """
        读取 JSON 对象。

        :param key: Redis key。
        :return: 反序列化对象；不存在、格式错误或 Redis 不可用时返回 ``None``。
        """
        value = await self.get_string(key)
        return self._decode_json(value, key)

    async def mget_json(self, keys: Sequence[str]) -> List[Any]:
        """
        批量读取 JSON 对象。

        :param keys: Redis key 列表。
        :return: 有效 JSON 对象列表。
        """
        if not keys:
            return []
        try:
            values = await self._client.mget(list(keys))
        except RedisError:
            logger.exception("Redis mget_json failed")
            return []
        result = []
        for index, value in enumerate(values):
            decoded = self._decode_json(value, keys[index])
            if decoded is not None:
                result.append(decoded)
        return result

    async def hset_json(
        self,
        key: str,
        field: str,
        value: Any,
        expire: int,
        unit: TimeUnit = TimeUnit.SECONDS,
    ) -> bool:
        """
        写入 hash 字段 JSON 并设置 hash 过期时间。

        :param key: Redis key。
        :param field: hash 字段。
        :param value: 可 JSON 序列化对象。
        :param expire: 过期时间，必须显式传入。
        :param unit: 过期时间单位，默认秒。
        :return: 是否写入成功。
        """
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            await self._client.hset(key, field, text)
            return await self.expire(key, expire, unit)
        except (RedisError, TypeError, ValueError):
            logger.exception("Redis hset_json failed, key=%s field=%s", key, field)
            return False

    async def hget_json(self, key: str, field: str) -> Optional[Any]:
        """
        读取 hash 字段 JSON。

        :param key: Redis key。
        :param field: hash 字段。
        :return: 反序列化对象。
        """
        try:
            value = await self._client.hget(key, field)
        except RedisError:
            logger.exception("Redis hget_json failed, key=%s field=%s", key, field)
            return None
        return self._decode_json(value, "{0}.{1}".format(key, field))

    async def hdel(self, key: str, field: str) -> bool:
        """
        删除 hash 字段。

        :param key: Redis key。
        :param field: hash 字段。
        :return: 是否删除了至少一个字段。
        """
        try:
            return bool(await self._client.hdel(key, field))
        except RedisError:
            logger.exception("Redis hdel failed, key=%s field=%s", key, field)
            return False

    async def hgetall_json(self, key: str) -> Dict[str, Any]:
        """
        读取 hash 全部字段并反序列化 JSON。

        :param key: Redis key。
        :return: 字段到对象的映射。
        """
        try:
            values = await self._client.hgetall(key)
        except RedisError:
            logger.exception("Redis hgetall_json failed, key=%s", key)
            return {}
        result = {}
        for field, value in values.items():
            decoded = self._decode_json(value, "{0}.{1}".format(key, field))
            if decoded is not None:
                result[field] = decoded
        return result

    async def sadd(self, key: str, value: str, expire: int, unit: TimeUnit = TimeUnit.SECONDS) -> bool:
        """
        写入 set 成员并设置 set 过期时间。

        :param key: Redis key。
        :param value: set 成员。
        :param expire: 过期时间，必须显式传入。
        :param unit: 过期时间单位，默认秒。
        :return: 是否写入成功。
        """
        try:
            await self._client.sadd(key, value)
            return await self.expire(key, expire, unit)
        except RedisError:
            logger.exception("Redis sadd failed, key=%s", key)
            return False

    async def smembers(self, key: str) -> Set[str]:
        """
        读取 set 全部成员。

        :param key: Redis key。
        :return: 成员集合。
        """
        try:
            return set(await self._client.smembers(key))
        except RedisError:
            logger.exception("Redis smembers failed, key=%s", key)
            return set()

    async def srem(self, key: str, value: str) -> bool:
        """
        从 set 中移除成员。

        :param key: Redis key。
        :param value: set 成员。
        :return: 是否移除成功。
        """
        try:
            await self._client.srem(key, value)
            return True
        except RedisError:
            logger.exception("Redis srem failed, key=%s", key)
            return False

    async def zadd(
        self,
        key: str,
        score: float,
        value: str,
        expire: int,
        unit: TimeUnit = TimeUnit.SECONDS,
    ) -> bool:
        """
        写入 sorted set 成员并设置过期时间。

        :param key: Redis key。
        :param score: 排序分数。
        :param value: 成员值。
        :param expire: 过期时间，必须显式传入。
        :param unit: 过期时间单位，默认秒。
        :return: 是否写入成功。
        """
        try:
            await self._client.zadd(key, {value: score})
            return await self.expire(key, expire, unit)
        except RedisError:
            logger.exception("Redis zadd failed, key=%s", key)
            return False

    async def zrange(self, key: str, start: int, end: int) -> List[str]:
        """
        读取 sorted set 范围成员。

        :param key: Redis key。
        :param start: 起始下标。
        :param end: 结束下标。
        :return: 成员列表。
        """
        try:
            return list(await self._client.zrange(key, start, end))
        except RedisError:
            logger.exception("Redis zrange failed, key=%s", key)
            return []

    async def zrangebyscore(
        self,
        key: str,
        min_score: float,
        max_score: float,
        start: int = 0,
        num: int = 1,
    ) -> List[str]:
        """
        按分数范围读取 sorted set 成员。

        :param key: Redis key。
        :param min_score: 最小分数。
        :param max_score: 最大分数。
        :param start: 偏移量。
        :param num: 返回数量。
        :return: 成员列表。
        """
        try:
            return list(
                await self._client.zrangebyscore(
                    key,
                    min_score,
                    max_score,
                    start=start,
                    num=num,
                )
            )
        except RedisError:
            logger.exception("Redis zrangebyscore failed, key=%s", key)
            return []

    async def zrem(self, key: str, value: str) -> bool:
        """
        从 sorted set 移除成员。

        :param key: Redis key。
        :param value: 成员值。
        :return: 是否移除成功。
        """
        try:
            return bool(await self._client.zrem(key, value))
        except RedisError:
            logger.exception("Redis zrem failed, key=%s", key)
            return False

    async def delete(self, key: str) -> bool:
        """
        删除 key。

        :param key: Redis key。
        :return: 是否删除了至少一个 key。
        """
        try:
            return bool(await self._client.delete(key))
        except RedisError:
            logger.exception("Redis delete failed, key=%s", key)
            return False

    async def exists(self, key: str) -> bool:
        """
        判断 key 是否存在。

        :param key: Redis key。
        :return: 是否存在。
        """
        try:
            return bool(await self._client.exists(key))
        except RedisError:
            logger.exception("Redis exists failed, key=%s", key)
            return False

    async def expire(self, key: str, expire: int, unit: TimeUnit = TimeUnit.SECONDS) -> bool:
        """
        设置 key 过期时间。

        :param key: Redis key。
        :param expire: 过期时间，必须显式传入。
        :param unit: 过期时间单位，默认秒。
        :return: 是否设置成功。
        """
        try:
            return bool(await self._client.expire(key, self._to_seconds(expire, unit)))
        except (RedisError, ValueError):
            logger.exception("Redis expire failed, key=%s", key)
            return False

    async def scan_keys(self, pattern: str) -> List[str]:
        """
        使用 scan 查询匹配 key。

        :param pattern: scan match pattern。
        :return: 匹配 key 列表。
        """
        keys = []
        try:
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key)
        except RedisError:
            logger.exception("Redis scan_keys failed, pattern=%s", pattern)
            return []
        return keys

    async def ping(self) -> bool:
        """
        检查 Redis 连接是否可用。

        :return: Redis ping 是否成功。
        """
        return bool(await self._client.ping())

    async def eval(
        self,
        script: str,
        num_keys: int,
        keys: Sequence[str],
        args: Sequence[str],
    ) -> Optional[int]:
        """
        执行 Lua 脚本并返回整型结果。

        :param script: Lua 脚本。
        :param num_keys: key 数量。
        :param keys: key 列表。
        :param args: 参数列表。
        :return: 执行结果；异常时返回 ``None``。
        """
        result = await self.eval_raw(script, num_keys, keys, args)
        if result is None:
            return None
        if isinstance(result, bool):
            return 1 if result else 0
        if isinstance(result, int):
            return result
        try:
            return int(result)
        except (TypeError, ValueError):
            return None

    async def eval_raw(
        self,
        script: str,
        num_keys: int,
        keys: Sequence[str],
        args: Sequence[str],
    ) -> Any:
        """
        执行 Lua 脚本并返回原始结果。

        :param script: Lua 脚本。
        :param num_keys: key 数量。
        :param keys: key 列表。
        :param args: 参数列表。
        :return: 执行结果；异常时返回 ``None``。
        """
        payload = list(keys) + list(args)
        try:
            return await self._client.eval(script, num_keys, *payload)
        except RedisError:
            logger.exception("Redis eval failed")
            return None

    def get_connection_info_for_log(self) -> Dict[str, Any]:
        """
        获取可安全打印的 Redis 连接信息。

        :return: 不包含密码的连接信息。
        """
        return {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
        }

    async def close(self) -> None:
        """
        关闭底层连接。

        :return: 无。
        """
        await self._client.aclose()

    def _to_seconds(self, expire: int, unit: TimeUnit) -> int:
        """
        将过期时间转换为秒。

        :param expire: 过期时间。
        :param unit: 时间单位。
        :return: 秒数。
        """
        if expire <= 0:
            raise ValueError("expire must be positive")
        if unit == TimeUnit.MINUTES:
            return expire * 60
        if unit == TimeUnit.HOURS:
            return expire * 3600
        return expire

    def _decode_json(self, value: Optional[str], key: str) -> Optional[Any]:
        """
        反序列化 JSON 字符串。

        :param value: JSON 字符串。
        :param key: 日志定位 key。
        :return: 反序列化对象。
        """
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            logger.warning("Redis JSON decode failed, key=%s", key)
            return None


redis_client = RedisClient()
