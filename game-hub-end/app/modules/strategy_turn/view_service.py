"""策略回合 GameView 构建服务。"""

from typing import List

from app.common.exceptions import ValidationException
from app.modules.strategy_turn.game_module import StrategyTurnGameModuleRegistry
from app.modules.strategy_turn.interaction.context import ActionInteractionContext
from app.modules.strategy_turn.interaction.gateway import ActionInteractionGateway
from app.modules.strategy_turn.schemas import GameEvent, GameView, RuntimeSnapshot
from app.core.clock import Clock, system_clock


class GameViewService(object):
    """组合状态投影与动作 Offer 构建最终 GameView。"""

    def __init__(
        self,
        module_registry: StrategyTurnGameModuleRegistry,
        interaction_gateway: ActionInteractionGateway,
        clock: Clock = system_clock,
    ) -> None:
        self._module_registry = module_registry
        self._interaction_gateway = interaction_gateway
        self._clock = clock

    def build_view(
        self,
        snapshot: RuntimeSnapshot,
        viewer_player_id: str,
        version: int,
        events: List[GameEvent],
    ) -> GameView:
        """
        构建玩家视角 GameView。

        :param snapshot: 当前运行时快照。
        :param viewer_player_id: 视角玩家 ID。
        :param version: 房间版本。
        :param events: 本帧事件。
        :return: 玩家视角 GameView。
        """
        viewer_id = str(viewer_player_id or "").strip()
        if not viewer_id:
            raise ValidationException("viewerPlayerId 不能为空")
        if viewer_id not in snapshot.runtimeRule.playerIds:
            raise ValidationException("viewerPlayerId 不在对局玩家列表中")
        game_code = str(snapshot.gameCode or "").strip()
        module = self._module_registry.require(game_code)
        current_time_ms = self._clock.now_ms()
        projection = module.stateProjector.project(
            snapshot.state,
            viewer_id,
            current_time_ms,
        )
        offers = []
        if not bool(snapshot.isGameOver):
            context = ActionInteractionContext(
                gameCode=game_code,
                roomId=snapshot.roomId,
                runtimeRule=snapshot.runtimeRule,
                state=snapshot.state,
                playerId=viewer_id,
                version=int(version),
                currentTimeMs=current_time_ms,
            )
            offers = self._interaction_gateway.build_offers(context)
        return GameView(
            roomId=snapshot.roomId,
            gameCode=game_code,
            viewerPlayerId=viewer_id,
            phase=projection.phase,
            currentPlayerId=projection.currentPlayerId,
            actionOffers=offers,
            publicState=projection.publicState,
            privateState=projection.privateState,
            isGameOver=bool(snapshot.isGameOver),
            terminalMetadata=snapshot.terminalMetadata,
            version=int(version),
            events=list(events or []),
        )
