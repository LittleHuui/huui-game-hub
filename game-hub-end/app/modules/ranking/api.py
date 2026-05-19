"""排行榜域 HTTP 接口。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.common.response import ApiResponse, success
from app.modules.ranking.deps import get_ranking_module_service
from app.modules.ranking.module_service import RankingModuleService
from app.modules.ranking.schemas import LeaderboardResponse

router = APIRouter(prefix="/rankings", tags=["ranking"])


@router.get(
    "",
    response_model=ApiResponse[LeaderboardResponse],
    summary="查询排行榜",
)
def get_rankings(
    game_code: str = Query(..., alias="gameCode", min_length=1),
    mode: str = Query(..., min_length=1),
    difficulty_code: Optional[str] = Query(default=None, alias="difficultyCode"),
    limit: int = Query(default=10, ge=1, le=100),
    service: RankingModuleService = Depends(get_ranking_module_service),
):
    """
    根据 ``score_record`` 实时计算排行榜。

    :param game_code: 游戏编码（查询参数 ``gameCode``）。
    :param mode: 玩法模式。
    :param difficulty_code: 难度编码（查询参数 ``difficultyCode``），可选。
    :param limit: 返回条数上限，最大 100。
    :param service: 排行榜模块服务。
    :return: 统一成功响应，``data`` 为排行榜结构。
    """
    data = service.get_leaderboard(game_code, mode, difficulty_code, limit)
    return success(data)
