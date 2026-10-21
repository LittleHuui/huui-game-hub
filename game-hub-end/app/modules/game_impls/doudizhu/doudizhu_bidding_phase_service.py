"""斗地主叫抢地主阶段服务。"""
from typing import Any, Dict, List, TYPE_CHECKING

from app.modules.game_impls.doudizhu.doudizhu_clock_service import DoudizhuClockService
from app.modules.game_impls.doudizhu.doudizhu_constants import (
    PHASE_CALLING,
    PHASE_DOUBLING,
    PHASE_LANDLORD_CONFIRM,
    PHASE_ROBBING,
    PHASE_SHOWING,
    ROLE_FARMER,
    ROLE_LANDLORD,
)
from app.modules.game_impls.doudizhu.doudizhu_event_factory import (
    DoudizhuEventContext,
    DoudizhuEventFactory,
)
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    all_players_decided,
    animation_durations,
    append_multiplier_detail,
    build_phase_auto_advance,
    first_seat_player_id,
    next_calling_player_id,
    next_seat_player_id,
    parse_cards,
    record_seat_action_feedback,
    resolve_bidding_start_seat_index,
)
from app.modules.strategy_turn.schemas import ResolvedGameAction

if TYPE_CHECKING:
    from app.modules.game_impls.doudizhu.doudizhu_deal_phase_service import (
        DoudizhuDealPhaseService,
    )
    from app.modules.game_impls.doudizhu.doudizhu_playing_phase_service import (
        DoudizhuPlayingPhaseService,
    )


