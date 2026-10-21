"""五子棋枚举动作目录与合法操作构建。"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.time_utils import now_ms
from app.modules.game_impls.gomoku.gomoku_board_rule import (
    empty_cells,
    find_last_effective_place_move,
)
from app.modules.game_impls.gomoku.gomoku_constants import (
    ACTION_ACCEPT_UNDO,
    ACTION_PLACE_STONE,
    ACTION_REJECT_UNDO,
    ACTION_REQUEST_UNDO,
    ACTION_RESIGN,
    PHASE_FINISHED,
)
from app.modules.game_impls.gomoku.gomoku_undo_rule import (
    can_handle_undo,
    can_request_undo,
    get_active_undo_request,
)


@dataclass
class GomokuEnumeratedOption(object):
    """五子棋枚举动作可选项。"""

    actionType: str
    actionId: str
    playerId: str
    payload: Dict[str, Any]
    selection: Dict[str, Any]


class GomokuActionCatalog(object):
    """五子棋合法枚举动作目录。"""

    def list_enumerated_options(
        self,
        state: Dict[str, Any],
        player_id: str,
        action_type: str,
        current_time_ms: Optional[int] = None,
    ) -> List[GomokuEnumeratedOption]:
        """
        列出指定动作类型的枚举可选项。

        :param state: 当前对局状态。
        :param player_id: 玩家 ID。
        :param action_type: 动作类型。
        :return: 枚举可选项列表。
        """
        normalized_type = str(action_type or "").strip()
        all_options = self.list_all_options(state, player_id, current_time_ms)
        return [
            option
            for option in all_options
            if option.actionType == normalized_type
        ]

    def list_all_options(
        self,
        state: Dict[str, Any],
        player_id: str,
        current_time_ms: Optional[int] = None,
    ) -> List[GomokuEnumeratedOption]:
        """
        列出玩家当前全部枚举可选项。

        :param state: 当前对局状态。
        :param player_id: 玩家 ID。
        :return: 枚举可选项列表。
        """
        now = int(current_time_ms) if current_time_ms is not None else now_ms()
        active_undo = get_active_undo_request(state, now)
        normalized_id = str(player_id).strip()
        if state.get("phase") == PHASE_FINISHED:
            return []
        if state.get("winnerPlayerId"):
            return []
        actions: List[GomokuEnumeratedOption] = []
        if state.get("currentPlayerId") == normalized_id:
            for row, col in empty_cells(state.get("board") or []):
                actions.append(
                    GomokuEnumeratedOption(
                        actionType=ACTION_PLACE_STONE,
                        actionId="PLACE_STONE:{0}:{1}".format(row, col),
                        playerId=normalized_id,
                        payload={"row": row, "col": col},
                        selection={
                            "type": "BOARD_CELL",
                            "config": {"row": row, "col": col},
                        },
                    )
                )
            actions.append(
                GomokuEnumeratedOption(
                    actionType=ACTION_RESIGN,
                    actionId=ACTION_RESIGN,
                    playerId=normalized_id,
                    payload={},
                    selection={"type": "ACTION_BUTTON", "config": {"name": "resign"}},
                )
            )
        if can_request_undo(state, normalized_id, active_undo):
            last_place = find_last_effective_place_move(state.get("moves") or [])
            target_move_id = str(last_place.get("moveId") or "") if last_place else ""
            actions.append(
                GomokuEnumeratedOption(
                    actionType=ACTION_REQUEST_UNDO,
                    actionId=ACTION_REQUEST_UNDO,
                    playerId=normalized_id,
                    payload={"targetMoveId": target_move_id},
                    selection={
                        "type": "ACTION_BUTTON",
                        "config": {"name": "requestUndo"},
                    },
                )
            )
        if can_handle_undo(state, normalized_id, active_undo):
            undo_request_id = str(active_undo.get("requestId") or "") if active_undo else ""
            actions.append(
                GomokuEnumeratedOption(
                    actionType=ACTION_ACCEPT_UNDO,
                    actionId=ACTION_ACCEPT_UNDO,
                    playerId=normalized_id,
                    payload={"undoRequestId": undo_request_id},
                    selection={
                        "type": "ACTION_BUTTON",
                        "config": {"name": "acceptUndo"},
                    },
                )
            )
            actions.append(
                GomokuEnumeratedOption(
                    actionType=ACTION_REJECT_UNDO,
                    actionId=ACTION_REJECT_UNDO,
                    playerId=normalized_id,
                    payload={"undoRequestId": undo_request_id},
                    selection={
                        "type": "ACTION_BUTTON",
                        "config": {"name": "rejectUndo"},
                    },
                )
            )
        return actions


def find_by_action_id(
    options: List[GomokuEnumeratedOption],
    action_id: str,
) -> Optional[GomokuEnumeratedOption]:
    """
    按 actionId 查找合法操作。

    :param options: 枚举可选项列表。
    :param action_id: 操作 ID。
    :return: 匹配项或 ``None``。
    """
    normalized = str(action_id).strip()
    for item in options:
        if item.actionId == normalized:
            return item
    return None
