from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.common.error_code import ErrorCode
from app.common.response import ApiResponse, success
from app.modules.boot.deps import get_boot_module_service, get_health_service
from app.modules.boot.health_service import HealthService
from app.modules.sync.deps import get_cloud_save_service
from app.modules.sync.cloud_save_service import CloudSaveService
from app.modules.boot.module_service import BootModuleService
from app.modules.boot.schemas import BootContextRequest
from app.modules.boot.schemas import BootContextResponse
from app.modules.sync.cloud_save_schemas import CloudSaveSyncRequest
from app.modules.sync.cloud_save_schemas import CloudSaveSyncResponse
from app.modules.boot.schemas import HealthCheckResponse

boot_router = APIRouter(tags=["启动模块"])


@boot_router.get(
    "/health",
    response_model=ApiResponse[HealthCheckResponse],
    summary="健康检查",
)
async def health_check(
    service: HealthService = Depends(get_health_service),
):
    """健康检查接口。"""
    data = await service.health_live()
    return success(data)


@boot_router.get(
    "/health/live",
    response_model=ApiResponse[HealthCheckResponse],
    summary="Live health check",
)
async def health_live(
    service: HealthService = Depends(get_health_service),
):
    """返回进程存活状态，不探测外部依赖。"""
    data = await service.health_live()
    return success(data)


@boot_router.get(
    "/health/ready",
    response_model=ApiResponse[HealthCheckResponse],
    summary="Readiness health check",
)
async def health_ready(
    service: HealthService = Depends(get_health_service),
):
    """依赖就绪检查接口。"""
    data = await service.health_ready()
    if data.status != "ok":
        response = ApiResponse.fail(
            ErrorCode.SYSTEM_ERROR,
            "服务依赖未就绪",
            detail=data.model_dump(),
        )
        return JSONResponse(
            status_code=503,
            content=response.model_dump(exclude_none=True),
        )
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
    service: CloudSaveService = Depends(get_cloud_save_service),
):
    """云存档同步接口。"""
    data = await service.sync_cloud_save(request)
    return success(data)
