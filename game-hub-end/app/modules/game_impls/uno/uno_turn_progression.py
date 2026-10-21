"""UNO 回合推进与终局判定。"""

from typing import Any, Dict, List, Tuple

from app.modules.game_impls.uno.uno_event_factory import append_domain_event, build_rule_context
from app.modules.game_impls.uno.uno_state_codec import dump_state, parse_state, resolve_room_config_from_state
from app.modules.game_impls.uno.uno_turn_rule import advance_turn
from app.modules.strategy_turn.schemas import DomainEventDraft


class UnoTurnProgression(object):
    """UNO 回合推进器。"""

    def advance(
        self,
        state: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[DomainEventDraft]]:
        """
        在操作结算后推进回合，牌效回到已完赛者时继续转交可行动玩家。

        :param state: 当前对局状态。
        :return: (推进后状态, 事件草稿列表)。
        """
        runtime_state = parse_state(state)
        room_config = resolve_room_config_from_state(state)
        runtime_state.drawDecision = None
        runtime_state.drawSource = None
        if runtime_state.phase == "finished":
            dumped = dump_state(runtime_state)
            dumped["roomConfig"] = room_config
            return dumped, []
        if runtime_state.drewThisTurn:
            dumped = dump_state(runtime_state)
            dumped["roomConfig"] = room_config
            return dumped, []
        if runtime_state.effectAdvanceHandled:
            runtime_state.effectAdvanceHandled = False
            current_player = runtime_state.players.get(runtime_state.currentPlayerId)
            if current_player is None or not current_player.isFinished:
                dumped = dump_state(runtime_state)
                dumped["roomConfig"] = room_config
                return dumped, []
        previous_player_id = runtime_state.currentPlayerId
        next_player_id = advance_turn(runtime_state, 1)
        if next_player_id != previous_player_id:
            context = build_rule_context(
                runtime_state,
                room_config,
                next_player_id,
            )
            append_domain_event(
                context,
                "uno.turn.advanced",
                {
                    "previousPlayerId": previous_player_id,
                    "nextPlayerId": next_player_id,
                },
            )
            dumped = dump_state(runtime_state)
            dumped["roomConfig"] = room_config
            return dumped, list(context.newEvents)
        dumped = dump_state(runtime_state)
        dumped["roomConfig"] = room_config
        return dumped, []

    def is_game_over(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        判断对局是否结束。

        :param state: 当前对局状态。
        :return: 已结束为 ``True``。
        """
        runtime_state = parse_state(state)
        return runtime_state.phase == "finished"
