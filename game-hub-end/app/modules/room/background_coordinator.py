"""房间后台组件启动协调。"""

import logging

from app.core.lock.distributed_lock import distributed_lock
from app.modules.room.managed_action_selector import ManagedActionSelector
from app.modules.room.managed_task_service import managed_turn_task_service
from app.modules.room.module_service import RoomModuleService
from app.modules.room.presence_service import room_presence_service
from app.modules.room.repository import RoomRepository
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService

logger = logging.getLogger(__name__)

_initialized = False
_background_module_service = None  # type: RoomModuleService


def get_background_room_module_service():
    """
    获取后台房间模块服务实例。

    :return: 后台 ``RoomModuleService`` 实例；未初始化时返回 ``None``。
    """
    return _background_module_service


def _build_room_module_service() -> RoomModuleService:
    """
    构造后台房间模块服务。

    :return: ``RoomModuleService`` 实例。
    """
    return RoomModuleService(
        RoomRepository(),
        distributed_lock,
        None,
        StrategyTurnRuntimeService(),
        None,
        managed_turn_task_service,
        ManagedActionSelector(),
    )


async def initialize_room_background() -> None:
    """
    初始化房间后台组件：绑定 handler 并启动后台循环。

    :return: 无。
    """
    global _initialized, _background_module_service
    if _initialized:
        return
    module_service = _build_room_module_service()
    _background_module_service = module_service
    managed_turn_task_service.bind_submit_handler(module_service.submit_managed_action)
    room_presence_service.bind_mark_member_shell_managed_handler(
        module_service.mark_member_shell_managed,
    )
    await managed_turn_task_service.start()
    await room_presence_service.start()
    _initialized = True
    logger.info("room background components initialized")


async def shutdown_room_background() -> None:
    """
    停止房间后台组件。

    :return: 无。
    """
    global _initialized, _background_module_service
    await managed_turn_task_service.stop()
    await room_presence_service.stop()
    _initialized = False
    _background_module_service = None
