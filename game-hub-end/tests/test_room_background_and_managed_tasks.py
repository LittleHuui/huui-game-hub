"""房间后台初始化、presence 职责与 Redis 托管任务测试。"""

import asyncio
import inspect
import json
from typing import Any, Dict, List, Optional, Sequence

import pytest

from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock
from app.core.redis.redis_keys import RedisKeys
from app.modules.room import background_coordinator, managed_task_service as managed_module
from app.modules.room.background_coordinator import (
    _build_room_module_service,
    get_background_room_module_service,
    initialize_room_background,
)
from app.modules.room.deps import get_distributed_lock
from app.modules.room.managed_task_repository import (
    MANAGED_TASK_VISIBILITY_TIMEOUT_MS,
    ManagedTaskRepository,
)
from app.modules.room.managed_task_service import (
    MANAGED_LOCK_RETRY_DELAYS_MS,
    MANAGED_TASK_MAX_CLAIM_PER_TICK,
    ManagedTaskSubmitResult,
    ManagedTurnTask,
    ManagedTurnTaskService,
)
from app.modules.room.module_service import RoomModuleService
from app.modules.room.presence_service import RoomPresenceService, room_presence_service
from app.modules.room.schemas import RoomActionRequest


class _FakeRedisClient(object):
    """托管任务与分布式锁测试用 Redis 假实现。"""

    def __init__(self) -> None:
        self._strings = {}
        self._zsets = {}
        self._fail_zadd = False

    async def set_string_if_absent(self, key, value, expire):
        del expire
        if key in self._strings:
            return False
        self._strings[key] = value
        return True

    async def set_string(self, key, value, expire):
        del expire
        self._strings[key] = value
        return True

    async def set_json(self, key, value, expire):
        del expire
        self._strings[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return True

    async def get_json(self, key):
        raw = self._strings.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        return dict(data)

    async def zadd(self, key, score, value, expire):
        del expire
        if self._fail_zadd:
            return False
        bucket = self._zsets.setdefault(key, {})
        bucket[value] = float(score)
        return True

    async def zrem(self, key, value):
        bucket = self._zsets.get(key, {})
        if value in bucket:
            del bucket[value]
            return True
        return False

    async def zrangebyscore(self, key, min_score, max_score, start=0, num=1):
        bucket = self._zsets.get(key, {})
        candidates = [
            member
            for member, score in bucket.items()
            if float(min_score) <= score <= float(max_score)
        ]
        candidates.sort(key=lambda member: bucket[member])
        return candidates[start : start + num]

    async def zrange(self, key, start, end):
        bucket = self._zsets.get(key, {})
        members = sorted(bucket.keys(), key=lambda member: bucket[member])
        if end < 0:
            end = len(members) + end
        return members[start : end + 1]

    async def eval(self, script, num_keys, keys, args):
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
            return 0

    async def eval_raw(self, script, num_keys, keys, args):
        del num_keys
        if script and "SET', KEYS[1], ARGV[1], 'NX'" in script:
            return self._eval_enqueue(keys, args)
        if script and "task['status'] = 'running'" in script:
            return self._eval_claim_due(keys, args)
        if script and "task['status'] = 'pending'" in script and "ZRANGEBYSCORE', KEYS[1]" in script:
            return self._eval_recover_stale(keys, args)
        if script and "redis.call('ZADD', KEYS[3], ARGV[3], ARGV[1])" in script:
            return self._eval_release_to_due(keys, args)
        if script and "redis.call('SET', KEYS[1], ARGV[2]" in script and "redis.call('ZREM', KEYS[3]" in script:
            return self._eval_finalize(keys, args)
        if script and script.count("ZREM") >= 2 and "SET" not in script and "ZADD" not in script:
            return self._eval_cleanup_orphan(keys, args)
        if script and "ZRANGEBYSCORE" in script:
            return self._eval_claim_due_legacy(keys, args)
        key = keys[0]
        token = args[0]
        if self._strings.get(key) == token:
            self._strings.pop(key, None)
            return 1
        return 0

    def _eval_enqueue(self, keys, args):
        dedupe_key, task_key, due_key = keys
        task_id = args[0]
        task_json = args[2]
        execute_after_ms = float(args[4])
        if dedupe_key in self._strings:
            return 2
        self._strings[dedupe_key] = task_id
        self._strings[task_key] = task_json
        if self._fail_zadd:
            self._strings.pop(dedupe_key, None)
            self._strings.pop(task_key, None)
            return 0
        bucket = self._zsets.setdefault(due_key, {})
        bucket[task_id] = execute_after_ms
        return 1

    def _eval_claim_due(self, keys, args):
        due_key, processing_key = keys
        max_score = float(args[0])
        visibility_deadline = float(args[1])
        task_prefix = args[3]
        updated_at = int(args[4])
        bucket = self._zsets.get(due_key, {})
        candidates = [
            (member, score)
            for member, score in bucket.items()
            if score <= max_score
        ]
        if not candidates:
            return ""
        candidates.sort(key=lambda item: (item[1], item[0]))
        task_id, _score = candidates[0]
        bucket.pop(task_id, None)
        processing = self._zsets.setdefault(processing_key, {})
        processing[task_id] = visibility_deadline
        task_key = "{0}{1}".format(task_prefix, task_id)
        task_json = self._strings.get(task_key)
        if not task_json:
            processing.pop(task_id, None)
            return "ORPHAN:{0}".format(task_id)
        try:
            task_data = json.loads(task_json)
        except (TypeError, ValueError):
            processing.pop(task_id, None)
            return "ORPHAN:{0}".format(task_id)
        status = str(task_data.get("status", "")).strip()
        if status in ("done", "skipped", "failed"):
            processing.pop(task_id, None)
            return "ORPHAN:{0}".format(task_id)
        if status not in ("pending", "running"):
            processing.pop(task_id, None)
            bucket.pop(task_id, None)
            return "ORPHAN:{0}".format(task_id)
        task_data["status"] = "running"
        task_data["updatedAt"] = updated_at
        self._strings[task_key] = json.dumps(task_data, ensure_ascii=False, separators=(",", ":"))
        return self._strings[task_key]

    def _eval_release_to_due(self, keys, args):
        task_key, processing_key, due_key = keys
        task_id = args[0]
        task_json = args[1]
        execute_after_ms = float(args[2])
        self._strings[task_key] = task_json
        due_bucket = self._zsets.setdefault(due_key, {})
        due_bucket[task_id] = execute_after_ms
        processing_bucket = self._zsets.get(processing_key, {})
        processing_bucket.pop(task_id, None)
        return 1

    def _eval_finalize(self, keys, args):
        task_key, processing_key, due_key = keys
        task_id = args[0]
        task_json = args[1]
        self._strings[task_key] = task_json
        processing_bucket = self._zsets.get(processing_key, {})
        processing_bucket.pop(task_id, None)
        due_bucket = self._zsets.get(due_key, {})
        due_bucket.pop(task_id, None)
        return 1

    def _eval_cleanup_orphan(self, keys, args):
        processing_key, due_key = keys
        task_id = args[0]
        processing_bucket = self._zsets.get(processing_key, {})
        processing_bucket.pop(task_id, None)
        due_bucket = self._zsets.get(due_key, {})
        due_bucket.pop(task_id, None)
        return 1

    def _eval_recover_stale(self, keys, args):
        processing_key, due_key = keys
        current_time_ms = float(args[0])
        task_prefix = args[1]
        updated_at = int(args[3])
        processing_bucket = self._zsets.get(processing_key, {})
        candidates = [
            (member, score)
            for member, score in processing_bucket.items()
            if score <= current_time_ms
        ]
        if not candidates:
            return ""
        candidates.sort(key=lambda item: (item[1], item[0]))
        task_id, _score = candidates[0]
        task_key = "{0}{1}".format(task_prefix, task_id)
        task_json = self._strings.get(task_key)
        if not task_json:
            processing_bucket.pop(task_id, None)
            due_bucket = self._zsets.get(due_key, {})
            due_bucket.pop(task_id, None)
            return "ORPHAN:{0}".format(task_id)
        try:
            task_data = json.loads(task_json)
        except (TypeError, ValueError):
            processing_bucket.pop(task_id, None)
            due_bucket = self._zsets.get(due_key, {})
            due_bucket.pop(task_id, None)
            return "ORPHAN:{0}".format(task_id)
        status = str(task_data.get("status", "")).strip()
        if status in ("done", "skipped", "failed"):
            processing_bucket.pop(task_id, None)
            return "FINAL:{0}".format(task_id)
        if status not in ("pending", "running"):
            processing_bucket.pop(task_id, None)
            due_bucket = self._zsets.get(due_key, {})
            due_bucket.pop(task_id, None)
            return "ORPHAN:{0}".format(task_id)
        execute_after = float(task_data.get("executeAfterMs") or current_time_ms)
        if execute_after < current_time_ms:
            execute_after = current_time_ms
        task_data["status"] = "pending"
        task_data["updatedAt"] = updated_at
        self._strings[task_key] = json.dumps(task_data, ensure_ascii=False, separators=(",", ":"))
        due_bucket = self._zsets.setdefault(due_key, {})
        due_bucket[task_id] = execute_after
        processing_bucket.pop(task_id, None)
        return task_id

    def _eval_claim_due_legacy(self, keys, args):
        return self._eval_claim_due(
            [keys[0], RedisKeys.managed_task_processing()],
            [args[0], "0", "0", RedisKeys.managed_task(""), "0", "0"],
        )

    async def delete(self, key):
        removed = 0
        if key in self._strings:
            del self._strings[key]
            removed += 1
        return removed > 0


def _sample_task(**overrides):
    payload = {
        "taskId": "task-1",
        "roomId": "room-1",
        "gameCode": "uno",
        "playerId": "p1",
        "expectedVersion": 1,
        "expectedCurrentPlayerId": "p1",
        "executeAfterMs": 100,
        "status": "pending",
        "createdAt": 0,
        "reason": "test",
    }
    payload.update(overrides)
    return ManagedTurnTask(**payload)


def test_get_distributed_lock_name() -> None:
    """业务侧通过 get_distributed_lock 获取通用锁工具。"""
    assert get_distributed_lock() is not None
    assert inspect.isfunction(get_distributed_lock)


def test_room_module_service_init_does_not_bind_background_handlers() -> None:
    """RoomModuleService.__init__ 不再绑定全局后台 handler。"""
    init_source = inspect.getsource(RoomModuleService.__init__)
    assert "bind_submit_handler" not in init_source
    assert "bind_mark_member_shell_managed_handler" not in init_source
    assert "bind_create_managed_turn_task_handler" not in init_source


def test_background_coordinator_does_not_create_sessionlocal() -> None:
    """后台协调器不创建长期 SessionLocal。"""
    source = inspect.getsource(_build_room_module_service)
    assert "SessionLocal" not in source


def test_presence_service_only_notifies_shell_handler() -> None:
    """RoomPresenceService 不直接修改成员或创建托管任务。"""
    source = inspect.getsource(RoomPresenceService)
    assert "save_player" not in source
    assert "delete_room_cascade" not in source
    assert "create_managed_turn_task" not in source
    assert "ownerPlayerId" not in source
    assert "_notify_shell_managed" in source


@pytest.mark.asyncio
async def test_background_handlers_bound_on_initialize(monkeypatch) -> None:
    """应用启动阶段绑定后台 handler，不依赖 room API 请求。"""
    background_coordinator._initialized = False
    background_coordinator._background_module_service = None
    started = {"managed": False, "presence": False}

    async def _fake_managed_start():
        started["managed"] = True

    async def _fake_presence_start():
        started["presence"] = True

    monkeypatch.setattr(
        background_coordinator.managed_turn_task_service,
        "start",
        _fake_managed_start,
    )
    monkeypatch.setattr(
        background_coordinator.room_presence_service,
        "start",
        _fake_presence_start,
    )
    await initialize_room_background()
    assert started["managed"] is True
    assert started["presence"] is True
    assert background_coordinator.managed_turn_task_service._submit_handler is not None
    assert room_presence_service._mark_member_shell_managed_handler is not None
    service = get_background_room_module_service()
    assert service is not None
    assert service._game_service is None
    await background_coordinator.shutdown_room_background()


def test_managed_task_enqueue_writes_redis() -> None:
    """创建托管任务后写入 due zset 与 task data。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    service = ManagedTurnTaskService(repository=repository)
    task = _sample_task(taskId="task-1", expectedVersion=3, executeAfterMs=1000)

    async def _run():
        created = await service.enqueue_task(task)
        assert created.created is True
        assert RedisKeys.managed_task("task-1") in fake_redis._strings
        assert fake_redis._zsets[RedisKeys.managed_task_due()]["task-1"] == 1000.0

    asyncio.run(_run())


def test_managed_task_dedupe_by_room_player_version() -> None:
    """同 roomId + playerId + expectedVersion 不重复创建任务。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    service = ManagedTurnTaskService(repository=repository)
    task = _sample_task(taskId="task-1", expectedVersion=2)

    async def _run():
        first = await service.enqueue_task(task)
        assert first.created is True
        duplicate = task.model_copy(update={"taskId": "task-2"})
        second = await service.enqueue_task(duplicate)
        assert second.duplicated is True

    asyncio.run(_run())


def test_enqueue_failure_does_not_leave_dedupe() -> None:
    """enqueue 失败时不残留 dedupe key。"""
    fake_redis = _FakeRedisClient()
    fake_redis._fail_zadd = True
    repository = ManagedTaskRepository(fake_redis)
    task = _sample_task(taskId="task-fail", expectedVersion=5)

    async def _run():
        created = await repository.enqueue_task(
            task.roomId,
            task.playerId,
            task.expectedVersion,
            task.model_dump(),
        )
        assert created.failed is True
        dedupe_key = RedisKeys.managed_task_dedupe(task.roomId, task.playerId, task.expectedVersion)
        assert dedupe_key not in fake_redis._strings
        assert RedisKeys.managed_task("task-fail") not in fake_redis._strings

    asyncio.run(_run())


def test_claim_moves_task_to_processing() -> None:
    """领取到期任务后进入 processing zset。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    service = ManagedTurnTaskService(repository=repository)
    task = _sample_task(taskId="task-claim", executeAfterMs=10)

    async def _run():
        await service.enqueue_task(task)
        claimed = await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        assert claimed is not None
        assert claimed["taskId"] == "task-claim"
        assert claimed["status"] == "running"
        assert "task-claim" not in fake_redis._zsets.get(RedisKeys.managed_task_due(), {})
        processing = fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})
        assert "task-claim" in processing
        assert processing["task-claim"] == 100 + MANAGED_TASK_VISIBILITY_TIMEOUT_MS

    asyncio.run(_run())


def test_processing_timeout_recovers_to_due() -> None:
    """processing 可见性超时后任务恢复回 due。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    task = _sample_task(taskId="task-recover", executeAfterMs=10, status="running")

    async def _run():
        await repository.enqueue_task(
            task.roomId,
            task.playerId,
            task.expectedVersion,
            task.model_dump(),
        )
        await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        recovered = await repository.recover_stale_processing_tasks(
            100 + MANAGED_TASK_VISIBILITY_TIMEOUT_MS + 1,
        )
        assert recovered == ["task-recover"]
        assert "task-recover" in fake_redis._zsets.get(RedisKeys.managed_task_due(), {})
        assert "task-recover" not in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})
        stored = await repository.get_task("task-recover")
        assert stored["status"] == "pending"

    asyncio.run(_run())


