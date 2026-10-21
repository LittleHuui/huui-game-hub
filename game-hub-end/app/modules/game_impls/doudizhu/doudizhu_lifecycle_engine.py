"""斗地主生命周期引擎。"""

from typing import Any, Dict

from app.common.exceptions import ValidationException
from app.modules.game_impls.doudizhu.doudizhu_bidding_phase_service import (
    DoudizhuBiddingPhaseService,
)
from app.modules.game_impls.doudizhu.doudizhu_clock_service import DoudizhuClockService
from app.modules.game_impls.doudizhu.doudizhu_constants import (
    ACTION_CALL_LANDLORD,
    ACTION_DOUBLE,
    ACTION_PASS,
    ACTION_PASS_CALL,
    ACTION_PASS_DOUBLE,
    ACTION_PASS_ROB,
    ACTION_PLAY_CARDS,
    ACTION_ROB_LANDLORD,
    ACTION_SHOW_CARDS,
    ACTION_SKIP_SHOW_CARDS,
    PHASE_DEALING,
    PHASE_FINISHED,
    PHASE_LANDLORD_CONFIRM,
    PHASE_LAIZI_REVEAL,
    PHASE_SETTLEMENT,
)
from app.modules.game_impls.doudizhu.doudizhu_deal_phase_service import (
    DoudizhuDealPhaseService,
)
from app.modules.game_impls.doudizhu.doudizhu_event_factory import DoudizhuEventFactory
from app.modules.game_impls.doudizhu.doudizhu_playing_phase_service import (
    DoudizhuPlayingPhaseService,
)
from app.modules.game_impls.doudizhu.doudizhu_settlement_service import (
    DoudizhuSettlementService,
)
from app.modules.game_impls.doudizhu.doudizhu_state_codec import parse_state
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    empty_player_state,
    resolve_room_config,
    resolve_rule_config,
    resolve_settlement_display_duration_ms,
)
from app.modules.strategy_turn.lifecycle import GameLifecycleEngine
from app.modules.strategy_turn.schemas import (
    ActionOutcome,
    AdvanceOutcome,
    InitialStateOutcome,
    ResolvedGameAction,
    StrategyTurnRuntimeRule,
    TerminalDirective,
    TheoreticalPlayerSettlement,
    TheoreticalSettlement,
)


