"""UNO 托管动作评分器。"""

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.modules.games.uno.uno_action_score_config import UNO_ACTION_SCORE_CONFIG, UnoActionScoreConfig
from app.modules.room.action_scorer import ActionScore, ManagedActionScorer
from app.modules.strategy_turn.player_order import (
    get_next_active_player,
    get_next_active_player_after_reverse,
    get_previous_active_player,
)
from app.modules.strategy_turn.schemas import GameView, LegalAction

_ACTION_PLAY_CARD = "PLAY_CARD"
_ACTION_DRAW_CARD = "DRAW_CARD"
_ACTION_PASS_TURN = "PASS_TURN"
_VALID_COLORS = ("RED", "YELLOW", "BLUE", "GREEN")
_ACTION_CARD_TYPES = frozenset(("DISABLE", "REVERSE", "DRAW_TWO"))


@dataclass
class _UnoScoreContext(object):
    """UNO 评分上下文。"""

    player_id: str
    ordered_players: List[Dict[str, Any]]
    play_direction: int
    pending_draw: Optional[Dict[str, Any]]
    current_color: Optional[str]
    hand_cards: List[Dict[str, Any]]
    legal_actions: List[LegalAction]
    has_any_play_card: bool
    self_hand_count: int
    top_discard: Optional[Dict[str, Any]]
    has_number_playable_actions: bool
    has_good_number_playable_actions: bool


@dataclass
class _UnoActionFeature(object):
    """单个合法动作的特征。"""

    action_id: str
    action_type: str
    card: Optional[Dict[str, Any]]
    card_type: str
    card_color: Optional[str]
    choose_color: Optional[str]
    is_play_action: bool
    is_draw_action: bool
    is_pass_action: bool
    will_finish: bool
    remaining_hand_count_after_play: Optional[int]
    next_player_hand_count: Optional[int]
    previous_player_hand_count: Optional[int]
    reverse_next_player_hand_count: Optional[int]
    has_other_playable_actions: bool
    card_value: Optional[str]
    has_number_playable_actions: bool
    has_good_number_playable_actions: bool


