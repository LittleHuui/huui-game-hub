"""购买域 HTTP 接口。"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.common.page_response import PageResponse
from app.common.response import ApiResponse, success
from app.modules.boot.schemas import PropPurchaseRecordResponse
from app.modules.purchase.deps import get_purchase_module_service
from app.modules.purchase.module_service import PurchaseModuleService
from app.modules.purchase.schemas import CreatePropPurchaseRequest, PropPurchaseResultResponse

purchase_router = APIRouter(tags=["purchase"])


@purchase_router.post(
    "/purchases",
    response_model=ApiResponse[PropPurchaseResultResponse],
    summary="购买道具",
)
def create_prop_purchase(
    body: CreatePropPurchaseRequest,
    service: PurchaseModuleService = Depends(get_purchase_module_service),
):
    """
    购买道具：校验规则与余额、扣减积分、写入购买记录并重算背包（幂等）。

    :param body: 购买请求。
    :param service: 购买模块服务。
    :return: 购买记录、钱包快照与对应背包行。
    """
    data = service.purchase_prop_with_result(body)
    return success(data)


@purchase_router.get(
    "/users/{userId}/purchases",
    response_model=ApiResponse[PageResponse[PropPurchaseRecordResponse]],
    summary="查询用户购买记录",
)
def list_user_purchases(
    userId: str,
    game_code: Optional[str] = Query(default=None, alias="gameCode"),
    prop_code: Optional[str] = Query(default=None, alias="propCode"),
    page_num: int = Query(default=1, alias="pageNum", ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    service: PurchaseModuleService = Depends(get_purchase_module_service),
):
    """
    分页查询用户道具购买记录。

    :param userId: 用户主键。
    :param game_code: 可选游戏编码过滤。
    :param prop_code: 可选道具编码过滤。
    :param page_num: 页码，从 1 开始。
    :param page_size: 每页条数。
    :param service: 购买模块服务。
    :return: 分页购买记录列表。
    """
    data = service.list_purchase_records_page(
        userId,
        game_code=game_code,
        prop_code=prop_code,
        page_num=page_num,
        page_size=page_size,
    )
    return success(data)
