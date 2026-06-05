"""五子棋规则引擎与托管评分单元测试。"""

from typing import Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from app.common.exceptions import ValidationException
from app.modules.game_impls.gomoku.gomoku_action_scorer import GomokuActionScorer
from app.modules.game_impls.gomoku.gomoku_rule_engine import GomokuRuleEngine
from app.modules.room.action_scorer import ManagedActionScorerRegistry
from app.modules.room.managed_action_selector import ManagedActionSelector
from app.modules.strategy_turn.schemas import GameAction, GameView, LegalAction, StrategyTurnRuntimeRule


def _runtime_rule(player_ids: List[str], config: Optional[Dict[str, object]] = None):
    """
    构造运行时规则。

    :param player_ids: 玩家 ID 列表。
    :param config: 房间配置。
    :return: 运行时规则对象。
    """
    return StrategyTurnRuntimeRule(
        gameCode="gomoku",
        mode="classic",
        playerIds=player_ids,
        config=config or {},
    )


def _engine_state(
    engine: GomokuRuleEngine,
    player_ids: Optional[List[str]] = None,
    config: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """
    生成初始对局状态。

    :param engine: 规则引擎。
    :param player_ids: 玩家列表。
    :param config: 配置。
    :return: 状态字典。
    """
    ids = player_ids or ["black", "white"]
    merged_config = {
        "boardSize": 15,
        "winLength": 5,
        "turnTimeoutSeconds": 30,
        "enableUndo": True,
    }
    if config:
        merged_config.update(config)
    return engine.build_initial_state(
        _runtime_rule(ids, merged_config),
    )


def _apply(
    engine: GomokuRuleEngine,
    state: Dict[str, object],
    player_id: str,
    action_id: str,
) -> Dict[str, object]:
    """
    应用操作并推进。

    :param engine: 规则引擎。
    :param state: 当前状态。
    :param player_id: 玩家 ID。
    :param action_id: 操作 ID。
    :return: 新状态。
    """
    action = GameAction(actionId=action_id, playerId=player_id)
    after = engine.apply_action(state, action)
    return engine.advance(after)


def _fill_line(
    board: List[List[Optional[str]]],
    stone: str,
    row: int,
    start_col: int,
    length: int,
    *,
    delta_row: int = 0,
    delta_col: int = 1,
) -> None:
    """
    在棋盘上填充连续棋子。

    :param board: 棋盘。
    :param stone: 棋子颜色。
    :param row: 起始行。
    :param start_col: 起始列。
    :param length: 长度。
    :param delta_row: 行步进。
    :param delta_col: 列步进。
    :return: 无。
    """
    current_row = row
    current_col = start_col
    for _ in range(length):
        board[current_row][current_col] = stone
        current_row += delta_row
        current_col += delta_col


def test_horizontal_five_in_row_win():
    """横向五连应判胜。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    _fill_line(state["board"], "BLACK", 7, 0, 4)
    state["currentPlayerId"] = "black"
    state["currentStone"] = "BLACK"
    state = _apply(engine, state, "black", "PLACE_STONE:7:4")
    assert state["winnerPlayerId"] == "black"
    assert state["finishReason"] == "FIVE_IN_ROW"


def test_vertical_five_in_row_win():
    """纵向五连应判胜。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    _fill_line(state["board"], "BLACK", 0, 7, 4, delta_row=1, delta_col=0)
    state["currentPlayerId"] = "black"
    state["currentStone"] = "BLACK"
    state = _apply(engine, state, "black", "PLACE_STONE:4:7")
    assert state["winnerPlayerId"] == "black"


def test_diagonal_five_in_row_win():
    """斜向五连应判胜。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    _fill_line(state["board"], "BLACK", 0, 0, 4, delta_row=1, delta_col=1)
    state["currentPlayerId"] = "black"
    state["currentStone"] = "BLACK"
    state = _apply(engine, state, "black", "PLACE_STONE:4:4")
    assert state["winnerPlayerId"] == "black"


def test_non_current_player_cannot_place():
    """非当前玩家不能落子。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    with pytest.raises(ValidationException):
        _apply(engine, state, "white", "PLACE_STONE:7:7")


def test_cannot_place_on_occupied_cell():
    """已有棋子的格子不能落子。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    with pytest.raises(ValidationException):
        _apply(engine, state, "white", "PLACE_STONE:7:7")


def test_undo_request_only_after_own_place_before_opponent():
    """悔棋请求只在自己刚下完且对手未下时出现。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    assert any(
        item.actionType == "REQUEST_UNDO"
        for item in engine.list_legal_actions(state, "black")
    )
    assert not any(
        item.actionType == "REQUEST_UNDO"
        for item in engine.list_legal_actions(state, "white")
    )


def test_undo_success_appends_undo_stone_and_restores_turn():
    """悔棋成功后 moves 只增不减，追加 UNDO_STONE，回合回到请求者。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    moves_before = len(state["moves"])
    state = _apply(engine, state, "black", "REQUEST_UNDO")
    state = _apply(engine, state, "white", "ACCEPT_UNDO")
    assert len(state["moves"]) >= moves_before + 3
    assert any(item.get("moveType") == "UNDO_STONE" for item in state["moves"])
    assert state["board"][7][7] is None
    assert state["currentPlayerId"] == "black"
    assert state["currentStone"] == "BLACK"


def test_undo_success_updates_last_effective_place_fields():
    """悔棋后 lastPlace 与 lastMove 应指向最后有效落子。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    state = _apply(engine, state, "white", "PLACE_STONE:7:8")
    state = _apply(engine, state, "white", "REQUEST_UNDO")
    state = _apply(engine, state, "black", "ACCEPT_UNDO")
    assert state["lastPlaceRow"] == 7
    assert state["lastPlaceCol"] == 7
    assert state["board"][7][8] is None
    view = engine.build_view(state, "black")
    last_move = view.publicState["gameState"]["lastMove"]
    assert isinstance(last_move, dict)
    assert last_move.get("row") == 7
    assert last_move.get("col") == 7


def test_advance_clears_last_action_events():
    """advance 应清空 lastActionEvents，避免重复提取事件。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    after_action = engine.apply_action(
        state,
        GameAction(actionId="PLACE_STONE:7:7", playerId="black"),
    )
    assert len(after_action.get("lastActionEvents") or []) == 1
    after_advance = engine.advance(after_action)
    assert after_advance.get("lastActionEvents") == []


def test_cannot_undo_after_opponent_placed():
    """对手落子后，上一手不能再悔。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    state = _apply(engine, state, "white", "PLACE_STONE:7:8")
    assert not any(
        item.actionType == "REQUEST_UNDO"
        for item in engine.list_legal_actions(state, "black")
    )


def test_gomoku_scorer_exception_falls_back_in_selector():
    """GomokuActionScorer 异常不影响 ManagedActionSelector fallback。"""
    legal_actions = [
        LegalAction(
            actionType="PLACE_STONE",
            actionId="PLACE_STONE:7:7",
            playerId="p1",
            payload={"row": 7, "col": 7},
            selection={"type": "BOARD_CELL", "config": {"row": 7, "col": 7}},
        )
    ]
    view = GameView(
        gameCode="gomoku",
        viewerPlayerId="p1",
        phase="playing",
        currentPlayerId="p1",
        legalActions=legal_actions,
        publicState={
            "players": [
                {"playerId": "p1", "stone": "BLACK"},
                {"playerId": "p2", "stone": "WHITE"},
            ],
            "gameState": {
                "boardSize": 15,
                "winLength": 5,
                "board": [[None for _ in range(15)] for _ in range(15)],
            },
        },
    )
    broken = MagicMock()
    broken.score_actions.side_effect = RuntimeError("boom")
    registry = ManagedActionScorerRegistry()
    registry.register("gomoku", broken)
    selector = ManagedActionSelector(registry)
    action_id = selector.select_action_id(view=view, legal_actions=legal_actions)
    assert action_id == "PLACE_STONE:7:7"


def test_gomoku_scorer_prefers_winning_move():
    """托管评分应优先选择能成五的落子。"""
    board = [[None for _ in range(15)] for _ in range(15)]
    _fill_line(board, "BLACK", 7, 0, 4)
    scorer = GomokuActionScorer()
    legal_actions = [
        LegalAction(
            actionType="PLACE_STONE",
            actionId="PLACE_STONE:7:4",
            playerId="black",
            payload={"row": 7, "col": 4},
            selection={"type": "BOARD_CELL", "config": {"row": 7, "col": 4}},
        ),
        LegalAction(
            actionType="PLACE_STONE",
            actionId="PLACE_STONE:0:0",
            playerId="black",
            payload={"row": 0, "col": 0},
            selection={"type": "BOARD_CELL", "config": {"row": 0, "col": 0}},
        ),
    ]
    view = GameView(
        gameCode="gomoku",
        viewerPlayerId="black",
        phase="playing",
        currentPlayerId="black",
        legalActions=legal_actions,
        publicState={
            "players": [
                {"playerId": "black", "stone": "BLACK"},
                {"playerId": "white", "stone": "WHITE"},
            ],
            "gameState": {
                "boardSize": 15,
                "winLength": 5,
                "board": board,
            },
        },
    )
    scores = scorer.score_actions(
        game_code="gomoku",
        game_view=view,
        legal_actions=legal_actions,
        player_id="black",
    )
    score_map = {item.actionId: item.score for item in scores}
    assert score_map["PLACE_STONE:7:4"] > score_map["PLACE_STONE:0:0"]


def test_expired_undo_request_removes_accept_and_reject_from_legal_actions():
    """悔棋请求过期后，ACCEPT_UNDO / REJECT_UNDO 不再出现在 legalActions。"""
    engine = GomokuRuleEngine()
    state = _state_with_expired_undo_request(engine)
    legal = engine.list_legal_actions(state, "white")
    action_types = {item.actionType for item in legal}
    assert "ACCEPT_UNDO" not in action_types
    assert "REJECT_UNDO" not in action_types
    assert state.get("undoRequest") is not None


def _state_with_expired_undo_request(engine: GomokuRuleEngine) -> Dict[str, object]:
    """
    构造含已过期悔棋申请的对局状态。

    :param engine: 规则引擎。
    :return: 对局状态。
    """
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    state = _apply(engine, state, "black", "REQUEST_UNDO")
    state["undoRequest"]["expiresAt"] = 1
    return state


def test_list_legal_actions_does_not_clear_expired_undo_request():
    """list_legal_actions 不清理过期 undoRequest，也不追加流水。"""
    engine = GomokuRuleEngine()
    state = _state_with_expired_undo_request(engine)
    moves_len_before = len(state["moves"])
    undo_before = state.get("undoRequest")
    legal = engine.list_legal_actions(state, "white")
    action_types = {item.actionType for item in legal}
    assert len(state["moves"]) == moves_len_before
    assert state.get("undoRequest") == undo_before
    assert "ACCEPT_UNDO" not in action_types
    assert "REJECT_UNDO" not in action_types


def test_build_view_does_not_clear_expired_undo_request():
    """build_view 不修改 state，对外不展示过期悔棋申请。"""
    engine = GomokuRuleEngine()
    state = _state_with_expired_undo_request(engine)
    moves_len_before = len(state["moves"])
    undo_before = state.get("undoRequest")
    view = engine.build_view(state, "white")
    assert len(state["moves"]) == moves_len_before
    assert state.get("undoRequest") == undo_before
    assert view.publicState["gameState"]["undoRequest"] is None


def test_apply_action_clears_expired_undo_request():
    """apply_action 会清理过期 undoRequest 并追加 UNDO_REJECT。"""
    engine = GomokuRuleEngine()
    state = _state_with_expired_undo_request(engine)
    moves_len_before = len(state["moves"])
    state = _apply(engine, state, "white", "PLACE_STONE:7:8")
    assert state.get("undoRequest") is None
    assert len(state["moves"]) == moves_len_before + 2
    last_move = state["moves"][-2]
    assert last_move.get("moveType") == "UNDO_REJECT"
    assert last_move.get("reason") == "EXPIRED"


def test_cannot_request_undo_again_after_reject():
    """悔棋被拒绝后，同一手不能再申请悔棋。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    state = _apply(engine, state, "black", "REQUEST_UNDO")
    state = _apply(engine, state, "white", "REJECT_UNDO")
    assert not any(
        item.actionType == "REQUEST_UNDO"
        for item in engine.list_legal_actions(state, "black")
    )


def test_request_undo_appends_undo_request_move():
    """REQUEST_UNDO 成功时追加 UNDO_REQUEST 流水。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine)
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    place_move = state["moves"][-1]
    state = _apply(engine, state, "black", "REQUEST_UNDO")
    last_move = state["moves"][-1]
    assert last_move.get("moveType") == "UNDO_REQUEST"
    assert last_move.get("targetMoveId") == place_move["moveId"]


