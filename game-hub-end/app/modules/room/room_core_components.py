"""房间模块长期组件组合根。"""

from dataclasses import dataclass
from typing import Optional

from app.core.clock import Clock, CancellableSleeper, system_clock
from app.core.lock.distributed_lock import RedisDistributedLock, distributed_lock
from app.game_runtime import GameRuntime, get_game_runtime
from app.modules.game_config.module_service import GameModuleService
from app.modules.room.auto_advance_task_service import (
    AutoAdvanceTaskService,
    room_auto_advance_task_service,
)
from app.modules.room.game_action_command_service import RoomGameActionCommandService
from app.modules.room.game_action_query_service import RoomGameActionQueryService
from app.modules.room.game_completion_planner import GameCompletionPlanner
from app.modules.room.game_presentation_service import GamePresentationService
from app.modules.room.game_session_validator import GameSessionValidator
from app.modules.room.game_settlement_service import GameSettlementService
from app.modules.room.game_settlement_transaction import GameSettlementTransaction
from app.modules.room.game_settlement_commit_service import GameSettlementCommitService
from app.core.database import session_scope
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.game_terminal_finalize_service import GameTerminalFinalizeService
from app.modules.room.managed_action_executor import RoomManagedActionExecutor
from app.modules.room.managed_task_service import ManagedTurnTaskService, managed_turn_task_service
from app.modules.room.post_turn_outbox_dispatcher import PostTurnOutboxDispatcher
from app.modules.room.post_turn_outbox_repository import PostTurnOutboxRepository
from app.modules.room.presence_service import RoomPresenceService
from app.modules.room.repository import RoomRepository
from app.core.redis.redis_client import redis_client
from app.modules.room.room_auto_advance_execution_service import RoomAutoAdvanceExecutionService
from app.modules.room.room_game_commit_service import RoomGameCommitService
from app.modules.room.room_game_view_push import RoomGameViewPushPort
from app.modules.room.room_lifecycle_service import RoomLifecycleService
from app.modules.room.room_member_control_service import RoomMemberControlService
from app.modules.room.room_membership_service import RoomMembershipService
from app.modules.room.room_mutation_commit_service import RoomMutationCommitService
from app.modules.room.room_task_scheduling_service import RoomTaskSchedulingService
from app.modules.room.turn_timeout_service import TurnTimeoutService
from app.modules.user.entity_service import UserAccountEntityService


_core_components_instance = None  # type: Optional[RoomCoreComponents]


@dataclass
class RoomCoreComponents(object):
    """不依赖请求级 SQLAlchemy Session 的房间长期组件。"""

    repository: RoomRepository
    lock_service: RedisDistributedLock
    game_runtime: GameRuntime
    state_reader: GameStateReader
    presentation_service: GamePresentationService
    session_validator: GameSessionValidator
    completion_planner: GameCompletionPlanner
    commit_service: RoomGameCommitService
    game_action_command_service: RoomGameActionCommandService
    game_action_query_service: RoomGameActionQueryService
    task_scheduling_service: RoomTaskSchedulingService
    auto_advance_execution_service: RoomAutoAdvanceExecutionService
    post_turn_outbox_repository: PostTurnOutboxRepository
    post_turn_outbox_dispatcher: PostTurnOutboxDispatcher
    settlement_service: GameSettlementService
    terminal_finalize_service: GameTerminalFinalizeService
    managed_task_service: ManagedTurnTaskService
    auto_advance_task_service: AutoAdvanceTaskService
    managed_action_executor: RoomManagedActionExecutor
    room_mutation_commit_service: RoomMutationCommitService
    game_view_push: RoomGameViewPushPort
    member_control_service: RoomMemberControlService
    clock: Clock
    presence_service: RoomPresenceService
    turn_timeout_service: TurnTimeoutService


@dataclass
class RoomApplicationServices(object):
    """请求级或后台组装的房间应用服务。"""

    lifecycle_service: RoomLifecycleService
    membership_service: RoomMembershipService
    member_control_service: RoomMemberControlService
    game_action_command_service: RoomGameActionCommandService
    game_action_query_service: RoomGameActionQueryService
    task_scheduling_service: RoomTaskSchedulingService
    auto_advance_execution_service: RoomAutoAdvanceExecutionService


