"""道具域 HTTP 接口。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Path, Query

from app.common.response import ApiResponse, success
from app.modules.game.schemas import GamePropRuleResponse
from app.modules.prop.deps import get_prop_module_service
from app.modules.prop.module_service import PropModuleService
from app.modules.prop.schemas import PropDefinitionResponse

router = APIRouter(tags=["prop"])


@router.get(
    "/props",
    response_model=ApiResponse[List[PropDefinitionResponse]],
    summary="查询道具定义列表",
)
def list_prop_definitions(
    enabled: Optional[bool] = Query(default=None, description="按启用状态过滤"),
    service: PropModuleService = Depends(get_prop_module_service),
):
    """
    查询平台道具定义列表。

    :param enabled: 为 ``True``/``False`` 时按启用状态过滤，省略则不过滤。
    :param service: 道具模块服务。
    :return: 道具定义列表。
    """
    items = service.list_prop_definitions(enabled=enabled)
    return success(items)


@router.get(
    "/games/{gameCode}/props",
    response_model=ApiResponse[List[GamePropRuleResponse]],
    summary="查询游戏可用道具规则",
)
def list_game_prop_rules(
    gameCode: str = Path(..., min_length=1, description="游戏编码"),
    service: PropModuleService = Depends(get_prop_module_service),
):
    """
    查询某游戏下已启用的道具规则。

    :param gameCode: 游戏编码。
    :param service: 道具模块服务。
    :return: 游戏规则列表。
    """
    items = service.list_game_prop_rules(gameCode)
    return success(items)
