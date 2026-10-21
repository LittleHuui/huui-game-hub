"""Redis 异步客户端工具封装。"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis.redis_errors import RedisOperationError
from app.core.redis.redis_constants import TimeUnit

logger = logging.getLogger(__name__)
REDIS_CONNECT_TIMEOUT_SECONDS = 3
REDIS_IO_TIMEOUT_SECONDS = 5


class RedisClient(object):
    """面向业务层的 Redis 数据结构操作工具。"""

    def __init__(self, client: Optional[Redis] = None) -> None:
        """
        初始化 Redis 工具。

        :param client: 可选底层 Redis client，便于测试注入。
        """
        self._injected_client = client is not None
        self._provided_client = client
        self._provided_client_loop = None  # type: Optional[asyncio.AbstractEventLoop]
        self._clients_by_loop = {}  # type: Dict[asyncio.AbstractEventLoop, Redis]

    @property
    def _client(self) -> Redis:
        """
        获取当前运行事件循环专属的底层客户端。

        redis.asyncio 的连接、Future 与 Pub/Sub 都绑定创建和使用它们的事件循环。
        单体应用的 lifespan、请求和后台任务运行在同一循环，因此复用同一客户端；
        测试或嵌入式运行环境切换循环时必须创建独立客户端，不能复用已绑定的连接。
        :return: 当前事件循环可安全使用的 Redis 客户端。
        """
        return self._get_client_for_running_loop()

    def _get_client_for_running_loop(self) -> Redis:
        """
        返回当前运行循环的客户端，并丢弃已关闭循环的客户端引用。

        已关闭循环上的异步连接不能在当前循环中关闭或复用；移除引用后由该循环
        的关闭过程释放其底层资源，避免跨循环等待 Future。
        :return: 当前运行循环对应的客户端。
        """
        loop = asyncio.get_running_loop()
        self._discard_closed_loop_clients(loop)
        client = self._clients_by_loop.get(loop)
        if client is not None:
            return client
        if self._injected_client:
            if self._provided_client_loop is None:
                self._provided_client_loop = loop
                self._clients_by_loop[loop] = self._provided_client
                return self._provided_client
            raise RuntimeError("injected Redis client is bound to a different event loop")
        client = self._create_client()
        self._clients_by_loop[loop] = client
        return client

    def _discard_closed_loop_clients(self, current_loop: asyncio.AbstractEventLoop) -> None:
        """
        清理已关闭循环持有的客户端引用。

        不能在另一个循环中调用这些客户端的 ``aclose``，否则 Redis 内部 Future
        会再次触发跨循环错误。运行中的其他循环不会被影响。
        :param current_loop: 当前正在运行的事件循环。
        :return: 无。
        """
        for loop in list(self._clients_by_loop):
            if loop is current_loop or not loop.is_closed():
                continue
            self._clients_by_loop.pop(loop, None)
            if self._provided_client_loop is loop:
                self._provided_client_loop = None

    def _create_client(self) -> Redis:
        """
        创建底层 Redis 异步客户端。

        :return: Redis 客户端实例。
        """
        return Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=settings.REDIS_DECODE_RESPONSES,
            socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=REDIS_IO_TIMEOUT_SECONDS,
        )

    async def reconnect(self) -> None:
        """
        关闭旧连接并创建新底层客户端（跨事件循环或应用重启场景）。

        :return: 无。
        """
        if self._injected_client:
            return
        loop = asyncio.get_running_loop()
        self._discard_closed_loop_clients(loop)
        previous = self._clients_by_loop.pop(loop, None)
        if previous is not None:
            try:
                await previous.aclose()
            except Exception:
                logger.debug("Redis aclose during reconnect ignored", exc_info=True)
        self._clients_by_loop[loop] = self._create_client()

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

    async def get_string_strict(self, key: str) -> Optional[str]:
        """
        严格读取字符串：key 不存在返回 ``None``，Redis 失败抛 ``RedisOperationError``。

        :param key: Redis key。
        :return: 字符串值；不存在时返回 ``None``。
        :raises RedisOperationError: Redis 不可用时抛出。
        """
        try:
            return await self._client.get(key)
        except RedisError as exc:
            logger.exception("Redis get_string_strict failed, key=%s", key)
            raise RedisOperationError("redis get_string failed") from exc

    async def get_json_strict(self, key: str) -> Optional[Any]:
        """
        严格读取 JSON：key 不存在返回 ``None``，Redis 失败抛 ``RedisOperationError``。

        :param key: Redis key。
        :return: 反序列化对象；不存在或格式非法时返回 ``None``。
        :raises RedisOperationError: Redis 不可用时抛出。
        """
        value = await self.get_string_strict(key)
        return self._decode_json(value, key)

    async def hgetall_json_strict(self, key: str) -> Dict[str, Any]:
        """
        严格读取 hash 全部 JSON 字段；Redis 失败抛 ``RedisOperationError``。

        :param key: Redis key。
        :return: 字段名到 JSON 对象的映射。
        :raises RedisOperationError: Redis 不可用时抛出。
        """
        try:
            raw = await self._client.hgetall(key)
        except RedisError as exc:
            logger.exception("Redis hgetall_json_strict failed, key=%s", key)
            raise RedisOperationError("redis hgetall failed") from exc
        result = {}
        for field, value in raw.items():
            decoded = self._decode_json(value, "{0}:{1}".format(key, field))
            if decoded is not None:
                result[str(field)] = decoded
        return result

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

    async def scan_keys_page(
        self,
        pattern: str,
        cursor: int = 0,
        count: int = 100,
    ) -> Tuple[int, List[str]]:
        """
        使用 SCAN 分页查询匹配 key（禁止 KEYS 全库扫描）。

        :param pattern: scan match pattern。
        :param cursor: 当前游标；0 表示新一轮扫描起点。
        :param count: 单次 SCAN 建议返回 key 数量。
        :return: ``(下一游标, 本批 key 列表)``；游标为 0 表示本轮扫描结束。
        """
        try:
            next_cursor, keys = await self._client.scan(
                cursor=int(cursor),
                match=pattern,
                count=max(1, int(count)),
            )
            return int(next_cursor), list(keys)
        except RedisError:
            logger.exception(
                "Redis scan_keys_page failed, pattern=%s cursor=%s",
                pattern,
                cursor,
            )
            return 0, []

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
        if self._injected_client:
            return
        loop = asyncio.get_running_loop()
        self._discard_closed_loop_clients(loop)
        client = self._clients_by_loop.pop(loop, None)
        if client is not None:
            await client.aclose()

    async def publish_json(self, channel: str, payload: Dict[str, Any]) -> int:
        """
        发布 JSON 格式的跨进程事件。
        :param channel: Redis 发布频道。
        :param payload: 可序列化事件载荷。
        :return: 实际订阅者数量。
        """
        try:
            result = await self._client.publish(
                str(channel or "").strip(),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
            return int(result or 0)
        except (RedisError, TypeError, ValueError):
            logger.exception("Redis publish_json failed, channel=%s", channel)
            return 0

    async def subscribe_json(self, channel: str) -> Any:
        """
        创建 JSON 频道订阅对象。
        :param channel: Redis 发布频道。
        :return: 底层订阅对象；调用方负责关闭。
        """
        pubsub = self._client.pubsub()
        try:
            await pubsub.subscribe(str(channel or "").strip())
        except BaseException:
            await pubsub.aclose()
            raise
        return pubsub

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