def build_room_core_components(
    repository: Optional[RoomRepository] = None,
    lock_service: Optional[RedisDistributedLock] = None,
    game_runtime: Optional[GameRuntime] = None,
    state_reader: Optional[GameStateReader] = None,
    clock: Optional[Clock] = None,
    managed_task_service: Optional[ManagedTurnTaskService] = None,
    auto_advance_task_service: Optional[AutoAdvanceTaskService] = None,
    presentation_service: Optional[GamePresentationService] = None,
    session_validator: Optional[GameSessionValidator] = None,
    post_turn_outbox_repository: Optional[PostTurnOutboxRepository] = None,
    commit_service: Optional[RoomGameCommitService] = None,
) -> RoomCoreComponents:
    """
    组装房间长期组件依赖图。

    :param repository: 房间 Redis 仓库。
    :param lock_service: 分布式锁服务。
    :param game_runtime: 游戏运行时。
    :param clock: 可注入时钟。
    :param managed_task_service: 托管回合任务服务。
    :param auto_advance_task_service: 自动推进任务服务。
    :param presentation_service: 对局展示服务。
    :param post_turn_outbox_repository: Outbox 仓库。
    :param commit_service: 原子提交编排服务。
    :return: 房间核心组件容器。
    """
    resolved_repository = repository or RoomRepository()
    resolved_lock = lock_service or distributed_lock
    resolved_runtime = game_runtime or get_game_runtime()
    resolved_clock = clock or system_clock
    resolved_managed_task_service = managed_task_service or managed_turn_task_service
    resolved_auto_advance_task_service = (
        auto_advance_task_service or room_auto_advance_task_service
    )
    resolved_state_reader = state_reader or GameStateReader(resolved_repository)
    resolved_presentation = presentation_service or GamePresentationService(
        resolved_runtime.game_view_service,
    )
    resolved_session_validator = session_validator or GameSessionValidator(resolved_repository)
    resolved_completion_planner = GameCompletionPlanner()
    resolved_outbox_repository = post_turn_outbox_repository or PostTurnOutboxRepository()
    resolved_commit_service = commit_service or RoomGameCommitService()
    resolved_action_command = RoomGameActionCommandService(
        resolved_repository,
        resolved_runtime.runtime_service,
        resolved_runtime.interaction_gateway,
        resolved_runtime.game_view_service,
        resolved_session_validator,
        resolved_state_reader,
        resolved_presentation,
        resolved_lock,
        resolved_completion_planner,
        commit_service=resolved_commit_service,
    )
    resolved_action_query = RoomGameActionQueryService(
        resolved_state_reader,
        resolved_runtime.game_view_service,
        resolved_runtime.interaction_gateway,
        resolved_session_validator,
    )
    resolved_task_scheduling = RoomTaskSchedulingService(
        resolved_repository,
        resolved_state_reader,
        resolved_managed_task_service,
        resolved_auto_advance_task_service,
        resolved_clock,
    )
    resolved_room_mutation = RoomMutationCommitService()
    resolved_game_view_push = RoomGameViewPushPort(
        resolved_repository,
        resolved_state_reader,
        resolved_presentation,
    )
    resolved_member_control = RoomMemberControlService(
        resolved_repository,
        resolved_lock,
        None,
        resolved_room_mutation,
        resolved_task_scheduling,
        resolved_game_view_push,
    )
    resolved_auto_advance_execution = RoomAutoAdvanceExecutionService(
        resolved_repository,
        resolved_lock,
        resolved_runtime.runtime_service,
        resolved_state_reader,
        resolved_commit_service,
        resolved_completion_planner,
        resolved_presentation,
        resolved_clock,
    )
    resolved_terminal_finalize = GameTerminalFinalizeService(
        resolved_repository,
        resolved_state_reader,
        resolved_lock,
    )
    resolved_settlement_committer = GameSettlementCommitService(
        resolved_repository, resolved_state_reader, resolved_commit_service, resolved_clock,
    )
    resolved_settlement = GameSettlementService(
        resolved_repository,
        resolved_state_reader,
        GameSettlementTransaction(session_scope, resolved_clock),
        resolved_settlement_committer,
        resolved_presentation,
    )
    resolved_dispatcher = PostTurnOutboxDispatcher(
        resolved_outbox_repository,
        resolved_repository,
        resolved_state_reader,
        resolved_task_scheduling,
        resolved_terminal_finalize,
        resolved_settlement,
        resolved_settlement_committer,
    )
    resolved_managed_executor = RoomManagedActionExecutor(
        resolved_repository,
        resolved_lock,
        resolved_runtime.managed_decision_service,
        resolved_action_command,
        resolved_state_reader,
    )
    resolved_presence_service = RoomPresenceService(
        resolved_repository,
        resolved_member_control.mark_member_shell_managed,
        resolved_clock,
        CancellableSleeper(),
        redis_client,
    )
    resolved_turn_timeout_service = TurnTimeoutService(
        resolved_repository,
        resolved_state_reader,
        resolved_clock,
        CancellableSleeper(),
        resolved_member_control.mark_member_active_managed,
    )
    return RoomCoreComponents(
        repository=resolved_repository,
        lock_service=resolved_lock,
        game_runtime=resolved_runtime,
        state_reader=resolved_state_reader,
        presentation_service=resolved_presentation,
        session_validator=resolved_session_validator,
        completion_planner=resolved_completion_planner,
        commit_service=resolved_commit_service,
        game_action_command_service=resolved_action_command,
        game_action_query_service=resolved_action_query,
        task_scheduling_service=resolved_task_scheduling,
        auto_advance_execution_service=resolved_auto_advance_execution,
        post_turn_outbox_repository=resolved_outbox_repository,
        post_turn_outbox_dispatcher=resolved_dispatcher,
        settlement_service=resolved_settlement,
        terminal_finalize_service=resolved_terminal_finalize,
        managed_task_service=resolved_managed_task_service,
        auto_advance_task_service=resolved_auto_advance_task_service,
        managed_action_executor=resolved_managed_executor,
        room_mutation_commit_service=resolved_room_mutation,
        game_view_push=resolved_game_view_push,
        member_control_service=resolved_member_control,
        clock=resolved_clock,
        presence_service=resolved_presence_service,
        turn_timeout_service=resolved_turn_timeout_service,
    )


