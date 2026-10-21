"""UNO 状态投影器。"""



from typing import Any, Dict



from app.modules.game_impls.uno.schemas import UnoRuntimeState

from app.modules.game_impls.uno.uno_state_codec import parse_state

from app.modules.strategy_turn.lifecycle import GameStateProjector

from app.modules.strategy_turn.schemas import GameStateProjection





class UnoStateProjector(GameStateProjector):

    """从 UNO 运行时状态构建玩家可见投影。"""



    def project(

        self,

        state: Dict[str, Any],

        viewer_player_id: str,

        current_time_ms: int = None,

    ) -> GameStateProjection:

        """

        构建 UNO 玩家视角状态投影。



        :param state: 当前对局状态。

        :param viewer_player_id: 视角玩家 ID。

        :return: 状态投影。

        """

        del current_time_ms
        runtime_state = parse_state(state)

        viewer_id = str(viewer_player_id).strip()

        public_state = build_public_state(runtime_state)

        private_state = build_private_state(runtime_state, viewer_id)

        return GameStateProjection(

            phase=runtime_state.phase,

            currentPlayerId=runtime_state.currentPlayerId,

            publicState=public_state,

            privateState=private_state,

        )





def build_public_state(runtime_state: UnoRuntimeState) -> Dict[str, Any]:

    """

    构建所有玩家可见的公有状态。



    :param runtime_state: 运行时状态。

    :return: 公有状态字典。

    """

    player_summaries = []

    for player_id in runtime_state.playerIds:

        player_state = runtime_state.players.get(player_id)

        if player_state is None:

            continue

        player_summaries.append(

            {

                "playerId": player_id,

                "handCount": len(player_state.handCards),

                "seatStatus": player_state.seatStatus,

                "isAi": player_state.isAi,

                "isFinished": player_state.isFinished,

                "finishRank": player_state.finishRank,

            }

        )

    pending_draw = None

    if runtime_state.pendingDraw is not None:

        pending_draw = runtime_state.pendingDraw.model_dump()

    discard_top_card = None

    if runtime_state.topDiscard is not None:

        discard_top_card = runtime_state.topDiscard.model_dump()

    return {

        "phase": runtime_state.phase,

        "playerIds": list(runtime_state.playerIds),

        "players": player_summaries,

        "drawPileCount": len(runtime_state.drawPile),

        "discardPileCount": len(runtime_state.discardPile),

        "discardTopCard": discard_top_card,

        "currentPlayerId": runtime_state.currentPlayerId,

        "playDirection": runtime_state.playDirection,

        "pendingDraw": pending_draw,

        "currentColor": runtime_state.currentColor,

        "rankings": [item.model_dump() for item in runtime_state.rankings],

        "completionOrder": [item.playerId for item in runtime_state.rankings],

        "deckSetCount": runtime_state.deckSetCount,

        "discardPileRecentCards": [

            item.model_dump() for item in runtime_state.discardPileRecentCards

        ],

        "currentTurnStartedAt": runtime_state.currentTurnStartedAt,

        "turnTimeoutSeconds": runtime_state.turnTimeoutSeconds,

        "currentTurnDeadlineAt": runtime_state.currentTurnDeadlineAt,

    }





def build_private_state(

    runtime_state: UnoRuntimeState,

    viewer_player_id: str,

) -> Dict[str, Any]:

    """

    构建仅视角玩家可见的私有状态。



    :param runtime_state: 运行时状态。

    :param viewer_player_id: 视角玩家 ID。

    :return: 私有状态字典。

    """

    player_state = runtime_state.players.get(viewer_player_id)

    hand_cards = []

    if player_state is not None:

        hand_cards = [card.model_dump() for card in player_state.handCards]

    return {

        "handCards": hand_cards,

    }
