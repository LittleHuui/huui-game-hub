"""同步域 HTTP 接口。

云存档同步 ``POST /sync/cloud-save`` 已统一由启动模块（``boot_router``）暴露；
本模块保留 ``SyncModuleService`` 等编排能力供内部或其它域复用，不再注册同路径 HTTP 接口。
"""

from fastapi import APIRouter

router = APIRouter(prefix="/sync", tags=["sync"])
