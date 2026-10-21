"""UNO 局势评估与功能牌策略评分。"""

from typing import List, Optional, Tuple

import random

from app.modules.game_impls.uno.uno_constants import ACTION_CARD_TYPES, VALID_CHOOSE_COLORS
from app.modules.game_impls.uno.uno_action_score_config import UnoActionScoreConfig
from app.modules.game_impls.uno.uno_scorer_context import (
    UnoActionFeature,
    UnoFeatureExtractor,
    UnoScoreContext,
)


class UnoActionEvaluator(object):
    """UNO 动作评分器（局势评估、功能牌策略与扰动）。"""

    def __init__(self, config: UnoActionScoreConfig, feature_extractor: UnoFeatureExtractor) -> None:
        """初始化动作评估依赖。"""
        self._config = config
        self._features = feature_extractor

    def score_action(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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
            self.score_immediate_finish,
            self.score_pending_draw,
            self.score_opponent_threat,
            self.score_reverse,
            self.score_self_uno,
            self.score_color_choice,
            self.score_card_type_value,
            self.score_number_fit,
            self.score_hand_count_strategy,
            self.score_wild_preservation,
            self.score_draw_or_pass,
            self.score_random_jitter,
        )
        for scoring_method in scoring_steps:
            delta, label = scoring_method(context, feature)
            if delta:
                total += delta
                if label:
                    parts.append(label)
        return total, "+".join(parts)

    def score_immediate_finish(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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

    def score_pending_draw(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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

    def get_hand_threat_multiplier(
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

    def score_opponent_threat(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        下家手牌较少时的压制评分（参与总分，不强制出牌）。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action:
            return 0.0, ""
        next_threat = self.get_hand_threat_multiplier(
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

    def score_reverse(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        反转牌场景评分（按威胁倍率差比较出牌前后下家）。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action or feature.card_type != "REVERSE":
            return 0.0, ""
        current_next_threat = self.get_hand_threat_multiplier(
            feature.next_player_hand_count,
            context.self_hand_count,
        )
        reverse_next_threat = self.get_hand_threat_multiplier(
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

    def score_self_uno(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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
        if feature.card_type in ACTION_CARD_TYPES:
            return self._config.self_uno_action_card, "selfUnoAct"
        if feature.card_type == "WILD":
            return self._config.self_uno_wild, "selfUnoWild"
        if feature.card_type == "WILD_DRAW4":
            return self._config.self_uno_wild_draw4, "selfUno+4"
        return 0.0, ""

    def score_color_choice(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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
        remaining_cards = self._features.remaining_hand_after_play(context, feature)
        color_counts = self._features.count_colors(remaining_cards)
        ranked_colors = sorted(
            VALID_CHOOSE_COLORS,
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

    def score_card_type_value(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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

    def score_number_fit(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
    ) -> Tuple[float, str]:
        """
        数字牌出牌结构与颜色链收益评分。

        :param context: 评分上下文。
        :param feature: 动作特征。
        :return: 分值与标签。
        """
        if not feature.is_play_action or feature.card_type != "NUMBER":
            return 0.0, ""
        score = self._features.calculate_number_fit_score(context, feature)
        if not score:
            return 0.0, ""
        return score, "numFit"

    def score_hand_count_strategy(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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
        if feature.card_type in ACTION_CARD_TYPES:
            return self._config.low_hand_action_card_penalty, "lowHandAct"
        return 0.0, ""

    def score_wild_preservation(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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

    def score_draw_or_pass(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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

    def score_random_jitter(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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