def test_finalize_removes_processing_and_due() -> None:
    """done/skipped/failed 后任务从 processing 与 due 移除。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    task_data = _sample_task(taskId="task-done").model_dump()

    async def _run():
        await repository.enqueue_task("room-1", "p1", 1, task_data)
        await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        task_data["status"] = "done"
        fake_redis._zsets.setdefault(RedisKeys.managed_task_due(), {})["task-done"] = 50.0
        await repository.finalize_task("task-done", task_data)
        assert "task-done" not in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})
        assert "task-done" not in fake_redis._zsets.get(RedisKeys.managed_task_due(), {})
        stored = await repository.get_task("task-done")
        assert stored["status"] == "done"

    asyncio.run(_run())


def test_release_to_due_forces_pending_even_when_caller_passes_running() -> None:
    """release_to_due 忽略调用方 status，写入 pending。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    task_data = _sample_task(taskId="task-run", status="running").model_dump()

    async def _run():
        await repository.enqueue_task("room-1", "p1", 1, task_data)
        await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        task_data["status"] = "running"
        assert await repository.release_to_due("task-run", 500, task_data) is True
        stored = await repository.get_task("task-run")
        assert stored["status"] == "pending"

    asyncio.run(_run())


def test_managed_lock_retry_delays_and_timeout(monkeypatch) -> None:
    """锁冲突按 100/300/700 退避，耗尽后 lockTimeout。"""
    fake_now = {"value": 0}
    monkeypatch.setattr(managed_module, "now_ms", lambda: fake_now["value"])
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    service = ManagedTurnTaskService(repository=repository)
    task = _sample_task(taskId="task-1", executeAfterMs=0)

    async def _run():
        await repository.enqueue_task(
            task.roomId,
            task.playerId,
            task.expectedVersion,
            task.model_dump(),
        )
        await repository.claim_due_task(0, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        await service._reschedule_or_skip(task, "lockTimeout")
        stored = await repository.get_task("task-1")
        assert stored is not None
        assert stored["retryCount"] == 1
        assert stored["executeAfterMs"] == MANAGED_LOCK_RETRY_DELAYS_MS[0]
        assert "task-1" in fake_redis._zsets.get(RedisKeys.managed_task_due(), {})

        task.retryCount = 1
        fake_now["value"] = 100
        await service._reschedule_or_skip(task, "lockTimeout")
        stored = await repository.get_task("task-1")
        assert stored["retryCount"] == 2
        assert stored["executeAfterMs"] == 100 + MANAGED_LOCK_RETRY_DELAYS_MS[1]

        task.retryCount = 2
        fake_now["value"] = 400
        await service._reschedule_or_skip(task, "lockTimeout")
        stored = await repository.get_task("task-1")
        assert stored["retryCount"] == 3
        assert stored["executeAfterMs"] == 400 + MANAGED_LOCK_RETRY_DELAYS_MS[2]

        task.retryCount = 3
        await service._reschedule_or_skip(task, "lockTimeout")
        stored = await repository.get_task("task-1")
        assert stored["status"] == "skipped"
        assert stored["skipReason"] == "lockTimeout"
        assert "task-1" not in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})

    asyncio.run(_run())


