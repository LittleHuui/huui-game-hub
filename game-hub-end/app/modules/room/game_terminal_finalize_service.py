"""Terminal room finalization service."""

import copy
import logging
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from app.core.clock import Clock, system_clock
from app.core.lock.distributed_lock import LockAcquireError, RedisDistributedLock
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.room_platform_support import ROOM_ACTION_LOCK_TTL_SECONDS
from app.modules.room.game_completion_schemas import OwnerTransferPlan
from app.modules.room.game_state_reader import (
    GameRuntimeNotFoundException,
    GameStateReader,
    RetryableGameStateInconsistentException,
)
from app.modules.room.post_turn_outbox_dispatch_result import (
    OutboxHandlerResult,
    OutboxHandlerStatus,
)
from app.modules.room.realtime_service import push_room_list_updated, push_room_updated
from app.modules.room.repository import RoomRepository
from app.modules.room.mapper import build_room_response
from app.modules.room.terminal_finalize_commit_repository import (
    TerminalFinalizeCommitRepository,
    terminal_finalize_commit_repository,
)

logger = logging.getLogger(__name__)

TERMINAL_RECOVERY_REQUIRED_CODES = frozenset(
    {
        "TERMINAL_RUNTIME_MISSING",
        "TERMINAL_METADATA_INVALID",
        "SETTLEMENT_STATUS_INVALID",
        "TERMINAL_DISPLAY_UNTIL_INVALID",
        "FINALIZE_PAYLOAD_INVALID",
    }
)


