"""UNO 评分上下文与动作特征提取。"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.modules.game_impls.uno.uno_action_score_config import UnoActionScoreConfig
from app.modules.strategy_turn.player_order import (
    get_next_active_player,
    get_next_active_player_after_reverse,
)
from app.modules.strategy_turn.schemas import ActionCandidate, ActionDecisionContext

from app.modules.game_impls.uno.uno_constants import (
    ACTION_DRAW_CARD, ACTION_PASS_TURN, ACTION_PLAY_CARD, VALID_CHOOSE_COLORS,
)


@dataclass
class UnoScoreContext(object):
    """UNO 评分上下文。"""

    player_id: str
    ordered_players: List[Dict[str, Any]]
    play_direction: int
    pending_draw: Optional[Dict[str, Any]]
    current_color: Optional[str]
    hand_cards: List[Dict[str, Any]]
    has_any_play_card: bool
    self_hand_count: int
    top_discard: Optional[Dict[str, Any]]
    has_number_playable_actions: bool
    has_good_number_playable_actions: bool


@dataclass
class UnoActionFeature(object):
    """单个合法动作的特征。"""

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
    reverse_next_player_hand_count: Optional[int]
    card_value: Optional[str]
    has_number_playable_actions: bool
    has_good_number_playable_actions: bool


class UnoFeatureExtractor(object):
    """UNO 动作特征提取器。"""

    def __init__(self, config: UnoActionScoreConfig) -> None:
        """保存数字牌结构评分参数。"""
        self._config = config

    def build_context(
        self,
        context: ActionDecisionContext,
        candidates: List[ActionCandidate],
    ) -> Optional[UnoScoreContext]:
        """
        从决策上下文解析评分上下文。

        :param context: 决策上下文。
        :param candidates: 候选动作列表。
        :return: 评分上下文，数据不足时返回 None。
        """
        normalized_player_id = str(context.playerId or "").strip()
        if not normalized_player_id:
            return None
        state = context.state if isinstance(context.state, dict) else {}
        hand_cards_raw = state.get("players", {})
        hand_cards = []
        player_state = None
        if isinstance(hand_cards_raw, dict):
            player_state = hand_cards_raw.get(normalized_player_id)
        if player_state is not None and hasattr(player_state, "handCards"):
            hand_cards = [card.model_dump() for card in player_state.handCards]
        elif isinstance(player_state, dict):
            raw_hand = player_state.get("handCards")
            if isinstance(raw_hand, list):
                hand_cards = [item for item in raw_hand if isinstance(item, dict)]
        player_ids = state.get("playerIds")
        if not isinstance(player_ids, list):
            player_ids = []
        summaries = []
        players_map = state.get("players")
        if isinstance(players_map, dict):
            for player_id in player_ids:
                item = players_map.get(player_id)
                if item is None:
                    continue
                if hasattr(item, "model_dump"):
                    summary = item.model_dump()
                elif isinstance(item, dict):
                    summary = dict(item)
                else:
                    continue
                summary_id = str(summary.get("playerId") or player_id).strip()
                summary["playerId"] = summary_id
                summary["handCount"] = len(summary.get("handCards") or [])
                summaries.append(summary)
        summary_by_id = {str(item.get("playerId")): item for item in summaries}
        ordered_players = []
        for seat_player_id in player_ids:
            seat_id = str(seat_player_id or "").strip()
            if seat_id and seat_id in summary_by_id:
                ordered_players.append(summary_by_id[seat_id])
        pending_draw = state.get("pendingDraw")
        if pending_draw is not None and not isinstance(pending_draw, dict):
            if hasattr(pending_draw, "model_dump"):
                pending_draw = pending_draw.model_dump()
            else:
                pending_draw = None
        current_color = state.get("currentColor")
        if current_color is not None:
            current_color = str(current_color).strip() or None
        play_direction = int(state.get("playDirection", 1) or 1)
        has_any_play_card = any(
            str(candidate.actionType or "").strip() == ACTION_PLAY_CARD for candidate in candidates
        )
        top_discard = None
        raw_top = state.get("topDiscard")
        if isinstance(raw_top, dict):
            top_discard = raw_top
        elif raw_top is not None and hasattr(raw_top, "model_dump"):
            top_discard = raw_top.model_dump()
        has_number_playable, has_good_number_playable = self.scan_number_playable_flags(
            hand_cards,
            candidates,
            current_color,
            top_discard,
        )
        return UnoScoreContext(
            player_id=normalized_player_id,
            ordered_players=ordered_players,
            play_direction=play_direction,
            pending_draw=pending_draw,
            current_color=current_color,
            hand_cards=hand_cards,
            has_any_play_card=has_any_play_card,
            self_hand_count=len(hand_cards),
            top_discard=top_discard,
            has_number_playable_actions=has_number_playable,
            has_good_number_playable_actions=has_good_number_playable,
        )

    def build_action_feature(
        self,
        context: UnoScoreContext,
        action: ActionCandidate,
    ) -> UnoActionFeature:
        """
        解析单个候选动作的特征。

        :param context: 评分上下文。
        :param action: 候选动作。
        :return: 动作特征。
        """
        action_type = str(action.actionType or "").strip()
        payload = action.normalizedAction.payload if isinstance(action.normalizedAction.payload, dict) else {}
        is_play_action = action_type == ACTION_PLAY_CARD
        is_draw_action = action_type == ACTION_DRAW_CARD
        is_pass_action = action_type == ACTION_PASS_TURN
        card = None
        card_type = ""
        card_color = None
        card_value = None
        choose_color = None
        remaining_after_play = None
        will_finish = False
        if is_play_action:
            card_instance_id = str(payload.get("cardInstanceId") or "").strip()
            card = self.find_hand_card(context.hand_cards, card_instance_id)
            if card is not None:
                card_type = str(card.get("cardType") or "").strip().upper()
                raw_color = card.get("color")
                card_color = str(raw_color).strip().upper() if raw_color else None
                card_value = self.card_value_from_dict(card)
            raw_choose = payload.get("chooseColor")
            if raw_choose is not None:
                choose_color = str(raw_choose).strip().upper() or None
            hand_count = len(context.hand_cards)
            remaining_after_play = max(hand_count - 1, 0)
            will_finish = remaining_after_play == 0
        next_hand_count = self.player_hand_count(
            get_next_active_player(
                context.ordered_players,
                context.player_id,
                context.play_direction,
            )
        )
        reverse_next_hand_count = self.player_hand_count(
            get_next_active_player_after_reverse(
                context.ordered_players,
                context.player_id,
                context.play_direction,
            )
        )
        return UnoActionFeature(
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
            reverse_next_player_hand_count=reverse_next_hand_count,
            card_value=card_value,
            has_number_playable_actions=context.has_number_playable_actions,
            has_good_number_playable_actions=context.has_good_number_playable_actions,
        )
    def calculate_number_fit_score(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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
        top_value = self.card_value_from_dict(context.top_discard)
        if top_value is not None and feature.card_value is not None and feature.card_value == top_value:
            score += self._config.number_match_value
        if (
            context.current_color is not None
            and feature.card_color is not None
            and feature.card_color == context.current_color
        ):
            score += self._config.number_match_current_color
        remaining_cards = self.remaining_hand_after_play(context, feature)
        if feature.card_color is not None:
            same_color_count = sum(
                1
                for card in remaining_cards
                if str(card.get("color") or "").strip().upper() == feature.card_color
            )
            if same_color_count > 0:
                score += self._config.number_keep_color_chain
                score += same_color_count * self._config.number_same_color_remaining_each
            color_counts = self.count_colors(remaining_cards)
            best_color = max(
                VALID_CHOOSE_COLORS,
                key=lambda color: (color_counts.get(color, 0), color),
            )
            if color_counts.get(best_color, 0) > 0 and feature.card_color == best_color:
                score += self._config.number_switch_to_best_color
        return score

    def scan_number_playable_flags(
        self,
        hand_cards: List[Dict[str, Any]],
        legal_actions: List[ActionCandidate],
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
        stub_context = UnoScoreContext(
            player_id="",
            ordered_players=[],
            play_direction=1,
            pending_draw=None,
            current_color=current_color,
            hand_cards=hand_cards,
            has_any_play_card=False,
            self_hand_count=len(hand_cards),
            top_discard=top_discard,
            has_number_playable_actions=False,
            has_good_number_playable_actions=False,
        )
        for action in legal_actions:
            if str(action.actionType or "").strip() != ACTION_PLAY_CARD:
                continue
            payload = action.normalizedAction.payload if isinstance(action.normalizedAction.payload, dict) else {}
            card_instance_id = str(payload.get("cardInstanceId") or "").strip()
            card = self.find_hand_card(hand_cards, card_instance_id)
            if card is None:
                continue
            card_type = str(card.get("cardType") or "").strip().upper()
            if card_type != "NUMBER":
                continue
            has_number = True
            raw_color = card.get("color")
            card_color = str(raw_color).strip().upper() if raw_color else None
            stub_feature = UnoActionFeature(
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
                reverse_next_player_hand_count=None,
                card_value=self.card_value_from_dict(card),
                has_number_playable_actions=False,
                has_good_number_playable_actions=False,
            )
            if (
                self.calculate_number_fit_score(stub_context, stub_feature)
                >= self._config.good_number_threshold
            ):
                has_good_number = True
                break
        return has_number, has_good_number

    def card_value_from_dict(self, card: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        从 UNO 牌模型的 numberValue 字段读取点数。

        :param card: 牌字典。
        :return: 点数字符串，未知时返回 ``None``。
        """
        if card is None:
            return None
        raw_value = card.get("numberValue")
        if raw_value is None:
            return None
        return str(raw_value).strip() or None

    def find_hand_card(
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

    def player_hand_count(self, player: Optional[Dict[str, Any]]) -> Optional[int]:
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

    def remaining_hand_after_play(
        self,
        context: UnoScoreContext,
        feature: UnoActionFeature,
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

    def count_colors(self, hand_cards: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        统计手牌各花色数量。

        :param hand_cards: 手牌列表。
        :return: 花色到数量的映射。
        """
        counts = {color: 0 for color in VALID_CHOOSE_COLORS}
        for card in hand_cards:
            raw_color = card.get("color")
            if raw_color is None:
                continue
            color = str(raw_color).strip().upper()
            if color in counts:
                counts[color] += 1
        return counts