def test_claim_due_task_and_execute(monkeypatch) -> None:
    """到期任务可被 worker 领取并执行。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    service = ManagedTurnTaskService(repository=repository)
    executed = []

    async def _submit_handler(task):
        executed.append(task.taskId)
        return ManagedTaskSubmitResult(status="done")

    service.bind_submit_handler(_submit_handler)
    task = _sample_task(taskId="task-due", executeAfterMs=10)

    class _AlwaysAcquireLock(RedisDistributedLock):
        async def acquire(self, key, ttl_seconds, wait_timeout_ms=0, retry_interval_ms=60, owner_hint=None):
            del key, ttl_seconds, wait_timeout_ms, retry_interval_ms, owner_hint
            return _LockStub()

    class _LockStub(object):
        async def release(self):
            return True

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            await self.release()

    service._lock_service = _AlwaysAcquireLock(fake_redis)

    async def _run():
        await service.enqueue_task(task)
        claimed = await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        assert claimed is not None
        assert claimed["status"] == "running"
        await service._process_claimed_task(claimed)
        assert executed == ["task-due"]
        stored = await repository.get_task("task-due")
        assert stored["status"] == "done"
        assert "task-due" not in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})

    asyncio.run(_run())


def test_room_running_lock_blocks_parallel_same_room(monkeypatch) -> None:
    """同一 roomId 托管任务串行执行。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    lock = RedisDistributedLock(fake_redis)
    service = ManagedTurnTaskService(repository=repository, lock_service=lock)
    running = {"count": 0, "max": 0}

    async def _submit_handler(task):
        del task
        running["count"] += 1
        running["max"] = max(running["max"], running["count"])
        await asyncio.sleep(0.05)
        running["count"] -= 1
        return ManagedTaskSubmitResult(status="done")

    service.bind_submit_handler(_submit_handler)
    monkeypatch.setattr(managed_module, "now_ms", lambda: 0)

    async def _enqueue(task_id, expected_version):
        task = _sample_task(
            taskId=task_id,
            roomId="room-same",
            expectedVersion=expected_version,
            executeAfterMs=0,
        )
        await service.enqueue_task(task)

    async def _run():
        await _enqueue("task-a", 1)
        await _enqueue("task-b", 2)
        claimed_a = await repository.claim_due_task(0, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        claimed_b = await repository.claim_due_task(0, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        await asyncio.gather(
            service._process_claimed_task(claimed_a),
            service._process_claimed_task(claimed_b),
        )
        assert running["max"] == 1

    asyncio.run(_run())


def test_different_room_tasks_can_run_in_parallel(monkeypatch) -> None:
    """不同 roomId 托管任务可分别执行。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    lock = RedisDistributedLock(fake_redis)
    service = ManagedTurnTaskService(repository=repository, lock_service=lock)
    concurrent = {"count": 0, "max": 0}

    async def _submit_handler(task):
        del task
        concurrent["count"] += 1
        concurrent["max"] = max(concurrent["max"], concurrent["count"])
        await asyncio.sleep(0.05)
        concurrent["count"] -= 1
        return ManagedTaskSubmitResult(status="done")

    service.bind_submit_handler(_submit_handler)
    monkeypatch.setattr(managed_module, "now_ms", lambda: 0)

    async def _run():
        for room_suffix in ("a", "b"):
            task = _sample_task(
                taskId="task-{0}".format(room_suffix),
                roomId="room-{0}".format(room_suffix),
                executeAfterMs=0,
            )
            await service.enqueue_task(task)
        claimed_a = await repository.claim_due_task(0, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        claimed_b = await repository.claim_due_task(0, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        await asyncio.gather(
            service._process_claimed_task(claimed_a),
            service._process_claimed_task(claimed_b),
        )
        assert concurrent["max"] == 2

    asyncio.run(_run())


def test_pending_task_survives_service_restart() -> None:
    """领取后任务在 processing 中，超时后可恢复扫描。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    first_service = ManagedTurnTaskService(repository=repository)
    task = _sample_task(taskId="task-restart", executeAfterMs=50)

    async def _run():
        await first_service.enqueue_task(task)
        ManagedTurnTaskService(repository=repository)
        claimed = await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        assert claimed is not None
        assert claimed["taskId"] == "task-restart"
        assert "task-restart" in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})
        recovered = await repository.recover_stale_processing_tasks(
            100 + MANAGED_TASK_VISIBILITY_TIMEOUT_MS + 1,
        )
        assert "task-restart" in recovered

    asyncio.run(_run())


