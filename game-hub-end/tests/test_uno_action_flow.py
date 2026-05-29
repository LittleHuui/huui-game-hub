"""UNO 操作结算、回合推进与视图一致性单元测试。"""

from typing import Dict, List, Optional

import pytest

from app.common.exceptions import ValidationException
from app.modules.games.uno.schemas import UnoCard, UnoPendingDraw, UnoPlayerState, UnoRuntimeState
from app.modules.games.uno.uno_rule_engine import UnoRuleEngine
from app.modules.strategy_turn.schemas import GameAction

_DEFAULT_ROOM_CONFIG = {
    "initialHandCount": 7,
    "allowDrawAndPlay": True,
    "allowDrawStacking": True,
    "finishMode": "UNTIL_REAL_PLAYER_COUNT",
    "remainingRealPlayerCountToEnd": 1,
}


def _card(
    instance_id: str,
    code: str,
    color: Optional[str],
    card_type: str,
    number_value: Optional[int] = None,
) -> UnoCard:
    """
    构造测试用牌实例。

    :param instance_id: 牌实例 ID。
    :param code: 牌编码。
    :param color: 花色。
    :param card_type: 牌型。
    :param number_value: 数字牌点数。
    :return: 牌对象。
    """
    return UnoCard(
        cardInstanceId=instance_id,
        cardCode=code,
        color=color,
        cardType=card_type,
        numberValue=number_value,
    )


