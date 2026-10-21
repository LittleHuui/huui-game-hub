"""平台积分结算编排服务。"""


import logging
from typing import Any, Dict, List
from app.common.exceptions import ValidationException
from app.modules.room.game_presentation_service import GamePresentationService
from app.modules.room.game_settlement_calculator import validate_theoretical_zero_sum
from app.modules.room.game_settlement_schemas import GameSettlementResult, SettlementExecutionResult, SettlementExecutionStatus, SettlementPersistenceStatus, build_player_ai_map
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.repository import RoomRepository
from app.modules.strategy_turn.schemas import RuntimeSnapshot
from app.modules.room.game_settlement_failure import (
    limit_settlement_failure_reason,
    SETTLEMENT_FAILURE_CODE_CONTRACT,
    SETTLEMENT_FAILURE_CODE_INFRASTRUCTURE,
    SETTLEMENT_FAILURE_CODE_THEORETICAL,
    SETTLEMENT_FAILURE_CODE_VALIDATION,
)
from app.modules.room.game_settlement_transaction import GameSettlementTransaction
from app.modules.room.game_settlement_commit_service import GameSettlementCommitService


logger = logging.getLogger(__name__)


class GameSettlementService:
    """校验结算上下文，并依次协调数据库、Redis 与展示通知。"""

    def __init__(self, repository: RoomRepository, state_reader: GameStateReader,
                 transaction: GameSettlementTransaction, state_committer: GameSettlementCommitService,
                 presentation_service: GamePresentationService) -> None:
        """一次性注入结算所需的事务、状态提交与展示端口。"""
        self._repository = repository
        self._state_reader = state_reader
        self._transaction = transaction
        self._state_committer = state_committer
        self._presentation_service = presentation_service

    async def dispatch_settlement(
        self,
        room_id: str,
        payload: Dict[str, Any],
    ) -> SettlementExecutionResult:
        """
        执行一局游戏的平台积分结算。

        :param room_id: 房间 ID。
        :param payload: GAME_SETTLEMENT Outbox 载荷。
        :return: 严格结算执行结果。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode=SETTLEMENT_FAILURE_CODE_CONTRACT,
                failureReason="roomId 不能为空",
            )
        settlement_id = str(payload.get("settlementId", "")).strip()
        if not settlement_id:
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode=SETTLEMENT_FAILURE_CODE_CONTRACT,
                failureReason="settlementId 不能为空",
            )
        game_code = str(payload.get("gameCode", "")).strip()
        expected_version = payload.get("gameVersion")
        if expected_version is None:
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode=SETTLEMENT_FAILURE_CODE_CONTRACT,
                failureReason="gameVersion 不能为空",
            )
        try:
            expected_version = int(expected_version)
        except (TypeError, ValueError):
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode=SETTLEMENT_FAILURE_CODE_CONTRACT,
                failureReason="gameVersion 必须是整数",
            )

        meta = await self._repository.get_meta(normalized_room_id)
        if meta is None or str(meta.get("status", "")).strip() != "playing":
            return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)

        try:
            consistent_state = await self._state_reader.load_consistent(normalized_room_id)
        except Exception as exc:
            logger.warning(
                "settlement runtime read failed, roomId=%s settlementId=%s "
                "expectedVersion=%s failureCode=%s failureReason=%s",
                normalized_room_id,
                settlement_id,
                expected_version,
                SETTLEMENT_FAILURE_CODE_INFRASTRUCTURE,
                str(exc),
                exc_info=True,
            )
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.RETRY_REQUIRED,
                failureCode=SETTLEMENT_FAILURE_CODE_INFRASTRUCTURE,
                failureReason=limit_settlement_failure_reason(str(exc)),
                retryable=True,
            )

        snapshot = consistent_state.snapshot
        if int(consistent_state.gameVersion) != int(expected_version):
            return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)
        if not bool(snapshot.isGameOver):
            return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)

        terminal_metadata = snapshot.terminalMetadata
        if terminal_metadata is None:
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.CONTRACT_FAILURE,
                failureCode=SETTLEMENT_FAILURE_CODE_CONTRACT,
                failureReason="终局元数据缺失",
            )
        metadata_settlement_id = str(terminal_metadata.settlementId or "").strip()
        if metadata_settlement_id and metadata_settlement_id != settlement_id:
            return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)
        settlement_status = str(terminal_metadata.settlementStatus or "").strip()
        if settlement_status == "COMPLETED":
            if terminal_metadata.settlementResult is not None:
                return SettlementExecutionResult(
                    status=SettlementExecutionStatus.ALREADY_COMPLETED,
                    committedVersion=int(consistent_state.gameVersion),
                )
        if settlement_status == "FAILED":
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.TERMINAL_FAILURE_COMMITTED,
                failureCode=terminal_metadata.settlementFailureCode,
                failureReason=terminal_metadata.settlementFailureReason,
                committedVersion=int(consistent_state.gameVersion),
            )

        directive = snapshot.terminalDirective
        if directive is None or not directive.requiresPlatformSettlement:
            return SettlementExecutionResult(status=SettlementExecutionStatus.OBSOLETE)
        theoretical = directive.theoreticalSettlement
        if theoretical is None:
            return await self._state_committer.commit_terminal_failure(
                normalized_room_id,
                int(expected_version),
                settlement_id,
                SETTLEMENT_FAILURE_CODE_CONTRACT,
                "理论结算合同缺失",
            )
        zero_sum_error = validate_theoretical_zero_sum(theoretical.playerSettlements)
        if zero_sum_error:
            logger.warning(
                "settlement invalid theoretical, roomId=%s settlementId=%s reason=%s",
                normalized_room_id,
                settlement_id,
                zero_sum_error,
            )
            return await self._state_committer.commit_terminal_failure(
                normalized_room_id,
                int(expected_version),
                settlement_id,
                SETTLEMENT_FAILURE_CODE_THEORETICAL,
                zero_sum_error,
            )

        members = await self._repository.list_players(normalized_room_id)
        player_ai_map = build_player_ai_map(members)

        try:
            persistence_result = self._transaction.execute(
                settlement_id=settlement_id,
                room_id=normalized_room_id,
                game_code=game_code or str(snapshot.gameCode or "").strip(),
                theoretical_players=theoretical.playerSettlements,
                player_ai_map=player_ai_map,
                snapshot=snapshot,
            )
            settlement_result = persistence_result.settlementResult
        except ValidationException as exc:
            logger.warning(
                "settlement validation failed, roomId=%s settlementId=%s reason=%s",
                normalized_room_id,
                settlement_id,
                str(exc),
            )
            return await self._state_committer.commit_terminal_failure(
                normalized_room_id,
                int(expected_version),
                settlement_id,
                SETTLEMENT_FAILURE_CODE_VALIDATION,
                str(exc),
            )
        except Exception as exc:
            logger.exception(
                "settlement transaction failed, roomId=%s settlementId=%s",
                normalized_room_id,
                settlement_id,
            )
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.RETRY_REQUIRED,
                failureCode=SETTLEMENT_FAILURE_CODE_INFRASTRUCTURE,
                failureReason=limit_settlement_failure_reason(str(exc)),
                retryable=True,
            )

        try:
            next_version, committed_snapshot, committed_meta = await self._state_committer.commit_success(
                normalized_room_id,
                snapshot,
                meta,
                int(expected_version),
                settlement_result,
                members,
            )
            await self._push_settlement_game_view(
                normalized_room_id,
                committed_meta,
                members,
                settlement_result,
                committed_snapshot,
                next_version,
            )
        except Exception as exc:
            logger.exception(
                "settlement redis commit failed after db success, roomId=%s settlementId=%s",
                normalized_room_id,
                settlement_id,
            )
            return SettlementExecutionResult(
                status=SettlementExecutionStatus.RETRY_REQUIRED,
                failureCode=SETTLEMENT_FAILURE_CODE_INFRASTRUCTURE,
                failureReason=limit_settlement_failure_reason(str(exc)),
                retryable=True,
            )
        execution_status = SettlementExecutionStatus.COMPLETED
        if persistence_result.status == SettlementPersistenceStatus.ALREADY_COMPLETED:
            execution_status = SettlementExecutionStatus.ALREADY_COMPLETED
        return SettlementExecutionResult(
            status=execution_status,
            committedVersion=int(next_version),
        )

    async def _push_settlement_game_view(
        self,
        room_id: str,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        settlement_result: GameSettlementResult,
        committed_snapshot: RuntimeSnapshot,
        game_version: int,
    ) -> None:
        """
        结算成功后将含实际结果的权威 GameView 推送给仍在房间的玩家。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 成员列表。
        :param settlement_result: 平台结算结果。
        :param committed_snapshot: 提交后的运行时快照。
        :param game_version: 提交后对局版本。
        :return: 无。
        """
        try:
            await self._presentation_service.push_authoritative_terminal_game_view(
                room_id,
                meta,
                members,
                committed_snapshot,
                int(game_version),
            )
        except Exception:
            logger.exception(
                "settlement game view push failed, roomId=%s settlementId=%s gameVersion=%s",
                room_id,
                settlement_result.settlementId,
                game_version,
            )