def test_client_seq_schema_not_idempotent() -> None:
    """clientSeq 字段描述不再声明已实现幂等。"""
    description = RoomActionRequest.model_fields["clientSeq"].description or ""
    assert "幂等" not in description


def test_room_module_service_uses_scoped_game_service_when_none() -> None:
    """game_service 为空时使用短生命周期会话。"""
    source = inspect.getsource(RoomModuleService._game_service_scope)
    assert "session_scope" in source
    assert "build_game_module_service" in source


def test_release_to_due_atomic_keeps_task_in_due() -> None:
    """release_to_due 原子恢复后任务在 due 中，不会从 processing 移除后丢失。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    task_data = _sample_task(taskId="task-release", executeAfterMs=500).model_dump()

    async def _run():
        await repository.enqueue_task("room-1", "p1", 1, task_data)
        await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        task_data["status"] = "pending"
        task_data["executeAfterMs"] = 600
        released = await repository.release_to_due("task-release", 600, task_data)
        assert released is True
        assert "task-release" in fake_redis._zsets.get(RedisKeys.managed_task_due(), {})
        assert "task-release" not in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})

    asyncio.run(_run())


def test_release_to_due_rejects_terminal_status() -> None:
    """done/skipped/failed 任务不能 release 回 due。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    task_data = _sample_task(taskId="task-done", status="done").model_dump()

    async def _run():
        await repository.enqueue_task("room-1", "p1", 1, task_data)
        await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        released = await repository.release_to_due("task-done", 600, task_data)
        assert released is False

    asyncio.run(_run())


