"""斗地主出牌阶段服务。"""

from typing import Any, Dict, TYPE_CHECKING

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_clock_service import DoudizhuClockService
from app.modules.game_impls.doudizhu.doudizhu_constants import PHASE_PLAYING
from app.modules.game_impls.doudizhu.doudizhu_event_factory import (
    DoudizhuEventContext,
    DoudizhuEventFactory,
)
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    apply_global_multiplier,
    build_combo_signature,
    build_last_play_signature,
    clear_seat_action_feedback,
    parse_cards,
    record_seat_action_feedback,
    select_cards_by_instance_ids,
)
from app.modules.game_impls.doudizhu.schemas import DoudizhuPlayCardsPayload
from app.modules.strategy_turn.schemas import ResolvedGameAction

if TYPE_CHECKING:
    from app.modules.game_impls.doudizhu.doudizhu_settlement_service import (
        DoudizhuSettlementService,
    )


class DoudizhuPlayingPhaseService(object):
    """处理斗地主出牌与过牌。"""

    def __init__(
        self,
        event_factory: DoudizhuEventFactory = None,
        clock_service: DoudizhuClockService = None,
        settlement_service: "DoudizhuSettlementService" = None,
    ) -> None:
        """
        初始化出牌阶段服务。

        :param event_factory: 事件工厂，可空则使用默认实例。
        :param clock_service: 计时服务，可空则使用默认实例。
        :param settlement_service: 结算服务，可空则使用默认实例。
        :return: 无。
        """
        self._events = event_factory or DoudizhuEventFactory()
        self._clock = clock_service or DoudizhuClockService()
        if settlement_service is None:
            from app.modules.game_impls.doudizhu.doudizhu_settlement_service import (
                DoudizhuSettlementService,
            )

            settlement_service = DoudizhuSettlementService(
                event_factory=self._events,
                clock_service=self._clock,
            )
        self._settlement = settlement_service

    def enter_playing_phase(self, state: Dict[str, Any]) -> None:
        """
        进入出牌阶段，地主先出。

        :param state: 对局状态。
        :return: 无。
        """
        landlord_id = str(state.get("landlordPlayerId") or "")
        state["phase"] = PHASE_PLAYING
        state["currentPlayerId"] = landlord_id
        state["roundLeadPlayerId"] = landlord_id
        state["lastPlay"] = None
        state["lastPlayCards"] = []
        state["lastPlayPlayerId"] = None
        clear_seat_action_feedback(state)
        state["passPlayerIds"] = []
        state["consecutivePassCount"] = 0
        self._clock.stamp_turn_clock(state)
        state["phaseAutoAdvance"] = None

    def apply_play_cards(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用出牌操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        raw_payload = action.payload or {}
        payload = DoudizhuPlayCardsPayload.model_validate(
            {
                "cardInstanceIds": raw_payload.get("cardInstanceIds"),
                "normalizedCombo": raw_payload.get("normalizedCombo"),
                "comboSignature": raw_payload.get("comboSignature"),
                "lastPlaySignature": raw_payload.get("lastPlaySignature"),
            },
        )
        if str(state.get("phase") or "") != PHASE_PLAYING:
            raise ValidationException("当前阶段不能出牌")
        if str(state.get("currentPlayerId") or "").strip() != str(player_id or "").strip():
            raise ValidationException("当前不是该玩家行动")
        card_instance_ids = list(payload.cardInstanceIds)
        if not card_instance_ids:
            raise ValidationException("请选择至少一张牌")
        if len(card_instance_ids) != len(set(card_instance_ids)):
            raise ValidationException("不能重复选择同一张牌")
        expected_last_signature = build_last_play_signature(state)
        if payload.lastPlaySignature != expected_last_signature:
            raise ValidationException("上家出牌已变化，请重新选择")
        combo = payload.normalizedCombo
        expected_combo_signature = build_combo_signature(combo)
        if payload.comboSignature != expected_combo_signature:
            raise ValidationException("牌型签名无效")
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        hand_cards = parse_cards(player.get("handCards") or [])
        selected_cards = select_cards_by_instance_ids(hand_cards, card_instance_ids)
        if len(selected_cards) != len(card_instance_ids):
            raise ValidationException("选择的牌不在当前玩家手牌中")
        remaining_hand = [
            card for card in hand_cards if card.cardInstanceId not in set(card_instance_ids)
        ]
        player["handCards"] = [card.model_dump() for card in remaining_hand]
        player["handCount"] = len(remaining_hand)
        player["playCount"] = int(player.get("playCount") or 0) + 1
        players[player_id] = player
        state["players"] = players
        state["lastPlay"] = combo.model_dump()
        state["lastPlayCards"] = [card.model_dump() for card in selected_cards]
        state["lastPlayPlayerId"] = player_id
        clear_seat_action_feedback(state)
        state["roundLeadPlayerId"] = player_id
        state["passPlayerIds"] = []
        state["consecutivePassCount"] = 0
        rule_config = state.get("ruleConfig") or {}
        if combo.isRocket:
            multiplier = int(rule_config.get("rocketMultiplier", 2))
            state["rocketCount"] = int(state.get("rocketCount") or 0) + 1
            apply_global_multiplier(
                state,
                "ROCKET",
                player_id,
                multiplier,
                "DOUDIZHU_ROCKET_MULTIPLIER",
            )
            self._events.append(
                context,
                "DOUDIZHU_ROCKET_MULTIPLIER",
                player_id,
                {"globalMultiplier": state.get("globalMultiplier")},
            )
        elif combo.isBomb:
            multiplier = int(rule_config.get("bombMultiplier", 2))
            state["bombCount"] = int(state.get("bombCount") or 0) + 1
            apply_global_multiplier(
                state,
                "BOMB",
                player_id,
                multiplier,
                "DOUDIZHU_BOMB_MULTIPLIER",
            )
            self._events.append(
                context,
                "DOUDIZHU_BOMB_MULTIPLIER",
                player_id,
                {"globalMultiplier": state.get("globalMultiplier")},
            )
        self._events.append(
            context,
            "DOUDIZHU_PLAY_CARDS",
            player_id,
            {
                "cardInstanceIds": card_instance_ids,
                "combo": combo.model_dump(),
            },
        )
        if not remaining_hand:
            self._settlement.enter_settlement_phase(state, player_id, context)
            return
        self.move_to_next_playing_player(state, player_id)

    def apply_pass(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用过牌操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        player["passCount"] = int(player.get("passCount") or 0) + 1
        players[player_id] = player
        state["players"] = players
        pass_ids = list(state.get("passPlayerIds") or [])
        pass_ids.append(player_id)
        state["passPlayerIds"] = pass_ids
        record_seat_action_feedback(state, player_id, "PASS")
        consecutive = int(state.get("consecutivePassCount") or 0) + 1
        state["consecutivePassCount"] = consecutive
        self._events.append(context, "DOUDIZHU_PASS", player_id, {})
        if consecutive >= 2:
            lead_player_id = str(state.get("roundLeadPlayerId") or "")
            state["lastPlay"] = None
            state["lastPlayCards"] = []
            state["lastPlayPlayerId"] = None
            state["passPlayerIds"] = []
            state["consecutivePassCount"] = 0
            state["currentPlayerId"] = lead_player_id
            self._clock.stamp_turn_clock(state)
            return
        self.move_to_next_playing_player(state, player_id)

    def move_to_next_playing_player(
        self,
        state: Dict[str, Any],
        current_player_id: str,
    ) -> None:
        """
        切换到出牌阶段下一位玩家。

        :param state: 对局状态。
        :param current_player_id: 当前玩家 ID。
        :return: 无。
        """
        player_ids = list(state.get("playerIds") or [])
        current_index = player_ids.index(current_player_id)
        next_player_id = player_ids[(current_index + 1) % len(player_ids)]
        state["currentPlayerId"] = next_player_id
        self._clock.stamp_turn_clock(state)