def test_build_initial_state_rejects_turn_timeout_too_small():
    """turnTimeoutSeconds < 10 报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="回合时间不能小于"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"turnTimeoutSeconds": 9}),
        )


def test_build_initial_state_rejects_turn_timeout_too_large():
    """turnTimeoutSeconds > 120 报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="回合时间不能大于"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"turnTimeoutSeconds": 121}),
        )


def test_build_initial_state_rejects_undo_expire_too_small():
    """undoRequestExpireSeconds < 10 报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="悔棋请求有效时间不能小于"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"undoRequestExpireSeconds": 9}),
        )


def test_build_initial_state_rejects_undo_expire_too_large():
    """undoRequestExpireSeconds > 120 报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="悔棋请求有效时间不能大于"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"undoRequestExpireSeconds": 121}),
        )


def test_build_initial_state_rejects_non_numeric_board_size():
    """boardSize 非数字时抛 ValidationException。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="boardSize"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"boardSize": "bad"}),
        )


def test_build_initial_state_rejects_non_numeric_win_length():
    """winLength 非数字时抛 ValidationException。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="winLength"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"winLength": "bad"}),
        )


def test_apply_accept_undo_fails_after_undo_request_expired():
    """悔棋请求过期后，再 apply ACCEPT_UNDO 会失败且 state 不被修改。"""
    engine = GomokuRuleEngine()
    state = _state_with_expired_undo_request(engine)
    snapshot = _state_snapshot(state)
    with pytest.raises(ValidationException, match="悔棋请求已失效"):
        engine.apply_action(
            state,
            GameAction(actionId="ACCEPT_UNDO", playerId="white"),
        )
    assert _state_snapshot(state) == snapshot


