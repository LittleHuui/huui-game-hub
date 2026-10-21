"""房间自动推进任务执行服务。"""

import logging

from app.core.clock import Clock, system_clock
from app.core.id_utils import generate_server_id
from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock
from app.modules.room.auto_advance_task_service import (
    AutoAdvanceTaskSubmitResult,
    RoomAutoAdvanceTask,
)
from app.modules.room.game_completion_planner import GameCompletionPlanner
from app.modules.room.game_presentation_service import GamePresentationService
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.repository import RoomRepository
from app.modules.room.room_game_commit_service import RoomGameCommitService
from app.modules.room.room_platform_support import acquire_auto_advance_room_lock
from app.modules.room.task_error_support import (
    auto_advance_submit_result_from_exception,
    temporary_reason_from_exception,
    wrap_redis_operation_error,
)
from app.modules.room.task_errors import (
    TaskObsoleteError,
    TaskObsoleteReason,
    TaskTemporaryInfrastructureError,
    TaskTemporaryReason,
)
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService

logger = logging.getLogger(__name__)


class RoomAutoAdvanceExecutionService(object):
    """自动推进任务锁内校验与运行时无动作推进。"""

    def __init__(
        self,
        repository: RoomRepository,
        lock_service: RedisDistributedLock,
        runtime_service: StrategyTurnRuntimeService,
        state_reader: GameStateReader,
        commit_service: RoomGameCommitService,
        completion_planner: GameCompletionPlanner,
        presentation_service: GamePresentationService,
        clock: Clock = system_clock,
    ) -> None:
        """
        初始化自动推进执行服务。

        :param repository: 房间 Redis 仓库。
        :param lock_service: 分布式锁服务。
        :param runtime_service: 策略回合制运行时服务。
        :param state_reader: 运行时读取端口。
        :param commit_service: 原子提交编排服务。
        :param completion_planner: 终局规划服务。
        :param presentation_service: 对局展示服务。
        :param clock: 可注入时钟。
        """
        self._repository = repository
        self._lock_service = lock_service
        self._runtime_service = runtime_service
        self._state_reader = state_reader
        self._commit_service = commit_service
        self._completion_planner = completion_planner
        self._presentation_service = presentation_service
        self._clock = clock

    async def submit_auto_advance_task(
        self,
        task: RoomAutoAdvanceTask,
    ) -> AutoAdvanceTaskSubmitResult:
        """
        自动推进任务入口：锁内校验并调用运行时无动作推进。

        :param task: 自动推进任务。
        :return: 自动推进任务执行结果。
        """
        try:
            return await self._submit_internal(task)
        except (TaskObsoleteError, TaskTemporaryInfrastructureError, LockAcquireError) as exc:
            return auto_advance_submit_result_from_exception(exc)
        except Exception as exc:
            logger.exception(
                "auto advance execute failed, roomId=%s taskId=%s",
                task.roomId,
                task.taskId,
            )
            return auto_advance_submit_result_from_exception(
                TaskTemporaryInfrastructureError(
                    temporary_reason_from_exception(exc),
                    cause=exc,
                ),
            )

    async def _submit_internal(
        self,
        task: RoomAutoAdvanceTask,
    ) -> AutoAdvanceTaskSubmitResult:
        """
        自动推进执行主流程。

        :param task: 自动推进任务。
        :return: 自动推进任务执行结果。
        """
        normalized_room_id = str(task.roomId or "").strip()
        try:
            lock_handle = await acquire_auto_advance_room_lock(
                self._lock_service,
                normalized_room_id,
                task.taskId,
            )
        except LockAcquireError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.LOCK_UNAVAILABLE, cause=exc)
        async with lock_handle:
            meta = await self._repository.get_meta_for_task(normalized_room_id)
            if meta is None:
                raise TaskObsoleteError(TaskObsoleteReason.ROOM_NOT_PLAYING)
            if str(meta.get("status", "")).strip() != "playing":
                raise TaskObsoleteError(TaskObsoleteReason.ROOM_NOT_PLAYING)
            current_version = await self._repository.get_game_version_for_task(normalized_room_id)
            if current_version is None:
                current_version = 0
            if int(current_version) != int(task.expectedVersion):
                raise TaskObsoleteError(TaskObsoleteReason.VERSION_CHANGED)
            consistent = await self._state_reader.load_consistent_for_task(normalized_room_id)
            snapshot = consistent.snapshot
            if snapshot.isGameOver is True:
                raise TaskObsoleteError(TaskObsoleteReason.GAME_ALREADY_OVER)
            state = snapshot.state if isinstance(snapshot.state, dict) else {}
            current_phase = str(state.get("phase", "")).strip()
            if current_phase != str(task.expectedPhase or "").strip():
                raise TaskObsoleteError(TaskObsoleteReason.PHASE_CHANGED)
            apply_result = self._runtime_service.advance_snapshot(snapshot)
            frame_events = self._presentation_service.filter_game_view_events(apply_result.newEvents)
            final_snapshot = apply_result.snapshot
            committed_at = int(self._clock.now_ms())
            outbox_records = None
            next_room_meta = dict(meta)
            next_room_meta["status"] = "playing"
            next_room_meta["updatedAt"] = committed_at
            terminal_snapshot = final_snapshot
            members = await self._repository.list_players_for_task(normalized_room_id)

            if bool(final_snapshot.isGameOver):
                completion_plan = self._completion_planner.build_plan(
                    meta,
                    members,
                    final_snapshot,
                    committed_at,
                )
                terminal_snapshot = completion_plan.terminalSnapshot
                next_room_meta = completion_plan.nextRoomMeta
                commit_id = generate_server_id("commit")
                next_version = int(current_version) + 1
                outbox_records = self._commit_service.build_terminal_outbox_records(
                    normalized_room_id,
                    completion_plan,
                    next_version,
                    commit_id,
                    committed_at,
                )

            outbox_reason = None if bool(final_snapshot.isGameOver) else "afterAutoAdvance"
            try:
                commit_result = await self._commit_service.commit_state_change(
                    room_id=normalized_room_id,
                    expected_version=int(current_version),
                    next_snapshot=terminal_snapshot,
                    next_room_meta=next_room_meta,
                    delete_runtime=False,
                    outbox_reason=outbox_reason,
                    outbox_records=outbox_records,
                    committed_at=committed_at,
                )
            except Exception as exc:
                raise wrap_redis_operation_error(exc)
            version = int(commit_result.committedVersion or (int(current_version) + 1))
            stamped_snapshot = terminal_snapshot.model_copy(update={"commitVersion": version})
            room_version = await self._repository.get_room_version_for_task(normalized_room_id)
            if room_version is None:
                room_version = 0
            try:
                await self._repository.refresh_room_ttl(normalized_room_id)
                await self._presentation_service.push_room_and_game_view(
                    normalized_room_id,
                    next_room_meta,
                    members,
                    stamped_snapshot,
                    version,
                    frame_events,
                    bool(final_snapshot.isGameOver),
                    int(room_version),
                )
            except Exception as exc:
                logger.exception(
                    "auto advance game view push failed, roomId=%s expectedVersion=%s committedVersion=%s phase=%s taskId=%s",
                    normalized_room_id,
                    int(task.expectedVersion),
                    version,
                    str(task.expectedPhase or ""),
                    str(task.taskId or ""),
                )
                del exc
            return AutoAdvanceTaskSubmitResult(status="done")
