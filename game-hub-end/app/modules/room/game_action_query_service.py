"""房间对局动作查询服务。"""

from typing import Optional

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.clock import Clock, system_clock
from app.modules.room.game_session_validator import GameSessionValidator
from app.modules.room.game_state_reader import GameStateReader
from app.modules.room.schemas import (
    RoomActionPreviewRequest,
    RoomActionSuggestionsRequest,
)
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.gateway import ActionInteractionGateway
from app.modules.strategy_turn.schemas import (
    ActionPreview,
    GameView,
    HintSuggestionPage,
    RuntimeSnapshot,
)
from app.modules.strategy_turn.view_service import GameViewService


class RoomGameActionQueryService(object):
    """负责房间 GameView、动作预览和动作提示查询。"""

    def __init__(
        self,
        state_reader: GameStateReader,
        game_view_service: GameViewService,
        interaction_gateway: ActionInteractionGateway,
        session_validator: GameSessionValidator,
        clock: Clock = system_clock,
    ) -> None:
        """
        初始化只读动作查询服务。

        :param state_reader: 一致对局状态读取器。
        :param game_view_service: GameView 构建服务。
        :param interaction_gateway: 动作交互网关。
        :param session_validator: 对局会话校验器。
        :param clock: 可注入时钟。
        """
        self._state_reader = state_reader
        self._game_view_service = game_view_service
        self._interaction_gateway = interaction_gateway
        self._session_validator = session_validator
        self._clock = clock

    async def view_room_game(self, room_id: str, player_id: str) -> GameView:
        """
        查询当前玩家在房间对局中的视图，不推进对局。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :return: 当前玩家的对局视图。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        meta = await self._session_validator.require_meta(normalized_room_id)
        if str(meta.get("status", "")).strip() != "playing":
            raise BizException(ErrorCode.PARAM_ERROR, message="对局尚未开始")
        members = await self._session_validator.list_members(normalized_room_id)
        self._session_validator.require_readable_member(members, normalized_player_id)
        consistent_state = await self._state_reader.load_consistent(normalized_room_id)
        return self._game_view_service.build_view(
            consistent_state.snapshot,
            normalized_player_id,
            int(consistent_state.gameVersion),
            [],
        )

    async def preview_room_action(
        self,
        room_id: str,
        player_id: str,
        request: RoomActionPreviewRequest,
    ) -> ActionPreview:
        """
        只读预览当前玩家动作。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request: 预览请求。
        :return: 预览结果。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        meta = await self._session_validator.require_meta(normalized_room_id)
        self._session_validator.require_playing_room(meta)
        members = await self._session_validator.list_members(normalized_room_id)
        self._session_validator.require_readable_member(members, normalized_player_id)
        return await self.preview(normalized_room_id, normalized_player_id, request)

    async def suggest_room_actions(
        self,
        room_id: str,
        player_id: str,
        request: RoomActionSuggestionsRequest,
    ) -> HintSuggestionPage:
        """
        只读查询当前玩家动作提示。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request: 提示请求。
        :return: 动作候选分页。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        meta = await self._session_validator.require_meta(normalized_room_id)
        self._session_validator.require_playing_room(meta)
        members = await self._session_validator.list_members(normalized_room_id)
        self._session_validator.require_readable_member(members, normalized_player_id)
        return await self.suggestions(normalized_room_id, normalized_player_id, request)

    async def build_game_view(
        self,
        snapshot: RuntimeSnapshot,
        player_id: str,
        version: int,
    ) -> GameView:
        """
        构建玩家对局视图。

        :param snapshot: 当前运行时快照。
        :param player_id: 玩家 ID。
        :param version: 对局版本号。
        :return: GameView。
        """
        return self._game_view_service.build_view(snapshot, player_id, version, [])

    async def preview(
        self,
        room_id: str,
        player_id: str,
        request: RoomActionPreviewRequest,
    ) -> ActionPreview:
        """
        只读预览动作提交。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request: 预览请求。
        :return: 预览结果。
        """
        snapshot, version = await self._load_consistent_snapshot(room_id, request.baseVersion)
        context = ActionInteractionContext(
            gameCode=snapshot.gameCode,
            roomId=room_id,
            runtimeRule=snapshot.runtimeRule,
            state=snapshot.state,
            playerId=player_id,
            version=version,
            currentTimeMs=self._clock.now_ms(),
        )
        return self._interaction_gateway.preview(context, request.submission)

    async def suggestions(
        self,
        room_id: str,
        player_id: str,
        request: RoomActionSuggestionsRequest,
    ) -> HintSuggestionPage:
        """
        只读查询动作提示。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request: 提示请求。
        :return: 候选分页。
        """
        snapshot, version = await self._load_consistent_snapshot(room_id, request.baseVersion)
        context = ActionInteractionContext(
            gameCode=snapshot.gameCode,
            roomId=room_id,
            runtimeRule=snapshot.runtimeRule,
            state=snapshot.state,
            playerId=player_id,
            version=version,
            currentTimeMs=self._clock.now_ms(),
        )
        return self._interaction_gateway.list_hint_suggestions(
            context,
            request.actionType,
            request.cursor or "",
            int(request.limit),
        )

    async def _load_consistent_snapshot(
        self,
        room_id: str,
        base_version: int,
    ):
        """
        读取与客户端版本一致的对局状态。

        :param room_id: 房间 ID。
        :param base_version: 客户端对局版本。
        :return: ``(snapshot, gameVersion)``。
        """
        consistent_state = await self._state_reader.load_consistent(room_id)
        current_version = int(consistent_state.gameVersion)
        if int(base_version) != int(current_version):
            raise BizException(ErrorCode.GAME_VIEW_VERSION_CONFLICT)
        snapshot = consistent_state.snapshot
        commit_version = int(snapshot.commitVersion or 0)
        if commit_version != int(current_version):
            raise BizException(ErrorCode.GAME_VIEW_VERSION_CONFLICT)
        return snapshot, int(current_version)