def test_apply_reject_undo_fails_after_undo_request_expired():
    """悔棋请求过期后，再 apply REJECT_UNDO 会失败且 state 不被修改。"""
    engine = GomokuRuleEngine()
    state = _state_with_expired_undo_request(engine)
    snapshot = _state_snapshot(state)
    with pytest.raises(ValidationException, match="悔棋请求已失效"):
        engine.apply_action(
            state,
            GameAction(actionId="REJECT_UNDO", playerId="white"),
        )
    assert _state_snapshot(state) == snapshot


def _state_snapshot(state: Dict[str, object]) -> Dict[str, object]:
    """
    提取对局状态快照，用于断言 apply_action 未修改原 state。

    :param state: 对局状态。
    :return: 可比较的快照字典。
    """
    return {
        "moves_len": len(state.get("moves") or []),
        "undoRequest": state.get("undoRequest"),
        "moveCounter": state.get("moveCounter"),
    }


def test_enable_undo_string_false_disables_request_undo():
    """enableUndo=\"false\" 时，不出现 REQUEST_UNDO。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine, config={"enableUndo": "false"})
    assert state.get("enableUndo") is False
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    assert not any(
        item.actionType == "REQUEST_UNDO"
        for item in engine.list_legal_actions(state, "black")
    )


def test_enable_undo_string_true_allows_request_undo():
    """enableUndo=\"true\" 时，允许 REQUEST_UNDO。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine, config={"enableUndo": "true"})
    assert state.get("enableUndo") is True
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    assert any(
        item.actionType == "REQUEST_UNDO"
        for item in engine.list_legal_actions(state, "black")
    )


