"""五子棋状态投影器。"""

from typing import Any, Dict

from app.modules.game_impls.gomoku.gomoku_state_codec import build_public_game_state
from app.modules.strategy_turn.lifecycle import GameStateProjector
from app.modules.strategy_turn.schemas import GameStateProjection


class GomokuStateProjector(GameStateProjector):
    """从五子棋运行时状态构建玩家可见投影。"""

    def project(
        self,
        state: Dict[str, Any],
        viewer_player_id: str,
        current_time_ms: int = None,
    ) -> GameStateProjection:
        """
        构建五子棋玩家视角状态投影。

        :param state: 当前对局状态。
        :param viewer_player_id: 视角玩家 ID。
        :return: 状态投影。
        """
        del viewer_player_id
        phase = str(state.get("phase") or "playing")
        return GameStateProjection(
            phase=phase,
            currentPlayerId=state.get("currentPlayerId"),
            publicState={
                "players": state.get("players") or [],
                "currentPlayerId": state.get("currentPlayerId"),
                "gameState": build_public_game_state(state, current_time_ms),
            },
            privateState={},
        )
