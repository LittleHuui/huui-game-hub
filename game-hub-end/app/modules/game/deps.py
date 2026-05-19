"""游戏模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.game.entity_service import (
    GameClientConfigEntityService,
    GameDefinitionEntityService,
    GameDifficultyEntityService,
)
from app.modules.game.module_service import GameModuleService
from app.modules.game.repository import (
    GameClientConfigRepository,
    GameDefinitionRepository,
    GameDifficultyRepository,
)
from app.modules.prop.entity_service import GamePropRuleEntityService
from app.modules.prop.repository import GamePropRuleRepository


def get_game_module_service(db: Session = Depends(get_db)) -> GameModuleService:
    """
    组装游戏模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``GameModuleService`` 实例。
    """
    return GameModuleService(
        GameDefinitionEntityService(GameDefinitionRepository(db)),
        GameDifficultyEntityService(GameDifficultyRepository(db)),
        GameClientConfigEntityService(GameClientConfigRepository(db)),
        GamePropRuleEntityService(GamePropRuleRepository(db)),
    )
