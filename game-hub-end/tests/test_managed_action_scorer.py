"""托管动作评分与选择器测试。"""

import math
from unittest.mock import MagicMock, patch

import pytest

from app.modules.games.uno.uno_action_scorer import UnoActionScorer
from app.modules.room.action_scorer import ActionScore, ManagedActionScorerRegistry
from app.modules.room.managed_action_selector import ManagedActionSelector
from app.modules.strategy_turn.schemas import GameView, LegalAction
from app.modules.strategy_turn.player_order import (
    get_next_active_player,
    get_next_active_player_after_reverse,
    get_previous_active_player,
)


def _player(player_id: str, hand_count: int, **extra):
    payload = {
        "playerId": player_id,
        "handCount": hand_count,
        "seatStatus": "PLAYING",
        "isAi": False,
        "isFinished": False,
        "finishRank": None,
    }
    payload.update(extra)
    return payload


def _uno_view(
    *,
    hand_cards,
    legal_actions,
    player_ids=None,
    players=None,
    play_direction=1,
    pending_draw=None,
    current_color="RED",
    top_discard=None,
    viewer_player_id="p1",
):
    if player_ids is None:
        player_ids = ["p1", "p2", "p3"]
    if players is None:
        players = [_player("p1", len(hand_cards)), _player("p2", 5), _player("p3", 4)]
    public_state = {
        "playerIds": player_ids,
        "players": players,
        "currentPlayerId": viewer_player_id,
        "playDirection": play_direction,
        "pendingDraw": pending_draw,
        "currentColor": current_color,
    }
    if top_discard is not None:
        public_state["topDiscard"] = top_discard
    return GameView(
        gameCode="uno",
        viewerPlayerId=viewer_player_id,
        phase="playing",
        currentPlayerId=viewer_player_id,
        legalActions=legal_actions,
        publicState=public_state,
        privateState={"handCards": hand_cards},
    )


def _number_card(card_id, color, value, card_code=None):
    return {
        "cardInstanceId": card_id,
        "cardCode": card_code or f"{color}_{value}",
        "color": color,
        "cardType": "NUMBER",
        "numberValue": value,
    }


def _action_card(card_id, card_type, color, card_code=None):
    return {
        "cardInstanceId": card_id,
        "cardCode": card_code or f"{color}_{card_type}",
        "color": color,
        "cardType": card_type,
        "numberValue": None,
    }


def _wild_card(card_id, card_type="WILD"):
    return {
        "cardInstanceId": card_id,
        "cardCode": card_type,
        "color": None,
        "cardType": card_type,
        "numberValue": None,
    }


def _score_map(scorer, view, legal, jitter=0.0):
    with patch("app.modules.games.uno.uno_action_scorer.random.uniform", return_value=jitter):
        scores = scorer.score_actions(
            game_code="uno",
            game_view=view,
            legal_actions=legal,
            player_id="p1",
        )
    return {item.actionId: item.score for item in scores}


def _play_action(action_id, card_instance_id, choose_color=None):
    payload = {"cardInstanceId": card_instance_id}
    if choose_color is not None:
        payload["chooseColor"] = choose_color
    return LegalAction(
        actionType="PLAY_CARD",
        actionId=action_id,
        playerId="p1",
        payload=payload,
    )


def _draw_action(action_id="draw"):
    return LegalAction(
        actionType="DRAW_CARD",
        actionId=action_id,
        playerId="p1",
        payload={"mode": "normal"},
    )


def _pass_action(action_id="pass"):
    return LegalAction(
        actionType="PASS_TURN",
        actionId=action_id,
        playerId="p1",
        payload={},
    )


