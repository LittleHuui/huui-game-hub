"""背包域 HTTP 接口。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from app.common.page_response import PageResponse
from app.common.response import ApiResponse, success
from app.modules.boot.schemas import PropUsageRecordResponse, UserPropBagResponse
from app.modules.inventory.deps import get_inventory_module_service
from app.modules.inventory.module_service import InventoryModuleService

inventory_router = APIRouter(prefix="/users", tags=["inventory"])


@inventory_router.get(
    "/{userId}/inventory",
    response_model=ApiResponse[List[UserPropBagResponse]],
    summary="查询用户背包",
)
def list_user_inventory(
    userId: str,
    game_code: Optional[str] = Query(default=None, alias="gameCode", description="按游戏过滤"),
    service: InventoryModuleService = Depends(get_inventory_module_service),
):
    """
    查询用户道具背包快照。

    :param userId: 用户主键。
    :param game_code: 游戏编码，可选。
    :param service: 背包模块服务。
    :return: 背包列表。
    """
    items = service.list_user_inventory(userId, game_code=game_code)
    return success(items)


@inventory_router.get(
    "/{userId}/inventory/usage-records",
    response_model=ApiResponse[PageResponse[PropUsageRecordResponse]],
    summary="查询道具使用记录",
)
def list_prop_usage_records(
    userId: str,
    game_code: Optional[str] = Query(default=None, alias="gameCode", description="按游戏过滤"),
    prop_code: Optional[str] = Query(default=None, alias="propCode", description="按道具过滤"),
    page_num: int = Query(default=1, ge=1, alias="pageNum", description="页码，从 1 开始"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页条数，最大 100"),
    service: InventoryModuleService = Depends(get_inventory_module_service),
):
    """
    分页查询用户道具使用记录。

    :param userId: 用户主键。
    :param game_code: 游戏编码，可选。
    :param prop_code: 道具编码，可选。
    :param page_num: 页码。
    :param page_size: 每页条数。
    :param service: 背包模块服务。
    :return: 分页使用记录。
    """
    page = service.list_usage_records_page(
        userId,
        game_code=game_code,
        prop_code=prop_code,
        page_num=page_num,
        page_size=page_size,
    )
    return success(page)
