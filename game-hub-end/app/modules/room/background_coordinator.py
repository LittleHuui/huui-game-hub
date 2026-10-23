"""房间后台组件启动协调。"""

import asyncio
import logging
from typing import Optional

from app.realtime.realtime_bootstrap import initialize_realtime_handlers
from app.modules.room.auto_advance_task_service import room_auto_advance_task_service
from app.modules.room.managed_task_service import managed_turn_task_service
from app.modules.room.post_commit_outbox_worker import PostCommitOutboxWorker
from app.modules.room.room_core_components import (
    RoomApplicationServices,
    RoomCoreComponents,
    build_room_application_services,
    get_room_core_components,
)

logger = logging.getLogger(__name__)
BACKGROUND_STOP_TIMEOUT_SECONDS = 5

_initialized = False
_background_services = None  # type: Optional[RoomApplicationServices]
_post_commit_outbox_worker = None  # type: Optional[PostCommitOutboxWorker]


def get_background_room_services() -> Optional[RoomApplicationServices]:
    """
    获取后台房间应用服务实例。

    :return: 后台应用服务容器；未初始化时返回 ``None``。
    """
    return _background_services


def get_post_commit_outbox_worker() -> Optional[PostCommitOutboxWorker]:
    """
    获取后台 Outbox Worker 实例。

    :return: ``PostCommitOutboxWorker`` 实例；未初始化时返回 ``None``。
    """
    return _post_commit_outbox_worker


def is_room_background_ready() -> bool:
    """判断房间后台组件是否已经完成初始化。"""
    return bool(
        _initialized
        and _background_services is not None
        and _post_commit_outbox_worker is not None
    )


def _build_background_room_services(
    core: RoomCoreComponents,
) -> RoomApplicationServices:
    """
    基于统一核心组件构造后台房间应用服务。

    :param core: 房间核心组件。
    :return: 房间应用服务容器。
    """
    return build_room_application_services(core, None, None)


async def start_presence_worker() -> None:
    """
    启动 Presence 后台 Worker。

    :return: 无。
    """
    core = get_room_core_components()
    try:
        rebuilt = await core.repository.rebuild_member_derived_indexes()
        if rebuilt > 0:
            logger.info("presence worker startup rebuilt derived indexes, count=%s", rebuilt)
    except Exception:
        logger.exception("presence worker startup derived index rebuild failed")
    await core.presence_service.start()


async def stop_presence_worker() -> None:
    """
    停止 Presence 后台 Worker。

    :return: 无。
    """
    core = get_room_core_components()
    await core.presence_service.stop()


async def initialize_room_background() -> None:
    """
    初始化房间后台组件：绑定 handler 并启动后台循环。

    :return: 无。
    """
    global _initialized, _background_services, _post_commit_outbox_worker
    if _initialized:
        return
    core = get_room_core_components()
    services = _build_background_room_services(core)
    _background_services = services
    managed_turn_task_service.bind_submit_handler(
        core.managed_action_executor.execute,
    )
    managed_turn_task_service.bind_recovery_validator(
        core.task_scheduling_service.validate_managed_turn_task_for_recovery,
    )
    _post_commit_outbox_worker = PostCommitOutboxWorker(
        core.post_turn_outbox_repository,
        core.post_turn_outbox_dispatcher,
        core.repository,
    )
    room_auto_advance_task_service.bind_submit_handler(
        core.auto_advance_execution_service.submit_auto_advance_task,
    )
    room_auto_advance_task_service.bind_recovery_validator(
        core.task_scheduling_service.validate_auto_advance_task_for_recovery,
    )
    initialize_realtime_handlers(core.repository, core.presence_service)
    await _post_commit_outbox_worker.start()
    await managed_turn_task_service.start()
    await room_auto_advance_task_service.start()
    await start_presence_worker()
    await core.turn_timeout_service.start()
    _initialized = True
    logger.info("room background components initialized")


async def shutdown_room_background() -> None:
    """
    停止房间后台组件。

    :return: 无。
    """
    global _initialized, _background_services, _post_commit_outbox_worker
    if not _initialized and _background_services is None and _post_commit_outbox_worker is None:
        return
    _initialized = False
    core = get_room_core_components()
    stops = [core.turn_timeout_service.stop, stop_presence_worker,
             room_auto_advance_task_service.stop, managed_turn_task_service.stop]
    if _post_commit_outbox_worker is not None:
        stops.append(_post_commit_outbox_worker.stop)
    for stop in stops:
        try:
            await asyncio.wait_for(stop(), BACKGROUND_STOP_TIMEOUT_SECONDS)
        except Exception:
            logger.exception("room background component shutdown failed: %s", stop.__name__)
    _background_services = None
    _post_commit_outbox_worker = None
    logger.info("room background components shutdown")