def _build_state(
    player_ids: List[str],
    current_player_id: str,
    hands: Dict[str, List[UnoCard]],
    top_card: UnoCard,
    *,
    draw_pile: Optional[List[UnoCard]] = None,
    pending_draw: Optional[UnoPendingDraw] = None,
    play_direction: int = 1,
    drew_this_turn: bool = False,
    last_drawn_card_instance_id: Optional[str] = None,
    effect_advance_handled: bool = False,
    room_config: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """
    构造可提交操作的 UNO 状态字典。

    :param player_ids: 玩家顺序。
    :param current_player_id: 当前玩家。
    :param hands: 各玩家手牌。
    :param top_card: 顶牌。
    :param draw_pile: 抽牌堆。
    :param pending_draw: 待抽惩罚。
    :param play_direction: 出牌方向。
    :param drew_this_turn: 本回合是否已抽牌。
    :param last_drawn_card_instance_id: 最近抽到的牌。
    :param effect_advance_handled: 牌面效果是否已推进。
    :param room_config: 房间配置覆盖项。
    :return: 状态字典。
    """
    players = {}
    for player_id in player_ids:
        players[player_id] = UnoPlayerState(
            playerId=player_id,
            handCards=list(hands.get(player_id, [])),
            seatStatus="PLAYING",
        )
    runtime_state = UnoRuntimeState(
        phase="playing",
        playerIds=player_ids,
        players=players,
        drawPile=list(draw_pile or []),
        discardPile=[top_card],
        topDiscard=top_card,
        currentPlayerId=current_player_id,
        playDirection=play_direction,
        pendingDraw=pending_draw,
        currentColor=top_card.color,
        deckSetCount=1,
        drewThisTurn=drew_this_turn,
        lastDrawnCardInstanceId=last_drawn_card_instance_id,
        effectAdvanceHandled=effect_advance_handled,
    )
    engine = UnoRuleEngine()
    dumped = engine._dump_state(runtime_state)
    merged_config = dict(_DEFAULT_ROOM_CONFIG)
    if room_config is not None:
        merged_config.update(room_config)
    dumped["roomConfig"] = merged_config
    return dumped


def _apply_and_advance(
    engine: UnoRuleEngine,
    state: Dict[str, object],
    player_id: str,
    action_id: str,
) -> Dict[str, object]:
    """
    应用玩家操作并推进回合。

    :param engine: 规则引擎。
    :param state: 当前状态。
    :param player_id: 玩家 ID。
    :param action_id: 操作 ID。
    :return: 推进后的状态。
    """
    action = GameAction(playerId=player_id, actionId=action_id)
    after_action = engine.apply_action(state, action)
    return engine.advance(after_action)


def _first_action_id(
    engine: UnoRuleEngine,
    state: Dict[str, object],
    player_id: str,
    action_type: Optional[str] = None,
) -> str:
    """
    读取指定类型的首个合法操作 ID。

    :param engine: 规则引擎。
    :param state: 当前状态。
    :param player_id: 玩家 ID。
    :param action_type: 操作类型过滤，可空。
    :return: actionId。
    """
    actions = engine.list_legal_actions(state, player_id)
    for item in actions:
        if action_type is None or item.actionType == action_type:
            return item.actionId
    raise AssertionError("未找到合法操作: {0}".format(action_type or "ANY"))


def _holder_card(instance_id: str) -> UnoCard:
    """
    构造留在手牌中、通常不可出的占位牌。

    :param instance_id: 牌实例 ID。
    :return: 牌对象。
    """
    return _card(instance_id, "blue_2", "BLUE", "NUMBER", 2)


def _parsed_current_player(state: Dict[str, object]) -> str:
    """
    解析当前玩家 ID。

    :param state: 状态字典。
    :return: 当前玩家 ID。
    """
    runtime_state = UnoRuleEngine()._parse_state(state)
    return runtime_state.currentPlayerId


def _wild_play_action_id(engine: UnoRuleEngine, player_id: str, card_instance_id: str, color: str = "BLUE") -> str:
    """
    构造普通 WILD 的 PLAY_CARD actionId（不依赖当前合法列表）。

    :param engine: 规则引擎。
    :param player_id: 玩家 ID。
    :param card_instance_id: 牌实例 ID。
    :param color: 选择花色。
    :return: actionId。
    """
    return engine._build_action_id(
        "PLAY_CARD",
        player_id,
        "{0}|{1}".format(card_instance_id, color),
    )


def _play_card_ids(legal_actions: List[object]) -> List[str]:
    """
    提取合法 PLAY_CARD 操作关联的牌实例 ID。

    :param legal_actions: 合法操作列表。
    :return: 牌实例 ID 列表。
    """
    result = []
    for item in legal_actions:
        if item.actionType != "PLAY_CARD":
            continue
        card_id = item.payload.get("cardInstanceId")
        if card_id:
            result.append(str(card_id))
    return result


def _view_legal_actions(
    engine: UnoRuleEngine,
    state: Dict[str, object],
    viewer_player_id: str,
) -> List[object]:
    """
    构建视图并返回合法操作列表。

    :param engine: 规则引擎。
    :param state: 状态字典。
    :param viewer_player_id: 视角玩家。
    :return: 合法操作列表。
    """
    view = engine.build_view(state, viewer_player_id)
    return list(view.legalActions)


def test_normal_play_advances_to_next_player() -> None:
    """普通牌出牌后应切到下一位玩家。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    play_card = _card("c1", "red_7", "RED", "NUMBER", 7)
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [play_card, _holder_card("hold1")], "p2": [_holder_card("hold2")]},
        top,
    )
    engine = UnoRuleEngine()
    action_id = _first_action_id(engine, state, "p1", "PLAY_CARD")
    next_state = _apply_and_advance(engine, state, "p1", action_id)
    assert _parsed_current_player(next_state) == "p2"


def test_wild_play_advances_to_next_player() -> None:
    """万用牌出牌后应切到下一位玩家。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    wild = _card("wild", "wild", None, "WILD")
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [wild, _holder_card("hold1")], "p2": [_holder_card("hold2")]},
        top,
    )
    engine = UnoRuleEngine()
    actions = engine.list_legal_actions(state, "p1")
    wild_action = next(item for item in actions if item.payload.get("chooseColor") == "BLUE")
    next_state = _apply_and_advance(engine, state, "p1", wild_action.actionId)
    assert _parsed_current_player(next_state) == "p2"


