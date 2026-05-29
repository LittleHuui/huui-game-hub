"""UNO 回合推进与结束判定单元测试。"""

from app.modules.games.uno.schemas import UnoPlayerState, UnoRankingItem, UnoRuntimeState
from app.modules.games.uno.uno_finish_rule import should_finish_game
from app.modules.games.uno.uno_turn_rule import advance_turn, get_player_index


def _build_state(player_ids, current_player_id, seat_statuses):
    players = {}
    for index, player_id in enumerate(player_ids):
        players[player_id] = UnoPlayerState(
            playerId=player_id,
            handCards=[],
            seatStatus=seat_statuses[index],
            isAi=False,
            isFinished=False,
        )
    return UnoRuntimeState(
        phase="playing",
        playerIds=player_ids,
        players=players,
        drawPile=[],
        discardPile=[],
        currentPlayerId=current_player_id,
        playDirection=1,
        deckSetCount=1,
    )


def test_advance_turn_ignores_non_playing_players() -> None:
    """出完牌变旁观后，下家应按原座位顺序推进而非回到 active[0]。"""
    player_ids = ["p1", "p2", "p3"]
    state = _build_state(player_ids, "p1", ["SPECTATING", "PLAYING", "PLAYING"])
    assert get_player_index(state, "p1") == 0
    next_player_id = advance_turn(state, 1)
    assert next_player_id == "p2"
    assert state.currentPlayerId == "p2"


def test_should_finish_game_first_finish_mode() -> None:
    """FIRST_FINISH：任意真人完赛即结束。"""
    state = _build_state(["p1", "p2"], "p2", ["SPECTATING", "PLAYING"])
    state.rankings = [UnoRankingItem(playerId="p1", rank=1, finishedAt=1)]
    room_config = {"finishMode": "FIRST_FINISH"}
    assert should_finish_game(state, room_config) is True


def test_should_finish_game_until_real_player_count() -> None:
    """UNTIL_REAL_PLAYER_COUNT：剩余真人 PLAYING 数量达到阈值时结束。"""
    state = _build_state(["p1", "p2", "p3"], "p2", ["PLAYING", "PLAYING", "PLAYING"])
    room_config = {
        "finishMode": "UNTIL_REAL_PLAYER_COUNT",
        "remainingRealPlayerCountToEnd": 2,
    }
    assert should_finish_game(state, room_config) is False
    state.players["p3"].seatStatus = "SPECTATING"
    state.rankings = [UnoRankingItem(playerId="p3", rank=1, finishedAt=1)]
    assert should_finish_game(state, room_config) is True