class DoudizhuBiddingPhaseService(object):
    """处理斗地主明牌、叫抢地主与加倍阶段。"""

    def __init__(
        self,
        event_factory: DoudizhuEventFactory = None,
        clock_service: DoudizhuClockService = None,
        playing_service: "DoudizhuPlayingPhaseService" = None,
    ) -> None:
        """
        初始化叫抢地主阶段服务。

        :param event_factory: 事件工厂，可空则使用默认实例。
        :param clock_service: 计时服务，可空则使用默认实例。
        :param playing_service: 出牌阶段服务，可空则使用默认实例。
        :return: 无。
        """
        self._events = event_factory or DoudizhuEventFactory()
        self._clock = clock_service or DoudizhuClockService()
        self._playing = playing_service

    def set_playing_service(self, playing_service: "DoudizhuPlayingPhaseService") -> None:
        """
        注入出牌阶段服务（解决循环依赖）。

        :param playing_service: 出牌阶段服务。
        :return: 无。
        """
        self._playing = playing_service

    def enter_showing_phase(self, state: Dict[str, Any]) -> None:
        """
        进入明牌选择阶段。

        :param state: 对局状态。
        :return: 无。
        """
        state["phase"] = PHASE_SHOWING
        state["currentPlayerId"] = first_seat_player_id(state)
        state["phaseAutoAdvance"] = None
        self._clock.stamp_decision_clock(state, "biddingTimeoutSeconds")

    def advance_landlord_confirm(self, state: Dict[str, Any]) -> None:
        """
        地主确认动画结束后进入加倍阶段。

        :param state: 当前状态。
        :return: 无。
        """
        state["phase"] = PHASE_DOUBLING
        state["currentPlayerId"] = first_seat_player_id(state)
        state["phaseAutoAdvance"] = None
        self._clock.stamp_decision_clock(state, "doublingTimeoutSeconds")

    def apply_show_cards(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用明牌操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        rule_config = state.get("ruleConfig") or {}
        multiplier = int(rule_config.get("showCardsMultiplier", 2))
        player["showCards"] = True
        player["showCardsDecided"] = True
        player["personalMultiplier"] = int(player.get("personalMultiplier") or 1) * multiplier
        players[player_id] = player
        state["players"] = players
        record_seat_action_feedback(state, player_id, "SHOW_CARDS")
        append_multiplier_detail(
            state,
            "SHOW_CARDS",
            player_id,
            multiplier,
            "DOUDIZHU_SHOW_CARDS",
        )
        self._events.append(
            context,
            "DOUDIZHU_SHOW_CARDS",
            player_id,
            {"personalMultiplier": player.get("personalMultiplier")},
        )
        self.advance_showing_turn(state)

    def apply_skip_show_cards(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用跳过明牌操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        player["showCardsDecided"] = True
        players[player_id] = player
        state["players"] = players
        record_seat_action_feedback(state, player_id, "SKIP_SHOW_CARDS")
        self._events.append(context, "DOUDIZHU_SKIP_SHOW_CARDS", player_id, {})
        self.advance_showing_turn(state)

    def apply_call_landlord(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用叫地主操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        player["callDecided"] = True
        players[player_id] = player
        state["players"] = players
        state["landlordCandidatePlayerId"] = player_id
        record_seat_action_feedback(state, player_id, "CALL_LANDLORD")
        rule_config = state.get("ruleConfig") or {}
        call_multiplier = int(rule_config.get("callLandlordMultiplier", 1))
        append_multiplier_detail(
            state,
            "CALL_LANDLORD",
            player_id,
            call_multiplier,
            "DOUDIZHU_CALL_LANDLORD",
        )
        self._events.append(
            context,
            "DOUDIZHU_CALL_LANDLORD",
            player_id,
            {"multiplier": call_multiplier},
        )
        self.enter_robbing_phase(state)

    def apply_pass_call(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
        deal_service: "DoudizhuDealPhaseService",
    ) -> None:
        """
        应用不叫地主操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :param deal_service: 发牌阶段服务。
        :return: 无。
        """
        player_id = action.playerId
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        player["callDecided"] = True
        players[player_id] = player
        state["players"] = players
        record_seat_action_feedback(state, player_id, "PASS_CALL")
        self._events.append(context, "DOUDIZHU_PASS_CALL", player_id, {})
        self.advance_calling_turn(state, deal_service, context)

    def apply_rob_landlord(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用抢地主操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        rule_config = state.get("ruleConfig") or {}
        rob_multiplier = int(rule_config.get("robLandlordMultiplier", 2))
        state["globalMultiplier"] = int(state.get("globalMultiplier") or 1) * rob_multiplier
        state["landlordCandidatePlayerId"] = player_id
        record_seat_action_feedback(state, player_id, "ROB_LANDLORD")
        append_multiplier_detail(
            state,
            "ROB_LANDLORD",
            player_id,
            rob_multiplier,
            "DOUDIZHU_ROB_LANDLORD",
        )
        self._events.append(
            context,
            "DOUDIZHU_ROB_LANDLORD",
            player_id,
            {
                "multiplier": rob_multiplier,
                "globalMultiplier": state.get("globalMultiplier"),
            },
        )
        self.record_robbing_response(state, player_id)
        self.advance_after_successful_rob(state, context)

    def apply_pass_rob(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用不抢地主操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        self.record_robbing_response(state, player_id)
        record_seat_action_feedback(state, player_id, "PASS_ROB")
        self._events.append(context, "DOUDIZHU_PASS_ROB", player_id, {})
        self.advance_robbing_turn(state, context)

    def apply_double(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用加倍操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        rule_config = state.get("ruleConfig") or {}
        multiplier = int(rule_config.get("doubleMultiplier", 2))
        player["isDoubled"] = True
        player["doubleDecided"] = True
        player["personalMultiplier"] = int(player.get("personalMultiplier") or 1) * multiplier
        players[player_id] = player
        state["players"] = players
        record_seat_action_feedback(state, player_id, "DOUBLE")
        append_multiplier_detail(
            state,
            "DOUBLE",
            player_id,
            multiplier,
            "DOUDIZHU_DOUBLE",
        )
        self._events.append(
            context,
            "DOUDIZHU_DOUBLE",
            player_id,
            {"personalMultiplier": player.get("personalMultiplier")},
        )
        self.advance_doubling_turn(state)

    def apply_pass_double(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
        context: DoudizhuEventContext,
    ) -> None:
        """
        应用不加倍操作。

        :param state: 对局状态。
        :param action: 已解析操作。
        :param context: 事件上下文。
        :return: 无。
        """
        player_id = action.playerId
        players = state.get("players") or {}
        player = dict(players.get(player_id) or {})
        player["doubleDecided"] = True
        players[player_id] = player
        state["players"] = players
        record_seat_action_feedback(state, player_id, "PASS_DOUBLE")
        self._events.append(context, "DOUDIZHU_PASS_DOUBLE", player_id, {})
        self.advance_doubling_turn(state)

    def enter_calling_phase(self, state: Dict[str, Any]) -> None:
        """
        进入叫地主阶段并确定本轮起叫座位。

        :param state: 对局状态。
        :return: 无。
        """
        player_ids = list(state.get("playerIds") or [])
        start_index = resolve_bidding_start_seat_index(state)
        if start_index is None:
            return
        start_player_id = player_ids[start_index]
        state["phase"] = PHASE_CALLING
        state["callingStartPlayerId"] = start_player_id
        state["callingStartSeatIndex"] = start_index
        state["currentPlayerId"] = start_player_id
        state["landlordCandidatePlayerId"] = None
        state["robPendingPlayerIds"] = []
        state["robRespondedPlayerIds"] = []
        state["phaseAutoAdvance"] = None
        players = state.get("players") or {}
        for player_id in player_ids:
            player = dict(players.get(player_id) or {})
            player["callDecided"] = False
            players[player_id] = player
        state["players"] = players
        self._clock.stamp_decision_clock(state, "biddingTimeoutSeconds")

    def enter_robbing_phase(self, state: Dict[str, Any]) -> None:
        """
        进入抢地主阶段。

        :param state: 对局状态。
        :return: 无。
        """
        caller_id = str(state.get("landlordCandidatePlayerId") or "")
        state["phase"] = PHASE_ROBBING
        state["phaseAutoAdvance"] = None
        state["robRespondedPlayerIds"] = []
        self.assign_robbing_pending_players(
            state,
            self._build_robbing_challenger_order(state, caller_id),
        )

    def record_robbing_response(
        self,
        state: Dict[str, Any],
        player_id: str,
    ) -> None:
        """
        记录当前玩家已经完成本轮抢地主响应。

        每个玩家在抢地主阶段最多响应一次。首叫者只有在其他玩家实际抢地主后，
        才会进入响应队列并占用其唯一一次响应资格。

        :param state: 当前对局状态。
        :param player_id: 已完成响应的玩家 ID。
        :return: 无。
        """
        current_player_id = str(player_id or "")
        responded_player_ids = list(state.get("robRespondedPlayerIds") or [])
        if current_player_id and current_player_id not in responded_player_ids:
            responded_player_ids.append(current_player_id)
        state["robRespondedPlayerIds"] = responded_player_ids

    def assign_robbing_pending_players(
        self,
        state: Dict[str, Any],
        pending_player_ids: List[str],
    ) -> None:
        """
        写入待响应队列并切换到队首玩家。

        :param state: 当前对局状态。
        :param pending_player_ids: 尚未响应的抢地主玩家列表。
        :return: 无。
        """
        state["robPendingPlayerIds"] = pending_player_ids
        if not pending_player_ids:
            self._clock.clear_turn_clock(state)
            return
        state["currentPlayerId"] = pending_player_ids[0]
        self._clock.stamp_decision_clock(state, "biddingTimeoutSeconds")

    def advance_after_successful_rob(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
    ) -> None:
        """
        抢地主成功后仅安排尚未响应的玩家，或直接确认地主。

        :param state: 当前对局状态。
        :param context: 事件上下文。
        :return: 无。
        """
        candidate_player_id = str(state.get("landlordCandidatePlayerId") or "")
        pending_player_ids = self._build_robbing_challenger_order(
            state,
            candidate_player_id,
        )
        if not pending_player_ids:
            self.enter_landlord_confirm_phase(state, context)
            return
        self.assign_robbing_pending_players(state, pending_player_ids)

    def enter_landlord_confirm_phase(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
    ) -> None:
        """
        确认地主身份、发放底牌并进入地主确认展示阶段。

        :param state: 对局状态。
        :param context: 事件上下文。
        :return: 无。
        """
        rule_config = state.get("ruleConfig") or {}
        animation_ms = animation_durations(rule_config)
        landlord_id = str(state.get("landlordCandidatePlayerId") or "")
        state["landlordPlayerId"] = landlord_id
        state["bottomCardsRevealed"] = True
        players = state.get("players") or {}
        bottom_cards = parse_cards(state.get("bottomCards") or [])
        for player_id, player_raw in list(players.items()):
            role = ROLE_LANDLORD if player_id == landlord_id else ROLE_FARMER
            player_raw["role"] = role
            player_raw["isLandlord"] = player_id == landlord_id
            if player_id == landlord_id:
                hand_cards = parse_cards(player_raw.get("handCards") or [])
                hand_cards.extend(bottom_cards)
                player_raw["handCards"] = [card.model_dump() for card in hand_cards]
                player_raw["handCount"] = len(hand_cards)
            players[player_id] = player_raw
        state["players"] = players
        state["phase"] = PHASE_LANDLORD_CONFIRM
        state["currentPlayerId"] = None
        state["robPendingPlayerIds"] = []
        self._clock.clear_turn_clock(state)
        state["phaseAutoAdvance"] = build_phase_auto_advance(
            animation_ms.get("landlordConfirm", 1500)
            + animation_ms.get("bottomCardsReveal", 1200),
            "LANDLORD_CONFIRM",
        )
        self._events.append(
            context,
            "DOUDIZHU_LANDLORD_CONFIRMED",
            landlord_id,
            {
                "playbackMs": animation_ms.get("landlordConfirm", 1500),
                "landlordPlayerId": landlord_id,
                "globalMultiplier": state.get("globalMultiplier"),
            },
        )
        self._events.append(
            context,
            "DOUDIZHU_BOTTOM_CARDS_REVEALED",
            landlord_id,
            {
                "playbackMs": animation_ms.get("bottomCardsReveal", 1200),
                "bottomCards": state.get("bottomCards"),
            },
        )

    def advance_showing_turn(self, state: Dict[str, Any]) -> None:
        """
        推进明牌阶段回合。

        :param state: 对局状态。
        :return: 无。
        """
        if all_players_decided(state, "showCardsDecided"):
            self.enter_calling_phase(state)
            return
        state["currentPlayerId"] = next_seat_player_id(state, state.get("currentPlayerId"))
        self._clock.stamp_decision_clock(state, "biddingTimeoutSeconds")

    def advance_calling_turn(
        self,
        state: Dict[str, Any],
        deal_service: "DoudizhuDealPhaseService",
        context: DoudizhuEventContext,
    ) -> None:
        """
        推进叫地主阶段回合。

        :param state: 对局状态。
        :param deal_service: 发牌阶段服务。
        :param context: 事件上下文。
        :return: 无。
        """
        if all_players_decided(state, "callDecided"):
            if state.get("landlordCandidatePlayerId") is None:
                deal_service.reshuffle_and_redeal(state, context)
            return
        state["currentPlayerId"] = next_calling_player_id(state)
        self._clock.stamp_decision_clock(state, "biddingTimeoutSeconds")

    def advance_robbing_turn(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
    ) -> None:
        """
        推进抢地主阶段回合。

        :param state: 对局状态。
        :param context: 事件上下文。
        :return: 无。
        """
        pending_player_ids = list(state.get("robPendingPlayerIds") or [])
        current_id = str(state.get("currentPlayerId") or "")
        if pending_player_ids and pending_player_ids[0] == current_id:
            pending_player_ids.pop(0)
        if not pending_player_ids:
            self.enter_landlord_confirm_phase(state, context)
            return
        self.assign_robbing_pending_players(state, pending_player_ids)

    @staticmethod
    def _build_robbing_challenger_order(
        state: Dict[str, Any],
        candidate_player_id: str,
    ) -> List[str]:
        """
        按座位顺序构建尚未响应的抢地主挑战者列表。

        :param state: 当前对局状态。
        :param candidate_player_id: 当前地主候选人 ID。
        :return: 依次行动的未响应玩家 ID 列表。
        """
        player_ids = list(state.get("playerIds") or [])
        if candidate_player_id not in player_ids:
            return []
        candidate_index = player_ids.index(candidate_player_id)
        responded_player_ids = {
            str(player_id)
            for player_id in list(state.get("robRespondedPlayerIds") or [])
        }
        return [
            player_ids[(candidate_index + step) % len(player_ids)]
            for step in range(1, len(player_ids))
            if player_ids[(candidate_index + step) % len(player_ids)]
            not in responded_player_ids
        ]

    def advance_doubling_turn(self, state: Dict[str, Any]) -> None:
        """
        推进加倍阶段回合。

        :param state: 对局状态。
        :return: 无。
        """
        if all_players_decided(state, "doubleDecided"):
            if self._playing is not None:
                self._playing.enter_playing_phase(state)
            return
        state["currentPlayerId"] = next_seat_player_id(state, state.get("currentPlayerId"))
        self._clock.stamp_decision_clock(state, "doublingTimeoutSeconds")
