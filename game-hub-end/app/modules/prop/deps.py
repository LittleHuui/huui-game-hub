"""道具模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.prop.entity_service import GamePropRuleEntityService, PropDefinitionEntityService
from app.modules.prop.module_service import PropModuleService
from app.modules.prop.repository import GamePropRuleRepository, PropDefinitionRepository


def get_prop_module_service(db: Session = Depends(get_db)) -> PropModuleService:
    """
    组装道具模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``PropModuleService`` 实例。
    """
    return PropModuleService(
        PropDefinitionEntityService(PropDefinitionRepository(db)),
        GamePropRuleEntityService(GamePropRuleRepository(db)),
    )
