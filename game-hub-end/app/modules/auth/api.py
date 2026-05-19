"""认证模块 HTTP 接口。"""

from fastapi import APIRouter, Depends

from app.common.response import ApiResponse, success
from app.modules.auth.deps import get_auth_module_service
from app.modules.auth.module_service import AuthModuleService
from app.modules.auth.schemas import LoginRequest, LoginResponse

auth_router = APIRouter(prefix="/auth", tags=["认证模块"])


@auth_router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="用户名登录",
)
def login(
    request: LoginRequest,
    service: AuthModuleService = Depends(get_auth_module_service),
):
    """
    用户名登录：绑定设备并返回启动基础数据。

    :param request: 登录请求体。
    :param service: 认证模块服务。
    :return: 统一成功响应。
    """
    data = service.login(request)
    return success(data)
