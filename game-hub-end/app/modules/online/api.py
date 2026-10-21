"""在线/临时态模块 HTTP 接口。"""

from fastapi import APIRouter, Depends

from app.common.response import ApiResponse, success
from app.modules.auth.deps import get_authenticated_account
from app.modules.online.module_service import OnlineModuleService
from app.modules.online.schemas import OnlineStatusRequest, OnlineUserResponse, OnlineUsersResponse
from app.modules.user.models import UserAccount

online_router = APIRouter(prefix="/online", tags=["在线模块"])


def get_online_module_service() -> OnlineModuleService:
    """
    组装在线模块服务依赖。

    :return: ``OnlineModuleService`` 实例。
    """
    return OnlineModuleService()


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
    current_user: UserAccount = Depends(get_authenticated_account),
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
