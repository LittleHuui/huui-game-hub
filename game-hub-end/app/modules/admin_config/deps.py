"""管理配置导入模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin_config.entity_service import (
    GameClientConfigImportEntityService,
    GameDefinitionImportEntityService,
    GameDifficultyImportEntityService,
    GamePropRuleImportEntityService,
    PropDefinitionImportEntityService,
)
from app.modules.admin_config.module_service import AdminConfigModuleService
from app.modules.game.repository import (
    GameClientConfigRepository,
    GameDefinitionRepository,
    GameDifficultyRepository,
)
from app.modules.prop.entity_service import PropDefinitionEntityService
from app.modules.prop.repository import GamePropRuleRepository, PropDefinitionRepository


def get_admin_config_module_service(db: Session = Depends(get_db)) -> AdminConfigModuleService:
    """
    组装管理配置导入模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``AdminConfigModuleService`` 实例。
    """
    prop_repo = PropDefinitionRepository(db)
    return AdminConfigModuleService(
        PropDefinitionImportEntityService(prop_repo),
        GameDefinitionImportEntityService(GameDefinitionRepository(db)),
        GameDifficultyImportEntityService(GameDifficultyRepository(db)),
        GameClientConfigImportEntityService(GameClientConfigRepository(db)),
        GamePropRuleImportEntityService(GamePropRuleRepository(db)),
        PropDefinitionEntityService(prop_repo),
    )
