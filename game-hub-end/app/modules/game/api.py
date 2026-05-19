"""游戏域 HTTP 接口。"""

from typing import List

from fastapi import APIRouter, Depends, Path

from app.common.response import ApiResponse, success
from app.modules.game.deps import get_game_module_service
from app.modules.game.module_service import GameModuleService, _to_game_summary
from app.modules.game.schemas import GameConfigResponse, GameSummaryResponse

router = APIRouter(prefix="/games", tags=["game"])


@router.get(
    "",
    response_model=ApiResponse[List[GameSummaryResponse]],
    summary="游戏列表",
)
def list_games(
    service: GameModuleService = Depends(get_game_module_service),
):
    """列出全部已启用游戏。"""
    items = service.list_enabled_games()
    data = [_to_game_summary(g) for g in items]
    return success(data)


@router.get(
    "/{gameCode}/config",
    response_model=ApiResponse[GameConfigResponse],
    summary="游戏配置详情",
)
def get_game_config(
    gameCode: str = Path(..., min_length=1, description="游戏编码"),
    service: GameModuleService = Depends(get_game_module_service),
):
    """返回游戏基础信息、难度、客户端适配与道具规则配置。"""
    data = service.get_game_config(gameCode)
    return success(data)


# GET /games/{gameCode}/client-config 已下线：客户端配置统一由 GET /games/{gameCode}/config 返回；底层 module_service 保留。
