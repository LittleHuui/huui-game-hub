"""房间对局动作提交命令服务。"""

import asyncio
import logging
from typing import Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.id_utils import generate_server_id
from app.core.lock.distributed_lock import RedisDistributedLock
from app.core.time_utils import now_ms
from app.modules.room.action_request_hash import build_action_request_hash
from app.modules.room.game_completion_planner import GameCompletionPlanner
from app.modules.room.game_presentation_service import GamePresentationService
from app.modules.room.game_session_validator import GameSessionValidator
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.repository import RoomRepository
from app.modules.room.room_action_command import RoomActionCommand
from app.modules.room.room_game_commit_repository import (
    ACTION_REQUEST_TTL_SECONDS,
    RoomGameCommitRepository,
    room_game_commit_repository,
)
from app.modules.room.room_game_commit_schemas import ActionRequestRecord
from app.modules.room.room_game_commit_service import (
    RoomGameCommitService,
    room_game_commit_service,
)
from app.modules.room.room_platform_support import acquire_user_room_lock
from app.modules.room.schemas import RoomActionRequest
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.gateway import ActionInteractionGateway
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService
from app.modules.strategy_turn.schemas import (
    ActionSubmission,
    ApplyActionCommand,
    GameView,
)
from app.modules.strategy_turn.view_service import GameViewService


logger = logging.getLogger(__name__)


