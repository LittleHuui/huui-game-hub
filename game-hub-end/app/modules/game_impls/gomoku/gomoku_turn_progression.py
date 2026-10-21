"""五子棋回合推进与终局判定。"""

import copy
from typing import Any, Dict, List, Tuple

from app.modules.game_impls.gomoku.gomoku_constants import PHASE_FINISHED
from app.modules.game_impls.gomoku.gomoku_state_codec import dump_state
from app.modules.strategy_turn.schemas import DomainEventDraft


class GomokuTurnProgression(object):
    """五子棋回合推进器。"""

    def advance(
        self,
        state: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        五子棋在 ``apply_action`` 内已完成回合切换，此处无需额外推进。

        :param state: 当前对局状态。
        :return: (状态副本, 空事件草稿列表)。
        """
        next_state = dump_state(copy.deepcopy(state))
        return next_state, []

    def is_game_over(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        判断对局是否已结束。

        :param state: 当前对局状态。
        :return: 已结束为 ``True``。
        """
        return state.get("phase") == PHASE_FINISHED or bool(state.get("winnerPlayerId"))
