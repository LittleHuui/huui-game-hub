"""房间对局原子提交编排服务。"""

from typing import List, Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.id_utils import generate_server_id
from app.core.time_utils import now_ms
from app.modules.room.game_completion_schemas import GameCompletionPlan
from app.modules.room.post_turn_plan import PostTurnPlan
from app.modules.room.room_game_commit_repository import (
    RoomGameCommitRepository,
    room_game_commit_repository,
)
from app.modules.room.room_game_commit_schemas import (
    ActionRequestRecord,
    PostTurnOutboxRecord,
    RoomGameCommit,
    RoomGameCommitResult,
)
from app.modules.strategy_turn.schemas import RuntimeSnapshot
from app.modules.strategy_turn.terminal_schemas import TerminalMetadata
from app.modules.room.match_event_store import MatchEventStore, match_event_store
import logging

logger = logging.getLogger(__name__)


class RoomGameCommitService(object):
    """封装对局状态原子提交的公共构建与执行逻辑。"""

    def __init__(
        self,
        commit_repository: Optional[RoomGameCommitRepository] = None,
        event_store: MatchEventStore = match_event_store,
    ) -> None:
        """
        初始化原子提交编排服务。

        :param commit_repository: 原子提交仓库。
        """
        self._commit_repository = commit_repository or room_game_commit_repository
        self._event_store = event_store

    async def commit_state_change(
        self,
        room_id: str,
        expected_version: int,
        next_snapshot: Optional[RuntimeSnapshot],
        next_room_meta: dict,
        delete_runtime: bool = False,
        request_record: Optional[ActionRequestRecord] = None,
        outbox_reason: Optional[str] = None,
        outbox_records: Optional[List[PostTurnOutboxRecord]] = None,
        commit_id: Optional[str] = None,
        committed_at: Optional[int] = None,
        expected_room_version: Optional[int] = None,
        next_room_version: Optional[int] = None,
        member_upserts: Optional[dict] = None,
        member_deletes: Optional[List[str]] = None,
    ) -> RoomGameCommitResult:
        """
        执行一次对局状态原子提交。

        :param room_id: 房间 ID。
        :param expected_version: 期望当前对局版本号。
        :param next_snapshot: 下一版运行时快照；删除运行时时可为 ``None``。
        :param next_room_meta: 下一版房间元信息。
        :param delete_runtime: 是否删除运行时快照。
        :param request_record: 可选动作请求幂等记录。
        :param outbox_reason: 回合后 Outbox 调度原因；为空时不写 Outbox。
        :param outbox_records: 显式 Outbox 记录；优先于 outbox_reason 推断。
        :param commit_id: 提交 ID；为空时自动生成。
        :param committed_at: 提交时间戳；为空时使用当前时间。
        :param expected_room_version: 期望房间元数据版本号。
        :param next_room_version: 下一版房间元数据版本号。
        :return: 提交结果。
        :raises BizException: 版本冲突、请求冲突或提交失败。
        """
        normalized_room_id = str(room_id or "").strip()
        current_version = int(expected_version)
        next_version = current_version + 1
        timestamp = int(committed_at) if committed_at is not None else now_ms()
        normalized_commit_id = str(commit_id or generate_server_id("commit")).strip()
        stamped_snapshot = None
        if next_snapshot is not None and not delete_runtime:
            stamped_snapshot = next_snapshot.model_copy(update={"commitVersion": next_version})
        outbox_items = list(outbox_records or [])
        if outbox_reason and stamped_snapshot is not None and not bool(stamped_snapshot.isGameOver):
            outbox_items.extend(
                self.build_post_turn_outbox_records(
                    normalized_room_id,
                    stamped_snapshot,
                    next_version,
                    normalized_commit_id,
                    timestamp,
                    outbox_reason,
                ),
            )
        commit = RoomGameCommit(
            roomId=normalized_room_id,
            expectedGameVersion=current_version,
            nextGameVersion=next_version,
            expectedRoomVersion=expected_room_version,
            nextRoomVersion=next_room_version,
            nextRuntimeSnapshot=stamped_snapshot,
            deleteRuntime=bool(delete_runtime),
            nextRoomMeta=next_room_meta,
            memberUpserts=dict(member_upserts or {}),
            memberDeletes=list(member_deletes or []),
            requestRecord=request_record,
            outboxRecords=outbox_items,
            commitId=normalized_commit_id,
            committedAt=timestamp,
        )
        result = await self._commit_repository.commit(commit)
        self._raise_on_commit_failure(result)
        if result.status == "COMMITTED" and stamped_snapshot is not None:
            try:
                await self._event_store.archive(
                    normalized_room_id,
                    list(stamped_snapshot.eventLog),
                )
            except Exception:
                logger.exception(
                    "match event archive failed after commit, roomId=%s commitId=%s",
                    normalized_room_id,
                    normalized_commit_id,
                )
        return result

    def build_post_turn_outbox_records(
        self,
        room_id: str,
        snapshot: RuntimeSnapshot,
        version: int,
        commit_id: str,
        committed_at: int,
        reason: str,
    ) -> List[PostTurnOutboxRecord]:
        """
        构造回合后 Outbox 记录。

        :param room_id: 房间 ID。
        :param snapshot: 当前运行时快照。
        :param version: 提交后的版本号。
        :param commit_id: 提交 ID。
        :param committed_at: 提交时间戳。
        :param reason: 调度原因。
        :return: Outbox 记录列表。
        """
        if bool(snapshot.isGameOver):
            return []
        state = snapshot.state if isinstance(snapshot.state, dict) else {}
        plan = PostTurnPlan(
            roomId=str(room_id or "").strip(),
            version=int(version),
            reason=str(reason or "").strip() or "afterAction",
            gameCode=str(snapshot.gameCode or "").strip(),
            currentPlayerId=str(state.get("currentPlayerId", "")).strip(),
            phase=str(state.get("phase", "")).strip(),
            enqueuedAtMs=int(committed_at),
        )
        dedupe_key = "{0}:{1}:{2}".format(plan.roomId, int(version), plan.reason)
        return [
            PostTurnOutboxRecord(
                outboxId=generate_server_id("outbox"),
                roomId=plan.roomId,
                sourceCommitId=commit_id,
                sourceVersion=int(version),
                taskType="postTurnPlan",
                payload=plan.model_dump(),
                status="PENDING",
                attemptCount=0,
                availableAt=int(committed_at),
                leaseUntil=None,
                lastFailureReason=None,
                createdAt=int(committed_at),
                updatedAt=int(committed_at),
                dedupeKey=dedupe_key,
            )
        ]

    def build_terminal_outbox_records(
        self,
        room_id: str,
        plan: GameCompletionPlan,
        version: int,
        commit_id: str,
        committed_at: int,
    ) -> List[PostTurnOutboxRecord]:
        """
        构造终局阶段 Outbox 记录。

        :param room_id: 房间 ID。
        :param plan: 终局计划。
        :param version: 提交后的对局版本号。
        :param commit_id: 提交 ID。
        :param committed_at: 提交时间戳。
        :return: Outbox 记录列表。
        """
        normalized_room_id = str(room_id or "").strip()
        records = []
        if plan.settlementRequired:
            settlement_id = None
            terminal_metadata = plan.terminalSnapshot.terminalMetadata
            if terminal_metadata is not None and terminal_metadata.settlementId:
                settlement_id = str(terminal_metadata.settlementId).strip() or None
            records.append(
                PostTurnOutboxRecord(
                    outboxId=generate_server_id("outbox"),
                    roomId=normalized_room_id,
                    sourceCommitId=commit_id,
                    sourceVersion=int(version),
                    taskType="GAME_SETTLEMENT",
                    payload={
                        "roomId": normalized_room_id,
                        "gameVersion": int(version),
                        "settlementId": settlement_id,
                        "gameCode": str(plan.terminalSnapshot.gameCode or "").strip(),
                    },
                    status="PENDING",
                    attemptCount=0,
                    availableAt=int(committed_at),
                    leaseUntil=None,
                    lastFailureReason=None,
                    createdAt=int(committed_at),
                    updatedAt=int(committed_at),
                    dedupeKey="{0}:settlement:{1}".format(normalized_room_id, settlement_id or version),
                ),
            )
            return records
        terminal_metadata = plan.terminalSnapshot.terminalMetadata
        if terminal_metadata is None:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="终局元数据缺失")
        records.append(
            self.build_finalize_outbox_record(
                normalized_room_id,
                terminal_metadata,
                int(version),
                commit_id,
                int(committed_at),
                int(plan.terminalDisplayUntil),
            ),
        )
        return records

    def build_finalize_outbox_record(
        self,
        room_id: str,
        terminal_metadata: TerminalMetadata,
        game_version: int,
        commit_id: str,
        committed_at: int,
        display_until: int,
    ) -> PostTurnOutboxRecord:
        """
        构造终局收敛 Outbox 记录（结算完成后或无需结算时调用）。

        :param room_id: 房间 ID。
        :param terminal_metadata: 终局元数据（含解散与成员清理计划）。
        :param game_version: 提交后的对局版本号。
        :param commit_id: 提交 ID。
        :param committed_at: 提交时间戳。
        :param display_until: 终局展示截止时间。
        :return: TERMINAL_FINALIZE Outbox 记录。
        """
        normalized_room_id = str(room_id or "").strip()
        owner_payload = None
        if terminal_metadata.ownerTransferPlan is not None:
            owner_payload = terminal_metadata.ownerTransferPlan.model_dump()
        member_ids = list(terminal_metadata.membersToRemoveAfterTerminal or [])
        finalize_payload = {
            "roomId": normalized_room_id,
            "gameVersion": int(game_version),
            "dissolveAfterTerminal": bool(terminal_metadata.dissolveAfterTerminal),
            "memberIdsToRemove": list(member_ids),
            "ownerTransferPlan": owner_payload,
            "finalizedAt": int(display_until),
        }
        return PostTurnOutboxRecord(
            outboxId=generate_server_id("outbox"),
            roomId=normalized_room_id,
            sourceCommitId=commit_id,
            sourceVersion=int(game_version),
            taskType="TERMINAL_FINALIZE",
            payload=finalize_payload,
            status="PENDING",
            attemptCount=0,
            availableAt=int(display_until),
            leaseUntil=None,
            lastFailureReason=None,
            createdAt=int(committed_at),
            updatedAt=int(committed_at),
            dedupeKey="{0}:terminal-finalize:{1}".format(normalized_room_id, int(game_version)),
        )

    def _raise_on_commit_failure(self, result: RoomGameCommitResult) -> None:
        """
        将提交失败结果转换为业务异常。

        :param result: 提交结果。
        :return: 无。
        :raises BizException: 非 COMMITTED/REPLAY 状态时抛出。
        """
        if result.status == "COMMITTED" or result.status == "REPLAY":
            return
        if result.status == "VERSION_CONFLICT":
            raise BizException(ErrorCode.GAME_VIEW_VERSION_CONFLICT)
        if result.status == "REQUEST_CONFLICT":
            raise BizException(ErrorCode.REQUEST_ID_CONFLICT)
        if result.status == "ROOM_NOT_FOUND":
            raise BizException(ErrorCode.ROOM_NOT_FOUND)
        raise BizException(ErrorCode.SYSTEM_ERROR, message="房间对局提交失败")


room_game_commit_service = RoomGameCommitService()
