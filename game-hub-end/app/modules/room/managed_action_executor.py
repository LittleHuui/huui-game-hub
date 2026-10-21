"""房间托管动作执行器。"""

import logging
from typing import Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.game_action_command_service import RoomGameActionCommandService
from app.modules.room.room_action_command import RoomActionCommand
from app.modules.room.room_member_support import find_member
from app.modules.room.room_platform_support import extract_current_player_id
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.managed_task_service import ManagedTaskSubmitResult, ManagedTurnTask
from app.modules.room.repository import RoomRepository
from app.modules.room.task_error_support import (
    managed_submit_result_from_exception,
    temporary_reason_from_exception,
    wrap_redis_operation_error,
)
from app.modules.room.task_errors import (
    TaskConflictReason,
    TaskContractError,
    TaskContractReason,
    TaskExecutionConflict,
    TaskObsoleteError,
    TaskObsoleteReason,
    TaskTemporaryInfrastructureError,
    TaskTemporaryReason,
)
from app.modules.strategy_turn.decision.managed_decision_service import ManagedDecisionService
from app.modules.strategy_turn.decision.schemas import (
    CandidateContractError,
    NoLegalCandidateError,
)

logger = logging.getLogger(__name__)


class RoomManagedActionExecutor(object):
    """托管动作执行入口。"""

    ROOM_ACTION_LOCK_TTL_SECONDS = 8
    MANAGED_ACTION_LOCK_WAIT_TIMEOUT_MS = 0

    def __init__(
        self,
        repository: RoomRepository,
        lock_service: RedisDistributedLock,
        managed_decision_service: ManagedDecisionService,
        game_action_command_service: RoomGameActionCommandService,
        state_reader: Optional[GameStateReader] = None,
    ) -> None:
        """
        初始化托管动作执行器。

        :param repository: 房间 Redis 仓库。
        :param lock_service: 分布式锁服务。
        :param managed_decision_service: 托管决策服务。
        :param game_action_command_service: 房间动作命令服务。
        :param state_reader: 运行时读取端口。
        :return: 无。
        """
        self._repository = repository
        self._lock_service = lock_service
        self._managed_decision_service = managed_decision_service
        self._game_action_command_service = game_action_command_service
        self._state_reader = state_reader or GameStateReader(repository)

    async def execute(self, task: ManagedTurnTask) -> ManagedTaskSubmitResult:
        """
        执行托管动作任务。

        :param task: 托管任务。
        :return: 托管任务提交结果。
        """
        try:
            return await self._execute_internal(task)
        except (
            TaskObsoleteError,
            TaskTemporaryInfrastructureError,
            TaskContractError,
            TaskExecutionConflict,
            LockAcquireError,
        ) as exc:
            return managed_submit_result_from_exception(exc)
        except Exception as exc:
            logger.exception(
                "managed action execute failed, roomId=%s taskId=%s",
                task.roomId,
                task.taskId,
            )
            return managed_submit_result_from_exception(
                TaskTemporaryInfrastructureError(
                    temporary_reason_from_exception(exc),
                    cause=exc,
                ),
            )

    async def _execute_internal(self, task: ManagedTurnTask) -> ManagedTaskSubmitResult:
        """
        托管动作执行主流程。

        :param task: 托管任务。
        :return: 托管任务提交结果。
        """
        normalized_room_id = str(task.roomId or "").strip()
        player_id = str(task.playerId or "").strip()
        meta = await self._repository.get_meta_for_task(normalized_room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            raise TaskObsoleteError(TaskObsoleteReason.ROOM_NOT_PLAYING)
        consistent_state = await self._state_reader.load_consistent_for_task(normalized_room_id)
        snapshot = consistent_state.snapshot
        if snapshot.isGameOver is True:
            raise TaskObsoleteError(TaskObsoleteReason.GAME_ALREADY_OVER)
        current_version = int(consistent_state.gameVersion)
        if current_version != int(task.expectedVersion):
            raise TaskObsoleteError(TaskObsoleteReason.VERSION_CHANGED)
        current_player_id = extract_current_player_id(snapshot)
        if current_player_id != player_id:
            raise TaskObsoleteError(TaskObsoleteReason.CURRENT_PLAYER_CHANGED)
        members = await self._repository.list_players_for_task(normalized_room_id)
        target_member = find_member(members, player_id)
        if target_member is None or (
            not bool(target_member.get("isManaged"))
            and not bool(target_member.get("isAi"))
        ):
            raise TaskObsoleteError(TaskObsoleteReason.PLAYER_NOT_MANAGED)
        try:
            decision = self._managed_decision_service.decide(
                snapshot=snapshot,
                player_id=player_id,
                version=current_version,
                room_id=normalized_room_id,
            )
        except NoLegalCandidateError:
            raise TaskContractError(TaskContractReason.NO_LEGAL_ACTION)
        except CandidateContractError:
            raise TaskContractError(TaskContractReason.CANDIDATE_CONTRACT_ERROR)
        if decision.submission is None:
            raise TaskContractError(TaskContractReason.NO_LEGAL_ACTION)
        try:
            lock_handle = await self._acquire_managed_room_lock(normalized_room_id, task.taskId)
        except LockAcquireError as exc:
            raise TaskTemporaryInfrastructureError(TaskTemporaryReason.LOCK_UNAVAILABLE, cause=exc)
        async with lock_handle:
            refreshed = await self._state_reader.load_consistent_for_task(normalized_room_id)
            if refreshed.snapshot.isGameOver is True:
                raise TaskObsoleteError(TaskObsoleteReason.GAME_ALREADY_OVER)
            if int(refreshed.gameVersion) != current_version:
                raise TaskObsoleteError(TaskObsoleteReason.VERSION_CHANGED)
            if extract_current_player_id(refreshed.snapshot) != player_id:
                raise TaskObsoleteError(TaskObsoleteReason.CURRENT_PLAYER_CHANGED)
            await self._require_player_still_managed(normalized_room_id, player_id)
            submission = decision.submission
            try:
                await self._game_action_command_service.submit_action_locked(
                    room_id=normalized_room_id,
                    player_id=player_id,
                    command=RoomActionCommand(
                        requestId="managed:{0}".format(str(task.taskId or "").strip()),
                        baseVersion=int(task.expectedVersion),
                        submission=submission,
                    ),
                )
            except BizException as exc:
                if exc.code == ErrorCode.GAME_VIEW_VERSION_CONFLICT.code:
                    await self._handle_version_conflict(
                        normalized_room_id,
                        player_id,
                        current_version,
                        task,
                    )
                logger.exception(
                    "managed action submit rejected, roomId=%s taskId=%s playerId=%s",
                    normalized_room_id,
                    task.taskId,
                    player_id,
                )
                raise TaskContractError(TaskContractReason.RESOLVER_REJECTED)
            except Exception as exc:
                logger.exception(
                    "managed action submit failed, roomId=%s taskId=%s playerId=%s",
                    normalized_room_id,
                    task.taskId,
                    player_id,
                )
                raise wrap_redis_operation_error(exc)
            return ManagedTaskSubmitResult(status="done")

    async def _require_player_still_managed(self, room_id: str, player_id: str) -> None:
        """
        在房间动作锁内确认玩家仍由自动决策接管。

        :param room_id: 房间 ID。
        :param player_id: 当前回合玩家 ID。
        :return: 无。
        :raises TaskObsoleteError: 玩家已取消托管、重连恢复或成员不存在时抛出。
        """
        members = await self._repository.list_players_for_task(room_id)
        member = find_member(members, player_id)
        if member is None:
            raise TaskObsoleteError(TaskObsoleteReason.PLAYER_NOT_MANAGED)
        if not bool(member.get("isManaged")) and not bool(member.get("isAi")):
            raise TaskObsoleteError(TaskObsoleteReason.PLAYER_NOT_MANAGED)

    async def _handle_version_conflict(
        self,
        room_id: str,
        player_id: str,
        current_version: int,
        task: ManagedTurnTask,
    ) -> None:
        """
        提交版本冲突时重新读取权威状态并抛出过期或冲突异常。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param current_version: 锁内读取的版本。
        :param task: 托管任务。
        :return: 无。
        :raises TaskObsoleteError: 权威状态已变化。
        :raises TaskExecutionConflict: 版本仍一致，可有限重试。
        """
        latest = await self._state_reader.load_consistent_for_task(room_id)
        if int(latest.gameVersion) != int(task.expectedVersion):
            raise TaskObsoleteError(TaskObsoleteReason.VERSION_CHANGED)
        if extract_current_player_id(latest.snapshot) != player_id:
            raise TaskObsoleteError(TaskObsoleteReason.CURRENT_PLAYER_CHANGED)
        if int(latest.gameVersion) != current_version:
            raise TaskObsoleteError(TaskObsoleteReason.VERSION_CHANGED)
        raise TaskExecutionConflict(TaskConflictReason.VERSION_CONFLICT)

    async def _acquire_managed_room_lock(self, room_id: str, task_id: str):
        """
        获取托管任务房间动作锁。

        :param room_id: 房间 ID。
        :param task_id: 托管任务 ID。
        :return: 锁句柄。
        :raises LockAcquireError: 锁获取失败。
        """
        lock_key = RedisKeys.room_lock(room_id.strip())
        owner_hint = "managed:{0}".format(task_id.strip())
        return await self._lock_service.acquire(
            lock_key,
            ttl_seconds=self.ROOM_ACTION_LOCK_TTL_SECONDS,
            wait_timeout_ms=self.MANAGED_ACTION_LOCK_WAIT_TIMEOUT_MS,
            owner_hint=owner_hint,
        )
