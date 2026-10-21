"""对局进行中推送当前 GameView 的端口。"""

import logging
from typing import Any, Dict, List

from app.common.exceptions import BizException
from app.modules.room.game_presentation_service import GamePresentationService
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.mapper import build_room_response
from app.modules.room.realtime_service import (
    build_views_for_members,
    collect_human_player_ids,
    push_game_view_updated,
)
from app.modules.room.repository import RoomRepository

logger = logging.getLogger(__name__)


class RoomGameViewPushPort(object):
    """对局进行中同步推送当前 GameView（可无新 events）。"""

    def __init__(
        self,
        repository: RoomRepository,
        state_reader: GameStateReader,
        presentation_service: GamePresentationService,
    ) -> None:
        """
        初始化 GameView 推送端口。

        :param repository: 房间 Redis 仓库。
        :param state_reader: 运行时读取端口。
        :param presentation_service: 对局展示服务。
        """
        self._repository = repository
        self._state_reader = state_reader
        self._presentation_service = presentation_service

    async def push_current_game_view_if_playing(
        self,
        room_id: str,
        meta: Dict[str, Any],
        members: List[Dict[str, Any]],
        version: int,
    ) -> None:
        """
        对局进行中时推送当前 GameView（同步版本与成员状态，可无新 events）。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 成员列表。
        :param version: bump 后的房间版本号。
        :return: 无。
        """
        normalized_room_id = str(room_id or "").strip()
        if not normalized_room_id:
            return
        if str(meta.get("status", "")).strip() != "playing":
            return
        try:
            snapshot = (await self._state_reader.load_consistent(normalized_room_id)).snapshot
        except BizException:
            logger.warning(
                "push_current_game_view_if_playing runtime missing, roomId=%s",
                normalized_room_id,
            )
            return
        room_response = build_room_response(meta, members, version)
        player_ids = collect_human_player_ids(room_response.members)
        game_version = await self._repository.get_game_version(normalized_room_id)
        if game_version is None:
            game_version = 0
        views = build_views_for_members(
            self._presentation_service.enrich_game_view,
            snapshot,
            int(game_version),
            [],
            player_ids,
        )
        await push_game_view_updated(normalized_room_id, views, room_response.members)
