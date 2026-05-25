"""在线/临时态模块 HTTP 接口。"""

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.common.response import ApiResponse, success
from app.core.database import get_db
from app.modules.online.module_service import OnlineModuleService
from app.modules.online.schemas import OnlineStatusRequest, OnlineUserResponse, OnlineUsersResponse
from app.modules.user.entity_service import UserAccountEntityService
from app.modules.user.models import UserAccount
from app.modules.user.repository import UserAccountRepository

online_router = APIRouter(prefix="/online", tags=["在线模块"])


def get_online_module_service() -> OnlineModuleService:
    """
    组装在线模块服务依赖。

    :return: ``OnlineModuleService`` 实例。
    """
    return OnlineModuleService()


def get_current_online_user(
    service_id: str = Header(..., alias="X-Game-Hub-User-Id"),
    db: Session = Depends(get_db),
) -> UserAccount:
    """
    从请求上下文解析并校验当前用户。

    :param service_id: 当前用户服务端 ID。
    :param db: 请求级数据库会话。
    :return: 当前用户账号。
    :raises BizException: 用户不存在或禁用。
    """
    account_service = UserAccountEntityService(UserAccountRepository(db))
    account = account_service.get_by_server_id(service_id, active_only=True)
    if account is None:
        raise BizException(ErrorCode.USER_NOT_FOUND)
    if account.status != "normal":
        raise BizException(ErrorCode.USER_DISABLED)
    return account


@online_router.get(
    "/users",
    response_model=ApiResponse[OnlineUsersResponse],
    summary="查询在线用户",
)
async def list_online_users(
    service: OnlineModuleService = Depends(get_online_module_service),
):
    """
    查询 Redis 中的在线用户列表。

    :param service: 在线模块服务。
    :return: 统一成功响应。
    """
    return success(await service.list_online_users())


@online_router.post(
    "/status",
    response_model=ApiResponse[OnlineUserResponse],
    summary="修改当前用户在线状态",
)
async def update_online_status(
    request: OnlineStatusRequest,
    current_user: UserAccount = Depends(get_current_online_user),
    service: OnlineModuleService = Depends(get_online_module_service),
):
    """
    修改当前用户在线状态。

    :param request: 在线状态请求。
    :param current_user: 当前用户账号。
    :param service: 在线模块服务。
    :return: 统一成功响应。
    """
    return success(await service.update_status(current_user, request))
