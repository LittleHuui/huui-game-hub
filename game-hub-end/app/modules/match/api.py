"""对局域 HTTP 接口。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.common.page_response import PageResponse
from app.common.response import ApiResponse, success
from app.modules.boot.schemas import MatchRecordResponse
from app.modules.match.deps import get_match_module_service
from app.modules.match.module_service import MatchModuleService

router = APIRouter(tags=["match"])


@router.get(
    "/users/{userId}/matches",
    response_model=ApiResponse[PageResponse[MatchRecordResponse]],
    summary="查询用户历史对局",
)
def list_user_matches(
    userId: str,
    game_code: Optional[str] = Query(default=None, alias="gameCode"),
    mode: Optional[str] = Query(default=None),
    result: Optional[str] = Query(default=None),
    difficulty_code: Optional[str] = Query(default=None, alias="difficultyCode"),
    page_num: int = Query(default=1, alias="pageNum", ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    service: MatchModuleService = Depends(get_match_module_service),
):
    """
    分页查询用户历史对局，支持按游戏、模式、结果、难度筛选。

    :param userId: 用户主键。
    :param game_code: 游戏编码（查询参数 ``gameCode``），可选。
    :param mode: 玩法模式，可选。
    :param result: 对局结果，可选。
    :param difficulty_code: 难度编码（查询参数 ``difficultyCode``），可选。
    :param page_num: 页码，从 1 开始（查询参数 ``pageNum``）。
    :param page_size: 每页条数，最大 100（查询参数 ``pageSize``）。
    :param service: 对局模块服务。
    :return: 统一成功响应，``data`` 为分页对局列表。
    """
    data = service.page_user_match_records(
        userId,
        game_code=game_code,
        mode=mode,
        result=result,
        difficulty_code=difficulty_code,
        page_num=page_num,
        page_size=page_size,
    )
    return success(data)


@router.get(
    "/matches/{matchId}",
    response_model=ApiResponse[MatchRecordResponse],
    summary="查询单局对局详情",
)
def get_match_detail(
    matchId: str,
    service: MatchModuleService = Depends(get_match_module_service),
):
    """
    根据对局主键查询单局详情。

    :param matchId: 对局主键（``match_record.server_id``）。
    :param service: 对局模块服务。
    :return: 统一成功响应，``data`` 为对局详情。
    """
    data = service.get_match_record_detail(matchId)
    return success(data)


# match_action 回放接口暂不开放，避免前端误接入；底层 model / repository / entity_service 保留。
