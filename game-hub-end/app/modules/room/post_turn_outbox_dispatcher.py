"""回合后任务 Outbox 分发器。"""

import logging
from typing import List, Optional, Protocol

from redis.exceptions import RedisError

from app.common.exceptions import BizException
from app.core.id_utils import generate_server_id
from app.core.time_utils import now_ms
from app.modules.room.auto_advance_task_service import AutoAdvanceScheduleResult
from app.modules.room.game_state_reader import (
    GameRuntimeNotFoundException,
    GameStateReader,
    RetryableGameStateInconsistentException,
)
from app.modules.room.game_settlement_service import GameSettlementService
from app.modules.room.game_settlement_commit_service import GameSettlementCommitService
from app.modules.room.game_settlement_schemas import (
    SettlementExecutionResult,
    SettlementExecutionStatus,
)
from app.modules.room.game_terminal_finalize_service import GameTerminalFinalizeService
from app.modules.strategy_turn.schemas import RuntimeSnapshot
from app.modules.room.post_turn_outbox_dispatch_result import (
    OutboxHandlerResult,
    OutboxHandlerStatus,
    TaskSchedulingStatus,
)
from app.modules.room.post_turn_outbox_repository import (
    POST_TURN_OUTBOX_BATCH_SIZE,
    POST_TURN_OUTBOX_MAX_ATTEMPTS,
    PostTurnOutboxRepository,
)
from app.modules.room.post_turn_outbox_policy import get_outbox_policy, pick_backoff
from app.modules.room.post_turn_plan import PostTurnPlan
from app.modules.room.repository import RoomRepository
from app.modules.room.room_game_commit_schemas import PostTurnOutboxRecord
from app.modules.strategy_turn.terminal_schemas import TerminalMetadata
logger = logging.getLogger(__name__)


class PostTurnTaskSchedulingPort(Protocol):
    """Outbox 分发所需的公开任务调度端口。"""

    async def create_auto_advance_task_if_needed(
        self,
        room_id: str,
        snapshot: RuntimeSnapshot,
        version: int,
        reason: str,
    ) -> str:
        """按当前阶段创建自动推进任务。"""

    async def create_current_player_managed_task_if_needed(
        self,
        room_id: str,
        reason: str,
    ) -> TaskSchedulingStatus:
        """按当前玩家状态创建托管任务。"""