def test_draw_two_sets_pending_draw_for_next_player() -> None:
    """+2 出牌后下家仅可承担 pendingDraw 或叠加，不可出普通数字牌。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    draw_two = _card("dt", "red_draw_two", "RED", "DRAW_TWO")
    normal = _card("n1", "blue_3", "BLUE", "NUMBER", 3)
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [draw_two, _holder_card("hold1")], "p2": [normal, _holder_card("hold2")]},
        top,
    )
    engine = UnoRuleEngine()
    action_id = _first_action_id(engine, state, "p1", "PLAY_CARD")
    next_state = _apply_and_advance(engine, state, "p1", action_id)
    assert _parsed_current_player(next_state) == "p2"
    runtime = engine._parse_state(next_state)
    assert runtime.pendingDraw is not None
    assert runtime.pendingDraw.amount == 2
    play_actions = [
        item for item in engine.list_legal_actions(next_state, "p2") if item.actionType == "PLAY_CARD"
    ]
    assert all(item.payload.get("cardInstanceId") != "n1" for item in play_actions)


def test_pending_draw_resolved_advances_turn() -> None:
    """下家承担 pendingDraw 摸牌后应切到下一玩家。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    pending = UnoPendingDraw(amount=2, stackable=True, sourceCardType="DRAW_TWO")
    state = _build_state(
        ["p1", "p2", "p3"],
        "p2",
        {"p2": [], "p3": []},
        top,
        pending_draw=pending,
        draw_pile=[
            _card("d1", "blue_1", "BLUE", "NUMBER", 1),
            _card("d2", "green_2", "GREEN", "NUMBER", 2),
        ],
    )
    engine = UnoRuleEngine()
    draw_id = _first_action_id(engine, state, "p2", "DRAW_CARD")
    next_state = _apply_and_advance(engine, state, "p2", draw_id)
    assert _parsed_current_player(next_state) == "p3"
    assert engine._parse_state(next_state).pendingDraw is None


def test_forced_draw_playable_card_then_advances() -> None:
    """无牌可出强制摸牌后，若抽到可出普通牌，出牌后应切到下一位玩家。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    drawn = _card("drawn", "red_8", "RED", "NUMBER", 8)
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [_holder_card("hold1")], "p2": [_holder_card("hold2")]},
        top,
        draw_pile=[drawn],
    )
    engine = UnoRuleEngine()
    draw_id = _first_action_id(engine, state, "p1", "DRAW_CARD")
    after_draw = engine.apply_action(state, GameAction(playerId="p1", actionId=draw_id))
    runtime = engine._parse_state(after_draw)
    assert runtime.drewThisTurn is True
    play_id = _first_action_id(engine, after_draw, "p1", "PLAY_CARD")
    next_state = engine.advance(
        engine.apply_action(after_draw, GameAction(playerId="p1", actionId=play_id))
    )
    assert _parsed_current_player(next_state) == "p2"


def test_forced_draw_unplayable_card_advances() -> None:
    """无牌可出强制摸牌且不可出时，应直接切到下一位玩家。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    drawn = _card("drawn", "blue_8", "BLUE", "NUMBER", 8)
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [_holder_card("hold1")], "p2": [_holder_card("hold2")]},
        top,
        draw_pile=[drawn],
    )
    engine = UnoRuleEngine()
    draw_id = _first_action_id(engine, state, "p1", "DRAW_CARD")
    next_state = _apply_and_advance(engine, state, "p1", draw_id)
    assert _parsed_current_player(next_state) == "p2"


def test_voluntary_draw_ends_turn() -> None:
    """主动摸牌后不能继续出牌，直接结束回合。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    playable = _card("play", "red_7", "RED", "NUMBER", 7)
    drawn = _card("drawn", "blue_1", "BLUE", "NUMBER", 1)
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [playable], "p2": []},
        top,
        draw_pile=[drawn],
    )
    engine = UnoRuleEngine()
    actions = engine.list_legal_actions(state, "p1")
    draw_action = next(
        item
        for item in actions
        if item.actionType == "DRAW_CARD" and item.payload.get("drawSource") == "voluntary"
    )
    after_draw = engine.apply_action(state, GameAction(playerId="p1", actionId=draw_action.actionId))
    assert engine.list_legal_actions(after_draw, "p1") == []
    next_state = engine.advance(after_draw)
    assert _parsed_current_player(next_state) == "p2"


def test_two_player_disable_keeps_current_player() -> None:
    """两人局 A 出禁用后仍轮到 A。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    disable = _card("skip", "red_disable", "RED", "DISABLE")
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [disable, _holder_card("hold1")], "p2": [_holder_card("hold2")]},
        top,
    )
    engine = UnoRuleEngine()
    action_id = _first_action_id(engine, state, "p1", "PLAY_CARD")
    next_state = _apply_and_advance(engine, state, "p1", action_id)
    assert _parsed_current_player(next_state) == "p1"