class GameTerminalFinalizeService(object):
    """Finalize terminal rooms after display and settlement completion."""

    def __init__(
        self,
        repository: RoomRepository,
        state_reader: GameStateReader,
        lock_service: RedisDistributedLock,
        finalize_commit_repository: Optional[TerminalFinalizeCommitRepository] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        """
        初始化终局收敛服务。
        :param repository: 房间 Redis 仓库。
        :param state_reader: 一致性对局状态读取器。
        :param finalize_commit_repository: 终局原子提交仓库。
        :param clock: 可注入时钟。
        """
        self._repository = repository
        self._state_reader = state_reader
        self._lock_service = lock_service
        self._finalize_commit_repository = (
            finalize_commit_repository or terminal_finalize_commit_repository
        )
        self._clock = clock or system_clock

    async def finalize_terminal_room(
        self,
        room_id: str,
        payload: Dict[str, Any],
    ) -> OutboxHandlerResult:
        """
        执行终局收敛：回到 waiting、清理 runtime，必要时解散房间。
        :param room_id: 房间 ID。
        :param payload: TERMINAL_FINALIZE Outbox 载荷。
        :return: 终局收敛严格执行结果。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return self._result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                "FINALIZE_ROOM_ID_INVALID",
                "roomId 不能为空",
            )
        contract_error = self._validate_payload(payload)
        if contract_error is not None:
            return await self._recover_invalid_finalize_payload(
                normalized_room_id,
                payload,
                contract_error.reasonCode,
                contract_error.reasonMessage,
            )
        payload = self._normalize_payload(payload)
        expected_game_version = int(payload["gameVersion"])

        try:
            meta = await self._repository.get_meta(normalized_room_id)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("FINALIZE_META_READ_FAILED", exc)
        except Exception as exc:
            logger.exception("terminal finalize meta read failed, roomId=%s", normalized_room_id)
            return self._temporary_failure("FINALIZE_META_READ_FAILED", exc)
        if meta is None:
            return self._result(
                OutboxHandlerStatus.ALREADY_DONE,
                "ROOM_ALREADY_DELETED",
                "room already deleted",
            )
        if str(meta.get("status", "")).strip() == "waiting":
            return self._result(
                OutboxHandlerStatus.ALREADY_DONE,
                "ROOM_ALREADY_WAITING",
                "房间已完成终局收敛",
            )
        if str(meta.get("status", "")).strip() != "playing":
            return self._result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                "ROOM_STATUS_INVALID",
                "终局收敛要求房间处于 playing",
            )

        game_code = str(meta.get("gameCode", "")).strip()
        dissolve = bool(payload.get("dissolveAfterTerminal"))
        owner_transfer = self._parse_owner_transfer(payload.get("ownerTransferPlan"))
        if payload.get("ownerTransferPlan") is not None and owner_transfer is None:
            return self._result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                "OWNER_TRANSFER_PLAN_INVALID",
                "ownerTransferPlan 合同损坏",
            )
        member_ids_to_remove = payload.get("memberIdsToRemove")
        try:
            consistent_state = await self._state_reader.load_consistent(normalized_room_id)
            members_before_finalize = await self._repository.list_players(normalized_room_id)
            room_version = await self._repository.get_room_version(normalized_room_id)
        except GameRuntimeNotFoundException:
            return await self._terminal_recovery_required(
                normalized_room_id,
                payload,
                "TERMINAL_RUNTIME_MISSING",
                "playing 房间缺少终局 Runtime",
            )
        except RetryableGameStateInconsistentException as exc:
            return self._temporary_failure("FINALIZE_STATE_INCONSISTENT", exc)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("FINALIZE_STATE_READ_FAILED", exc)
        except Exception as exc:
            logger.exception("terminal finalize state read failed, roomId=%s", normalized_room_id)
            return self._temporary_failure("FINALIZE_STATE_READ_FAILED", exc)
        snapshot = consistent_state.snapshot
        runtime_data = snapshot.model_dump()
        if int(consistent_state.gameVersion) != int(expected_game_version):
            return await self._classify_version_conflict(
                normalized_room_id,
                payload,
                int(expected_game_version),
            )
        if not bool(snapshot.isGameOver) or snapshot.terminalMetadata is None:
            return self._result(
                OutboxHandlerStatus.OBSOLETE,
                "FINALIZE_STATE_OBSOLETE",
                "权威快照已不再处于终局",
            )
        readiness_result = self._evaluate_terminal_readiness(runtime_data)
        if readiness_result is not None:
            if readiness_result.reasonCode in TERMINAL_RECOVERY_REQUIRED_CODES:
                return await self._terminal_recovery_required(
                    normalized_room_id,
                    payload,
                    readiness_result.reasonCode,
                    readiness_result.reasonMessage,
                )
            return readiness_result
        require_settlement_done = self._runtime_requires_settlement(runtime_data)

        next_meta = copy.deepcopy(meta)
        if owner_transfer is not None:
            next_meta["ownerPlayerId"] = owner_transfer.ownerPlayerId
            next_meta["ownerNickname"] = owner_transfer.ownerNickname
        next_meta["status"] = "waiting"
        finalized_at = int(payload.get("finalizedAt") or 0)
        next_meta["updatedAt"] = finalized_at or next_meta.get("updatedAt", 0)

        if room_version is None:
            room_version = 0
        next_room_version = int(room_version) + 1

        try:
            cleanup_payload = {
                "roomId": normalized_room_id,
                "terminalVersion": int(expected_game_version),
                "terminalRoomVersion": next_room_version,
                "playerIds": [
                    str(item.get("playerId", "")).strip()
                    for item in members_before_finalize
                    if str(item.get("playerId", "")).strip()
                ],
                "memberIdsToRemove": list(member_ids_to_remove or []),
                "dissolveRoom": bool(dissolve),
                "ownerTransferPlan": payload.get("ownerTransferPlan"),
                "cleanupReason": "terminalFinalize",
                "gameCode": game_code,
            }
            cleanup_dedupe_key = "{0}:terminal-derived-cleanup:{1}".format(
                normalized_room_id,
                next_room_version,
            )
            commit_result = await self._finalize_commit_repository.commit_finalize(
                room_id=normalized_room_id,
                expected_game_version=int(expected_game_version),
                expected_room_version=int(room_version),
                next_room_version=next_room_version,
                next_meta=next_meta,
                member_ids_to_remove=member_ids_to_remove,
                require_settlement_done=require_settlement_done,
                dissolve_room=dissolve,
                cleanup_payload=cleanup_payload,
                cleanup_outbox_id=cleanup_dedupe_key,
                cleanup_dedupe_key=cleanup_dedupe_key,
                cleanup_available_at=int(self._clock.now_ms()),
                commit_id=str(payload.get("commitId") or cleanup_dedupe_key),
            )
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("FINALIZE_COMMIT_TEMPORARY_FAILURE", exc)
        except Exception as exc:
            logger.exception("terminal finalize commit failed, roomId=%s", normalized_room_id)
            return self._temporary_failure("FINALIZE_COMMIT_TEMPORARY_FAILURE", exc)
        if commit_result.status == "ALREADY_FINALIZED":
            return self._result(
                OutboxHandlerStatus.ALREADY_DONE,
                "ROOM_ALREADY_FINALIZED",
                "房间已完成终局收敛",
            )
        if commit_result.status == "ROOM_NOT_FOUND":
            return self._result(
                OutboxHandlerStatus.ALREADY_DONE,
                "ROOM_ALREADY_DELETED",
                "room already deleted",
            )
        if commit_result.status == "VERSION_CONFLICT":
            return await self._classify_version_conflict(
                normalized_room_id,
                payload,
                int(expected_game_version),
            )
        if commit_result.status == "ROOM_VERSION_CONFLICT":
            return await self._classify_version_conflict(
                normalized_room_id,
                payload,
                int(expected_game_version),
                require_newer_game_version=False,
            )
        if commit_result.status == "SETTLEMENT_NOT_READY":
            return self._result(
                OutboxHandlerStatus.RETRY,
                "SETTLEMENT_PENDING",
                "平台结算尚未完成",
            )
        if commit_result.status != "COMMITTED":
            logger.warning(
                "terminal finalize commit unexpected status=%s roomId=%s",
                commit_result.status,
                normalized_room_id,
            )
            return self._result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                "FINALIZE_COMMIT_STATUS_INVALID",
                "terminal finalize commit returned unrecoverable status",
            )

        return self._result(
            OutboxHandlerStatus.DONE,
            "ROOM_RETURNED_TO_WAITING",
            "房间终局已提交，派生清理由独立 Outbox 补偿",
        )

    async def _classify_version_conflict(
        self,
        room_id: str,
        payload: Dict[str, Any],
        expected_game_version: int,
        require_newer_game_version: bool = True,
    ) -> OutboxHandlerResult:
        """CAS 冲突后重读权威快照并重建终局载荷。"""
        try:
            meta = await self._repository.get_meta(room_id)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("FINALIZE_CONFLICT_REREAD_FAILED", exc)
        if meta is None or str(meta.get("status", "")).strip() == "waiting":
            return self._result(
                OutboxHandlerStatus.ALREADY_DONE,
                "ROOM_ALREADY_FINALIZED",
                "房间已完成终局收敛",
            )
        if str(meta.get("status", "")).strip() != "playing":
            return self._result(
                OutboxHandlerStatus.OBSOLETE,
                "FINALIZE_CONFLICT_ROOM_OBSOLETE",
                "房间状态已变化",
            )
        try:
            consistent_state = await self._state_reader.load_consistent(room_id)
        except GameRuntimeNotFoundException:
            return self._result(
                OutboxHandlerStatus.OBSOLETE,
                "FINALIZE_CONFLICT_RUNTIME_MISSING",
                "权威 Runtime 已不存在",
            )
        except RetryableGameStateInconsistentException as exc:
            return self._temporary_failure("FINALIZE_CONFLICT_REREAD_INCONSISTENT", exc)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("FINALIZE_CONFLICT_REREAD_FAILED", exc)
        except Exception as exc:
            logger.exception("finalize conflict state reader failed, roomId=%s", room_id)
            return self._temporary_failure("FINALIZE_CONFLICT_REREAD_FAILED", exc)
        snapshot = consistent_state.snapshot
        if not bool(snapshot.isGameOver) or snapshot.terminalMetadata is None:
            return self._result(
                OutboxHandlerStatus.OBSOLETE,
                "FINALIZE_CONFLICT_STATE_OBSOLETE",
                "权威快照已不再处于终局",
            )
        next_version = int(consistent_state.gameVersion)
        if require_newer_game_version and next_version <= int(expected_game_version):
            return self._result(
                OutboxHandlerStatus.RETRY,
                "FINALIZE_VERSION_CONFLICT_RACE",
                "CAS 冲突后未读取到更新的权威版本",
            )
        next_payload = self._build_payload_from_terminal_snapshot(room_id, consistent_state)
        return await self.finalize_terminal_room(room_id, next_payload)

    async def _recover_invalid_finalize_payload(
        self,
        room_id: str,
        payload: Dict[str, Any],
        reason_code: str,
        reason_message: str,
    ) -> OutboxHandlerResult:
        """从权威终局快照恢复损坏的 Finalize 载荷。"""
        try:
            meta = await self._repository.get_meta(room_id)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("FINALIZE_PAYLOAD_RECOVERY_READ_FAILED", exc)
        if meta is None or str(meta.get("status", "")).strip() == "waiting":
            return self._result(
                OutboxHandlerStatus.ALREADY_DONE,
                "ROOM_ALREADY_FINALIZED",
                "房间已完成终局收敛",
            )
        if str(meta.get("status", "")).strip() != "playing":
            return self._result(
                OutboxHandlerStatus.OBSOLETE,
                "FINALIZE_PAYLOAD_ROOM_OBSOLETE",
                "房间状态已变化",
            )
        try:
            consistent_state = await self._state_reader.load_consistent(room_id)
        except GameRuntimeNotFoundException:
            return await self._terminal_recovery_required(
                room_id,
                payload,
                "TERMINAL_RUNTIME_MISSING",
                reason_message,
            )
        except RetryableGameStateInconsistentException as exc:
            return self._temporary_failure("FINALIZE_PAYLOAD_RECOVERY_INCONSISTENT", exc)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("FINALIZE_PAYLOAD_RECOVERY_READ_FAILED", exc)
        except Exception:
            logger.exception("finalize payload recovery state reader failed, roomId=%s", room_id)
            return await self._terminal_recovery_required(
                room_id,
                payload,
                reason_code,
                reason_message,
            )
        snapshot = consistent_state.snapshot
        if not bool(snapshot.isGameOver) or snapshot.terminalMetadata is None:
            return self._result(
                OutboxHandlerStatus.OBSOLETE,
                "FINALIZE_PAYLOAD_STATE_OBSOLETE",
                "权威快照已不再处于终局",
            )
        return await self.finalize_terminal_room(
            room_id,
            self._build_payload_from_terminal_snapshot(room_id, consistent_state),
        )

    @staticmethod
    def _build_payload_from_terminal_snapshot(room_id: str, consistent_state: Any) -> Dict[str, Any]:
        """根据一致性终局快照构造 TERMINAL_FINALIZE 载荷。"""
        metadata = consistent_state.snapshot.terminalMetadata
        owner_transfer = (
            metadata.ownerTransferPlan.model_dump()
            if metadata.ownerTransferPlan is not None
            else None
        )
        game_version = int(consistent_state.gameVersion)
        return {
            "roomId": room_id,
            "gameVersion": game_version,
            "dissolveAfterTerminal": bool(metadata.dissolveAfterTerminal),
            "memberIdsToRemove": list(metadata.membersToRemoveAfterTerminal or []),
            "ownerTransferPlan": owner_transfer,
            "finalizedAt": int(metadata.terminalDisplayUntil),
            "commitId": "{0}:terminal-finalize:{1}".format(room_id, game_version),
        }

    async def _terminal_recovery_required(
        self,
        room_id: str,
        payload: Dict[str, Any],
        reason_code: str,
        reason_message: str,
    ) -> OutboxHandlerResult:
        """将损坏终局以当前权威版本 CAS 收敛为安全 waiting 状态。"""
        normalized_reason = str(reason_code or "TERMINAL_RECOVERY_REQUIRED").strip()
        if normalized_reason not in TERMINAL_RECOVERY_REQUIRED_CODES:
            return self._result(
                OutboxHandlerStatus.PERMANENT_FAILURE,
                normalized_reason,
                reason_message,
            )
        try:
            meta = await self._repository.get_meta(room_id)
            runtime_data = await self._repository.get_runtime(room_id)
            room_version = await self._repository.get_room_version(room_id)
            game_version = await self._repository.get_game_version(room_id)
            members = await self._repository.list_players(room_id)
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("TERMINAL_RECOVERY_READ_FAILED", exc)
        if meta is None or str(meta.get("status", "")).strip() == "waiting":
            return self._result(
                OutboxHandlerStatus.ALREADY_DONE,
                "ROOM_ALREADY_FINALIZED",
                "房间已完成终局收敛",
            )
        if str(meta.get("status", "")).strip() != "playing":
            return self._result(
                OutboxHandlerStatus.OBSOLETE,
                "TERMINAL_RECOVERY_ROOM_OBSOLETE",
                "房间状态已变化",
            )
        if game_version is None:
            return self._result(
                OutboxHandlerStatus.RETRY,
                "TERMINAL_RECOVERY_VERSION_MISSING",
                "无法获得终局 CAS 所需的对局版本",
            )
        payload_game_version = 0
        if isinstance(payload, dict):
            try:
                payload_game_version = int(payload.get("gameVersion") or 0)
            except (TypeError, ValueError):
                payload_game_version = 0
        authoritative_game_version = int(game_version)
        logger.error(
            "terminal recovery required, roomId=%s roomVersion=%s gameVersion=%s "
            "reasonCode=%s reasonMessage=%s payload=%s terminalMetadata=%s",
            room_id,
            room_version,
            game_version,
            normalized_reason,
            str(reason_message or "")[:500],
            payload,
            runtime_data.get("terminalMetadata") if isinstance(runtime_data, dict) else None,
        )
        next_meta = copy.deepcopy(meta)
        next_meta["status"] = "waiting"
        next_meta["updatedAt"] = int(self._clock.now_ms())
        next_meta["terminalRecovery"] = {
            "status": "MANUAL_COMPENSATION_REQUIRED",
            "requiresManualCompensation": True,
            "reasonCode": normalized_reason,
            "reasonMessage": str(reason_message or "")[:500],
            "roomVersion": int(room_version or 0),
            "gameVersion": authoritative_game_version,
            "terminalMetadata": (
                runtime_data.get("terminalMetadata") if isinstance(runtime_data, dict) else None
            ),
            "terminalDirective": (
                runtime_data.get("terminalDirective") if isinstance(runtime_data, dict) else None
            ),
            "settlementEvidence": self._extract_settlement_evidence(runtime_data),
        }
        player_ids = [
            str(item.get("playerId", "")).strip()
            for item in members
            if str(item.get("playerId", "")).strip()
        ]
        cleanup_payload = {
            "roomId": room_id,
            "terminalVersion": authoritative_game_version,
            "terminalRoomVersion": int(room_version or 0) + 1,
            "playerIds": player_ids,
            "memberIdsToRemove": [],
            "dissolveRoom": False,
            "ownerTransferPlan": None,
            "cleanupReason": "terminalRecoveryRequired",
            "gameCode": str(meta.get("gameCode", "")).strip(),
        }
        cleanup_dedupe_key = "{0}:terminal-derived-cleanup:recovery:{1}".format(
            room_id,
            int(room_version or 0) + 1,
        )
        try:
            commit_result = await self._finalize_commit_repository.commit_finalize(
                room_id=room_id,
                expected_game_version=authoritative_game_version,
                expected_room_version=int(room_version or 0),
                next_room_version=int(room_version or 0) + 1,
                next_meta=next_meta,
                member_ids_to_remove=[],
                require_settlement_done=False,
                dissolve_room=False,
                cleanup_payload=cleanup_payload,
                cleanup_outbox_id=cleanup_dedupe_key,
                cleanup_dedupe_key=cleanup_dedupe_key,
                cleanup_available_at=int(self._clock.now_ms()),
                commit_id="{0}:terminal-recovery:{1}:{2}".format(
                    room_id,
                    normalized_reason,
                    payload_game_version,
                ),
            )
        except (RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("TERMINAL_RECOVERY_COMMIT_FAILED", exc)
        if commit_result.status in ("COMMITTED", "ALREADY_FINALIZED", "ROOM_NOT_FOUND"):
            return self._result(
                OutboxHandlerStatus.DONE,
                "TERMINAL_RECOVERY_REQUIRED",
                "terminal recovery committed safe waiting state",
            )
        if commit_result.status == "VERSION_CONFLICT":
            return self._result(
                OutboxHandlerStatus.RETRY,
                "TERMINAL_RECOVERY_VERSION_CONFLICT",
                "终局恢复 CAS 冲突，需重读权威状态",
            )
        return self._result(
            OutboxHandlerStatus.RETRY,
            "TERMINAL_RECOVERY_REQUIRED",
            "terminal recovery could not commit yet",
        )

    async def cleanup_terminal_derived(
        self,
        room_id: str,
        payload: Dict[str, Any],
    ) -> OutboxHandlerResult:
        """与开局共用房间锁，并以终局房间版本原子清理所属索引。"""
        if not isinstance(payload, dict) or not payload:
            return self._result(OutboxHandlerStatus.PERMANENT_FAILURE,
                                "DERIVED_CLEANUP_PAYLOAD_INVALID", "payload 不能为空")
        normalized_room_id = str(room_id or payload.get("roomId") or "").strip()
        try:
            terminal_room_version = int(payload["terminalRoomVersion"])
            if not normalized_room_id or terminal_room_version < 1:
                raise ValueError("invalid terminal room version")
        except (KeyError, TypeError, ValueError):
            return self._result(OutboxHandlerStatus.PERMANENT_FAILURE,
                                "DERIVED_CLEANUP_GENERATION_INVALID", "终局房间版本缺失或无效")
        try:
            lock = await self._lock_service.acquire(
                RedisKeys.room_lock(normalized_room_id),
                ttl_seconds=ROOM_ACTION_LOCK_TTL_SECONDS,
                owner_hint="terminal-cleanup",
            )
            async with lock:
                meta = await self._repository.get_meta(normalized_room_id)
                members = await self._repository.list_players(normalized_room_id) if meta else []
                game_code = str(payload.get("gameCode") or (meta or {}).get("gameCode") or "").strip()
                cleanup_member_ids = list(dict.fromkeys(
                    str(item).strip()
                    for item in list(payload.get("playerIds", []))
                    + list(payload.get("memberIdsToRemove", []))
                    + [member.get("playerId", "") for member in members]
                    if item and str(item).strip()
                ))
                cleaned = await self._finalize_commit_repository.cleanup_derived_indexes(
                    normalized_room_id, terminal_room_version, game_code, cleanup_member_ids,
                )
                if not cleaned:
                    return self._result(OutboxHandlerStatus.OBSOLETE,
                                        "DERIVED_CLEANUP_OBSOLETE", "房间已进入新的状态或对局")
                if not bool(payload.get("dissolveRoom")) and meta is not None:
                    room_response = build_room_response(meta, members, terminal_room_version)
                    try:
                        await push_room_updated(room_response)
                    except Exception:
                        logger.exception("terminal cleanup room push failed, roomId=%s", normalized_room_id)
                if game_code:
                    try:
                        await push_room_list_updated(game_code)
                    except Exception:
                        logger.exception("terminal cleanup list push failed, roomId=%s", normalized_room_id)
        except (LockAcquireError, RedisError, OSError, TimeoutError) as exc:
            return self._temporary_failure("DERIVED_CLEANUP_TEMPORARY_FAILURE", exc)
        except Exception as exc:
            logger.exception("terminal derived cleanup failed, roomId=%s", normalized_room_id)
            return self._temporary_failure("DERIVED_CLEANUP_FAILED", exc)
        return self._result(OutboxHandlerStatus.DONE,
                            "DERIVED_CLEANUP_DONE", "terminal derived indexes cleaned")

    def _evaluate_terminal_readiness(
        self,
        runtime_data: Dict[str, Any],
    ) -> Optional[OutboxHandlerResult]:
        """
        Check settlement and display-window readiness.
        :param runtime_data: Authoritative runtime data.
        :return: Blocking result, or None when finalization may run.
        """
        terminal_metadata = runtime_data.get("terminalMetadata")
        if not isinstance(terminal_metadata, dict):
            return self._result(
                OutboxHandlerStatus.RECOVER,
                "TERMINAL_METADATA_INVALID",
                "terminalMetadata 合同损坏",
            )
        raw_settlement_status = terminal_metadata.get("settlementStatus")
        raw_settlement_id = terminal_metadata.get("settlementId")
        settlement_status = "" if raw_settlement_status is None else str(raw_settlement_status).strip()
        settlement_id = "" if raw_settlement_id is None else str(raw_settlement_id).strip()
        if settlement_id and settlement_status == "PENDING":
            return self._result(
                OutboxHandlerStatus.RETRY,
                "SETTLEMENT_PENDING",
                "平台结算尚未完成",
            )
        if settlement_id and settlement_status not in ("COMPLETED", "FAILED"):
            return self._result(
                OutboxHandlerStatus.RECOVER,
                "SETTLEMENT_STATUS_INVALID",
                "settlementStatus 合同损坏",
            )
        display_until = terminal_metadata.get("terminalDisplayUntil")
        try:
            normalized_display_until = int(display_until)
        except (TypeError, ValueError):
            return self._result(
                OutboxHandlerStatus.RECOVER,
                "TERMINAL_DISPLAY_UNTIL_INVALID",
                "terminalDisplayUntil 合同损坏",
            )
        remaining_ms = normalized_display_until - int(self._clock.now_ms())
        if remaining_ms > 0:
            return self._result(
                OutboxHandlerStatus.RETRY,
                "TERMINAL_DISPLAY_NOT_FINISHED",
                "终局展示时间尚未结束",
                remaining_ms,
            )
        return None

    @staticmethod
    def _runtime_requires_settlement(runtime_data: Dict[str, Any]) -> bool:
        """
        判断 Runtime 是否包含平台结算合同。
        :param runtime_data: 权威 Runtime 数据。
        :return: 是否要求提交层校验结算状态。
        """
        terminal_metadata = runtime_data.get("terminalMetadata")
        if not isinstance(terminal_metadata, dict):
            return False
        return bool(str(terminal_metadata.get("settlementId", "")).strip())

    @staticmethod
    def _validate_payload(payload: Dict[str, Any]) -> Optional[OutboxHandlerResult]:
        """
        校验 TERMINAL_FINALIZE Outbox 载荷合同。
        :param payload: Outbox 载荷。
        :return: 合同失败结果；合法时返回 ``None``。
        """
        if not isinstance(payload, dict) or not payload:
            return GameTerminalFinalizeService._result(
                OutboxHandlerStatus.RECOVER,
                "FINALIZE_PAYLOAD_INVALID",
                "memberIdsToRemove must be a list",
            )
        try:
            int(payload.get("gameVersion"))
            int(payload.get("finalizedAt"))
        except (TypeError, ValueError):
            return GameTerminalFinalizeService._result(
                OutboxHandlerStatus.RECOVER,
                "FINALIZE_PAYLOAD_INVALID",
                "gameVersion 或 finalizedAt 合同损坏",
            )
        member_ids = payload.get("memberIdsToRemove")
        if isinstance(member_ids, dict) and not member_ids:
            return None
        if not isinstance(member_ids, list):
            return GameTerminalFinalizeService._result(
                OutboxHandlerStatus.RECOVER,
                "FINALIZE_PAYLOAD_INVALID",
                "TERMINAL_FINALIZE payload 不能为空",
            )
        return None

    @staticmethod
    def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Lua/cjson artifacts in terminal finalize payloads.
        :param payload: Raw TERMINAL_FINALIZE payload.
        :return: Normalized payload.
        """
        normalized = dict(payload)
        member_ids = normalized.get("memberIdsToRemove")
        if isinstance(member_ids, dict) and not member_ids:
            normalized["memberIdsToRemove"] = []
        return normalized

    @staticmethod
    def _result(
        status: OutboxHandlerStatus,
        reason_code: str,
        reason_message: str,
        retry_after_ms: Optional[int] = None,
    ) -> OutboxHandlerResult:
        """
        构造终局收敛严格结果。
        :param status: 执行状态。
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

    @staticmethod
    def _temporary_failure(reason_code: str, exc: Exception) -> OutboxHandlerResult:
        """
        Convert infrastructure errors into retryable results.
        :param reason_code: Reason code.
        :param exc: Original exception.
        :return: Retryable result.
        """
        return GameTerminalFinalizeService._result(
            OutboxHandlerStatus.RETRY,
            reason_code,
            str(exc or "temporary infrastructure failure"),
        )

    def _parse_owner_transfer(self, raw: object) -> Optional[OwnerTransferPlan]:
        """
        Parse owner transfer payload.
        :param raw: Raw payload.
        :return: Owner transfer plan, or ``None`` when invalid.
        """
        if not isinstance(raw, dict):
            return None
        try:
            return OwnerTransferPlan.model_validate(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_settlement_evidence(runtime_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取可用于人工补偿核对的终局结算证据。
        :param runtime_data: 当前可读取的权威 Runtime 原始数据。
        :return: 仅包含结算标识、状态和结果标识的审计数据。
        """
        metadata = runtime_data.get("terminalMetadata") if isinstance(runtime_data, dict) else None
        if not isinstance(metadata, dict):
            return {}
        return {
            "settlementId": metadata.get("settlementId"),
            "settlementStatus": metadata.get("settlementStatus"),
            "settlementResultId": metadata.get("settlementResultId"),
        }
