"""用户模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.user.entity_service import (
    UserAccountEntityService,
    UserDeviceEntityService,
    UserGameSettingEntityService,
    UserSystemSettingEntityService,
)
from app.modules.user.module_service import UserModuleService
from app.modules.user.repository import (
    UserAccountRepository,
    UserDeviceRepository,
    UserGameSettingRepository,
    UserSystemSettingRepository,
)


def get_user_module_service(db: Session = Depends(get_db)) -> UserModuleService:
    """
    组装用户模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``UserModuleService`` 实例。
    """
    account_repo = UserAccountRepository(db)
    device_repo = UserDeviceRepository(db)
    game_repo = UserGameSettingRepository(db)
    system_repo = UserSystemSettingRepository(db)
    return UserModuleService(
        UserAccountEntityService(account_repo),
        UserDeviceEntityService(device_repo),
        UserGameSettingEntityService(game_repo),
        UserSystemSettingEntityService(system_repo),
    )