def test_build_initial_state_rejects_invalid_enable_undo():
    """enableUndo 非法字符串时抛 ValidationException。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="enableUndo"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"enableUndo": "abc"}),
        )


def test_build_initial_state_rejects_one_player():
    """build_initial_state 传 1 人时报错。"""
    engine = GomokuRuleEngine()
    runtime_rule = StrategyTurnRuntimeRule.model_construct(
        gameCode="gomoku",
        mode="classic",
        playerIds=["only"],
        config={},
    )
    with pytest.raises(ValidationException, match="2 名玩家"):
        engine.build_initial_state(runtime_rule)


def test_build_initial_state_rejects_three_players():
    """build_initial_state 传 3 人时报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="2 名玩家"):
        engine.build_initial_state(_runtime_rule(["a", "b", "c"]))


def test_build_initial_state_rejects_board_size_too_small():
    """boardSize < 5 报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="棋盘尺寸不能小于"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"boardSize": 4}),
        )


def test_build_initial_state_rejects_board_size_too_large():
    """boardSize > 30 报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="棋盘尺寸不能大于"):
        engine.build_initial_state(
            _runtime_rule(["black", "white"], {"boardSize": 31}),
        )


def test_build_initial_state_rejects_win_length_over_board_size():
    """winLength > boardSize 报错。"""
    engine = GomokuRuleEngine()
    with pytest.raises(ValidationException, match="连子长度不能大于棋盘"):
        engine.build_initial_state(
            _runtime_rule(
                ["black", "white"],
                {"boardSize": 10, "winLength": 11},
            ),
        )


def test_request_undo_not_in_legal_actions_when_enable_undo_false():
    """enableUndo=false 时，不出现 REQUEST_UNDO。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine, config={"enableUndo": False})
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    assert not any(
        item.actionType == "REQUEST_UNDO"
        for item in engine.list_legal_actions(state, "black")
    )
    assert state.get("enableUndo") is False


def test_undo_request_expire_seconds_from_state():
    """undoRequestExpireSeconds 来自对局 state。"""
    engine = GomokuRuleEngine()
    state = _engine_state(engine, config={"undoRequestExpireSeconds": 12})
    state = _apply(engine, state, "black", "PLACE_STONE:7:7")
    state = _apply(engine, state, "black", "REQUEST_UNDO")
    undo_request = state.get("undoRequest")
    assert isinstance(undo_request, dict)
    requested_at = int(undo_request["requestedAt"])
    expires_at = int(undo_request["expiresAt"])
    assert expires_at - requested_at == 12 * 1000