def get_room_core_components() -> RoomCoreComponents:
    """
    获取房间核心组件单例。

    :return: 房间核心组件容器。
    """
    global _core_components_instance
    if _core_components_instance is None:
        _core_components_instance = build_room_core_components()
    return _core_components_instance


def build_room_application_services(
    components: RoomCoreComponents,
    game_service: Optional[GameModuleService],
    account_service: Optional[UserAccountEntityService],
) -> RoomApplicationServices:
    """
    基于核心组件与请求级依赖组装房间应用服务。

    :param components: 房间核心组件。
    :param game_service: 游戏模块服务；后台可为 ``None``。
    :param account_service: 用户账号服务；后台可为 ``None``。
    :return: 房间应用服务容器。
    """
    runtime = components.game_runtime
    lifecycle_service = RoomLifecycleService(
        components.repository,
        components.lock_service,
        game_service,
        runtime.runtime_service,
        account_service,
        components.state_reader,
        components.commit_service,
        components.room_mutation_commit_service,
        components.presentation_service,
    )
    membership_service = RoomMembershipService(
        components.repository,
        components.lock_service,
        game_service,
        components.room_mutation_commit_service,
        components.state_reader,
        components.presentation_service,
        components.member_control_service,
        components.task_scheduling_service,
    )
    return RoomApplicationServices(
        lifecycle_service=lifecycle_service,
        membership_service=membership_service,
        member_control_service=components.member_control_service,
        game_action_command_service=components.game_action_command_service,
        game_action_query_service=components.game_action_query_service,
        task_scheduling_service=components.task_scheduling_service,
        auto_advance_execution_service=components.auto_advance_execution_service,
    )
