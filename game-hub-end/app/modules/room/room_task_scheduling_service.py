"""房间托管与自动推进任务调度服务。"""

import logging
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.common.exceptions import BizException
from app.core.clock import Clock, system_clock
from app.core.id_utils import generate_server_id
from app.modules.room.auto_advance_task_service import (
    AutoAdvanceScheduleResult,
    AutoAdvanceTaskService,
    RoomAutoAdvanceTask,
)
from app.modules.room.game_state_reader import (
    GameRuntimeNotFoundException,
    GameStateReader,
    RetryableGameStateInconsistentException,
)
from app.modules.room.managed_task_service import (
    MANAGED_TURN_DELAY_MS,
    ManagedTurnTask,
    ManagedTurnTaskService,
)
from app.modules.room.repository import RoomRepository
from app.modules.room.post_turn_outbox_dispatch_result import TaskSchedulingStatus
from app.modules.room.room_member_support import find_member
from app.modules.room.room_platform_support import extract_current_player_id
from app.modules.room.task_errors import TaskObsoleteReason
from app.modules.strategy_turn.schemas import RuntimeSnapshot

logger = logging.getLogger(__name__)


class ManagedTaskCreationResult(BaseModel):
    """托管任务创建的严格内部结果。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    status: TaskSchedulingStatus
    task: Optional[ManagedTurnTask] = None


class RoomTaskSchedulingService(object):
    """实现 Outbox 与房间入口共用的任务调度端口。"""

    def __init__(
        self,
        repository: RoomRepository,
        state_reader: GameStateReader,
        managed_task_service: ManagedTurnTaskService,
        auto_advance_task_service: AutoAdvanceTaskService,
        clock: Clock,
    ) -> None:
        """
        初始化任务调度服务。

        :param repository: 房间 Redis 仓库。
        :param state_reader: 运行时读取端口。
        :param managed_task_service: 托管回合任务服务。
        :param auto_advance_task_service: 自动推进任务服务。
        :param clock: 可注入时钟。
        """
        self._repository = repository
        self._state_reader = state_reader
        self._managed_task_service = managed_task_service
        self._auto_advance_task_service = auto_advance_task_service
        self._clock = clock

    async def create_managed_turn_task(
        self,
        room_id: str,
        player_id: str,
        reason: str,
    ) -> Optional[ManagedTurnTask]:
        """
        创建托管回合任务（后端内部）。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 创建原因。
        :return: 创建的任务，未创建返回 ``None``。
        """
        result = await self._create_managed_turn_task_result(room_id, player_id, reason)
        return result.task

    async def _create_managed_turn_task_result(
        self,
        room_id: str,
        player_id: str,
        reason: str,
    ) -> ManagedTaskCreationResult:
        """
        创建托管任务并保留去重、无需创建与临时失败语义。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param reason: 创建原因。
        :return: 托管任务严格创建结果。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        if not normalized_room_id or not normalized_player_id:
            return ManagedTaskCreationResult(status=TaskSchedulingStatus.NOT_REQUIRED)
        meta = await self._repository.get_meta(normalized_room_id)
        if meta is None:
            return ManagedTaskCreationResult(status=TaskSchedulingStatus.NOT_REQUIRED)
        if str(meta.get("status", "")).strip() != "playing":
            return ManagedTaskCreationResult(status=TaskSchedulingStatus.NOT_REQUIRED)
        snapshot = (await self._state_reader.load_consistent(normalized_room_id)).snapshot
        current_player_id = extract_current_player_id(snapshot)
        if current_player_id != normalized_player_id:
            return ManagedTaskCreationResult(status=TaskSchedulingStatus.NOT_REQUIRED)
        members = await self._repository.list_players(normalized_room_id)
        target_member = find_member(members, normalized_player_id)
        if target_member is None:
            return ManagedTaskCreationResult(status=TaskSchedulingStatus.NOT_REQUIRED)
        if (not bool(target_member.get("isManaged"))) and (not bool(target_member.get("isAi"))):
            return ManagedTaskCreationResult(status=TaskSchedulingStatus.NOT_REQUIRED)
        current_version = await self._repository.get_game_version(normalized_room_id)
        if current_version is None:
            current_version = 0
        current_time = self._clock.now_ms()
        task = ManagedTurnTask(
            taskId=generate_server_id("managed-task"),
            roomId=normalized_room_id,
            gameCode=str(meta.get("gameCode", "")).strip(),
            playerId=normalized_player_id,
            expectedVersion=int(current_version),
            expectedGameVersion=int(current_version),
            expectedPhase=str(snapshot.state.get("phase", "")).strip(),
            expectedPlayerId=normalized_player_id,
            expectedCurrentPlayerId=normalized_player_id,
            executeAfterMs=current_time + MANAGED_TURN_DELAY_MS,
            status="PENDING",
            createdAt=current_time,
            reason=str(reason or "").strip() or "managedTurn",
            skipReason=None,
            retryCount=0,
            attemptCount=0,
            recoveryCount=0,
            nextAttemptAt=current_time + MANAGED_TURN_DELAY_MS,
        )
        enqueue_result = await self._managed_task_service.enqueue_task(task)
        if enqueue_result.created:
            return ManagedTaskCreationResult(
                status=TaskSchedulingStatus.SCHEDULED,
                task=task,
            )
        if enqueue_result.duplicated:
            logger.debug(
                "create_managed_turn_task dedupe hit, roomId=%s playerId=%s reason=%s",
                normalized_room_id,
                normalized_player_id,
                reason,
            )
            return ManagedTaskCreationResult(status=TaskSchedulingStatus.ALREADY_EXISTS)
        if enqueue_result.failed:
            logger.warning(
                "create_managed_turn_task enqueue failed, roomId=%s playerId=%s reason=%s",
                normalized_room_id,
                normalized_player_id,
                reason,
            )
        return ManagedTaskCreationResult(status=TaskSchedulingStatus.RETRY)

    async def create_current_player_managed_task_if_needed(
        self,
        room_id: str,
        reason: str,
    ) -> TaskSchedulingStatus:
        """
        对局进行中且当前行动玩家为托管或 AI 时，按最新房间版本创建托管任务。

        :param room_id: 房间 ID。
        :param reason: 创建原因。
        :return: 托管任务调度状态。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_reason = str(reason or "").strip() or "managedTurn"
        if not normalized_room_id:
            return TaskSchedulingStatus.NOT_REQUIRED
        meta = await self._repository.get_meta(normalized_room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            return TaskSchedulingStatus.NOT_REQUIRED
        try:
            snapshot = (await self._state_reader.load_consistent(normalized_room_id)).snapshot
        except GameRuntimeNotFoundException:
            logger.warning(
                "create_current_player_managed_task_if_needed runtime missing, roomId=%s reason=%s",
                normalized_room_id,
                normalized_reason,
            )
            return TaskSchedulingStatus.NOT_REQUIRED
        except RetryableGameStateInconsistentException:
            logger.warning(
                "create_current_player_managed_task_if_needed runtime inconsistent, "
                "roomId=%s reason=%s",
                normalized_room_id,
                normalized_reason,
            )
            return TaskSchedulingStatus.RETRY
        except BizException:
            logger.exception(
                "create_current_player_managed_task_if_needed contract invalid, "
                "roomId=%s reason=%s",
                normalized_room_id,
                normalized_reason,
            )
            return TaskSchedulingStatus.RETRY
        current_player_id = extract_current_player_id(snapshot)
        if not current_player_id:
            return TaskSchedulingStatus.NOT_REQUIRED
        members = await self._repository.list_players(normalized_room_id)
        target_member = find_member(members, current_player_id)
        if target_member is None:
            return TaskSchedulingStatus.NOT_REQUIRED
        if (not bool(target_member.get("isManaged"))) and (not bool(target_member.get("isAi"))):
            return TaskSchedulingStatus.NOT_REQUIRED
        result = await self._create_managed_turn_task_result(
            normalized_room_id,
            current_player_id,
            normalized_reason,
        )
        return result.status

    async def create_auto_advance_task_if_needed(
        self,
        room_id: str,
        snapshot: RuntimeSnapshot,
        version: int,
        reason: str,
    ) -> str:
        """
        对局阶段需自动推进时，按房间版本与阶段创建自动推进任务。

        :param room_id: 房间 ID。
        :param snapshot: 当前运行时快照。
        :param version: 当前房间版本号。
        :param reason: 创建原因。
        :return: 自动推进调度结果。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id or bool(snapshot.isGameOver):
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        meta = await self._repository.get_meta(normalized_room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        state = snapshot.state if isinstance(snapshot.state, dict) else {}
        phase_auto_advance = state.get("phaseAutoAdvance")
        if not isinstance(phase_auto_advance, dict):
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        if not bool(phase_auto_advance.get("enabled")):
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        delay_ms = phase_auto_advance.get("delayMs")
        if delay_ms is None:
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        try:
            normalized_delay_ms = int(delay_ms)
        except (TypeError, ValueError):
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        if normalized_delay_ms < 0:
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        expected_phase = str(state.get("phase", "")).strip()
        if not expected_phase:
            return AutoAdvanceScheduleResult.NOT_REQUIRED
        task_reason = str(reason or "").strip()
        if not task_reason:
            task_reason = str(phase_auto_advance.get("reason", "")).strip()
        if not task_reason:
            task_reason = "phaseAutoAdvance"
        current_time = self._clock.now_ms()
        task = RoomAutoAdvanceTask(
            taskId=generate_server_id("auto-advance-task"),
            roomId=normalized_room_id,
            gameCode=str(meta.get("gameCode", "")).strip(),
            expectedVersion=int(version),
            expectedGameVersion=int(version),
            expectedPhase=expected_phase,
            executeAfterMs=current_time + normalized_delay_ms,
            status="PENDING",
            createdAt=current_time,
            reason=task_reason,
            skipReason=None,
            retryCount=0,
            attemptCount=0,
            recoveryCount=0,
            nextAttemptAt=current_time + normalized_delay_ms,
        )
        enqueue_result = await self._auto_advance_task_service.enqueue_task(task)
        if enqueue_result.created:
            return AutoAdvanceScheduleResult.SCHEDULED
        if enqueue_result.duplicated:
            logger.debug(
                "create_auto_advance_task_if_needed dedupe hit, roomId=%s version=%s phase=%s",
                normalized_room_id,
                version,
                expected_phase,
            )
            return AutoAdvanceScheduleResult.DUPLICATED
        if enqueue_result.failed:
            logger.warning(
                "create_auto_advance_task_if_needed enqueue failed, roomId=%s version=%s phase=%s",
                normalized_room_id,
                version,
                expected_phase,
            )
        return AutoAdvanceScheduleResult.FAILED

    async def validate_managed_turn_task_for_recovery(
        self,
        task: ManagedTurnTask,
    ) -> Optional[str]:
        """
        托管任务短重试耗尽后，校验同一任务是否仍应恢复。

        :param task: 待恢复的托管任务。
        :return: 永久跳过原因；仍有效时返回 ``None``。
        """
        normalized_room_id = str(task.roomId or "").strip()
        if not normalized_room_id:
            return TaskObsoleteReason.TASK_ALREADY_OBSOLETE
        meta = await self._repository.get_meta_for_task(normalized_room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            return TaskObsoleteReason.ROOM_NOT_PLAYING
        current_version = await self._repository.get_game_version_for_task(normalized_room_id)
        if current_version is None:
            current_version = 0
        if int(current_version) != int(task.expectedVersion):
            return TaskObsoleteReason.VERSION_CHANGED
        consistent = await self._state_reader.load_consistent_for_task(normalized_room_id)
        snapshot = consistent.snapshot
        if snapshot.isGameOver is True:
            return TaskObsoleteReason.GAME_ALREADY_OVER
        expected_phase = str(task.expectedPhase or "").strip()
        if expected_phase:
            state = snapshot.state if isinstance(snapshot.state, dict) else {}
            current_phase = str(state.get("phase", "")).strip()
            if current_phase != expected_phase:
                return TaskObsoleteReason.PHASE_CHANGED
        current_player_id = extract_current_player_id(snapshot)
        if current_player_id != str(task.expectedCurrentPlayerId or "").strip():
            return TaskObsoleteReason.CURRENT_PLAYER_CHANGED
        members = await self._repository.list_players_for_task(normalized_room_id)
        target_member = find_member(members, current_player_id)
        if target_member is None:
            return TaskObsoleteReason.PLAYER_NOT_MANAGED
        if (not bool(target_member.get("isManaged"))) and (not bool(target_member.get("isAi"))):
            return TaskObsoleteReason.PLAYER_NOT_MANAGED
        return None

    async def validate_auto_advance_task_for_recovery(
        self,
        task: RoomAutoAdvanceTask,
    ) -> Optional[str]:
        """
        自动推进任务短重试耗尽后，校验同一任务是否仍应恢复。

        :param task: 待恢复的自动推进任务。
        :return: 永久跳过原因；仍有效时返回 ``None``。
        """
        normalized_room_id = str(task.roomId or "").strip()
        if not normalized_room_id:
            return TaskObsoleteReason.TASK_ALREADY_OBSOLETE
        meta = await self._repository.get_meta_for_task(normalized_room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            return TaskObsoleteReason.ROOM_NOT_PLAYING
        current_version = await self._repository.get_game_version_for_task(normalized_room_id)
        if current_version is None:
            current_version = 0
        if int(current_version) != int(task.expectedVersion):
            return TaskObsoleteReason.VERSION_CHANGED
        consistent = await self._state_reader.load_consistent_for_task(normalized_room_id)
        snapshot = consistent.snapshot
        if snapshot.isGameOver is True:
            return TaskObsoleteReason.GAME_ALREADY_OVER
        state = snapshot.state if isinstance(snapshot.state, dict) else {}
        current_phase = str(state.get("phase", "")).strip()
        if current_phase != str(task.expectedPhase or "").strip():
            return TaskObsoleteReason.PHASE_CHANGED
        return None