def test_claim_cleans_orphan_due_entry() -> None:
    """task data 缺失时 claim 清理脏 due/processing 项。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    due_key = RedisKeys.managed_task_due()
    fake_redis._zsets[due_key] = {"orphan-task": 10.0}

    async def _run():
        claimed = await repository.claim_due_task(100, MANAGED_TASK_VISIBILITY_TIMEOUT_MS)
        assert claimed is None
        assert "orphan-task" not in fake_redis._zsets.get(due_key, {})
        assert "orphan-task" not in fake_redis._zsets.get(RedisKeys.managed_task_processing(), {})

    asyncio.run(_run())


def test_tick_once_claims_at_most_max_per_tick(monkeypatch) -> None:
    """_tick_once 单轮最多领取 MANAGED_TASK_MAX_CLAIM_PER_TICK 个任务。"""
    fake_redis = _FakeRedisClient()
    repository = ManagedTaskRepository(fake_redis)
    service = ManagedTurnTaskService(repository=repository)
    created_tasks = []

    async def _submit_handler(task):
        created_tasks.append(task.taskId)
        return ManagedTaskSubmitResult(status="done")

    service.bind_submit_handler(_submit_handler)
    monkeypatch.setattr(managed_module, "now_ms", lambda: 0)

    async def _run():
        total = MANAGED_TASK_MAX_CLAIM_PER_TICK + 5
        for index in range(total):
            task = _sample_task(
                taskId="task-{0}".format(index),
                expectedVersion=index + 1,
                executeAfterMs=0,
            )
            await service.enqueue_task(task)
        await service._tick_once()
        await asyncio.sleep(0.1)
        assert len(created_tasks) <= MANAGED_TASK_MAX_CLAIM_PER_TICK

    asyncio.run(_run())


def test_presence_service_has_no_disconnect_shell_handler() -> None:
    """RoomPresenceService 不再在 disconnect 时直接 shell。"""
    source = inspect.getsource(RoomPresenceService)
    assert "handle_disconnect" not in source
    assert '"disconnect"' not in source
