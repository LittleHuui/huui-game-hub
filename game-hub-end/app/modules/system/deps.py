"""系统模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.system.entity_service import (
    LoginLogEntityService,
    RequestLogEntityService,
    SystemConfigEntityService,
)
from app.modules.system.module_service import SystemModuleService
from app.modules.system.repository import (
    LoginLogRepository,
    RequestLogRepository,
    SystemConfigRepository,
)


def get_system_module_service(db: Session = Depends(get_db)) -> SystemModuleService:
    """
    组装系统模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``SystemModuleService`` 实例。
    """
    return SystemModuleService(
        SystemConfigEntityService(SystemConfigRepository(db)),
        RequestLogEntityService(RequestLogRepository(db)),
        LoginLogEntityService(LoginLogRepository(db)),
    )
