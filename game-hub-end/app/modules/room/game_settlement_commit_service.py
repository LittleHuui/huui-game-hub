"""平台积分结算编排服务。"""


import logging
from typing import Any, Dict, List, Optional, Tuple
from app.common.exceptions import ValidationException
from app.core.clock import Clock
from app.core.id_utils import generate_server_id
from app.modules.room.game_completion_schemas import TERMINAL_DISPLAY_MS
from app.modules.room.game_settlement_schemas import GameSettlementResult, SettlementExecutionResult, SettlementExecutionStatus, build_player_ai_map
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.repository import RoomRepository
from app.modules.room.room_game_commit_service import RoomGameCommitService
from app.modules.strategy_turn.schemas import RuntimeSnapshot
from app.modules.strategy_turn.terminal_schemas import (
    PlatformPlayerSettlementView,
    PlatformSettlementResultView,
)
from app.modules.room.game_settlement_failure import (
    limit_settlement_failure_reason,
    SETTLEMENT_FAILURE_CODE_CONTRACT,
    SETTLEMENT_FAILURE_CODE_INFRASTRUCTURE,
    SETTLEMENT_FAILURE_CODE_LIMIT,
)


logger = logging.getLogger(__name__)


class GameSettlementCommitService:
    """成功与失败结算的 Runtime/CAS/Finalize Outbox 提交。"""

    def __init__(self, repository: RoomRepository, state_reader: GameStateReader,
                 commit_service: RoomGameCommitService, clock: Clock) -> None:
        """注入权威读取、原子提交和时钟端口。"""
        self._repository = repository
        self._state_reader = state_reader
        self._commit_service = commit_service
        self._clock = clock

    def _build_settlement_result_view(
        self,
        settlement_result: GameSettlementResult,
        player_ai_map: Optional[Dict[str, bool]] = None,
    ) -> PlatformSettlementResultView:
        """
        将平台结算结果转换为 RuntimeSnapshot 视图模型。

        :param settlement_result: 平台结算结果。
        :param player_ai_map: AI 玩家映射。
        :return: 平台结算结果视图。
        """
        ai_map = player_ai_map or {}
        return PlatformSettlementResultView(
            settlementId=settlement_result.settlementId,
            matchId=settlement_result.matchId,
            status=settlement_result.status,
            playerSettlements=[
                PlatformPlayerSettlementView(
                    playerId=item.playerId,
                    expectedDelta=int(item.expectedDelta),
                    actualDelta=int(item.actualDelta),
                    balanceBefore=int(item.balanceBefore),
                    balanceAfter=int(item.balanceAfter),
                    insufficientAmount=int(item.insufficientAmount),
                    isAi=bool(item.isAi or ai_map.get(item.playerId, False)),
                )
                for item in settlement_result.playerSettlements
            ],
            systemDelta=int(settlement_result.systemDelta),
        )

    async def commit_success(
        self,
        room_id: str,
        snapshot: RuntimeSnapshot,
        meta: Dict[str, Any],
        expected_version: int,
        settlement_result: GameSettlementResult,
        members: List[Dict[str, Any]],
    ) -> Tuple[int, RuntimeSnapshot, Dict[str, Any]]:
        """
        结算成功后更新 terminal 元数据并写入 TERMINAL_FINALIZE Outbox。

        :param room_id: 房间 ID。
        :param snapshot: 当前终局快照。
        :param meta: 房间元信息。
        :param expected_version: 期望对局版本。
        :param settlement_result: 平台结算结果。
        :param members: 房间成员。
        :return: ``(提交后对局版本, 提交后快照, 提交后房间元信息)``。
        """
        committed_at = int(self._clock.now_ms())
        terminal_metadata = snapshot.terminalMetadata
        if terminal_metadata is None:
            raise ValidationException("终局元数据缺失")
        display_duration_ms = TERMINAL_DISPLAY_MS
        directive = snapshot.terminalDirective
        if directive is not None:
            display_duration_ms = int(directive.displayDurationMs or TERMINAL_DISPLAY_MS)
        display_until = int(committed_at) + int(display_duration_ms)
        player_ai_map = build_player_ai_map(members)
        settlement_result_view = self._build_settlement_result_view(
            settlement_result,
            player_ai_map,
        )
        updated_metadata = terminal_metadata.model_copy(
            update={
                "settlementStatus": "COMPLETED",
                "settlementResultId": settlement_result.settlementId,
                "terminalStatus": "DISPLAYING",
                "terminalDisplayUntil": display_until,
                "settlementResult": settlement_result_view,
            },
        )
        updated_snapshot = snapshot.model_copy(
            update={
                "terminalMetadata": updated_metadata,
                "updatedAt": committed_at,
            },
        )
        next_meta = dict(meta)
        next_meta["status"] = "playing"
        next_meta["updatedAt"] = committed_at
        commit_id = generate_server_id("commit")
        next_version = int(expected_version) + 1
        finalize_record = self._commit_service.build_finalize_outbox_record(
            room_id=room_id,
            terminal_metadata=updated_metadata,
            game_version=next_version,
            commit_id=commit_id,
            committed_at=committed_at,
            display_until=display_until,
        )
        await self._commit_service.commit_state_change(
            room_id=room_id,
            expected_version=int(expected_version),
            next_snapshot=updated_snapshot,
            next_room_meta=next_meta,
            outbox_records=[finalize_record],
            commit_id=commit_id,
            committed_at=committed_at,
        )
        return next_version, updated_snapshot, next_meta

    async def commit_terminal_failure(
        self,
        room_id: str,
        expected_version: int,
        settlement_id: str,
        failure_code: str,
        reason: str,
    ) -> SettlementExecutionResult:
        """
        幂等提交结算失败终局与 TERMINAL_FINALIZE Outbox。

        :param room_id: 房间 ID。
        :param expected_version: 期望对局版本。
        :param settlement_id: 结算 ID。
        :param failure_code: 失败错误码。
        :param reason: 失败原因。
        :return: 严格结算执行结果。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_settlement_id = str(settlement_id or "").strip()
        normalized_failure_code = str(failure_code or SETTLEMENT_FAILURE_CODE_INFRASTRUCTURE).strip()[:SETTLEMENT_FAILURE_CODE_LIMIT]
        normalized_reason = limit_settlement_failure_reason(reason)
        if not normalized_room_id or not normalized_settlement_id:
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode=SETTLEMENT_FAILURE_CODE_CONTRACT,
                failureReason="失败终局提交缺少 roomId 或 settlementId",
            )

        try:
            meta = await self._repository.get_meta(normalized_room_id)
            if meta is None or str(meta.get("status", "")).strip() != "playing":
                return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)
            consistent_state = await self._state_reader.load_consistent(normalized_room_id)
        except Exception:
            logger.exception(
                "settlement terminal failure state read failed, roomId=%s settlementId=%s "
                "expectedVersion=%s failureCode=%s failureReason=%s terminalFailureCommitted=%s",
                normalized_room_id,
                normalized_settlement_id,
                expected_version,
                normalized_failure_code,
                normalized_reason,
                False,
            )
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.RETRY_REQUIRED,
                failureCode=normalized_failure_code,
                failureReason=normalized_reason,
                retryable=True,
            )

        snapshot = consistent_state.snapshot
        authoritative_version = int(consistent_state.gameVersion)
        terminal_metadata = snapshot.terminalMetadata
        if terminal_metadata is None:
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode=SETTLEMENT_FAILURE_CODE_CONTRACT,
                failureReason="终局元数据缺失",
            )
        metadata_settlement_id = str(terminal_metadata.settlementId or "").strip()
        if metadata_settlement_id != normalized_settlement_id:
            return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)
        settlement_status = str(terminal_metadata.settlementStatus or "").strip()
        if settlement_status == "COMPLETED":
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.ALREADY_COMPLETED,
                committedVersion=authoritative_version,
            )
        if settlement_status == "FAILED":
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.TERMINAL_FAILURE_COMMITTED,
                failureCode=terminal_metadata.settlementFailureCode,
                failureReason=terminal_metadata.settlementFailureReason,
                committedVersion=authoritative_version,
            )
        if not bool(snapshot.isGameOver):
            return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)

        committed_at = int(self._clock.now_ms())
        display_duration_ms = TERMINAL_DISPLAY_MS
        directive = snapshot.terminalDirective
        if directive is not None:
            display_duration_ms = int(directive.displayDurationMs or TERMINAL_DISPLAY_MS)
        display_until = int(committed_at) + int(display_duration_ms)
        updated_metadata = terminal_metadata.model_copy(
            update={
                "settlementStatus": "FAILED",
                "settlementFailureCode": normalized_failure_code,
                "settlementFailureReason": normalized_reason,
                "terminalStatus": "DISPLAYING_SETTLEMENT_FAILED",
                "terminalDisplayUntil": display_until,
            },
        )
        updated_snapshot = snapshot.model_copy(
            update={
                "terminalMetadata": updated_metadata,
                "updatedAt": committed_at,
            },
        )
        next_meta = dict(meta)
        next_meta["status"] = "playing"
        next_meta["updatedAt"] = committed_at
        commit_id = generate_server_id("commit")
        next_version = authoritative_version + 1
        finalize_record = self._commit_service.build_finalize_outbox_record(
            room_id=normalized_room_id,
            terminal_metadata=updated_metadata,
            game_version=next_version,
            commit_id=commit_id,
            committed_at=committed_at,
            display_until=display_until,
        )
        try:
            await self._commit_service.commit_state_change(
                room_id=normalized_room_id,
                expected_version=authoritative_version,
                next_snapshot=updated_snapshot,
                next_room_meta=next_meta,
                outbox_records=[finalize_record],
                commit_id=commit_id,
                committed_at=committed_at,
            )
        except Exception:
            logger.exception(
                "settlement terminal failure commit failed, roomId=%s settlementId=%s "
                "expectedVersion=%s authoritativeVersion=%s failureCode=%s "
                "failureReason=%s terminalFailureCommitted=%s",
                normalized_room_id,
                normalized_settlement_id,
                expected_version,
                authoritative_version,
                normalized_failure_code,
                normalized_reason,
                False,
            )
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.RETRY_REQUIRED,
                failureCode=normalized_failure_code,
                failureReason=normalized_reason,
                retryable=True,
            )
        logger.warning(
            "settlement terminal failure committed, roomId=%s settlementId=%s "
            "expectedVersion=%s authoritativeVersion=%s committedVersion=%s "
            "failureCode=%s failureReason=%s terminalFailureCommitted=%s",
            normalized_room_id,
            normalized_settlement_id,
            expected_version,
            authoritative_version,
            next_version,
            normalized_failure_code,
            normalized_reason,
            True,
        )
        return SettlementExecutionResult(
            status=SettlementExecutionStatus.TERMINAL_FAILURE_COMMITTED,
            failureCode=normalized_failure_code,
            failureReason=normalized_reason,
            committedVersion=next_version,
        )
