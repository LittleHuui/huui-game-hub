"""分布式锁能力。"""

from app.core.lock.distributed_lock import (
    LockAcquireError,
    LockHandle,
    RedisDistributedLock,
    distributed_lock,
)

__all__ = [
    "LockAcquireError",
    "LockHandle",
    "RedisDistributedLock",
    "distributed_lock",
]
