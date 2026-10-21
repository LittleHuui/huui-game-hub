"""UNO 初始对局状态构建。"""

from typing import Any, Dict, List

from app.modules.game_impls.uno.schemas import (
    UnoDiscardRecentCard,
    UnoPlayerState,
    UnoRuntimeState,
)
from app.modules.game_impls.uno.uno_constants import SEAT_PLAYING
from app.modules.game_impls.uno.uno_state_codec import (
    dump_state,
    resolve_ai_player_ids,
    resolve_room_config,
)
from app.modules.game_impls.uno.uno_deck_factory import (
    build_initial_draw_pile,
    draw_cards_from_pile,
    pop_starting_discard_card,
    resolve_deck_set_count,
)
from app.modules.game_impls.uno.uno_finish_rule import sync_game_over_phase
from app.modules.game_impls.uno.uno_turn_rule import stamp_turn_clock
from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED
from app.modules.strategy_turn.schemas import StrategyTurnRuntimeRule


class UnoStateFactory(object):
    """UNO 开局状态工厂。"""

    def build_initial_state(
        self,
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> Dict[str, Any]:
        """
        根据玩家列表生成初始状态并完成发牌。

        :param runtime_rule: 运行时规则。
        :return: 对局状态字典。
        """
        seed = UNO_ONLINE_GAME_RULE_SEED
        player_ids = list(runtime_rule.playerIds)
        room_config = resolve_room_config(runtime_rule)
        ai_player_ids = resolve_ai_player_ids(runtime_rule)
        deck_set_count = resolve_deck_set_count(seed, len(player_ids))
        draw_pile = build_initial_draw_pile(seed, len(player_ids), shuffle=True)
        initial_hand_count = int(room_config.get("initialHandCount", 7))
        dealing_state = UnoRuntimeState(
            phase="playing",
            playerIds=player_ids,
            players={},
            drawPile=draw_pile,
            discardPile=[],
            currentPlayerId=player_ids[0],
            deckSetCount=deck_set_count,
        )
        players = {}
        for player_id in player_ids:
            hand_cards = draw_cards_from_pile(
                dealing_state,
                seed,
                initial_hand_count,
                room_config,
            )
            players[player_id] = UnoPlayerState(
                playerId=player_id,
                handCards=hand_cards,
                seatStatus=SEAT_PLAYING,
                isAi=player_id in ai_player_ids,
                isFinished=False,
            )
        runtime_state = UnoRuntimeState(
            phase="playing",
            playerIds=player_ids,
            players=players,
            drawPile=dealing_state.drawPile,
            discardPile=[],
            topDiscard=None,
            currentPlayerId=first_playing_player_id(player_ids, players),
            playDirection=1,
            pendingDraw=None,
            currentColor=None,
            rankings=[],
            deckSetCount=deck_set_count,
        )
        top_discard = pop_starting_discard_card(runtime_state.drawPile)
        if top_discard is not None:
            runtime_state.topDiscard = top_discard
            runtime_state.currentColor = top_discard.color
            runtime_state.discardPile.append(top_discard)
            runtime_state.discardPileRecentCards = [
                UnoDiscardRecentCard(
                    cardInstanceId=top_discard.cardInstanceId,
                    cardCode=top_discard.cardCode,
                    playerId=None,
                    sequence=0,
                )
            ]
        stamp_turn_clock(runtime_state)
        sync_game_over_phase(runtime_state, room_config)
        dumped = dump_state(runtime_state)
        dumped["roomConfig"] = room_config
        return dumped


def first_playing_player_id(
    player_ids: List[str],
    players: Dict[str, UnoPlayerState],
) -> str:
    """
    取座位顺序中首位 PLAYING 玩家作为开局当前玩家。

    :param player_ids: 玩家顺序。
    :param players: 玩家状态映射。
    :return: 当前玩家 ID。
    """
    for player_id in player_ids:
        player_state = players.get(player_id)
        if player_state is not None and player_state.seatStatus == SEAT_PLAYING:
            return player_id
    return player_ids[0]