def test_two_player_reverse_advances_to_opponent() -> None:
    """两人局 A 出转向后应轮到 B。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    reverse = _card("rev", "red_reverse", "RED", "REVERSE")
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [reverse, _holder_card("hold1")], "p2": [_holder_card("hold2")]},
        top,
    )
    engine = UnoRuleEngine()
    action_id = _first_action_id(engine, state, "p1", "PLAY_CARD")
    next_state = _apply_and_advance(engine, state, "p1", action_id)
    assert _parsed_current_player(next_state) == "p2"


def test_three_player_disable_skips_to_third() -> None:
    """三人局 A 出禁用后应轮到 C。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    disable = _card("skip", "red_disable", "RED", "DISABLE")
    state = _build_state(
        ["p1", "p2", "p3"],
        "p1",
        {
            "p1": [disable, _holder_card("hold1")],
            "p2": [_holder_card("hold2")],
            "p3": [_holder_card("hold3")],
        },
        top,
    )
    engine = UnoRuleEngine()
    action_id = _first_action_id(engine, state, "p1", "PLAY_CARD")
    next_state = _apply_and_advance(engine, state, "p1", action_id)
    assert _parsed_current_player(next_state) == "p3"


def test_three_player_reverse_follows_new_direction() -> None:
    """三人局 A 出转向后按反向轮到 C。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    reverse = _card("rev", "red_reverse", "RED", "REVERSE")
    state = _build_state(
        ["p1", "p2", "p3"],
        "p1",
        {
            "p1": [reverse, _holder_card("hold1")],
            "p2": [_holder_card("hold2")],
            "p3": [_holder_card("hold3")],
        },
        top,
    )
    engine = UnoRuleEngine()
    action_id = _first_action_id(engine, state, "p1", "PLAY_CARD")
    next_state = _apply_and_advance(engine, state, "p1", action_id)
    assert _parsed_current_player(next_state) == "p3"


def test_pending_wild_draw4_blocks_wild_play_and_apply() -> None:
    """pendingDraw=WILD_DRAW4 时不可列出或提交普通 WILD。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    wild = _card("wild", "wild", None, "WILD")
    wild_draw4 = _card("w4", "wild_draw4", None, "WILD_DRAW4")
    pending = UnoPendingDraw(amount=4, stackable=True, sourceCardType="WILD_DRAW4")
    state = _build_state(
        ["p1", "p2"],
        "p2",
        {"p2": [wild, wild_draw4]},
        top,
        pending_draw=pending,
    )
    engine = UnoRuleEngine()
    legal_actions = engine.list_legal_actions(state, "p2")
    play_ids = _play_card_ids(legal_actions)
    assert "wild" not in play_ids
    assert "w4" in play_ids
    wild_action_id = _wild_play_action_id(engine, "p2", "wild")
    with pytest.raises(ValidationException):
        engine.apply_action(state, GameAction(playerId="p2", actionId=wild_action_id))