class TestPlayerOrder(object):
    """座位顺序工具测试。"""

    def test_next_skips_inactive(self):
        players = [
            _player("p1", 3),
            _player("p2", 2, seatStatus="LEFT"),
            _player("p3", 1),
        ]
        nxt = get_next_active_player(players, "p1", 1)
        assert nxt is not None
        assert nxt["playerId"] == "p3"

    def test_reverse_next_uses_opposite_direction(self):
        players = [_player("p1", 3), _player("p2", 5), _player("p3", 4)]
        forward = get_next_active_player(players, "p1", 1)
        reversed_next = get_next_active_player_after_reverse(players, "p1", 1)
        assert forward["playerId"] == "p2"
        assert reversed_next["playerId"] == "p3"

    def test_previous_is_opposite_of_next(self):
        players = [_player("p1", 3), _player("p2", 5), _player("p3", 4)]
        nxt = get_next_active_player(players, "p1", 1)
        prev = get_previous_active_player(players, "p1", 1)
        assert nxt["playerId"] == "p2"
        assert prev["playerId"] == "p3"


class TestManagedActionSelector(object):
    """选择器兜底与评分集成测试。"""

    def test_fallback_without_registry_matches_first_action(self):
        selector = ManagedActionSelector()
        actions = [
            LegalAction(actionType="DRAW_CARD", actionId="", playerId="p1"),
            LegalAction(actionType="DRAW_CARD", actionId="a2", playerId="p1"),
        ]
        view = GameView(gameCode="uno", viewerPlayerId="p1", phase="playing")
        assert selector.select_action_id(view, actions) == "a2"

    def test_scorer_exception_falls_back(self):
        broken = MagicMock()
        broken.score_actions.side_effect = RuntimeError("boom")
        registry = ManagedActionScorerRegistry()
        registry.register("uno", broken)
        selector = ManagedActionSelector(registry)
        actions = [_draw_action("draw-1"), _pass_action("pass-1")]
        view = GameView(gameCode="uno", viewerPlayerId="p1", phase="playing")
        assert selector.select_action_id(view, actions) == "draw-1"

    def test_invalid_scores_filtered(self):
        registry = ManagedActionScorerRegistry()
        registry.register(
            "uno",
            MagicMock(
                score_actions=MagicMock(
                    return_value=[
                        ActionScore(actionId="missing", score=9999.0),
                        ActionScore(actionId="ok", score=float("nan")),
                        ActionScore(actionId="good", score=10.0),
                    ],
                ),
            ),
        )
        selector = ManagedActionSelector(registry)
        actions = [_draw_action("good"), _pass_action("pass-1")]
        view = GameView(gameCode="uno", viewerPlayerId="p1", phase="playing")
        assert selector.select_action_id(view, actions) == "good"


