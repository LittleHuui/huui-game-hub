"""系统域 HTTP 接口。"""

from fastapi import APIRouter, Depends

from app.common.response import ApiResponse, success
from app.modules.system.deps import get_system_module_service
from app.modules.system.module_service import SystemModuleService
from app.modules.system.schemas import (
    SystemConfigListResponse,
    SystemConfigResponse,
    SystemConfigUpsert,
    system_config_to_response,
)

router = APIRouter(prefix="/system", tags=["system"])


@router.get(
    "/configs",
    response_model=ApiResponse[SystemConfigListResponse],
    summary="列出系统配置",
)
def list_system_configs(
    service: SystemModuleService = Depends(get_system_module_service),
) -> ApiResponse[SystemConfigListResponse]:
    """
    列出全部平台级系统配置。

    :param service: 系统模块服务。
    :return: 配置列表。
    """
    items = service.list_configs()
    data = SystemConfigListResponse(
        items=[system_config_to_response(item) for item in items],
    )
    return success(data)


@router.put(
    "/configs/{configKey}",
    response_model=ApiResponse[SystemConfigResponse],
    summary="创建或更新系统配置",
)
def upsert_system_config(
    configKey: str,
    body: SystemConfigUpsert,
    service: SystemModuleService = Depends(get_system_module_service),
) -> ApiResponse[SystemConfigResponse]:
    """
    按 configKey 创建或更新系统配置。

    :param configKey: 配置键。
    :param body: 更新载荷。
    :param service: 系统模块服务。
    :return: 持久化后的配置。
    """
    entity = service.upsert_config(configKey, body)
    return success(system_config_to_response(entity))
