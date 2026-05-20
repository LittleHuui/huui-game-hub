"""排行榜模块 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.game.repository import GameDefinitionRepository
from app.modules.ranking.entity_service import RankingEntityService
from app.modules.ranking.module_service import RankingModuleService
from app.modules.score.repository import ScoreRecordRepository


def get_score_record_repository(db: Session = Depends(get_db)) -> ScoreRecordRepository:
    """
    组装成绩仓储依赖（排行榜查询只读）。

    :param db: 请求级数据库会话。
    :return: ``ScoreRecordRepository`` 实例。
    """
    return ScoreRecordRepository(db, GameDefinitionRepository(db))


def get_ranking_module_service(
    score_repository: ScoreRecordRepository = Depends(get_score_record_repository),
) -> RankingModuleService:
    """
    组装排行榜模块服务依赖。

    :param score_repository: 成绩仓储（排行榜派生查询）。
    :return: ``RankingModuleService`` 实例。
    """
    return RankingModuleService(RankingEntityService(score_repository))
