"""成绩模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.score.entity_service import ScoreRecordEntityService
from app.modules.score.module_service import ScoreModuleService
from app.modules.score.repository import ScoreRecordRepository


def get_score_record_entity_service(db: Session = Depends(get_db)) -> ScoreRecordEntityService:
    """
    组装成绩实体服务依赖。

    :param db: 请求级数据库会话。
    :return: ``ScoreRecordEntityService`` 实例。
    """
    return ScoreRecordEntityService(ScoreRecordRepository(db))


def get_score_module_service(
    score_entity: ScoreRecordEntityService = Depends(get_score_record_entity_service),
) -> ScoreModuleService:
    """
    组装成绩模块服务依赖。

    :param score_entity: 成绩实体服务。
    :return: ``ScoreModuleService`` 实例。
    """
    return ScoreModuleService(score_entity)