class PostTurnOutboxDispatcher(object):
    """异步消费 Outbox 并调度托管/自动推进/终局任务。"""

    def __init__(
        self,
        outbox_repository: PostTurnOutboxRepository,
        repository: RoomRepository,
        state_reader: GameStateReader,
        task_scheduling_port: PostTurnTaskSchedulingPort,
        terminal_finalize_service: GameTerminalFinalizeService,
        settlement_service: GameSettlementService,
        settlement_committer: GameSettlementCommitService,
    ) -> None:
        """
        初始化可靠回合后任务分发器。

        :param outbox_repository: Outbox 仓库。
        :param repository: 房间 Redis 仓库。
        :param state_reader: 运行时读取端口。
        :param task_scheduling_port: 任务调度端口。
        :param terminal_finalize_service: 终局收敛服务。
        :param settlement_service: 平台积分结算服务。
        """
        self._outbox_repository = outbox_repository
        self._repository = repository
        self._state_reader = state_reader
        self._task_scheduling_port = task_scheduling_port
        self._terminal_finalize_service = terminal_finalize_service
        self._settlement_service = settlement_service
        self._settlement_committer = settlement_committer

    async def dispatch_claimed_records(self, records: List[PostTurnOutboxRecord]) -> int:
        """
        批量分发已领取的 Outbox 记录。

        :param records: 已领取记录列表。
        :return: 实际处理条数。
        """
        processed = 0
        for record in records:
            await self._dispatch_record(record)
            processed += 1
        return processed

    async def process_pending(self, limit: Optional[int] = None) -> int:
        """
        从 ready-room 索引领取并执行调度（测试/手动触发入口）。

        :param limit: 最大处理条数。
        :return: 实际处理条数。
        """
        batch_size = int(limit) if limit is not None else POST_TURN_OUTBOX_BATCH_SIZE
        records = await self._outbox_repository.claim_from_ready_rooms(
            OUTBOX_READY_ROOM_SCAN_LIMIT,
            batch_size,
        )
        return await self.dispatch_claimed_records(records)

    async def recover_missing_post_turn_tasks(self, room_ids: List[str]) -> int:
        """Watchdog for playing rooms that have no valid follow-up task."""
        recovered = 0
        for room_id in room_ids:
            try:
                if await self._outbox_repository.room_has_pending_outbox(room_id):
                    continue
                meta = await self._repository.get_meta(room_id)
                if meta is None or str(meta.get("status", "")).strip() != "playing":
                    continue
                current_version = await self._repository.get_game_version(room_id)
                if current_version is None:
                    continue
                snapshot = (await self._state_reader.load_consistent(room_id)).snapshot
                if bool(snapshot.isGameOver):
                    continue
                auto_result = await self._task_scheduling_port.create_auto_advance_task_if_needed(
                    room_id,
                    snapshot,
                    int(current_version),
                    "postTurnWatchdog",
                )
                if auto_result == AutoAdvanceScheduleResult.FAILED:
                    continue
                if auto_result == AutoAdvanceScheduleResult.NOT_REQUIRED:
                    managed_result = await self._task_scheduling_port.create_current_player_managed_task_if_needed(
                        room_id,
                        "postTurnWatchdog",
                    )
                    if managed_result == TaskSchedulingStatus.RETRY:
                        continue
                recovered += 1
            except Exception:
                logger.exception("post turn watchdog failed, roomId=%s", room_id)
        return recovered

    async def recover_missing_terminal_finalize(self, room_ids: List[str]) -> int:
        """Watchdog for terminal playing rooms that lost the finalize outbox."""
        recovered = 0
        for room_id in room_ids:
            try:
                if await self._outbox_repository.room_has_pending_outbox(room_id):
                    continue
                meta = await self._repository.get_meta(room_id)
                if meta is None or str(meta.get("status", "")).strip() != "playing":
                    continue
                runtime_data = await self._repository.get_runtime(room_id)
                if not isinstance(runtime_data, dict):
                    continue
                if not bool(runtime_data.get("isGameOver")):
                    continue
                terminal_metadata_raw = runtime_data.get("terminalMetadata")
                if not isinstance(terminal_metadata_raw, dict):
                    continue
                terminal_metadata = TerminalMetadata.model_validate(terminal_metadata_raw)
                current_version = await self._repository.get_game_version(room_id)
                if current_version is None:
                    continue
                record = self._build_finalize_record(
                    room_id,
                    terminal_metadata,
                    int(current_version),
                    "terminalFinalizeWatchdog",
                )
                if await self._outbox_repository.enqueue_record_if_absent(record):
                    recovered += 1
            except Exception:
                logger.exception("terminal finalize watchdog failed, roomId=%s", room_id)
        return recovered

    async def _dispatch_record(self, record: PostTurnOutboxRecord) -> None:
        """
        执行单条 Outbox 记录并按结果 Ack/Retry/Discard/Fail。

        :param record: Outbox 记录。
        :return: 无。
        """
        task_type = str(record.taskType or "").strip()
        try:
            if task_type == "GAME_SETTLEMENT":
                await self._dispatch_game_settlement_record(record)
                return
            result = await self._dispatch_by_type(record, task_type)
            await self._apply_handler_result(record, result)
        except RedisError as exc:
            logger.warning(
                "post turn outbox redis error, roomId=%s outboxId=%s",
                record.roomId,
                record.outboxId,
                exc_info=True,
            )
            if task_type == "GAME_SETTLEMENT":
                await self._outbox_repository.retry_game_settlement(
                    record.roomId,
                    record,
                    "redisError",
                )
                return
            await self._apply_handler_result(
                record,
                self._handler_result(
                    OutboxHandlerStatus.RETRY,
                    "REDIS_TEMPORARY_FAILURE",
                    str(exc),
                ),
            )
        except Exception as exc:
            logger.exception(
                "post turn outbox dispatch failed, roomId=%s outboxId=%s taskType=%s",
                record.roomId,
                record.outboxId,
                task_type,
            )
            if task_type == "GAME_SETTLEMENT":
                await self._outbox_repository.retry_game_settlement(
                    record.roomId,
                    record,
                    "dispatchException",
                )
                return
            await self._apply_handler_result(
                record,
                self._handler_result(
                    OutboxHandlerStatus.RETRY,
                    "DISPATCH_TEMPORARY_FAILURE",
                    str(exc),
                ),
            )

    async def _dispatch_by_type(
        self,
        record: PostTurnOutboxRecord,
        task_type: str,
    ) -> OutboxHandlerResult:
        """
        按任务类型执行分发并返回结果语义。

        :param record: Outbox 记录。
        :param task_type: 任务类型。
        :return: 分发结果。
        """
        if task_type == "TERMINAL_FINALIZE":
            return await self._dispatch_terminal_finalize(record)
        if task_type == "TERMINAL_DERIVED_CLEANUP":
            return await self._dispatch_terminal_derived_cleanup(record)
        if task_type == "postTurnPlan":
            return await self._dispatch_post_turn_plan(record)
        return self._handler_result(
            OutboxHandlerStatus.PERMANENT_FAILURE,
            "OUTBOX_TASK_TYPE_UNSUPPORTED",
            "不支持的 Outbox taskType",
        )

    async def _dispatch_terminal_finalize(
        self,
        record: PostTurnOutboxRecord,
    ) -> OutboxHandlerResult:
        """
        执行终局收敛 Outbox。

        :param record: Outbox 记录。
        :return: 分发结果。
        """
        return await self._terminal_finalize_service.finalize_terminal_room(
            record.roomId,
            record.payload,
        )

    async def _dispatch_terminal_derived_cleanup(
        self,
        record: PostTurnOutboxRecord,
    ) -> OutboxHandlerResult:
        """校验清理载荷并交给带终局代际保护的幂等索引清理。"""
        payload = record.payload if isinstance(record.payload, dict) else {}
        if not payload:
            return self._handler_result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                "DERIVED_CLEANUP_PAYLOAD_INVALID",
                "TERMINAL_DERIVED_CLEANUP payload 为空",
            )
        return await self._terminal_finalize_service.cleanup_terminal_derived(
            record.roomId,
            payload,
        )

    async def _dispatch_game_settlement_record(self, record: PostTurnOutboxRecord) -> None:
        """
        执行 GAME_SETTLEMENT，并仅在失败终局提交后终止原 Outbox。

        :param record: Outbox 记录。
        :return: 无。
        """
        payload = record.payload if isinstance(record.payload, dict) else {}
        if not payload:
            result = SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode="SETTLEMENT_CONTRACT_INVALID",
                failureReason="GAME_SETTLEMENT payload 为空",
            )
        else:
            result = await self._settlement_service.dispatch_settlement(record.roomId, payload)
        await self._apply_settlement_result(record, result)

    async def _apply_settlement_result(
        self,
        record: PostTurnOutboxRecord,
        result: SettlementExecutionResult,
    ) -> None:
        """
        将严格结算结果转换为安全的 Outbox 状态迁移。

        :param record: GAME_SETTLEMENT Outbox 记录。
        :param result: 严格结算执行结果。
        :return: 无。
        """
        payload = record.payload if isinstance(record.payload, dict) else {}
        settlement_id = str(payload.get("settlementId", "")).strip()
        expected_version = payload.get("gameVersion")
        failure_code = str(result.failureCode or "SETTLEMENT_EXECUTION_FAILED").strip()
        failure_reason = str(result.failureReason or failure_code).strip()[:500]
        logger.warning(
            "game settlement outbox result, roomId=%s settlementId=%s outboxId=%s "
            "expectedVersion=%s attemptCount=%s recoveryCount=%s failureCode=%s "
            "failureReason=%s terminalFailureCommitted=%s",
            record.roomId,
            settlement_id,
            record.outboxId,
            expected_version,
            record.attemptCount,
            record.recoveryCount,
            failure_code,
            failure_reason,
            result.status == SettlementExecutionStatus.TERMINAL_FAILURE_COMMITTED,
        )
        if result.status in (
            SettlementExecutionStatus.COMPLETED,
            SettlementExecutionStatus.ALREADY_COMPLETED,
        ):
            await self._outbox_repository.ack(record.roomId, record)
            return
        if result.status == SettlementExecutionStatus.TERMINAL_FAILURE_COMMITTED:
            await self._outbox_repository.fail(record.roomId, record, failure_reason)
            return
        if result.status == SettlementExecutionStatus.OBSOLETE:
            await self._outbox_repository.discard(record.roomId, record, "obsolete")
            return

        if int(record.attemptCount) >= POST_TURN_OUTBOX_MAX_ATTEMPTS:
            terminal_result = await self._settlement_committer.commit_terminal_failure(
                record.roomId,
                int(expected_version or record.sourceVersion),
                settlement_id,
                failure_code,
                failure_reason,
            )
            if terminal_result.status == SettlementExecutionStatus.TERMINAL_FAILURE_COMMITTED:
                await self._outbox_repository.fail(record.roomId, record, failure_reason)
                return
            if terminal_result.status == SettlementExecutionStatus.ALREADY_COMPLETED:
                await self._outbox_repository.ack(record.roomId, record)
                return
            if terminal_result.status == SettlementExecutionStatus.OBSOLETE:
                await self._outbox_repository.discard(record.roomId, record, "obsolete")
                return

        await self._outbox_repository.retry_game_settlement(
            record.roomId,
            record,
            failure_reason,
        )

    async def _dispatch_post_turn_plan(
        self,
        record: PostTurnOutboxRecord,
    ) -> OutboxHandlerResult:
        """
        执行回合后计划 Outbox。

        :param record: Outbox 记录。
        :return: 分发结果。
        """
        plan = self._record_to_plan(record)
        if plan is None:
            return self._handler_result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                "POST_TURN_PAYLOAD_INVALID",
                "postTurnPlan payload 合同损坏",
            )
        try:
            meta = await self._repository.get_meta(plan.roomId)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "POST_TURN_META_READ_FAILED",
                str(exc),
            )
        if meta is None or meta.get("status") != "playing":
            return self._handler_result(
                OutboxHandlerStatus.OBSOLETE,
                "POST_TURN_ROOM_NOT_PLAYING",
                "房间已不再 playing",
            )
        try:
            current_version = await self._repository.get_game_version(plan.roomId)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "POST_TURN_VERSION_READ_FAILED",
                str(exc),
            )
        if current_version is None:
            try:
                runtime_data = await self._repository.get_runtime(plan.roomId)
            except (RedisError, OSError, TimeoutError) as exc:
                return self._handler_result(
                    OutboxHandlerStatus.RETRY,
                    "POST_TURN_RUNTIME_READ_FAILED",
                    str(exc),
                )
            if runtime_data is None:
                return self._handler_result(
                    OutboxHandlerStatus.OBSOLETE,
                    "POST_TURN_RUNTIME_MISSING",
                    "权威检查确认 Runtime 不存在",
                )
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "POST_TURN_VERSION_READ_INCOMPLETE",
                "Runtime 存在但版本读取不完整",
            )
        if int(current_version) != int(plan.version):
            return self._handler_result(
                OutboxHandlerStatus.OBSOLETE,
                "POST_TURN_VERSION_OBSOLETE",
                "postTurnPlan 版本已过期",
            )
        try:
            snapshot = (await self._state_reader.load_consistent(plan.roomId)).snapshot
        except GameRuntimeNotFoundException:
            return self._handler_result(
                OutboxHandlerStatus.OBSOLETE,
                "POST_TURN_RUNTIME_MISSING",
                "权威检查确认 Runtime 不存在",
            )
        except RetryableGameStateInconsistentException as exc:
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "POST_TURN_STATE_INCONSISTENT",
                str(exc),
            )
        except (RedisError, OSError, TimeoutError) as exc:
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "POST_TURN_STATE_READ_FAILED",
                str(exc),
            )
        except BizException as exc:
            return self._handler_result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                "POST_TURN_STATE_CONTRACT_INVALID",
                str(exc),
            )
        except Exception as exc:
            logger.exception("post turn state read failed, roomId=%s", plan.roomId)
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "POST_TURN_STATE_READ_FAILED",
                str(exc),
            )
        if bool(snapshot.isGameOver):
            return self._handler_result(
                OutboxHandlerStatus.OBSOLETE,
                "POST_TURN_GAME_OVER",
                "终局无需继续创建回合任务",
            )
        try:
            auto_result = await self._task_scheduling_port.create_auto_advance_task_if_needed(
                plan.roomId,
                snapshot,
                plan.version,
                plan.reason,
            )
        except (RedisError, OSError, TimeoutError) as exc:
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "AUTO_ADVANCE_SCHEDULE_FAILED",
                str(exc),
            )
        if auto_result == AutoAdvanceScheduleResult.NOT_REQUIRED:
            managed_result = await self._task_scheduling_port.create_current_player_managed_task_if_needed(
                plan.roomId,
                plan.reason,
            )
            if managed_result == TaskSchedulingStatus.RETRY:
                return self._handler_result(
                    OutboxHandlerStatus.RETRY,
                    "MANAGED_TASK_SCHEDULE_FAILED",
                    "托管任务创建临时失败",
                )
        elif auto_result == AutoAdvanceScheduleResult.FAILED:
            logger.warning(
                "post turn auto advance schedule failed, roomId=%s version=%s",
                plan.roomId,
                plan.version,
            )
            return self._handler_result(
                OutboxHandlerStatus.RETRY,
                "AUTO_ADVANCE_SCHEDULE_FAILED",
                "自动推进任务创建临时失败",
            )
        return self._handler_result(
            OutboxHandlerStatus.DONE,
            "POST_TURN_TASK_SCHEDULED",
            "回合后任务已创建或已存在",
        )

    async def _apply_handler_result(
        self,
        record: PostTurnOutboxRecord,
        result: OutboxHandlerResult,
    ) -> None:
        """
        根据分发结果执行 Outbox 状态转换。

        :param record: Outbox 记录。
        :param result: Handler 严格执行结果。
        :return: 无。
        """
        room_id = record.roomId
        reason = str(result.reasonCode or "").strip()
        if result.status in (OutboxHandlerStatus.DONE, OutboxHandlerStatus.ALREADY_DONE):
            await self._outbox_repository.ack(room_id, record)
            return
        if result.status == OutboxHandlerStatus.OBSOLETE:
            await self._outbox_repository.discard(
                room_id,
                record,
                reason,
            )
            return
        if result.status == OutboxHandlerStatus.PERMANENT_FAILURE:
            await self._outbox_repository.fail(
                room_id,
                record,
                reason,
            )
            return
        policy = get_outbox_policy(record.taskType)
        if result.status == OutboxHandlerStatus.RECOVER or (
            int(record.retryCount) + 1 >= int(policy.maxShortRetryCount)
        ):
            if int(record.recoveryCount) >= int(policy.maxRecoveryCount):
                await self._handle_recovery_exhausted(record, result, policy)
                return
            await self._outbox_repository.recover(
                room_id,
                record,
                reason,
                str(result.reasonMessage or reason),
                backoff_ms=pick_backoff(policy.recoveryBackoffMs, int(record.recoveryCount)),
            )
            return
        await self._outbox_repository.retry(
            room_id,
            record,
            reason,
            backoff_ms=(
                int(result.retryAfterMs)
                if result.retryAfterMs is not None
                else pick_backoff(policy.retryBackoffMs, int(record.retryCount))
            ),
        )

    async def _handle_recovery_exhausted(
        self,
        record: PostTurnOutboxRecord,
        result: OutboxHandlerResult,
        policy,
    ) -> None:
        """Apply task-specific convergence after normal recovery is exhausted."""
        task_type = str(record.taskType or "").strip()
        reason = str(result.reasonCode or "").strip()
        if task_type == "postTurnPlan":
            authoritative = await self._dispatch_post_turn_plan(record)
            if authoritative.status in (
                OutboxHandlerStatus.DONE,
                OutboxHandlerStatus.ALREADY_DONE,
                OutboxHandlerStatus.OBSOLETE,
                OutboxHandlerStatus.PERMANENT_FAILURE,
            ):
                await self._apply_handler_result(record, authoritative)
                return
            await self._outbox_repository.recover(
                record.roomId,
                record,
                authoritative.reasonCode,
                str(authoritative.reasonMessage or authoritative.reasonCode),
                backoff_ms=pick_backoff(policy.recoveryBackoffMs, int(record.recoveryCount)),
            )
            return
        if task_type in ("TERMINAL_FINALIZE", "TERMINAL_DERIVED_CLEANUP"):
            await self._outbox_repository.recover(
                record.roomId,
                record,
                reason or "OUTBOX_RECOVERY_REQUIRED",
                str(result.reasonMessage or reason),
                backoff_ms=pick_backoff(policy.recoveryBackoffMs, int(record.recoveryCount)),
            )
            return
        await self._outbox_repository.fail(record.roomId, record, reason)

    def _build_finalize_record(
        self,
        room_id: str,
        terminal_metadata: TerminalMetadata,
        game_version: int,
        reason: str,
    ) -> PostTurnOutboxRecord:
        """Build an idempotent TERMINAL_FINALIZE record from authoritative runtime."""
        current_time = now_ms()
        owner_payload = None
        if terminal_metadata.ownerTransferPlan is not None:
            owner_payload = terminal_metadata.ownerTransferPlan.model_dump()
        payload = {
            "roomId": room_id,
            "gameVersion": int(game_version),
            "dissolveAfterTerminal": bool(terminal_metadata.dissolveAfterTerminal),
            "memberIdsToRemove": list(terminal_metadata.membersToRemoveAfterTerminal or []),
            "ownerTransferPlan": owner_payload,
            "finalizedAt": int(terminal_metadata.terminalDisplayUntil),
        }
        available_at = max(current_time, int(terminal_metadata.terminalDisplayUntil))
        return PostTurnOutboxRecord(
            outboxId=generate_server_id("outbox"),
            roomId=room_id,
            sourceCommitId=str(reason or "terminalFinalizeWatchdog"),
            sourceVersion=int(game_version),
            taskType="TERMINAL_FINALIZE",
            payload=payload,
            status="PENDING",
            attemptCount=0,
            retryCount=0,
            recoveryCount=0,
            availableAt=available_at,
            nextAttemptAt=available_at,
            leaseUntil=None,
            lastFailureCode=None,
            lastFailureReason=None,
            createdAt=current_time,
            updatedAt=current_time,
            dedupeKey="{0}:terminal-finalize:{1}".format(room_id, int(game_version)),
        )

    @staticmethod
    def _handler_result(
        status: OutboxHandlerStatus,
        reason_code: str,
        reason_message: str,
        retry_after_ms: Optional[int] = None,
    ) -> OutboxHandlerResult:
        """
        构造 Outbox Handler 严格结果。

        :param status: Handler 状态。
        :param reason_code: 原因编码。
        :param reason_message: 原因说明。
        :param retry_after_ms: 建议重试等待毫秒数。
        :return: 严格结果。
        """
        return OutboxHandlerResult(
            status=status,
            reasonCode=reason_code,
            reasonMessage=str(reason_message or "")[:500],
            retryAfterMs=retry_after_ms,
        )

    def _record_to_plan(self, record: PostTurnOutboxRecord) -> Optional[PostTurnPlan]:
        """
        从 Outbox 记录提取 PostTurnPlan。

        :param record: Outbox 记录。
        :return: 回合后计划；无效时返回 ``None``。
        """
        payload = record.payload if isinstance(record.payload, dict) else {}
        try:
            return PostTurnPlan.model_validate(payload)
        except (TypeError, ValueError):
            return None


OUTBOX_READY_ROOM_SCAN_LIMIT = 20
