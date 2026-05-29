"""房间模块 FastAPI 依赖注入。"""

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.database import get_db
from app.core.lock.distributed_lock import RedisDistributedLock, distributed_lock
from app.modules.game.deps import get_game_module_service
from app.modules.game.module_service import GameModuleService
from app.modules.room.managed_action_selector import ManagedActionSelector
from app.modules.room.managed_task_service import managed_turn_task_service
from app.modules.room.module_service import RoomModuleService
from app.modules.room.repository import RoomRepository
from app.modules.strategy_turn.runtime_service import StrategyTurnRuntimeService
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.models import UserAccount
from app.modules.user.repository import UserAccountRepository


def get_room_repository() -> RoomRepository:
    """
    组装房间 Redis 仓库依赖。

    :return: ``RoomRepository`` 实例。
    """
    return RoomRepository()


def get_distributed_lock() -> RedisDistributedLock:
    """
    组装分布式锁依赖。

    :return: ``RedisDistributedLock`` 实例。
    """
    return distributed_lock


def get_strategy_turn_runtime_service() -> StrategyTurnRuntimeService:
    """
    组装策略回合制运行时服务依赖。

    :return: ``StrategyTurnRuntimeService`` 实例。
    """
    return StrategyTurnRuntimeService()


def get_managed_action_selector() -> ManagedActionSelector:
    """
    组装托管动作选择器依赖。

    :return: ``ManagedActionSelector`` 实例。
    """
    return ManagedActionSelector()


def get_room_module_service(
    repository: RoomRepository = Depends(get_room_repository),
    lock_service: RedisDistributedLock = Depends(get_distributed_lock),
    game_service: GameModuleService = Depends(get_game_module_service),
    runtime_service: StrategyTurnRuntimeService = Depends(get_strategy_turn_runtime_service),
    managed_action_selector: ManagedActionSelector = Depends(get_managed_action_selector),
    db: Session = Depends(get_db),
) -> RoomModuleService:
    """
    组装房间模块服务依赖。

    :param repository: 房间 Redis 仓库。
    :param lock_service: 分布式锁工具。
    :param game_service: 游戏模块服务。
    :param runtime_service: 策略回合制运行时服务。
    :param db: 请求级数据库会话。
    :return: ``RoomModuleService`` 实例。
    """
    account_service = UserAccountEntityService(UserAccountRepository(db))
    return RoomModuleService(
        repository,
        lock_service,
        game_service,
        runtime_service,
        account_service,
        managed_turn_task_service,
        managed_action_selector,
    )


def get_current_room_user(
    service_id: str = Header(..., alias="X-Game-Hub-User-Id"),
    db: Session = Depends(get_db),
) -> UserAccount:
    """
    从请求上下文解析并校验当前用户。

    :param service_id: 当前用户服务端 ID。
    :param db: 请求级数据库会话。
    :return: 当前用户账号。
    :raises BizException: 用户不存在或禁用。
    """
    account_service = UserAccountEntityService(UserAccountRepository(db))
    account = account_service.get_by_server_id(service_id, active_only=True)
    if account is None:
        raise BizException(ErrorCode.USER_NOT_FOUND)
    if account.status != "normal":
        raise BizException(ErrorCode.USER_DISABLED)
    return account
