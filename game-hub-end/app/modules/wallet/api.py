"""钱包域 HTTP 接口。"""

from fastapi import APIRouter, Depends, Path, Query

from app.common.page_response import PageResponse
from app.common.response import ApiResponse, success
from app.modules.boot.schemas import UserWalletResponse, WalletLedgerResponse
from app.modules.wallet.deps import get_wallet_module_service
from app.modules.wallet.module_service import WalletModuleService

router = APIRouter(prefix="/users", tags=["wallet"])


@router.get(
    "/{userId}/wallet",
    response_model=ApiResponse[UserWalletResponse],
    summary="查询用户钱包",
)
def get_user_wallet(
    userId: str = Path(..., min_length=1),
    service: WalletModuleService = Depends(get_wallet_module_service),
):
    """
    查询用户钱包快照；若钱包不存在则创建默认空钱包。

    :param userId: 用户主键。
    :param service: 钱包模块服务。
    :return: 统一成功响应，``data`` 为钱包快照。
    """
    data = service.get_user_wallet(userId)
    return success(data)


@router.get(
    "/{userId}/wallet/ledgers",
    response_model=ApiResponse[PageResponse[WalletLedgerResponse]],
    summary="查询用户钱包流水",
)
def list_user_wallet_ledgers(
    userId: str = Path(..., min_length=1),
    page_num: int = Query(default=1, ge=1, alias="pageNum"),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    service: WalletModuleService = Depends(get_wallet_module_service),
):
    """
    分页查询用户钱包流水（``deleted_at`` 为空，按 ``created_at`` 降序）。

    :param userId: 用户主键。
    :param page_num: 页码，从 1 开始。
    :param page_size: 每页条数，最大 100。
    :param service: 钱包模块服务。
    :return: 统一成功响应，``data`` 为分页流水列表。
    """
    data = service.page_wallet_ledgers(userId, page_num, page_size)
    return success(data)
