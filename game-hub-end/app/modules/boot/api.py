from fastapi import APIRouter, Depends

from app.common.response import ApiResponse, success
from app.modules.boot.deps import get_boot_module_service
from app.modules.boot.module_service import BootModuleService
from app.modules.boot.schemas import (
    BootContextRequest,
    BootContextResponse,
    CloudSaveSyncRequest,
    CloudSaveSyncResponse,
    HealthCheckResponse,
)

boot_router = APIRouter(tags=["启动模块"])


@boot_router.get(
    "/health",
    response_model=ApiResponse[HealthCheckResponse],
    summary="健康检查",
)
async def health_check(
    service: BootModuleService = Depends(get_boot_module_service),
):
    """健康检查接口。"""
    data = await service.health_check()
    return success(data)


@boot_router.post(
    "/boot/context",
    response_model=ApiResponse[BootContextResponse],
    summary="获取启动上下文",
)
async def get_boot_context(
    request: BootContextRequest,
    service: BootModuleService = Depends(get_boot_module_service),
):
    """获取启动上下文接口。"""
    data = await service.get_boot_context(request)
    return success(data)


@boot_router.post(
    "/sync/cloud-save",
    response_model=ApiResponse[CloudSaveSyncResponse],
    summary="云存档同步",
)
async def sync_cloud_save(
    request: CloudSaveSyncRequest,
    service: BootModuleService = Depends(get_boot_module_service),
):
    """云存档同步接口。"""
    data = await service.sync_cloud_save(request)
    return success(data)