class RoomGameActionCommandService(object):
    """房间对局动作提交核心链路。"""

    def __init__(
        self,
        repository: RoomRepository,
        runtime_service: StrategyTurnRuntimeService,
        interaction_gateway: ActionInteractionGateway,
        game_view_service: GameViewService,
        session_validator: GameSessionValidator,
        state_reader: GameStateReader,
        presentation_service: GamePresentationService,
        lock_service: RedisDistributedLock,
        completion_planner: Optional[GameCompletionPlanner] = None,
        commit_repository: Optional[RoomGameCommitRepository] = None,
        commit_service: Optional[RoomGameCommitService] = None,
    ) -> None:
        """
        初始化房间动作命令服务。

        :param repository: 房间 Redis 仓库。
        :param runtime_service: 策略回合运行时服务。
        :param interaction_gateway: 动作交互网关。
        :param game_view_service: GameView 构建服务。
        :param session_validator: 对局会话校验器。
        :param state_reader: 运行时读取端口。
        :param presentation_service: 对局展示与推送端口。
        :param lock_service: 分布式锁服务。
        :param completion_planner: 终局纯规划器。
        :param commit_repository: 原子提交仓库。
        :param commit_service: 原子提交编排服务。
        """
        self._repository = repository
        self._lock_service = lock_service
        self._runtime_service = runtime_service
        self._interaction_gateway = interaction_gateway
        self._game_view_service = game_view_service
        self._session_validator = session_validator
        self._state_reader = state_reader
        self._presentation_service = presentation_service
        self._completion_planner = completion_planner or GameCompletionPlanner()
        self._commit_repository = commit_repository or room_game_commit_repository
        self._commit_service = commit_service or room_game_commit_service

    async def apply_room_action(
        self,
        room_id: str,
        player_id: str,
        request: RoomActionRequest,
    ) -> GameView:
        """
        提交玩家操作并保存更新后的运行时快照。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request: 操作请求。
        :return: 当前玩家的对局视图。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        async with await acquire_user_room_lock(
            self._lock_service,
            normalized_room_id,
            normalized_player_id,
        ):
            meta = await self._session_validator.require_meta(normalized_room_id)
            self._session_validator.require_playing_room(meta)
            members = await self._session_validator.list_members(normalized_room_id)
            self._session_validator.require_active_human_member(members, normalized_player_id)
            return await self.submit_action_locked(
                room_id=normalized_room_id,
                player_id=normalized_player_id,
                command=RoomActionCommand(
                    requestId=str(request.requestId or "").strip(),
                    baseVersion=int(request.baseVersion),
                    submission=request.submission,
                ),
            )

    async def submit_action_locked(
        self,
        room_id: str,
        player_id: str,
        command: RoomActionCommand,
    ) -> GameView:
        """
        提交动作核心链路（调用方必须已持有房间动作锁）。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param command: 房间动作命令。
        :return: 提交者视角 GameView。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        normalized_submission = self._normalize_submission(command.submission)
        request_id = str(command.requestId or "").strip()
        if not request_id:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="requestId 不能为空")
        request_hash = build_action_request_hash(
            normalized_room_id,
            normalized_player_id,
            int(command.baseVersion),
            normalized_submission,
        )
        replay_view = await self._try_build_replay_view(
            normalized_room_id,
            normalized_player_id,
            request_id,
            request_hash,
        )
        if replay_view is not None:
            return replay_view

        meta = await self._session_validator.require_meta(normalized_room_id)
        self._session_validator.require_playing_room(meta)
        members = await self._session_validator.list_members(normalized_room_id)
        self._session_validator.require_member(members, normalized_player_id)

        consistent_state = await self._state_reader.load_consistent(normalized_room_id)
        snapshot = consistent_state.snapshot
        current_version = int(consistent_state.gameVersion)
        if int(current_version) != int(command.baseVersion):
            raise BizException(ErrorCode.GAME_VIEW_VERSION_CONFLICT)

        context = ActionInteractionContext(
            gameCode=snapshot.gameCode,
            roomId=normalized_room_id,
            runtimeRule=snapshot.runtimeRule,
            state=snapshot.state,
            playerId=normalized_player_id,
            version=int(current_version),
            currentTimeMs=now_ms(),
        )
        action = self._interaction_gateway.resolve_submission(context, normalized_submission)
        apply_result = self._runtime_service.apply_resolved_action(
            snapshot,
            ApplyActionCommand(action=action),
        )
        frame_events = self._presentation_service.filter_game_view_events(apply_result.newEvents)
        final_snapshot = apply_result.snapshot
        committed_at = now_ms()
        outbox_records = None
        next_room_meta = dict(meta)
        next_room_meta["status"] = "playing"
        next_room_meta["updatedAt"] = committed_at
        terminal_snapshot = final_snapshot

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

        request_record = self._build_request_record(
            normalized_room_id,
            normalized_player_id,
            request_id,
            request_hash,
            normalized_submission,
            action.actionId,
            int(current_version) + 1,
            committed_at,
        )
        outbox_reason = None if bool(final_snapshot.isGameOver) else "afterAction"
        commit_result = await self._commit_service.commit_state_change(
            room_id=normalized_room_id,
            expected_version=int(current_version),
            next_snapshot=terminal_snapshot,
            next_room_meta=next_room_meta,
            delete_runtime=False,
            request_record=request_record,
            outbox_reason=outbox_reason,
            outbox_records=outbox_records,
            committed_at=committed_at,
        )
        if commit_result.status == "REPLAY":
            return await self._build_current_game_view(normalized_room_id, normalized_player_id)

        next_version = int(commit_result.committedVersion or (int(current_version) + 1))
        stamped_snapshot = terminal_snapshot.model_copy(update={"commitVersion": next_version})
        room_version = await self._repository.get_room_version(normalized_room_id)
        if room_version is None:
            room_version = 0
        pushed = await self._push_presentation_after_commit(
            normalized_room_id,
            normalized_player_id,
            request_id,
            next_version,
            next_room_meta,
            members,
            stamped_snapshot,
            frame_events,
            bool(final_snapshot.isGameOver),
            int(room_version),
        )
        if not pushed:
            self._schedule_presentation_retry(
                normalized_room_id,
                normalized_player_id,
                request_id,
                next_version,
                next_room_meta,
                members,
                stamped_snapshot,
                frame_events,
                bool(final_snapshot.isGameOver),
                int(room_version),
            )
        return self._presentation_service.enrich_game_view(
            stamped_snapshot,
            normalized_player_id,
            next_version,
            frame_events,
        )

    async def _push_presentation_after_commit(
        self,
        room_id: str,
        player_id: str,
        request_id: str,
        game_version: int,
        room_meta: dict,
        members: list,
        snapshot,
        frame_events: list,
        is_game_over: bool,
        room_version: int,
    ) -> bool:
        """
        提交成功后刷新 TTL 并推送展示更新。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request_id: 请求 ID。
        :param game_version: 提交后对局版本号。
        :param room_meta: 房间元信息。
        :param members: 房间成员列表。
        :param snapshot: 已提交运行时快照。
        :param frame_events: 帧事件列表。
        :param is_game_over: 是否终局。
        :param room_version: 房间元数据版本号。
        :return: 推送是否成功。
        """
        try:
            await self._repository.refresh_room_ttl(room_id)
            await self._presentation_service.push_room_and_game_view(
                room_id,
                room_meta,
                members,
                snapshot,
                game_version,
                frame_events,
                is_game_over,
                room_version,
            )
            return True
        except Exception:
            logger.exception(
                "post-commit presentation failed, roomId=%s playerId=%s requestId=%s gameVersion=%s",
                room_id,
                player_id,
                request_id,
                game_version,
            )
            return False

    def _schedule_presentation_retry(
        self,
        room_id: str,
        player_id: str,
        request_id: str,
        game_version: int,
        room_meta: dict,
        members: list,
        snapshot,
        frame_events: list,
        is_game_over: bool,
        room_version: int,
    ) -> None:
        """
        异步重试一次展示推送，不进入 Lifecycle 且不改变 gameVersion。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request_id: 请求 ID。
        :param game_version: 对局版本号。
        :param room_meta: 房间元信息。
        :param members: 房间成员列表。
        :param snapshot: 运行时快照。
        :param frame_events: 帧事件列表。
        :param is_game_over: 是否终局。
        :param room_version: 房间元数据版本号。
        :return: 无。
        """
        async def _retry_once() -> None:
            pushed = await self._push_presentation_after_commit(
                room_id,
                player_id,
                request_id,
                game_version,
                room_meta,
                members,
                snapshot,
                frame_events,
                is_game_over,
                room_version,
            )
            if not pushed:
                logger.warning(
                    "post-commit presentation retry exhausted, roomId=%s playerId=%s requestId=%s gameVersion=%s",
                    room_id,
                    player_id,
                    request_id,
                    game_version,
                )

        try:
            asyncio.get_running_loop().create_task(_retry_once())
        except RuntimeError:
            logger.warning(
                "post-commit presentation retry skipped without event loop, roomId=%s requestId=%s",
                room_id,
                request_id,
            )

    async def _try_build_replay_view(
        self,
        room_id: str,
        player_id: str,
        request_id: str,
        request_hash: str,
    ) -> Optional[GameView]:
        """
        若请求已提交且摘要一致，则返回重放视图。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request_id: 请求 ID。
        :param request_hash: 请求摘要。
        :return: 重放 GameView；不可重放时返回 ``None``。
        """
        existing = await self._commit_repository.load_request_record(
            room_id,
            player_id,
            request_id,
        )
        if existing is None:
            return None
        if str(existing.requestHash or "").strip() != str(request_hash or "").strip():
            raise BizException(ErrorCode.REQUEST_ID_CONFLICT)
        return await self._build_current_game_view(room_id, player_id)

    async def _build_current_game_view(self, room_id: str, player_id: str) -> GameView:
        """
        构建当前权威 GameView。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 当前 GameView。
        """
        consistent_state = await self._state_reader.load_consistent(room_id)
        return self._presentation_service.enrich_game_view(
            consistent_state.snapshot,
            player_id,
            int(consistent_state.gameVersion),
            [],
        )

    def _normalize_submission(self, submission: ActionSubmission) -> ActionSubmission:
        """
        将提交对象规范化为 ``ActionSubmission``。

        :param submission: 外部提交对象。
        :return: 规范化后的提交对象。
        """
        if isinstance(submission, ActionSubmission):
            return submission
        return ActionSubmission.model_validate(submission)

    def _build_request_record(
        self,
        room_id: str,
        player_id: str,
        request_id: str,
        request_hash: str,
        submission: ActionSubmission,
        resolved_action_id: str,
        committed_version: int,
        committed_at: int,
    ) -> ActionRequestRecord:
        """
        构造动作请求幂等记录。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request_id: 请求 ID。
        :param request_hash: 请求摘要。
        :param submission: 动作提交。
        :param resolved_action_id: 解析后的动作 ID。
        :param committed_version: 提交后的对局版本号。
        :param committed_at: 提交时间戳。
        :return: 请求记录。
        """
        return ActionRequestRecord(
            roomId=room_id,
            playerId=player_id,
            requestId=str(request_id or "").strip(),
            requestHash=str(request_hash),
            actionType=str(submission.actionType or "").strip(),
            committedGameVersion=int(committed_version),
            resolvedActionId=str(resolved_action_id or "").strip(),
            createdAt=int(committed_at),
            expiresAt=int(committed_at) + ACTION_REQUEST_TTL_SECONDS * 1000,
        )
