"""Redis 分布式锁工具。"""

import asyncio
import time
import uuid
from typing import Optional

from app.core.redis.redis_client import RedisClient, redis_client

_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class LockAcquireError(Exception):
    """获取分布式锁失败。"""


class LockHandle(object):
    """分布式锁上下文句柄。"""

    def __init__(self, lock: "RedisDistributedLock", key: str, token: str) -> None:
        self._lock = lock
        self.key = key
        self.token = token
        self._released = False

    async def release(self) -> bool:
        """释放锁。"""
        if self._released:
            return False
        released = await self._lock.release(self.key, self.token)
        self._released = True
        return released

    async def __aenter__(self) -> "LockHandle":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.release()


class RedisDistributedLock(object):
    """基于 Redis 的分布式锁。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        self._redis = redis

    async def acquire(
        self,
        key: str,
        ttl_seconds: int,
        wait_timeout_ms: int = 0,
        retry_interval_ms: int = 60,
        owner_hint: Optional[str] = None,
    ) -> LockHandle:
        """
        获取分布式锁并返回上下文句柄。

        :param key: 锁 key。
        :param ttl_seconds: 锁超时时间（秒）。
        :param wait_timeout_ms: 等待超时（毫秒）。
        :param retry_interval_ms: 轮询间隔（毫秒）。
        :param owner_hint: token 前缀提示。
        :return: 锁句柄。
        :raises LockAcquireError: 获取失败时抛出。
        """
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise LockAcquireError("lock key is empty")
        if int(ttl_seconds) <= 0:
            raise LockAcquireError("lock ttl must be positive")
        token = self._build_token(owner_hint)
        start_ms = self._now_ms()
        interval_ms = max(10, int(retry_interval_ms))
        while True:
            acquired = await self._redis.set_string_if_absent(
                normalized_key,
                token,
                int(ttl_seconds),
            )
            if acquired:
                return LockHandle(self, normalized_key, token)
            elapsed_ms = self._now_ms() - start_ms
            if elapsed_ms >= max(0, int(wait_timeout_ms)):
                raise LockAcquireError("lock acquire timeout")
            await asyncio.sleep(interval_ms / 1000.0)

    async def release(self, key: str, token: str) -> bool:
        """
        按 token 原子释放锁。

        :param key: 锁 key。
        :param token: 持有 token。
        :return: 是否释放成功。
        """
        normalized_key = str(key or "").strip()
        normalized_token = str(token or "").strip()
        if not normalized_key or not normalized_token:
            return False
        result = await self._redis.eval(
            _RELEASE_SCRIPT,
            1,
            [normalized_key],
            [normalized_token],
        )
        return int(result or 0) > 0

    def _build_token(self, owner_hint: Optional[str]) -> str:
        hint = str(owner_hint or "").strip()
        suffix = uuid.uuid4().hex
        if hint:
            return "{0}:{1}".format(hint, suffix)
        return "lock:{0}".format(suffix)

    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000)


distributed_lock = RedisDistributedLock()
