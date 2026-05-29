"""房间锁与托管任务关键行为测试。"""

import asyncio

from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock
from app.modules.room.realtime_service import collect_human_player_ids
from app.modules.room.schemas import RoomMemberResponse


class _FakeRedisClient(object):
    """用于分布式锁测试的最小 Redis 假实现。"""

    def __init__(self) -> None:
        self._store = {}

    async def set_string_if_absent(self, key, value, expire):
        if key in self._store:
            return False
        self._store[key] = value
        return True

    async def eval(self, script, num_keys, keys, args):
        key = keys[0]
        token = args[0]
        if self._store.get(key) == token:
            self._store.pop(key, None)
            return 1
        return 0


def test_distributed_lock_release_requires_same_token() -> None:
    """只有持有 token 的句柄可以释放锁。"""
    redis = _FakeRedisClient()
    lock = RedisDistributedLock(redis)

    async def _run():
        first = await lock.acquire("room:1", ttl_seconds=8, wait_timeout_ms=0, owner_hint="user:a")
        assert first.token.startswith("user:a:")
        assert await lock.release("room:1", "wrong-token") is False
        assert await first.release() is True
        second = await lock.acquire("room:1", ttl_seconds=8, wait_timeout_ms=0, owner_hint="user:b")
        assert second.token.startswith("user:b:")
        await second.release()

    asyncio.run(_run())


def test_distributed_lock_timeout_when_lock_is_held() -> None:
    """锁已被占用且等待超时后抛出获取失败异常。"""
    redis = _FakeRedisClient()
    lock = RedisDistributedLock(redis)

    async def _run():
        handle = await lock.acquire("room:2", ttl_seconds=8, wait_timeout_ms=0)
        try:
            raised = False
            try:
                await lock.acquire("room:2", ttl_seconds=8, wait_timeout_ms=20, retry_interval_ms=10)
            except LockAcquireError:
                raised = True
            assert raised is True
        finally:
            await handle.release()

    asyncio.run(_run())


def test_collect_human_player_ids_excludes_shell_and_ai() -> None:
    """推送目标应排除 AI 与 shell 成员，保留 active 托管成员。"""
    members = [
        RoomMemberResponse(
            playerId="u-active",
            nickname="u-active",
            joinedAt=1,
            isAi=False,
            isManaged=True,
            managedMode="active",
        ),
        RoomMemberResponse(
            playerId="u-shell",
            nickname="u-shell",
            joinedAt=2,
            isAi=False,
            isManaged=True,
            managedMode="shell",
        ),
        RoomMemberResponse(
            playerId="u-normal",
            nickname="u-normal",
            joinedAt=3,
            isAi=False,
            isManaged=False,
            managedMode=None,
        ),
        RoomMemberResponse(
            playerId="ai-1",
            nickname="ai-1",
            joinedAt=4,
            isAi=True,
            isManaged=False,
            managedMode=None,
        ),
    ]
    assert collect_human_player_ids(members) == ["u-active", "u-normal"]


