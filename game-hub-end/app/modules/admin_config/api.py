"""管理配置导入 HTTP 接口。"""

from fastapi import APIRouter, Depends, Query

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
    importMode: str = Query(
        default="merge",
        description="导入模式：merge=新增+更新；full=全量覆盖（含清理库内多余项）",
    ),
    deleteMode: str = Query(
        default="logical",
        description="删除模式：logical=软删+禁用；physical=物理删除（仅 importMode=full 时生效）",
    ),
    service: AdminConfigModuleService = Depends(get_admin_config_module_service),
) -> ApiResponse[ImportGameSeedResponse]:
    """
    将统一游戏种子配置 JSON 导入服务端。

    仅供开发或运维手动调用；前端业务启动流程不得自动调用。

    :param body: 种子配置请求体。
    :param importMode: 导入模式 merge / full。
    :param deleteMode: 删除模式 logical / physical（仅 full 生效）。
    :param service: 管理配置模块服务。
    :return: 导入统计结果。
    """
    data = service.import_game_seed(body, import_mode=importMode, delete_mode=deleteMode)
    return success(data)
