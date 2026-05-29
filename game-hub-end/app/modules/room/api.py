"""房间模块 HTTP 接口。"""

from typing import List

from fastapi import APIRouter, Depends, Query, Body

from app.common.response import ApiResponse, success
from app.modules.room.deps import get_current_room_user, get_room_module_service
from app.modules.room.module_service import RoomModuleService
from app.modules.room.schemas import (
    CreateRoomRequest,
    MyActiveRoomResponse,
    RemoveRoomMemberRequest,
    RoomActionRequest,
    RoomGameViewResponse,
    RoomLeaveResponse,
    RoomListItemResponse,
    RoomResponse,
    UpdateRoomConfigRequest,
)
from app.modules.user.models import UserAccount

room_router = APIRouter(prefix="/rooms", tags=["房间模块"])


@room_router.get(
    "",
    response_model=ApiResponse[List[RoomListItemResponse]],
    summary="查询房间列表",
)
async def list_rooms(
    gameCode: str = Query(min_length=1, description="游戏编码"),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    按游戏编码查询房间列表。

    :param gameCode: 游戏编码。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.list_rooms(gameCode))


@room_router.post(
    "",
    response_model=ApiResponse[RoomResponse],
    summary="创建房间",
)
async def create_room(
    request: CreateRoomRequest,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    创建房间并将当前用户写入成员列表。

    :param request: 创建房间请求。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.create_room(current_user, request))


@room_router.get(
    "/my-active",
    response_model=ApiResponse[MyActiveRoomResponse],
    summary="查询当前用户活跃房间",
)
async def get_my_active_room(
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    查询当前用户活跃房间（跨游戏）。

    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.get_my_active_room(current_user))


@room_router.get(
    "/my-managed-shell",
    response_model=ApiResponse[MyActiveRoomResponse],
    summary="查询当前用户托管空壳房间",
)
async def get_my_managed_shell_room(
    gameCode: str = Query(min_length=1, description="游戏编码"),
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    查询当前用户在指定游戏下可恢复的托管空壳房间。

    :param gameCode: 游戏编码。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.get_my_managed_shell_room(current_user, gameCode))


@room_router.get(
    "/{roomId}",
    response_model=ApiResponse[RoomResponse],
    summary="查询房间详情",
)
async def get_room(
    roomId: str,
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    查询房间元信息与成员列表。

    :param roomId: 房间 ID。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.get_room(roomId))


@room_router.post(
    "/{roomId}/join",
    response_model=ApiResponse[RoomResponse],
    summary="加入房间",
)
async def join_room(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    当前用户加入房间。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.join_room(current_user, roomId))


@room_router.post(
    "/{roomId}/rejoin",
    response_model=ApiResponse[RoomResponse],
    summary="恢复托管席位并重连房间",
)
async def rejoin_managed_room(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    在对局中恢复当前用户托管席位。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.rejoin_managed_room(current_user, roomId))


@room_router.post(
    "/{roomId}/managed/start",
    response_model=ApiResponse[RoomResponse],
    summary="开启在线托管",
)
async def start_managed_mode(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    当前用户在对局中开启在线托管。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.start_managed_mode(current_user, roomId))


@room_router.post(
    "/{roomId}/managed/stop",
    response_model=ApiResponse[RoomResponse],
    summary="取消在线托管",
)
async def stop_managed_mode(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    当前用户在对局中取消在线托管。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.stop_managed_mode(current_user, roomId))


@room_router.post(
    "/{roomId}/members/remove",
    response_model=ApiResponse[RoomResponse],
    summary="房主移除房间成员",
)
async def remove_room_member(
    roomId: str,
    request: RemoveRoomMemberRequest,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    房主在等待中的房间内移除普通玩家或 AI。

    :param roomId: 房间 ID。
    :param request: 移除成员请求。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.remove_room_member(current_user, roomId, request))


@room_router.patch(
    "/{roomId}/config",
    response_model=ApiResponse[RoomResponse],
    summary="房主更新房间配置",
)
async def update_room_config(
    roomId: str,
    request: UpdateRoomConfigRequest = Body(...),
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    房主在等待中的房间内更新人数上限与玩法配置。

    :param roomId: 房间 ID。
    :param request: 更新配置请求（maxPlayers、roomConfig）。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.update_room_config(current_user, roomId, request))


@room_router.post(
    "/{roomId}/ai",
    response_model=ApiResponse[RoomResponse],
    summary="添加 AI 玩家",
)
async def add_room_ai(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    在 waiting 房间中添加一名平台代管 AI 玩家；AI 行动走托管动作链路。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.add_room_ai(current_user, roomId))


@room_router.post(
    "/{roomId}/leave",
    response_model=ApiResponse[RoomLeaveResponse],
    summary="离开房间",
)
async def leave_room(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    当前用户离开房间。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.leave_room(current_user, roomId))


@room_router.post(
    "/{roomId}/start",
    response_model=ApiResponse[RoomGameViewResponse],
    summary="开始房间对局",
)
async def start_room_game(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    在房间内开始策略回合制对局。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.start_room_game(current_user, roomId))


@room_router.get(
    "/{roomId}/view",
    response_model=ApiResponse[RoomGameViewResponse],
    summary="查询房间对局视图",
)
async def view_room_game(
    roomId: str,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    查询当前玩家在房间对局中的视图。

    :param roomId: 房间 ID。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.view_room_game(current_user, roomId))


@room_router.post(
    "/{roomId}/actions",
    response_model=ApiResponse[RoomGameViewResponse],
    summary="提交房间对局操作",
)
async def apply_room_action(
    roomId: str,
    request: RoomActionRequest,
    current_user: UserAccount = Depends(get_current_room_user),
    service: RoomModuleService = Depends(get_room_module_service),
):
    """
    提交当前玩家在房间对局中的操作。

    :param roomId: 房间 ID。
    :param request: 操作请求。
    :param current_user: 当前用户账号。
    :param service: 房间模块服务。
    :return: 统一成功响应。
    """
    return success(await service.apply_room_action(current_user, roomId, request))
