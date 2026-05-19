"""管理配置导入 HTTP 接口。"""

from fastapi import APIRouter, Depends

from app.common.response import ApiResponse, success
from app.modules.admin_config.deps import get_admin_config_module_service
from app.modules.admin_config.module_service import AdminConfigModuleService
from app.modules.admin_config.schemas import ImportGameSeedRequest, ImportGameSeedResponse

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


@router.post(
    "/import-game-seed",
    response_model=ApiResponse[ImportGameSeedResponse],
    summary="导入游戏种子配置（管理/开发）",
)
def import_game_seed(
    body: ImportGameSeedRequest,
    service: AdminConfigModuleService = Depends(get_admin_config_module_service),
) -> ApiResponse[ImportGameSeedResponse]:
    """
    将统一游戏种子配置 JSON 导入服务端（upsert）。

    仅供开发或运维手动调用；前端业务启动流程不得自动调用。

    :param body: 种子配置请求体。
    :param service: 管理配置模块服务。
    :return: 导入统计结果。
    """
    data = service.import_game_seed(body)
    return success(data)
