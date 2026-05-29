"""UNO +2/+4 叠加规则单元测试。"""

from app.modules.games.uno.schemas import (
    UnoCard,
    UnoPendingDraw,
    UnoPlayerState,
    UnoRuleContext,
    UnoRuntimeState,
)
from app.modules.games.uno.uno_card_rule_registry import (
    _can_play_wild_draw4_under_pending,
    _can_stack_draw_two,
    get_card_rule_by_card_type,
)


def _build_context(*, allow_draw_stacking, pending_source, player_id="p1"):
    """
    构建带 pendingDraw 的规则上下文。

    :param allow_draw_stacking: 是否允许叠加。
    :param pending_source: 待抽来源牌型。
    :param player_id: 行动玩家 ID。
    :return: 规则上下文。
    """
    runtime_state = UnoRuntimeState(
        phase="playing",
        playerIds=["p1", "p2"],
        players={
            "p1": UnoPlayerState(playerId="p1", handCards=[], seatStatus="PLAYING"),
            "p2": UnoPlayerState(playerId="p2", handCards=[], seatStatus="PLAYING"),
        },
        drawPile=[],
        discardPile=[],
        currentPlayerId=player_id,
        playDirection=1,
        pendingDraw=UnoPendingDraw(
            amount=2,
            stackable=allow_draw_stacking,
            sourceCardType=pending_source,
        ),
        deckSetCount=1,
    )
    return UnoRuleContext(
        runtimeState=runtime_state,
        roomConfig={"allowDrawStacking": allow_draw_stacking},
        actingPlayerId=player_id,
    )


def test_draw_two_blocked_when_stacking_disabled() -> None:
    """allowDrawStacking=false 时 pendingDraw 下不能出 +2。"""
    context = _build_context(allow_draw_stacking=False, pending_source="DRAW_TWO")
    draw_two_rule = get_card_rule_by_card_type("DRAW_TWO")
    card = UnoCard(
        cardInstanceId="c1",
        cardCode="red_draw_two",
        color="RED",
        cardType="DRAW_TWO",
    )
    assert draw_two_rule is not None
    assert draw_two_rule.can_play(context, card) is False


def test_draw_two_stackable_when_enabled() -> None:
    """allowDrawStacking=true 且 pending +2 时可接 +2。"""
    context = _build_context(allow_draw_stacking=True, pending_source="DRAW_TWO")
    assert _can_stack_draw_two(context) is True
    draw_two_rule = get_card_rule_by_card_type("DRAW_TWO")
    card = UnoCard(
        cardInstanceId="c1",
        cardCode="red_draw_two",
        color="RED",
        cardType="DRAW_TWO",
    )
    assert draw_two_rule.can_play(context, card) is True


def test_wild_draw4_on_draw_two_when_stacking_enabled() -> None:
    """allowDrawStacking=true 时 +2 可接 +4。"""
    context = _build_context(allow_draw_stacking=True, pending_source="DRAW_TWO")
    wild_draw4_rule = get_card_rule_by_card_type("WILD_DRAW4")
    card = UnoCard(
        cardInstanceId="c2",
        cardCode="wild_draw4",
        color=None,
        cardType="WILD_DRAW4",
    )
    assert wild_draw4_rule is not None
    assert wild_draw4_rule.can_play(context, card) is True


def test_wild_draw4_only_chains_wild_draw4_when_pending_is_wild_draw4() -> None:
    """allowDrawStacking=true 时 +4 只能接 +4。"""
    context = _build_context(allow_draw_stacking=True, pending_source="WILD_DRAW4")
    assert _can_stack_draw_two(context) is False
    assert _can_play_wild_draw4_under_pending(context) is True
    draw_two_rule = get_card_rule_by_card_type("DRAW_TWO")
    draw_two_card = UnoCard(
        cardInstanceId="c3",
        cardCode="red_draw_two",
        color="RED",
        cardType="DRAW_TWO",
    )
    assert draw_two_rule.can_play(context, draw_two_card) is False


def test_wild_blocked_under_pending_wild_draw4() -> None:
    """pendingDraw=WILD_DRAW4 时普通 WILD 不可出。"""
    context = _build_context(allow_draw_stacking=True, pending_source="WILD_DRAW4")
    wild_rule = get_card_rule_by_card_type("WILD")
    wild_card = UnoCard(
        cardInstanceId="wild1",
        cardCode="wild",
        color=None,
        cardType="WILD",
    )
    assert wild_rule is not None
    assert wild_rule.can_play(context, wild_card) is False


def test_wild_blocked_under_pending_draw_two() -> None:
    """pendingDraw=DRAW_TWO 时普通 WILD 不可出。"""
    context = _build_context(allow_draw_stacking=True, pending_source="DRAW_TWO")
    wild_rule = get_card_rule_by_card_type("WILD")
    wild_card = UnoCard(
        cardInstanceId="wild1",
        cardCode="wild",
        color=None,
        cardType="WILD",
    )
    assert wild_rule is not None
    assert wild_rule.can_play(context, wild_card) is False


def test_pending_draw_stacking_disabled_blocks_all_play_cards() -> None:
    """allowDrawStacking=false 时 pendingDraw 下不可出任何牌。"""
    context = _build_context(allow_draw_stacking=False, pending_source="DRAW_TWO")
    for card_type in ("DRAW_TWO", "WILD_DRAW4", "WILD", "NUMBER"):
        rule = get_card_rule_by_card_type(card_type)
        if card_type == "NUMBER":
            card = UnoCard(
                cardInstanceId="n1",
                cardCode="red_5",
                color="RED",
                cardType="NUMBER",
                numberValue=5,
            )
        elif card_type == "WILD":
            card = UnoCard(
                cardInstanceId="w1",
                cardCode="wild",
                color=None,
                cardType="WILD",
            )
        elif card_type == "WILD_DRAW4":
            card = UnoCard(
                cardInstanceId="w4",
                cardCode="wild_draw4",
                color=None,
                cardType="WILD_DRAW4",
            )
        else:
            card = UnoCard(
                cardInstanceId="d1",
                cardCode="red_draw_two",
                color="RED",
                cardType="DRAW_TWO",
            )
        assert rule is not None
        assert rule.can_play(context, card) is False