def test_wild_draw4_flow_next_player_only_wild_draw4_or_draw() -> None:
    """A 出 +4 后 B 只能接 +4 或摸牌，提交 WILD 必须失败。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    wild_draw4_a = _card("w4a", "wild_draw4", None, "WILD_DRAW4")
    wild_b = _card("wild_b", "wild", None, "WILD")
    wild_draw4_b = _card("w4b", "wild_draw4", None, "WILD_DRAW4")
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {
            "p1": [wild_draw4_a, _holder_card("hold1")],
            "p2": [wild_b, wild_draw4_b, _holder_card("hold2")],
        },
        top,
    )
    engine = UnoRuleEngine()
    play_w4 = next(
        item
        for item in engine.list_legal_actions(state, "p1")
        if item.actionType == "PLAY_CARD"
        and item.payload.get("cardInstanceId") == "w4a"
    )
    after_a = _apply_and_advance(engine, state, "p1", play_w4.actionId)
    assert _parsed_current_player(after_a) == "p2"
    runtime = engine._parse_state(after_a)
    assert runtime.pendingDraw is not None
    assert runtime.pendingDraw.sourceCardType == "WILD_DRAW4"
    legal_actions = engine.list_legal_actions(after_a, "p2")
    play_actions = [item for item in legal_actions if item.actionType == "PLAY_CARD"]
    assert len(play_actions) == 4
    assert all(item.payload.get("cardInstanceId") == "w4b" for item in play_actions)
    assert all(item.payload.get("chooseColor") in ("RED", "YELLOW", "BLUE", "GREEN") for item in play_actions)
    assert any(item.actionType == "DRAW_CARD" for item in legal_actions)
    wild_action_id = _wild_play_action_id(engine, "p2", "wild_b")
    with pytest.raises(ValidationException):
        engine.apply_action(after_a, GameAction(playerId="p2", actionId=wild_action_id))
    stack_action = play_actions[0]
    after_b = engine.apply_action(
        after_a,
        GameAction(playerId="p2", actionId=stack_action.actionId),
    )
    assert engine._parse_state(after_b).pendingDraw.amount == 8


def test_pending_draw_two_allows_draw_two_and_wild_draw4_not_wild() -> None:
    """pendingDraw=DRAW_TWO 时 +2/+4 可出，普通 WILD 不可出。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    wild = _card("wild", "wild", None, "WILD")
    draw_two = _card("dt", "blue_draw_two", "BLUE", "DRAW_TWO")
    wild_draw4 = _card("w4", "wild_draw4", None, "WILD_DRAW4")
    pending = UnoPendingDraw(amount=2, stackable=True, sourceCardType="DRAW_TWO")
    state = _build_state(
        ["p1", "p2"],
        "p2",
        {"p2": [wild, draw_two, wild_draw4]},
        top,
        pending_draw=pending,
    )
    engine = UnoRuleEngine()
    play_ids = _play_card_ids(engine.list_legal_actions(state, "p2"))
    assert "wild" not in play_ids
    assert "dt" in play_ids
    assert "w4" in play_ids
    with pytest.raises(ValidationException):
        engine.apply_action(
            state,
            GameAction(playerId="p2", actionId=_wild_play_action_id(engine, "p2", "wild")),
        )


def test_pending_draw_stacking_disabled_only_draw_card() -> None:
    """allowDrawStacking=false 时 pendingDraw 下只能摸牌。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    draw_two = _card("dt", "blue_draw_two", "BLUE", "DRAW_TWO")
    wild_draw4 = _card("w4", "wild_draw4", None, "WILD_DRAW4")
    pending = UnoPendingDraw(amount=2, stackable=False, sourceCardType="DRAW_TWO")
    state = _build_state(
        ["p1", "p2"],
        "p2",
        {"p2": [draw_two, wild_draw4]},
        top,
        pending_draw=pending,
        room_config={"allowDrawStacking": False},
    )
    engine = UnoRuleEngine()
    legal_actions = engine.list_legal_actions(state, "p2")
    assert _play_card_ids(legal_actions) == []
    assert len(legal_actions) == 1
    assert legal_actions[0].actionType == "DRAW_CARD"


def test_build_view_legal_actions_only_for_current_player() -> None:
    """非当前玩家视图的 legalActions 必须为空。"""
    top = _card("top", "red_5", "RED", "NUMBER", 5)
    card = _card("c1", "red_7", "RED", "NUMBER", 7)
    state = _build_state(
        ["p1", "p2"],
        "p1",
        {"p1": [card], "p2": [_card("c2", "blue_3", "BLUE", "NUMBER", 3)]},
        top,
    )
    engine = UnoRuleEngine()
    current_actions = _view_legal_actions(engine, state, "p1")
    other_actions = _view_legal_actions(engine, state, "p2")
    assert len(current_actions) > 0
    assert other_actions == []