class UnoActionScorer(ManagedActionScorer):
    """UNO 托管动作评分实现。"""

    def __init__(self, config: Optional[UnoActionScoreConfig] = None) -> None:
        self._config = config or UNO_ACTION_SCORE_CONFIG

    def score_actions(
        self,
        *,
        game_code: str,
        game_view: GameView,
        legal_actions: List[LegalAction],
        player_id: str,
    ) -> List[ActionScore]:
        """
        对 UNO 合法动作评分。

        :param game_code: 游戏编码。
        :param game_view: 当前玩家视角 GameView。
        :param legal_actions: 合法动作列表。
        :param player_id: 当前行动玩家 ID。
        :return: 评分列表。
        """
        del game_code
        context = self._build_context(game_view, legal_actions, player_id)
        if context is None:
            return []
        results = []
        for action in legal_actions:
            feature = self._build_action_feature(context, action)
            score, reason = self._score_action(context, feature)
            action_id = str(feature.action_id or "").strip()
            if not action_id:
                continue
            results.append(ActionScore(actionId=action_id, score=score, reason=reason))
        return results

    def _build_context(
        self,
        game_view: GameView,
        legal_actions: List[LegalAction],
        player_id: str,
    ) -> Optional[_UnoScoreContext]:
        """
        从 GameView 解析评分上下文。

        :param game_view: 玩家视角视图。
        :param legal_actions: 合法动作列表。
        :param player_id: 当前行动玩家 ID。
        :return: 上下文，数据不足时返回 ``None``。
        """
        normalized_player_id = str(player_id or game_view.viewerPlayerId or "").strip()
        if not normalized_player_id:
            return None
        public_state = game_view.publicState if isinstance(game_view.publicState, dict) else {}
        private_state = game_view.privateState if isinstance(game_view.privateState, dict) else {}
        player_ids = public_state.get("playerIds")
        if not isinstance(player_ids, list):
            player_ids = []
        summaries = public_state.get("players")
        if not isinstance(summaries, list):
            summaries = []
        summary_by_id: Dict[str, Dict[str, Any]] = {}
        for item in summaries:
            if not isinstance(item, dict):
                continue
            summary_id = str(item.get("playerId") or "").strip()
            if summary_id:
                summary_by_id[summary_id] = item
        ordered_players = []
        for seat_player_id in player_ids:
            seat_id = str(seat_player_id or "").strip()
            if seat_id and seat_id in summary_by_id:
                ordered_players.append(summary_by_id[seat_id])
        hand_cards_raw = private_state.get("handCards")
        hand_cards = []
        if isinstance(hand_cards_raw, list):
            hand_cards = [item for item in hand_cards_raw if isinstance(item, dict)]
        pending_draw = public_state.get("pendingDraw")
        if pending_draw is not None and not isinstance(pending_draw, dict):
            pending_draw = None
        current_color = public_state.get("currentColor")
        if current_color is not None:
            current_color = str(current_color).strip() or None
        play_direction = int(public_state.get("playDirection", 1) or 1)
        has_any_play_card = any(
            str(action.actionType or "").strip() == _ACTION_PLAY_CARD for action in legal_actions
        )
        top_discard = None
        for top_key in ("topDiscard", "discardTop", "topCard", "discardTopCard"):
            raw_top = public_state.get(top_key)
            if isinstance(raw_top, dict):
                top_discard = raw_top
                break
        has_number_playable, has_good_number_playable = self._scan_number_playable_flags(
            hand_cards,
            legal_actions,
            current_color,
            top_discard,
        )
        return _UnoScoreContext(
            player_id=normalized_player_id,
            ordered_players=ordered_players,
            play_direction=play_direction,
            pending_draw=pending_draw,
            current_color=current_color,
            hand_cards=hand_cards,
            legal_actions=legal_actions,
            has_any_play_card=has_any_play_card,
            self_hand_count=len(hand_cards),
            top_discard=top_discard,
            has_number_playable_actions=has_number_playable,
            has_good_number_playable_actions=has_good_number_playable,
        )

    def _build_action_feature(
        self,
        context: _UnoScoreContext,
        action: LegalAction,
    ) -> _UnoActionFeature:
        """
        解析单个合法动作的特征。

        :param context: 评分上下文。
        :param action: 合法动作。
        :return: 动作特征。
        """
        action_type = str(action.actionType or "").strip()
        action_id = str(action.actionId or "").strip()
        payload = action.payload if isinstance(action.payload, dict) else {}
        is_play_action = action_type == _ACTION_PLAY_CARD
        is_draw_action = action_type == _ACTION_DRAW_CARD
        is_pass_action = action_type == _ACTION_PASS_TURN
        card = None
        card_type = ""
        card_color = None
        card_value = None
        choose_color = None
        remaining_after_play = None
        will_finish = False
        if is_play_action:
            card_instance_id = str(payload.get("cardInstanceId") or "").strip()
            card = self._find_hand_card(context.hand_cards, card_instance_id)
            if card is not None:
                card_type = str(card.get("cardType") or "").strip().upper()
                raw_color = card.get("color")
                card_color = str(raw_color).strip().upper() if raw_color else None
                card_value = self._card_value_from_dict(card)
            raw_choose = payload.get("chooseColor")
            if raw_choose is not None:
                choose_color = str(raw_choose).strip().upper() or None
            hand_count = len(context.hand_cards)
            remaining_after_play = max(hand_count - 1, 0)
            will_finish = remaining_after_play == 0
        next_hand_count = self._player_hand_count(
            get_next_active_player(
                context.ordered_players,
                context.player_id,
                context.play_direction,
            )
        )
        previous_hand_count = self._player_hand_count(
            get_previous_active_player(
                context.ordered_players,
                context.player_id,
                context.play_direction,
            )
        )
        reverse_next_hand_count = self._player_hand_count(
            get_next_active_player_after_reverse(
                context.ordered_players,
                context.player_id,
                context.play_direction,
            )
        )
        has_other_playable = False
        for other_action in context.legal_actions:
            if str(other_action.actionType or "").strip() != _ACTION_PLAY_CARD:
                continue
            if str(other_action.actionId or "").strip() == action_id:
                continue
            has_other_playable = True
            break
        return _UnoActionFeature(
            action_id=action_id,
            action_type=action_type,
            card=card,
            card_type=card_type,
            card_color=card_color,
            choose_color=choose_color,
            is_play_action=is_play_action,
            is_draw_action=is_draw_action,
            is_pass_action=is_pass_action,
            will_finish=will_finish,
            remaining_hand_count_after_play=remaining_after_play,
            next_player_hand_count=next_hand_count,
            previous_player_hand_count=previous_hand_count,
            reverse_next_player_hand_count=reverse_next_hand_count,
            has_other_playable_actions=has_other_playable,
            card_value=card_value,
            has_number_playable_actions=context.has_number_playable_actions,
            has_good_number_playable_actions=context.has_good_number_playable_actions,
        )

    def _score_action(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        汇总单项动作总分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 总分与原因摘要。
        """
        parts: List[str] = []
        total = 0.0
        scoring_steps = (
            self._score_immediate_finish,
            self._score_pending_draw,
            self._score_opponent_threat,
            self._score_reverse,
            self._score_self_uno,
            self._score_color_choice,
            self._score_card_type_value,
            self._score_number_fit,
            self._score_hand_count_strategy,
            self._score_wild_preservation,
            self._score_draw_or_pass,
            self._score_risk,
            self._score_random_jitter,
        )
        for scoring_method in scoring_steps:
            delta, label = scoring_method(context, feature)
            if delta:
                total += delta
                if label:
                    parts.append(label)
        return total, "+".join(parts)

    def _score_immediate_finish(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        立即获胜场景评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        del context
        if feature.is_play_action and feature.will_finish:
            return self._config.immediate_finish, "finish"
        return 0.0, ""

    def _score_pending_draw(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        待摸牌惩罚场景评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if context.pending_draw is None:
            return 0.0, ""
        if feature.is_draw_action:
            return self._config.pending_draw, "pendingDraw"
        if not feature.is_play_action:
            return 0.0, ""
        if feature.card_type == "WILD_DRAW4":
            return self._config.pending_stack_wild_draw4, "stack+4"
        if feature.card_type == "DRAW_TWO":
            return self._config.pending_stack_draw_two, "stack+2"
        return 0.0, ""

    def _get_hand_threat_multiplier(
        self,
        hand_count: Optional[int],
        self_hand_count: Optional[int] = None,
    ) -> float:
        """
        按对手剩余手牌数返回威胁倍率。

        :param hand_count: 对手手牌数。
        :param self_hand_count: 自己手牌数，用于高牌量时加强压制。
        :return: 威胁倍率，无威胁时返回 ``0.0``。
        """
        if hand_count == 1:
            multiplier = self._config.threat_multiplier_hand_1
        elif hand_count == 2:
            multiplier = self._config.threat_multiplier_hand_2
        elif hand_count == 3:
            multiplier = self._config.threat_multiplier_hand_3
        else:
            return 0.0
        if (
            self_hand_count is not None
            and self_hand_count >= self._config.high_hand_count_threshold
            and multiplier > 0
        ):
            multiplier += self._config.high_hand_threat_multiplier_bonus
        return min(multiplier, 1.0)

    def _score_opponent_threat(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        下家手牌较少时的压制评分（参与总分，不强制出牌）。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action:
            return 0.0, ""
        next_threat = self._get_hand_threat_multiplier(
            feature.next_player_hand_count,
            context.self_hand_count,
        )
        if next_threat <= 0:
            return 0.0, ""
        if feature.card_type == "WILD_DRAW4":
            return self._config.threat_next_wild_draw4 * next_threat, "threat+4"
        if feature.card_type == "DISABLE":
            return self._config.threat_next_disable * next_threat, "threatSkip"
        if feature.card_type == "DRAW_TWO":
            return self._config.threat_next_draw_two * next_threat, "threat+2"
        if feature.card_type == "WILD":
            return self._config.threat_next_wild * next_threat, "threatWild"
        return 0.0, ""

    def _score_reverse(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        反转牌场景评分（按威胁倍率差比较出牌前后下家）。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action or feature.card_type != "REVERSE":
            return 0.0, ""
        current_next_threat = self._get_hand_threat_multiplier(
            feature.next_player_hand_count,
            context.self_hand_count,
        )
        reverse_next_threat = self._get_hand_threat_multiplier(
            feature.reverse_next_player_hand_count,
            context.self_hand_count,
        )
        score = 0.0
        labels: List[str] = []
        if current_next_threat > reverse_next_threat:
            delta = self._config.reverse_avoids_one_card_next * (
                current_next_threat - reverse_next_threat
            )
            score += delta
            labels.append("reverseAvoid")
        if reverse_next_threat > current_next_threat:
            delta = self._config.reverse_to_one_card_player_penalty * (
                reverse_next_threat - current_next_threat
            )
            score += delta
            labels.append("reverseRisk")
        if not score:
            return 0.0, ""
        return score, "+".join(labels)

    def _score_self_uno(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        出牌后自己即将 UNO 的场景评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        del context
        if not feature.is_play_action or feature.remaining_hand_count_after_play != 1:
            return 0.0, ""
        if feature.card_type == "NUMBER":
            return self._config.self_uno_number, "selfUnoNum"
        if feature.card_type in _ACTION_CARD_TYPES:
            return self._config.self_uno_action_card, "selfUnoAct"
        if feature.card_type == "WILD":
            return self._config.self_uno_wild, "selfUnoWild"
        if feature.card_type == "WILD_DRAW4":
            return self._config.self_uno_wild_draw4, "selfUno+4"
        return 0.0, ""

    def _score_color_choice(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        万能牌选色场景评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action or feature.card_type not in ("WILD", "WILD_DRAW4"):
            return 0.0, ""
        if not feature.choose_color:
            return 0.0, ""
        remaining_cards = self._remaining_hand_after_play(context, feature)
        color_counts = self._count_colors(remaining_cards)
        ranked_colors = sorted(
            _VALID_COLORS,
            key=lambda color: (-color_counts.get(color, 0), color),
        )
        non_zero_colors = [color for color in ranked_colors if color_counts.get(color, 0) > 0]
        if not non_zero_colors:
            if feature.choose_color not in color_counts:
                return self._config.choose_missing_color_penalty, "wildNoColor"
            return 0.0, ""
        if feature.choose_color == non_zero_colors[0]:
            return self._config.choose_most_color, "wildTopColor"
        if len(non_zero_colors) > 1 and feature.choose_color == non_zero_colors[1]:
            return self._config.choose_second_color, "wildSecondColor"
        if color_counts.get(feature.choose_color, 0) <= 0:
            return self._config.choose_missing_color_penalty, "wildMissing"
        return 0.0, ""

    def _score_card_type_value(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        普通出牌基础价值评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        del context
        if not feature.is_play_action:
            return 0.0, ""
        normal_scores = {
            "NUMBER": (self._config.normal_number, "normalNum"),
            "REVERSE": (self._config.normal_reverse, "normalRev"),
            "DISABLE": (self._config.normal_disable, "normalSkip"),
            "DRAW_TWO": (self._config.normal_draw_two, "normal+2"),
            "WILD": (self._config.normal_wild, "normalWild"),
            "WILD_DRAW4": (self._config.normal_wild_draw4, "normal+4"),
        }
        matched = normal_scores.get(feature.card_type)
        if matched is None:
            return 0.0, ""
        return matched[0], matched[1]

    def _score_number_fit(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        数字牌出牌结构与颜色链收益评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action or feature.card_type != "NUMBER":
            return 0.0, ""
        score = self._calculate_number_fit_score(context, feature)
        if not score:
            return 0.0, ""
        return score, "numFit"

    def _score_hand_count_strategy(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        按自己手牌数量调整出牌倾向。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action:
            return 0.0, ""
        if context.self_hand_count > self._config.low_hand_count_threshold:
            return 0.0, ""
        if feature.card_type == "NUMBER":
            return self._config.low_hand_number_bonus, "lowHandNum"
        if feature.card_type in _ACTION_CARD_TYPES:
            return self._config.low_hand_action_card_penalty, "lowHandAct"
        return 0.0, ""

    def _score_wild_preservation(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        有数字牌可出时保留 WILD / +4 的惩罚。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if feature.will_finish:
            return 0.0, ""
        if context.pending_draw is not None:
            return 0.0, ""
        if feature.next_player_hand_count == 1:
            return 0.0, ""
        if not feature.is_play_action:
            return 0.0, ""
        if feature.card_type not in ("WILD", "WILD_DRAW4"):
            return 0.0, ""
        if not feature.has_number_playable_actions:
            return 0.0, ""
        score = 0.0
        labels: List[str] = []
        if feature.card_type == "WILD":
            score += self._config.wild_when_number_playable_penalty
            labels.append("keepWild")
        else:
            score += self._config.wild_draw4_when_number_playable_penalty
            labels.append("keep+4")
        if feature.has_good_number_playable_actions:
            if feature.card_type == "WILD":
                score += self._config.wild_when_good_number_playable_penalty
                labels.append("keepWildGood")
            else:
                score += self._config.wild_draw4_when_good_number_playable_penalty
                labels.append("keep+4Good")
        if not score:
            return 0.0, ""
        return score, "+".join(labels)

    def _score_draw_or_pass(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        摸牌与 PASS 场景评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if feature.is_draw_action:
            if context.has_any_play_card:
                return self._config.draw_when_playable_penalty, "drawPenalty"
            return self._config.draw_when_no_playable, "drawNeeded"
        if feature.is_pass_action:
            return self._config.pass_turn, "pass"
        return 0.0, ""

    def _score_risk(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        风险项评分占位（当前无额外规则）。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        del context
        del feature
        return 0.0, ""

    def _score_random_jitter(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        普通动作的随机扰动，避免相近分数时总是同一选择。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if feature.is_play_action and feature.will_finish:
            return 0.0, ""
        if context.pending_draw is not None:
            return 0.0, ""
        if feature.is_draw_action and not context.has_any_play_card:
            return 0.0, ""
        if feature.is_pass_action:
            return 0.0, ""
        jitter = random.uniform(self._config.random_jitter_min, self._config.random_jitter_max)
        return jitter, "jitter"

    def _calculate_number_fit_score(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> float:
        """
        计算数字牌出牌结构收益（不含随机扰动与其它评分项）。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 数字牌结构分。
        """
        if not feature.is_play_action or feature.card_type != "NUMBER":
            return 0.0
        score = self._config.number_discard_value
        top_value = self._card_value_from_dict(context.top_discard)
        if top_value is not None and feature.card_value is not None and feature.card_value == top_value:
            score += self._config.number_match_value
        if (
            context.current_color is not None
            and feature.card_color is not None
            and feature.card_color == context.current_color
        ):
            score += self._config.number_match_current_color
        remaining_cards = self._remaining_hand_after_play(context, feature)
        if feature.card_color is not None:
            same_color_count = sum(
                1
                for card in remaining_cards
                if str(card.get("color") or "").strip().upper() == feature.card_color
            )
            if same_color_count > 0:
                score += self._config.number_keep_color_chain
                score += same_color_count * self._config.number_same_color_remaining_each
            color_counts = self._count_colors(remaining_cards)
            best_color = max(
                _VALID_COLORS,
                key=lambda color: (color_counts.get(color, 0), color),
            )
            if color_counts.get(best_color, 0) > 0 and feature.card_color == best_color:
                score += self._config.number_switch_to_best_color
        return score

    def _has_good_number_alternative(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> bool:
        """
        是否存在其他可出的优秀数字牌动作。

        :param context: 评分上下文。
        :param feature: 当前动作特征。
        :return: 有优秀数字牌替代时返回 ``True``。
        """
        for other_action in context.legal_actions:
            if str(other_action.actionType or "").strip() != _ACTION_PLAY_CARD:
                continue
            if str(other_action.actionId or "").strip() == feature.action_id:
                continue
            other_feature = self._build_action_feature(context, other_action)
            if other_feature.card_type != "NUMBER":
                continue
            if self._calculate_number_fit_score(context, other_feature) >= self._config.good_number_threshold:
                return True
        return False

    def _scan_number_playable_flags(
        self,
        hand_cards: List[Dict[str, Any]],
        legal_actions: List[LegalAction],
        current_color: Optional[str],
        top_discard: Optional[Dict[str, Any]],
    ) -> Tuple[bool, bool]:
        """
        扫描合法动作中是否存在数字牌 / 优秀数字牌可出。

        :param hand_cards: 当前手牌。
        :param legal_actions: 合法动作列表。
        :param current_color: 当前生效颜色。
        :param top_discard: 顶牌。
        :return: (有数字牌可出, 有优秀数字牌可出)。
        """
        has_number = False
        has_good_number = False
        stub_context = _UnoScoreContext(
            player_id="",
            ordered_players=[],
            play_direction=1,
            pending_draw=None,
            current_color=current_color,
            hand_cards=hand_cards,
            legal_actions=legal_actions,
            has_any_play_card=False,
            self_hand_count=len(hand_cards),
            top_discard=top_discard,
            has_number_playable_actions=False,
            has_good_number_playable_actions=False,
        )
        for action in legal_actions:
            if str(action.actionType or "").strip() != _ACTION_PLAY_CARD:
                continue
            payload = action.payload if isinstance(action.payload, dict) else {}
            card_instance_id = str(payload.get("cardInstanceId") or "").strip()
            card = self._find_hand_card(hand_cards, card_instance_id)
            if card is None:
                continue
            card_type = str(card.get("cardType") or "").strip().upper()
            if card_type != "NUMBER":
                continue
            has_number = True
            raw_color = card.get("color")
            card_color = str(raw_color).strip().upper() if raw_color else None
            stub_feature = _UnoActionFeature(
                action_id=str(action.actionId or "").strip(),
                action_type=_ACTION_PLAY_CARD,
                card=card,
                card_type=card_type,
                card_color=card_color,
                choose_color=None,
                is_play_action=True,
                is_draw_action=False,
                is_pass_action=False,
                will_finish=max(len(hand_cards) - 1, 0) == 0,
                remaining_hand_count_after_play=max(len(hand_cards) - 1, 0),
                next_player_hand_count=None,
                previous_player_hand_count=None,
                reverse_next_player_hand_count=None,
                has_other_playable_actions=False,
                card_value=self._card_value_from_dict(card),
                has_number_playable_actions=False,
                has_good_number_playable_actions=False,
            )
            if (
                self._calculate_number_fit_score(stub_context, stub_feature)
                >= self._config.good_number_threshold
            ):
                has_good_number = True
                break
        return has_number, has_good_number

    def _card_value_from_dict(self, card: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        从牌字典读取点数（兼容多种字段名）。

        :param card: 牌字典。
        :return: 点数字符串，未知时返回 ``None``。
        """
        if card is None:
            return None
        for key in ("value", "cardValue", "number", "numberValue"):
            raw_value = card.get(key)
            if raw_value is None:
                continue
            normalized = str(raw_value).strip()
            if normalized:
                return normalized
        return None

    def _find_hand_card(
        self,
        hand_cards: List[Dict[str, Any]],
        card_instance_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        按实例 ID 查找手牌。

        :param hand_cards: 手牌列表。
        :param card_instance_id: 牌实例 ID。
        :return: 牌字典，未找到时返回 ``None``。
        """
        normalized_id = str(card_instance_id or "").strip()
        if not normalized_id:
            return None
        for card in hand_cards:
            if str(card.get("cardInstanceId") or "").strip() == normalized_id:
                return card
        return None

    def _player_hand_count(self, player: Optional[Dict[str, Any]]) -> Optional[int]:
        """
        读取玩家手牌数。

        :param player: 玩家摘要。
        :return: 手牌数，未知时返回 ``None``。
        """
        if player is None:
            return None
        raw_count = player.get("handCount")
        if raw_count is None:
            return None
        try:
            return int(raw_count)
        except (TypeError, ValueError):
            return None

    def _remaining_hand_after_play(
        self,
        context: _UnoScoreContext,
        feature: _UnoActionFeature,
    ) -> List[Dict[str, Any]]:
        """
        计算出牌后剩余手牌。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 剩余手牌列表。
        """
        if not feature.is_play_action or feature.card is None:
            return list(context.hand_cards)
        played_id = str(feature.card.get("cardInstanceId") or "").strip()
        if not played_id:
            return list(context.hand_cards)
        return [
            card
            for card in context.hand_cards
            if str(card.get("cardInstanceId") or "").strip() != played_id
        ]

    def _count_colors(self, hand_cards: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        统计手牌各花色数量。

        :param hand_cards: 手牌列表。
        :return: 花色到数量的映射。
        """
        counts = {color: 0 for color in _VALID_COLORS}
        for card in hand_cards:
            raw_color = card.get("color")
            if raw_color is None:
                continue
            color = str(raw_color).strip().upper()
            if color in counts:
                counts[color] += 1
        return counts