class TestUnoActionScorer(object):
    """UNO 评分规则测试。"""

    def test_immediate_finish_prefers_winning_play(self):
        card_id = "c-last"
        hand = [
            {
                "cardInstanceId": card_id,
                "cardCode": "RED_5",
                "color": "RED",
                "cardType": "NUMBER",
                "numberValue": 5,
            }
        ]
        legal = [
            _play_action("play-win", card_id),
            _draw_action("draw-1"),
        ]
        view = _uno_view(hand_cards=hand, legal_actions=legal)
        scorer = UnoActionScorer()
        scores = scorer.score_actions(
            game_code="uno",
            game_view=view,
            legal_actions=legal,
            player_id="p1",
        )
        by_id = {item.actionId: item.score for item in scores}
        assert by_id["play-win"] > by_id["draw-1"]

    def test_pending_draw_prefers_stack_draw_two(self):
        wild4 = {
            "cardInstanceId": "w4",
            "cardCode": "WILD_DRAW4",
            "color": None,
            "cardType": "WILD_DRAW4",
            "numberValue": None,
        }
        draw_two = {
            "cardInstanceId": "d2",
            "cardCode": "RED_DRAW2",
            "color": "RED",
            "cardType": "DRAW_TWO",
            "numberValue": None,
        }
        hand = [wild4, draw_two]
        legal = [
            _play_action("play-w4", "w4", "RED"),
            _play_action("play-d2", "d2"),
            _draw_action("draw-pending"),
        ]
        view = _uno_view(
            hand_cards=hand,
            legal_actions=legal,
            pending_draw={"amount": 2, "stackable": True, "sourceCardType": "DRAW_TWO"},
        )
        scorer = UnoActionScorer()
        scores = scorer.score_actions(
            game_code="uno",
            game_view=view,
            legal_actions=legal,
            player_id="p1",
        )
        by_id = {item.actionId: item.score for item in scores}
        assert by_id["play-d2"] > by_id["play-w4"] > by_id["draw-pending"]

    def test_threat_next_one_card_prefers_disable(self):
        reverse_card = {
            "cardInstanceId": "rev",
            "cardCode": "GREEN_REVERSE",
            "color": "GREEN",
            "cardType": "REVERSE",
            "numberValue": None,
        }
        disable_card = {
            "cardInstanceId": "skip",
            "cardCode": "GREEN_SKIP",
            "color": "GREEN",
            "cardType": "DISABLE",
            "numberValue": None,
        }
        hand = [reverse_card, disable_card]
        legal = [
            _play_action("play-rev", "rev"),
            _play_action("play-skip", "skip"),
        ]
        players = [_player("p1", 2), _player("p2", 1), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        scorer = UnoActionScorer()
        scores = scorer.score_actions(
            game_code="uno",
            game_view=view,
            legal_actions=legal,
            player_id="p1",
        )
        by_id = {item.actionId: item.score for item in scores}
        assert by_id["play-skip"] > by_id["play-rev"]

    def test_draw_penalty_when_playable_exists(self):
        hand = [
            {
                "cardInstanceId": "n1",
                "cardCode": "RED_1",
                "color": "RED",
                "cardType": "NUMBER",
                "numberValue": 1,
            }
        ]
        legal = [_play_action("play-1", "n1"), _draw_action("draw-voluntary")]
        view = _uno_view(hand_cards=hand, legal_actions=legal)
        scorer = UnoActionScorer()
        scores = scorer.score_actions(
            game_code="uno",
            game_view=view,
            legal_actions=legal,
            player_id="p1",
        )
        by_id = {item.actionId: item.score for item in scores}
        assert by_id["play-1"] > by_id["draw-voluntary"]

    def test_wild_color_prefers_most_common_remaining(self):
        wild = {
            "cardInstanceId": "wild",
            "cardCode": "WILD",
            "color": None,
            "cardType": "WILD",
            "numberValue": None,
        }
        hand = [
            wild,
            {
                "cardInstanceId": "b1",
                "cardCode": "BLUE_1",
                "color": "BLUE",
                "cardType": "NUMBER",
                "numberValue": 1,
            },
            {
                "cardInstanceId": "b2",
                "cardCode": "BLUE_2",
                "color": "BLUE",
                "cardType": "NUMBER",
                "numberValue": 2,
            },
            {
                "cardInstanceId": "r1",
                "cardCode": "RED_1",
                "color": "RED",
                "cardType": "NUMBER",
                "numberValue": 1,
            },
        ]
        legal = [
            _play_action("wild-blue", "wild", "BLUE"),
            _play_action("wild-red", "wild", "RED"),
        ]
        view = _uno_view(hand_cards=hand, legal_actions=legal)
        scorer = UnoActionScorer()
        with patch("app.modules.games.uno.uno_action_scorer.random.uniform", return_value=0.0):
            scores = scorer.score_actions(
                game_code="uno",
                game_view=view,
                legal_actions=legal,
                player_id="p1",
            )
        by_id = {item.actionId: item.score for item in scores}
        assert by_id["wild-blue"] > by_id["wild-red"]

    def test_selector_picks_highest_scored_action(self):
        card_id = "only"
        hand = [
            {
                "cardInstanceId": card_id,
                "cardCode": "RED_9",
                "color": "RED",
                "cardType": "NUMBER",
                "numberValue": 9,
            }
        ]
        legal = [_play_action("play-only", card_id), _draw_action("draw-only")]
        view = _uno_view(hand_cards=hand, legal_actions=legal)
        registry = ManagedActionScorerRegistry()
        registry.register("uno", UnoActionScorer())
        selector = ManagedActionSelector(registry)
        assert selector.select_action_id(view, legal) == "play-only"

    def test_pass_is_lowest_among_post_draw_options(self):
        drawn = {
            "cardInstanceId": "new",
            "cardCode": "GREEN_3",
            "color": "GREEN",
            "cardType": "NUMBER",
            "numberValue": 3,
        }
        legal = [_play_action("play-new", "new"), _pass_action("pass-turn")]
        view = _uno_view(hand_cards=[drawn], legal_actions=legal)
        scorer = UnoActionScorer()
        scores = scorer.score_actions(
            game_code="uno",
            game_view=view,
            legal_actions=legal,
            player_id="p1",
        )
        by_id = {item.actionId: item.score for item in scores}
        assert by_id["play-new"] > by_id["pass-turn"]

    def test_normalize_finite_only(self):
        selector = ManagedActionSelector()
        valid = selector._normalize_valid_scores(
            [
                ActionScore(actionId="a", score=float("inf")),
                ActionScore(actionId="b", score=1.0),
            ],
            {"a", "b"},
        )
        assert len(valid) == 1
        assert valid[0].actionId == "b"
        assert math.isfinite(valid[0].score)

    def test_many_numbers_prefers_number_over_wild_draw4(self):
        wild4 = {
            "cardInstanceId": "w4",
            "cardCode": "WILD_DRAW4",
            "color": None,
            "cardType": "WILD_DRAW4",
            "numberValue": None,
        }
        numbers = []
        legal = [_play_action("play-w4", "w4", "RED")]
        for index in range(5):
            card_id = f"n{index}"
            numbers.append(
                {
                    "cardInstanceId": card_id,
                    "cardCode": f"RED_{index}",
                    "color": "RED",
                    "cardType": "NUMBER",
                    "numberValue": index,
                }
            )
            legal.append(_play_action(f"play-{card_id}", card_id))
        hand = [wild4] + numbers
        view = _uno_view(hand_cards=hand, legal_actions=legal)
        scorer = UnoActionScorer()
        with patch("app.modules.games.uno.uno_action_scorer.random.uniform", return_value=0.0):
            scores = scorer.score_actions(
                game_code="uno",
                game_view=view,
                legal_actions=legal,
                player_id="p1",
            )
        by_id = {item.actionId: item.score for item in scores}
        number_scores = [by_id[f"play-n{index}"] for index in range(5)]
        assert max(number_scores) > by_id["play-w4"]

    def test_table_red5_prefers_matching_blue5(self):
        """桌面红5时优先出可匹配点数的蓝5。"""
        blue5_a = _number_card("b5a", "BLUE", 5)
        blue5_b = _number_card("b5b", "BLUE", 5)
        blue4 = _number_card("b4", "BLUE", 4)
        wild = _wild_card("wild")
        hand = [blue5_a, blue5_b, blue4, wild]
        legal = [
            _play_action("play-b5a", "b5a"),
            _play_action("play-b5b", "b5b"),
            _play_action("play-b4", "b4"),
            _play_action("play-wild", "wild", "BLUE"),
        ]
        players = [_player("p1", len(hand)), _player("p2", 2), _player("p3", 4)]
        view = _uno_view(
            hand_cards=hand,
            legal_actions=legal,
            players=players,
            top_discard=_number_card("top", "RED", 5, "RED_5"),
        )
        by_id = _score_map(UnoActionScorer(), view, legal)
        assert by_id["play-b5a"] > by_id["play-b4"]
        assert by_id["play-b5a"] > by_id["play-wild"]

    def test_low_hand_prefers_numbers_over_wild_draw4(self):
        """手牌不多时优先数字牌而非 +4。"""
        hand = [
            _number_card("r2", "RED", 2),
            _number_card("r7", "RED", 7),
            _number_card("b7", "BLUE", 7),
            _wild_card("w4", "WILD_DRAW4"),
        ]
        legal = [
            _play_action("play-r2", "r2"),
            _play_action("play-r7", "r7"),
            _play_action("play-b7", "b7"),
            _play_action("play-w4", "w4", "RED"),
        ]
        players = [_player("p1", len(hand)), _player("p2", 2), _player("p3", 5)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        by_id = _score_map(UnoActionScorer(), view, legal)
        number_best = max(by_id["play-r2"], by_id["play-r7"], by_id["play-b7"])
        assert number_best > by_id["play-w4"]

    def test_normal_scene_prefers_red1_over_wild_with_many_next_cards(self):
        """普通场景下家5张时优先红1而非 WILD。"""
        hand = [
            _number_card("r1", "RED", 1),
            _action_card("r2", "DRAW_TWO", "RED", "RED_DRAW2"),
            _wild_card("wild"),
        ]
        legal = [
            _play_action("play-r1", "r1"),
            _play_action("play-r2", "r2"),
            _play_action("play-wild", "wild", "RED"),
        ]
        players = [_player("p1", len(hand)), _player("p2", 5), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        by_id = _score_map(UnoActionScorer(), view, legal)
        assert by_id["play-r1"] > by_id["play-wild"]

    def test_low_self_hand_prefers_red1_over_draw_two_vs_next_two(self):
        """自己3张、下家2张时更倾向红1。"""
        hand = [
            _number_card("r1", "RED", 1),
            _action_card("r2", "DRAW_TWO", "RED", "RED_DRAW2"),
            _wild_card("wild"),
        ]
        legal = [
            _play_action("play-r1", "r1"),
            _play_action("play-r2", "r2"),
            _play_action("play-wild", "wild", "RED"),
        ]
        players = [_player("p1", 3), _player("p2", 2), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        by_id = _score_map(UnoActionScorer(), view, legal)
        assert by_id["play-r1"] >= by_id["play-r2"] - 50.0

    def test_high_self_hand_can_prefer_draw_two_over_red1(self):
        """自己手牌多时 +2 可压过红1。"""
        fillers = [
            _number_card(f"f{i}", "BLUE", i)
            for i in range(5)
        ]
        hand = [
            _number_card("r1", "RED", 1),
            _action_card("r2", "DRAW_TWO", "RED", "RED_DRAW2"),
            _wild_card("wild"),
        ] + fillers
        legal = [
            _play_action("play-r1", "r1"),
            _play_action("play-r2", "r2"),
            _play_action("play-wild", "wild", "RED"),
        ]
        players = [_player("p1", len(hand)), _player("p2", 2), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        by_id = _score_map(UnoActionScorer(), view, legal)
        assert by_id["play-r2"] > by_id["play-r1"]

    def test_threat_hand_one_disable_and_reverse_close_scores(self):
        """下家1张时禁用与反转分数接近，同属强威胁压制档。"""
        disable_card = _action_card("skip", "DISABLE", "GREEN", "GREEN_SKIP")
        reverse_card = _action_card("rev", "REVERSE", "GREEN", "GREEN_REVERSE")
        hand = [disable_card, reverse_card]
        legal = [
            _play_action("play-skip", "skip"),
            _play_action("play-rev", "rev"),
        ]
        players = [_player("p1", 2), _player("p2", 1), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        scorer = UnoActionScorer()
        by_id = _score_map(scorer, view, legal, jitter=0.0)
        gap = abs(by_id["play-skip"] - by_id["play-rev"])
        jitter_span = scorer._config.random_jitter_max - scorer._config.random_jitter_min
        assert gap < jitter_span * 2
        assert by_id["play-skip"] > scorer._config.normal_disable
        assert by_id["play-rev"] > scorer._config.normal_reverse

    def test_threat_hand_two_low_self_hand_prefers_number(self):
        """下家2张且自己手牌少时，优秀数字牌可压过轻度威胁功能牌。"""
        disable_card = _action_card("skip", "DISABLE", "GREEN", "GREEN_SKIP")
        number_card = _number_card("num", "GREEN", 3)
        hand = [disable_card, number_card]
        legal = [
            _play_action("play-skip", "skip"),
            _play_action("play-num", "num"),
        ]
        players = [_player("p1", 2), _player("p2", 2), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        by_id = _score_map(UnoActionScorer(), view, legal)
        assert by_id["play-num"] > by_id["play-skip"]

    def test_threat_hand_two_many_cards_can_prefer_disable(self):
        """下家2张且自己手牌多时可用禁用压制。"""
        disable_card = _action_card("skip", "DISABLE", "GREEN", "GREEN_SKIP")
        draw_two = _action_card("d2", "DRAW_TWO", "GREEN", "GREEN_DRAW2")
        reverse_card = _action_card("rev", "REVERSE", "GREEN", "GREEN_REVERSE")
        number_card = _number_card("num", "GREEN", 3)
        fillers = [_number_card(f"f{i}", "BLUE", i) for i in range(4)]
        hand = [disable_card, draw_two, reverse_card, number_card] + fillers
        legal = [
            _play_action("play-skip", "skip"),
            _play_action("play-d2", "d2"),
            _play_action("play-rev", "rev"),
            _play_action("play-num", "num"),
        ]
        players = [_player("p1", len(hand)), _player("p2", 2), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        by_id = _score_map(UnoActionScorer(), view, legal)
        assert by_id["play-skip"] > by_id["play-num"]

    def test_threat_hand_three_mild_boost(self):
        draw_two = {
            "cardInstanceId": "d2",
            "cardCode": "GREEN_DRAW2",
            "color": "GREEN",
            "cardType": "DRAW_TWO",
            "numberValue": None,
        }
        number_card = {
            "cardInstanceId": "num",
            "cardCode": "GREEN_5",
            "color": "GREEN",
            "cardType": "NUMBER",
            "numberValue": 5,
        }
        filler = {
            "cardInstanceId": "f1",
            "cardCode": "BLUE_1",
            "color": "BLUE",
            "cardType": "NUMBER",
            "numberValue": 1,
        }
        hand = [draw_two, number_card, filler]
        legal = [
            _play_action("play-d2", "d2"),
            _play_action("play-num", "num"),
        ]
        players = [_player("p1", len(hand)), _player("p2", 3), _player("p3", 4)]
        view = _uno_view(hand_cards=hand, legal_actions=legal, players=players)
        scorer = UnoActionScorer()
        with patch("app.modules.games.uno.uno_action_scorer.random.uniform", return_value=0.0):
            scores = scorer.score_actions(
                game_code="uno",
                game_view=view,
                legal_actions=legal,
                player_id="p1",
            )
        by_id = {item.actionId: item.score for item in scores}
        number_best = max(by_id["play-num"], by_id.get("play-f1", 0.0))
        mild_threat = (
            scorer._config.threat_next_draw_two * scorer._config.threat_multiplier_hand_3
        )
        full_threat = (
            scorer._config.threat_next_draw_two * scorer._config.threat_multiplier_hand_1
        )
        assert mild_threat < full_threat
        assert by_id["play-d2"] - number_best < full_threat + 200.0

    def test_finish_and_pending_draw_skip_jitter(self):
        wild4 = {
            "cardInstanceId": "w4",
            "cardCode": "WILD_DRAW4",
            "color": None,
            "cardType": "WILD_DRAW4",
            "numberValue": None,
        }
        finish_card = {
            "cardInstanceId": "last",
            "cardCode": "RED_9",
            "color": "RED",
            "cardType": "NUMBER",
            "numberValue": 9,
        }
        hand_finish = [finish_card]
        legal_finish = [_play_action("play-last", "last")]
        view_finish = _uno_view(hand_cards=hand_finish, legal_actions=legal_finish)
        scorer = UnoActionScorer()
        with patch(
            "app.modules.games.uno.uno_action_scorer.random.uniform",
            side_effect=AssertionError("jitter on finish"),
        ):
            scores_finish = scorer.score_actions(
                game_code="uno",
                game_view=view_finish,
                legal_actions=legal_finish,
                player_id="p1",
            )
        assert "jitter" not in scores_finish[0].reason
        assert scores_finish[0].score >= scorer._config.immediate_finish

        hand_pending = [wild4]
        legal_pending = [_play_action("play-w4", "w4", "RED"), _draw_action("draw-p")]
        view_pending = _uno_view(
            hand_cards=hand_pending,
            legal_actions=legal_pending,
            pending_draw={"amount": 2, "stackable": True, "sourceCardType": "DRAW_TWO"},
        )
        with patch(
            "app.modules.games.uno.uno_action_scorer.random.uniform",
            side_effect=AssertionError("jitter on pending"),
        ):
            scores_pending = scorer.score_actions(
                game_code="uno",
                game_view=view_pending,
                legal_actions=legal_pending,
                player_id="p1",
            )
        by_id = {item.actionId: item.score for item in scores_pending}
        pending_item = next(item for item in scores_pending if item.actionId == "play-w4")
        assert "jitter" not in pending_item.reason
        assert by_id["play-w4"] >= scorer._config.pending_stack_wild_draw4

    def test_random_jitter_can_flip_close_number_plays(self):
        numbers = []
        legal = []
        for index in range(2):
            card_id = f"c{index}"
            numbers.append(
                {
                    "cardInstanceId": card_id,
                    "cardCode": f"RED_{index}",
                    "color": "RED",
                    "cardType": "NUMBER",
                    "numberValue": index,
                }
            )
            legal.append(_play_action(f"play-{card_id}", card_id))
        view = _uno_view(hand_cards=numbers, legal_actions=legal)
        scorer = UnoActionScorer()
        with patch(
            "app.modules.games.uno.uno_action_scorer.random.uniform",
            side_effect=[25.0, -25.0],
        ):
            scores = scorer.score_actions(
                game_code="uno",
                game_view=view,
                legal_actions=legal,
                player_id="p1",
            )
        by_id = {item.actionId: item.score for item in scores}
        assert by_id["play-c0"] > by_id["play-c1"]

    def test_threat_hand_one_stronger_than_hand_three(self):
        disable_card = {
            "cardInstanceId": "skip",
            "cardCode": "GREEN_SKIP",
            "color": "GREEN",
            "cardType": "DISABLE",
            "numberValue": None,
        }
        hand = [disable_card]
        legal = [_play_action("play-skip", "skip")]
        view_one = _uno_view(
            hand_cards=hand,
            legal_actions=legal,
            players=[_player("p1", 1), _player("p2", 1), _player("p3", 4)],
        )
        view_three = _uno_view(
            hand_cards=hand,
            legal_actions=legal,
            players=[_player("p1", 1), _player("p2", 3), _player("p3", 4)],
        )
        scorer = UnoActionScorer()
        with patch("app.modules.games.uno.uno_action_scorer.random.uniform", return_value=0.0):
            score_one = scorer.score_actions(
                game_code="uno",
                game_view=view_one,
                legal_actions=legal,
                player_id="p1",
            )[0].score
            score_three = scorer.score_actions(
                game_code="uno",
                game_view=view_three,
                legal_actions=legal,
                player_id="p1",
            )[0].score
        assert score_one > score_three
