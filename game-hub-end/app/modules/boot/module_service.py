"""启动上下文编排：用户绑定、设置与游戏摘要。"""

from typing import List
from app.core.time_utils import now_ms
from app.modules.boot.schemas import BootContextRequest, BootContextResponse
from app.modules.game_config.response_schemas import GameSummaryResponse
from app.modules.game_config.models import GameDefinition
from app.modules.game_config.module_service import GameModuleService
from app.modules.user.module_service import UserModuleService
from app.modules.user.response_mappers import to_user_summary, to_user_system_setting_response


def _to_game_summary(game: GameDefinition) -> GameSummaryResponse:
    """
    将游戏定义 ORM 转为启动模块游戏摘要。

    :param game: 游戏定义实体。
    :return: ``GameSummaryResponse``。
    """
    return GameSummaryResponse(
        gameCode=game.game_code,
        gameName=game.game_name,
        gameSubName=game.game_sub_name,
        supportOnline=bool(game.support_online),
        enabled=bool(game.enabled),
        sortNo=game.sort_no,
    )

class BootModuleService:
    """负责启动上下文；依赖在构造时完整提供。"""

    def __init__(self, user_module_service: UserModuleService, game_module_service: GameModuleService) -> None:
        """注入启动时必须的用户与游戏查询服务。"""
        self._user_module_service = user_module_service
        self._game_module_service = game_module_service

    def _list_enabled_games(self) -> List[GameSummaryResponse]:
        """
        查询已启用游戏列表并转为响应对象。

        :return: 游戏摘要列表。
        """
        games = self._game_module_service.list_enabled_games()
        return [_to_game_summary(game) for game in games]

    async def get_boot_context(
        self,
        request: BootContextRequest,
    ) -> BootContextResponse:
        """获取启动上下文。"""
        server_time = now_ms()
        games = self._list_enabled_games()

        user_id = request.userId
        if user_id is None or not user_id.strip():
            return BootContextResponse(
                serverTime=server_time,
                userExists=False,
                user=None,
                systemSetting=None,
                games=games,
            )

        user_id = user_id.strip()
        user = self._user_module_service.get_user_by_id(user_id)
        if user is None:
            return BootContextResponse(
                serverTime=server_time,
                userExists=False,
                user=None,
                systemSetting=None,
                games=games,
            )

        self._user_module_service.bind_or_update_device_for_boot(user_id, request.deviceId)
        setting_entity = self._user_module_service.get_or_create_user_system_setting(user_id)

        return BootContextResponse(
            serverTime=server_time,
            userExists=True,
            user=to_user_summary(user),
            systemSetting=to_user_system_setting_response(setting_entity),
            games=games,
        )
