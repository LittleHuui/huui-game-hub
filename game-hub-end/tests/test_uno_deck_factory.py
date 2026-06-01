"""UNO 牌堆工厂单元测试。"""

from typing import List, Optional

from app.modules.game_seed.uno_seed import UNO_ONLINE_GAME_RULE_SEED
from app.modules.games.uno.schemas import UnoCard
from app.modules.games.uno.uno_deck_factory import (
    build_initial_draw_pile,
    pop_starting_discard_card,
)
from app.modules.games.uno.uno_rule_engine import UnoRuleEngine
from app.modules.strategy_turn.schemas import StrategyTurnRuntimeRule


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


def test_pop_starting_discard_card_skips_action_cards_and_preserves_order() -> None:
    """
    开局顶牌应跳过功能牌，取首张数字牌且不打乱剩余顺序。

    :return: 无。
    """
    draw_pile = [
        _card("1", "wild", None, "WILD"),
        _card("2", "reverse_red", "RED", "REVERSE"),
        _card("3", "red_5", "RED", "NUMBER", 5),
        _card("4", "blue_2", "BLUE", "NUMBER", 2),
    ]
    top_discard = pop_starting_discard_card(draw_pile)
    assert top_discard is not None
    assert top_discard.cardType == "NUMBER"
    assert top_discard.cardInstanceId == "3"
    assert top_discard.color == "RED"
    assert [card.cardInstanceId for card in draw_pile] == ["1", "2", "4"]


def test_pop_starting_discard_card_returns_none_when_no_number_card() -> None:
    """
    抽牌堆无数字牌时应返回 None。

    :return: 无。
    """
    draw_pile = [
        _card("1", "wild", None, "WILD"),
        _card("2", "reverse_red", "RED", "REVERSE"),
    ]
    assert pop_starting_discard_card(draw_pile) is None
    assert len(draw_pile) == 2


def test_build_initial_state_top_discard_is_always_number_card() -> None:
    """
    多次开局时顶牌必须为数字牌，且 currentColor 与顶牌花色一致。

    :return: 无。
    """
    engine = UnoRuleEngine()
    runtime_rule = StrategyTurnRuntimeRule(
        gameCode="uno",
        mode="classic",
        playerIds=["p1", "p2", "p3"],
        config={},
    )
    for _ in range(30):
        state = engine.build_initial_state(runtime_rule)
        top_discard = state.get("topDiscard")
        assert top_discard is not None
        assert top_discard["cardType"] == "NUMBER"
        assert state.get("currentColor") == top_discard["color"]


def test_pop_starting_discard_card_does_not_shuffle_draw_pile() -> None:
    """
    取开局顶牌后，剩余抽牌堆顺序应与移除前一致。

    :return: 无。
    """
    seed = UNO_ONLINE_GAME_RULE_SEED
    draw_pile = build_initial_draw_pile(seed, 2, shuffle=False)
    expected_after_pop: List[str] = []
    first_number_index = None
    for index, card in enumerate(draw_pile):
        if card.cardType == "NUMBER":
            first_number_index = index
            break
    assert first_number_index is not None
    expected_after_pop = [
        card.cardInstanceId
        for card in draw_pile[:first_number_index] + draw_pile[first_number_index + 1 :]
    ]
    top_discard = pop_starting_discard_card(draw_pile)
    assert top_discard is not None
    assert top_discard.cardType == "NUMBER"
    assert [card.cardInstanceId for card in draw_pile] == expected_after_pop
