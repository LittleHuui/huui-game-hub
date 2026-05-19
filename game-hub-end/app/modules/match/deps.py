"""对局域 FastAPI 依赖注入。"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.match.entity_service import MatchActionRecordEntityService, MatchRecordEntityService
from app.modules.match.module_service import MatchModuleService
from app.modules.match.repository import MatchActionRecordRepository, MatchRecordRepository
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.repository import UserAccountRepository


def get_match_module_service(db: Session = Depends(get_db)) -> MatchModuleService:
    """
    组装对局模块服务依赖。

    :param db: 请求级数据库会话。
    :return: ``MatchModuleService`` 实例。
    """
    return MatchModuleService(
        MatchRecordEntityService(MatchRecordRepository(db)),
        MatchActionRecordEntityService(MatchActionRecordRepository(db)),
        UserAccountEntityService(UserAccountRepository(db)),
    )
