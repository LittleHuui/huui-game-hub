"""房间模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.lock.distributed_lock import RedisDistributedLock, distributed_lock
from app.modules.game_config.deps import get_game_module_service
from app.modules.game_config.module_service import GameModuleService
from app.modules.auth.deps import get_authenticated_account
from app.modules.room.game_action_command_service import RoomGameActionCommandService
from app.modules.room.game_action_query_service import RoomGameActionQueryService
from app.modules.room.repository import RoomRepository
from app.modules.room.room_core_components import (
    RoomApplicationServices,
    RoomCoreComponents,
    build_room_application_services,
    get_room_core_components,
)
from app.modules.room.room_lifecycle_service import RoomLifecycleService
from app.modules.room.room_member_control_service import RoomMemberControlService
from app.modules.room.room_membership_service import RoomMembershipService
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.models import UserAccount
from app.modules.user.repository import UserAccountRepository


def get_room_repository() -> RoomRepository:
    """
    组装房间 Redis 仓库依赖。

    :return: ``RoomRepository`` 实例。
    """
    return get_room_core_components().repository


def get_distributed_lock() -> RedisDistributedLock:
    """
    组装分布式锁依赖。

    :return: ``RedisDistributedLock`` 实例。
    """
    return distributed_lock


def get_room_core() -> RoomCoreComponents:
    """
    组装房间核心组件依赖。

    :return: ``RoomCoreComponents`` 实例。
    """
    return get_room_core_components()


def _get_room_application_services(
    core: RoomCoreComponents = Depends(get_room_core),
    game_service: GameModuleService = Depends(get_game_module_service),
    db: Session = Depends(get_db),
) -> RoomApplicationServices:
    """
    组装请求级房间应用服务。

    :param core: 房间核心组件。
    :param game_service: 游戏模块服务。
    :param db: 请求级数据库会话。
    :return: 房间应用服务容器。
    """
    account_service = UserAccountEntityService(UserAccountRepository(db))
    return build_room_application_services(core, game_service, account_service)


def get_room_lifecycle_service(
    services: RoomApplicationServices = Depends(_get_room_application_services),
) -> RoomLifecycleService:
    """
    组装房间生命周期服务依赖。

    :param services: 房间应用服务容器。
    :return: ``RoomLifecycleService`` 实例。
    """
    return services.lifecycle_service


def get_room_membership_service(
    services: RoomApplicationServices = Depends(_get_room_application_services),
) -> RoomMembershipService:
    """
    组装房间成员服务依赖。

    :param services: 房间应用服务容器。
    :return: ``RoomMembershipService`` 实例。
    """
    return services.membership_service


def get_room_member_control_service(
    services: RoomApplicationServices = Depends(_get_room_application_services),
) -> RoomMemberControlService:
    """
    组装房间成员控制服务依赖。

    :param services: 房间应用服务容器。
    :return: ``RoomMemberControlService`` 实例。
    """
    return services.member_control_service


def get_room_game_action_command_service(
    services: RoomApplicationServices = Depends(_get_room_application_services),
) -> RoomGameActionCommandService:
    """
    组装房间对局动作命令服务依赖。

    :param services: 房间应用服务容器。
    :return: ``RoomGameActionCommandService`` 实例。
    """
    return services.game_action_command_service


def get_room_game_action_query_service(
    services: RoomApplicationServices = Depends(_get_room_application_services),
) -> RoomGameActionQueryService:
    """
    组装房间对局动作查询服务依赖。

    :param services: 房间应用服务容器。
    :return: ``RoomGameActionQueryService`` 实例。
    """
    return services.game_action_query_service


def get_current_room_user(
    current_user: UserAccount = Depends(get_authenticated_account),
) -> UserAccount:
    """
    从访问令牌解析并校验当前房间操作用户。

    :param current_user: 已认证用户账号。
    :return: 当前用户账号。
    """
    return current_user