class DoudizhuLifecycleEngine(GameLifecycleEngine):
    """斗地主生命周期编排：发牌、叫抢地主、出牌与结算。"""

    def __init__(
        self,
        event_factory: DoudizhuEventFactory = None,
        clock_service: DoudizhuClockService = None,
        settlement_service: DoudizhuSettlementService = None,
        deal_service: DoudizhuDealPhaseService = None,
        bidding_service: DoudizhuBiddingPhaseService = None,
        playing_service: DoudizhuPlayingPhaseService = None,
    ) -> None:
        """
        初始化生命周期引擎及各阶段服务。

        :param event_factory: 事件工厂，可空则使用默认实例。
        :param clock_service: 计时服务，可空则使用默认实例。
        :param settlement_service: 结算服务，可空则使用默认实例。
        :param deal_service: 发牌阶段服务，可空则使用默认实例。
        :param bidding_service: 叫抢地主阶段服务，可空则使用默认实例。
        :param playing_service: 出牌阶段服务，可空则使用默认实例。
        :return: 无。
        """
        self._events = event_factory or DoudizhuEventFactory()
        self._clock = clock_service or DoudizhuClockService()
        self._settlement = settlement_service or DoudizhuSettlementService(
            event_factory=self._events,
            clock_service=self._clock,
        )
        self._deal = deal_service or DoudizhuDealPhaseService(
            event_factory=self._events,
            clock_service=self._clock,
        )
        self._playing = playing_service or DoudizhuPlayingPhaseService(
            event_factory=self._events,
            clock_service=self._clock,
            settlement_service=self._settlement,
        )
        self._bidding = bidding_service or DoudizhuBiddingPhaseService(
            event_factory=self._events,
            clock_service=self._clock,
            playing_service=self._playing,
        )
        if bidding_service is None:
            self._bidding.set_playing_service(self._playing)

    def build_initial_state(
        self,
        runtime_rule: StrategyTurnRuntimeRule,
    ) -> InitialStateOutcome:
        """
        构建斗地主初始状态；癞子玩法先揭示点数，再发牌。

        :param runtime_rule: 运行时规则。
        :return: 初始状态结果。
        """
        player_ids = list(runtime_rule.playerIds)
        if len(player_ids) != 3:
            raise ValidationException("斗地主需要且仅需要 3 名玩家")
        room_config = resolve_room_config(runtime_rule)
        rule_config = resolve_rule_config()
        players = {}
        for seat_index, player_id in enumerate(player_ids):
            players[player_id] = empty_player_state(player_id, seat_index)
        state = {
            "phase": PHASE_DEALING,
            "phaseStep": "DEAL_DISPLAY",
            "playerIds": player_ids,
            "players": players,
            "bottomCards": [],
            "bottomCardsRevealed": False,
            "enableLaizi": bool(room_config.get("enableLaizi", False)),
            "laiziRankCode": None,
            "laiziRankValue": None,
            "laiziCardCodes": [],
            "currentPlayerId": None,
            "callingStartPlayerId": None,
            "callingStartSeatIndex": None,
            "biddingStartSeed": None,
            "robPendingPlayerIds": [],
            "robRespondedPlayerIds": [],
            "landlordCandidatePlayerId": None,
            "landlordPlayerId": None,
            "lastPlay": None,
            "lastPlayCards": [],
            "lastPlayPlayerId": None,
            "lastActionEvent": None,
            "passPlayerIds": [],
            "consecutivePassCount": 0,
            "roundLeadPlayerId": None,
            "globalMultiplier": 1,
            "multiplierDetails": [],
            "bombCount": 0,
            "rocketCount": 0,
            "currentTurnStartedAt": None,
            "currentTurnDeadlineAt": None,
            "winnerRole": None,
            "springType": None,
            "settlement": None,
            "dealingRound": 0,
            "roomConfig": room_config,
            "ruleConfig": rule_config,
            "phaseAutoAdvance": None,
        }
        context = self._events.build_context()
        self._deal.start_dealing_round(state, context)
        return InitialStateOutcome(
            state=state,
            events=self._events.collect(context),
            gameOver=self.is_game_over(state),
        )

    def apply_resolved_action(
        self,
        state: Dict[str, Any],
        action: ResolvedGameAction,
    ) -> ActionOutcome:
        """
        按 actionType/payload 直接应用已解析操作。

        :param state: 当前对局状态。
        :param action: 已解析操作。
        :return: 动作执行结果。
        """
        working = parse_state(state)
        phase = str(working.get("phase") or "")
        if phase == PHASE_FINISHED:
            raise ValidationException("对局已结束，无法继续操作")
        player_id = str(action.playerId).strip()
        if player_id != str(working.get("currentPlayerId") or "").strip():
            raise ValidationException("当前不是该玩家行动")
        context = self._events.build_context()
        action_type = str(action.actionType or "").strip()
        if action_type == ACTION_SHOW_CARDS:
            self._bidding.apply_show_cards(working, action, context)
        elif action_type == ACTION_SKIP_SHOW_CARDS:
            self._bidding.apply_skip_show_cards(working, action, context)
        elif action_type == ACTION_CALL_LANDLORD:
            self._bidding.apply_call_landlord(working, action, context)
        elif action_type == ACTION_PASS_CALL:
            self._bidding.apply_pass_call(working, action, context, self._deal)
        elif action_type == ACTION_ROB_LANDLORD:
            self._bidding.apply_rob_landlord(working, action, context)
        elif action_type == ACTION_PASS_ROB:
            self._bidding.apply_pass_rob(working, action, context)
        elif action_type == ACTION_DOUBLE:
            self._bidding.apply_double(working, action, context)
        elif action_type == ACTION_PASS_DOUBLE:
            self._bidding.apply_pass_double(working, action, context)
        elif action_type == ACTION_PLAY_CARDS:
            self._playing.apply_play_cards(working, action, context)
        elif action_type == ACTION_PASS:
            self._playing.apply_pass(working, action, context)
        else:
            raise ValidationException("不支持的操作类型: {0}".format(action_type))
        return ActionOutcome(
            resolvedAction=action,
            state=working,
            events=self._events.collect(context),
            gameOver=self.is_game_over(working),
        )

    def advance(
        self,
        state: Dict[str, Any],
    ) -> AdvanceOutcome:
        """
        推进自动阶段（发牌、癞子揭示、地主确认、结算）。

        :param state: 当前对局状态。
        :return: 推进结果。
        """
        working = parse_state(state)
        phase = str(working.get("phase") or "")
        if phase in (
            PHASE_DEALING,
            PHASE_LAIZI_REVEAL,
            PHASE_LANDLORD_CONFIRM,
            PHASE_SETTLEMENT,
        ):
            working["phaseAutoAdvance"] = None
        context = self._events.build_context()
        if phase == PHASE_DEALING:
            self._deal.advance_dealing(working, self._bidding)
        elif phase == PHASE_LAIZI_REVEAL:
            self._deal.advance_laizi_reveal(working, context)
        elif phase == PHASE_LANDLORD_CONFIRM:
            self._bidding.advance_landlord_confirm(working)
        elif phase == PHASE_SETTLEMENT:
            self._settlement.advance_settlement(working)
        return AdvanceOutcome(
            state=working,
            events=self._events.collect(context),
            gameOver=self.is_game_over(working),
        )

    def is_game_over(
        self,
        state: Dict[str, Any],
    ) -> bool:
        """
        判断对局是否已结束。

        :param state: 当前对局状态。
        :return: 仅 ``finished`` 阶段为 ``True``。
        """
        return str(state.get("phase") or "") == PHASE_FINISHED

    def build_terminal_directive(
        self,
        state: Dict[str, Any],
        runtime_rule: StrategyTurnRuntimeRule,
    ):
        """
        构建斗地主平台终局指令，携带理论零和结算。

        :param state: 当前对局状态。
        :param runtime_rule: 运行时规则。
        :return: 终局指令。
        """
        del runtime_rule
        display_duration_ms = resolve_settlement_display_duration_ms(state)
        settlement_raw = state.get("settlement")
        if not isinstance(settlement_raw, dict):
            return TerminalDirective(
                requiresPlatformSettlement=False,
                displayDurationMs=display_duration_ms,
            )
        player_settlements = []
        for item in settlement_raw.get("playerSettlements") or []:
            if not isinstance(item, dict):
                continue
            player_id = str(item.get("playerId", "")).strip()
            if not player_id:
                continue
            player_settlements.append(
                TheoreticalPlayerSettlement(
                    playerId=player_id,
                    expectedDelta=int(item.get("scoreDelta") or 0),
                ),
            )
        rule_details = {
            "landlordPlayerId": settlement_raw.get("landlordPlayerId"),
            "winnerRole": settlement_raw.get("winnerRole"),
            "baseScore": settlement_raw.get("baseScore"),
            "globalMultiplier": settlement_raw.get("globalMultiplier"),
            "springType": settlement_raw.get("springType"),
            "multiplierDetails": settlement_raw.get("multiplierDetails"),
        }
        return TerminalDirective(
            requiresPlatformSettlement=True,
            settlementType="doudizhu_score",
            theoreticalSettlement=TheoreticalSettlement(
                settlementType="doudizhu_score",
                playerSettlements=player_settlements,
                ruleDetails=rule_details,
            ),
            displayDurationMs=display_duration_ms,
        )
