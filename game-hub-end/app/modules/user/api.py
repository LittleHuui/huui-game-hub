"""用户域 HTTP 接口。"""

from fastapi import APIRouter, Depends

from app.common.response import ApiResponse, success
from app.modules.user.deps import get_user_module_service
from app.modules.user.module_service import UserModuleService
from app.modules.user.schemas import (
    UserAccountCreate,
    UserAccountResponse,
    UserAccountUpdateNickname,
    UserDetailResponse,
    UserDeviceBind,
    UserDeviceResponse,
    UserGameSettingResponse,
    UserGameSettingUpsert,
    UserSystemSettingResponse,
    UserSystemSettingUpsert,
    user_account_to_response,
    user_detail_to_response,
    user_device_to_response,
    user_game_setting_read_to_response,
    user_game_setting_to_read,
    user_system_setting_read_to_response,
    user_system_setting_to_read,
)

router = APIRouter(prefix="/users", tags=["user"])


@router.post(
    "/",
    response_model=ApiResponse[UserAccountResponse],
    summary="创建用户",
)
def create_user(
    body: UserAccountCreate,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserAccountResponse]:
    """创建用户。"""
    entity = service.create_user(body)
    return success(user_account_to_response(entity))


@router.get(
    "/{userId}",
    response_model=ApiResponse[UserDetailResponse],
    summary="查询用户详情",
)
def get_user_detail(
    userId: str,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserDetailResponse]:
    """查询用户详情。"""
    detail = service.get_user_detail(userId)
    return success(user_detail_to_response(detail))


@router.put(
    "/{userId}/nickname",
    response_model=ApiResponse[UserAccountResponse],
    summary="更新用户昵称",
)
def update_user_nickname(
    userId: str,
    body: UserAccountUpdateNickname,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserAccountResponse]:
    """更新用户昵称。"""
    entity = service.update_nickname(userId, body)
    return success(user_account_to_response(entity))


@router.post(
    "/{userId}/devices",
    response_model=ApiResponse[UserDeviceResponse],
    summary="绑定或更新用户设备",
)
def bind_user_device(
    userId: str,
    body: UserDeviceBind,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserDeviceResponse]:
    """绑定或更新用户设备。"""
    entity = service.bind_or_update_device(userId, body)
    return success(user_device_to_response(entity))


@router.get(
    "/{userId}/games/{gameCode}/setting",
    response_model=ApiResponse[UserGameSettingResponse],
    summary="获取用户游戏设置",
)
def get_user_game_setting(
    userId: str,
    gameCode: str,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserGameSettingResponse]:
    """获取（若无则创建）用户在某游戏中的设置。"""
    data = service.read_user_game_setting(userId, gameCode)
    return success(user_game_setting_read_to_response(data))


@router.put(
    "/{userId}/games/{gameCode}/setting",
    response_model=ApiResponse[UserGameSettingResponse],
    summary="写入用户游戏设置",
)
def put_user_game_setting(
    userId: str,
    gameCode: str,
    body: UserGameSettingUpsert,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserGameSettingResponse]:
    """覆盖写入用户在某游戏中的设置。"""
    entity = service.update_user_game_setting(userId, gameCode, body.setting)
    return success(user_game_setting_read_to_response(user_game_setting_to_read(entity)))


@router.get(
    "/{userId}/system-setting",
    response_model=ApiResponse[UserSystemSettingResponse],
    summary="获取用户系统设置",
)
def get_user_system_setting(
    userId: str,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserSystemSettingResponse]:
    """获取（若无则创建）用户平台级系统设置。"""
    data = service.read_user_system_setting(userId)
    return success(user_system_setting_read_to_response(data))


@router.put(
    "/{userId}/system-setting",
    response_model=ApiResponse[UserSystemSettingResponse],
    summary="写入用户系统设置",
)
def put_user_system_setting(
    userId: str,
    body: UserSystemSettingUpsert,
    service: UserModuleService = Depends(get_user_module_service),
) -> ApiResponse[UserSystemSettingResponse]:
    """覆盖写入用户平台级系统设置。"""
    entity = service.update_user_system_setting(userId, body.setting)
    return success(
        user_system_setting_read_to_response(user_system_setting_to_read(entity)),
    )
