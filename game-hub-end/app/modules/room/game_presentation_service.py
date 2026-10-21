"""房间对局视图展示与推送端口。"""

from typing import List

from app.modules.room.mapper import build_room_response
from app.modules.room.realtime_service import (
    build_views_for_members,
    collect_human_player_ids,
    push_game_view_updated,
    push_room_list_updated,
    push_room_updated,
)
from app.modules.strategy_turn.schemas import GameEvent, GameView, RuntimeSnapshot
from app.modules.strategy_turn.view_service import GameViewService


class GamePresentationService(object):
    """构建 GameView 并推送房间/对局更新。"""

    def __init__(self, game_view_service: GameViewService) -> None:
        self._game_view_service = game_view_service

    def filter_game_view_events(self, events: List[GameEvent]) -> List[GameEvent]:
        """
        过滤不应进入 GameView.events 的房间级事件。

        :param events: 原始事件列表。
        :return: 供前端动画播放的事件列表。
        """
        filtered = []
        for event in events or []:
            if str(event.eventType or "").strip() == "gameStarted":
                continue
            filtered.append(event)
        return filtered

    def enrich_game_view(
        self,
        snapshot: RuntimeSnapshot,
        player_id: str,
        version: int,
        events: List[GameEvent],
    ) -> GameView:
        """
        为房间接口响应补充版本号与待播放事件列表。

        :param snapshot: 运行时快照。
        :param player_id: 视角玩家 ID。
        :param version: 对局版本号。
        :param events: 本帧事件列表。
        :return: 对局视图。
        """
        return self._game_view_service.build_view(snapshot, player_id, version, events)

    async def push_room_and_game_view(
        self,
        room_id: str,
        meta: dict,
        members: list,
        snapshot: RuntimeSnapshot,
        game_version: int,
        frame_events: List[GameEvent],
        is_game_over: bool,
        room_version: int,
    ) -> None:
        """
        推送房间更新与各成员对局视图。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 成员列表。
        :param snapshot: 运行时快照。
        :param game_version: 对局版本号。
        :param frame_events: 本帧事件列表。
        :param is_game_over: 是否已对局结束。
        :param room_version: 与 meta、members 同一事实快照的房间元数据版本号。
        :return: 无。
        """
        normalized_room_id = str(room_id or "").strip()
        room_response = build_room_response(meta, members, int(room_version))
        player_ids = collect_human_player_ids(room_response.members)
        enrich_fn = self.enrich_game_view
        views = build_views_for_members(
            enrich_fn,
            snapshot,
            int(game_version),
            frame_events,
            player_ids,
        )
        game_code = str(meta.get("gameCode", "")).strip()
        if is_game_over:
            await push_game_view_updated(normalized_room_id, views, room_response.members)
            await push_room_updated(room_response)
            await push_room_list_updated(game_code)
        else:
            await push_room_updated(room_response)
            await push_game_view_updated(normalized_room_id, views, room_response.members)

    async def push_authoritative_terminal_game_view(
        self,
        room_id: str,
        meta: dict,
        members: list,
        snapshot: RuntimeSnapshot,
        game_version: int,
        room_version: int,
    ) -> None:
        """
        推送终局元数据更新后的权威 GameView（不附带领域事件）。

        :param room_id: 房间 ID。
        :param meta: 房间元信息。
        :param members: 成员列表。
        :param snapshot: 提交后的运行时快照。
        :param game_version: 对局版本号。
        :param room_version: 与 meta、members 同一事实快照的房间元数据版本号。
        :return: 无。
        """
        await self.push_room_and_game_view(
            room_id,
            meta,
            members,
            snapshot,
            int(game_version),
            [],
            True,
            room_version,
        )
