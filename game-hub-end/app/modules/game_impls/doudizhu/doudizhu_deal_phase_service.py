"""斗地主发牌阶段服务。"""

from typing import Any, Dict, TYPE_CHECKING

from app.modules.game_impls.doudizhu.doudizhu_clock_service import DoudizhuClockService
from app.modules.game_impls.doudizhu.doudizhu_constants import (
    PHASE_DEALING,
    PHASE_LAIZI_REVEAL,
)
from app.modules.game_impls.doudizhu.doudizhu_deck_factory import (
    build_shuffled_deck,
    deal_initial_cards,
)
from app.modules.game_impls.doudizhu.doudizhu_event_factory import (
    DoudizhuEventContext,
    DoudizhuEventFactory,
)
from app.modules.game_impls.doudizhu.doudizhu_laizi_rule import (
    generate_laizi_rank_code,
    mark_laizi_on_cards,
    rank_value_for_code,
)
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    animation_durations,
    build_phase_auto_advance,
    clear_seat_action_feedback,
    empty_player_state,
)
from app.modules.game_seed.doudizhu_seed import DOUDIZHU_ONLINE_GAME_RULE_SEED

if TYPE_CHECKING:
    from app.modules.game_impls.doudizhu.doudizhu_bidding_phase_service import (
        DoudizhuBiddingPhaseService,
    )


class DoudizhuDealPhaseService(object):
    """处理斗地主发牌、癞子揭示与重新发牌。"""

    def __init__(
        self,
        event_factory: DoudizhuEventFactory = None,
        clock_service: DoudizhuClockService = None,
    ) -> None:
        """
        初始化发牌阶段服务。

        :param event_factory: 事件工厂，可空则使用默认实例。
        :param clock_service: 计时服务，可空则使用默认实例。
        :return: 无。
        """
        self._events = event_factory or DoudizhuEventFactory()
        self._clock = clock_service or DoudizhuClockService()

    def start_dealing_round(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
    ) -> None:
        """
        开始一轮发牌；癞子玩法先确定并展示癞子点数。

        :param state: 当前状态。
        :param context: 事件上下文。
        :return: 无。
        """
        rule_config = state.get("ruleConfig") or {}
        animation_ms = animation_durations(rule_config)
        if bool(state.get("enableLaizi")):
            self.enter_laizi_reveal_display(state, context, animation_ms)
        else:
            self.prepare_dealing_display(state, context)

    def advance_dealing(
        self,
        state: Dict[str, Any],
        bidding_service: "DoudizhuBiddingPhaseService",
    ) -> None:
        """
        发牌展示结束后进入明牌阶段。

        :param state: 当前状态。
        :param bidding_service: 叫抢地主阶段服务。
        :return: 无。
        """
        bidding_service.enter_showing_phase(state)

    def advance_laizi_reveal(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
    ) -> None:
        """
        癞子揭示展示结束后洗牌并进入发牌展示阶段。

        :param state: 当前状态。
        :param context: 事件上下文。
        :return: 无。
        """
        self.prepare_dealing_display(state, context)

    def prepare_dealing_display(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
    ) -> None:
        """
        预先发牌并生成阻塞展示事件，保持 dealing 非玩家阶段。

        :param state: 当前状态。
        :param context: 事件上下文。
        :return: 无。
        """
        rule_config = state.get("ruleConfig") or {}
        animation_ms = animation_durations(rule_config)
        player_ids = list(state.get("playerIds") or [])
        hand_count = int(rule_config.get("handCount", 17))
        bottom_count = int(rule_config.get("bottomCardCount", 3))
        deck = build_shuffled_deck(DOUDIZHU_ONLINE_GAME_RULE_SEED, shuffle=True)
        deck = mark_laizi_on_cards(
            deck,
            state.get("laiziRankCode"),
            bool(state.get("enableLaizi")),
        )
        deal_result = deal_initial_cards(deck, player_ids, hand_count, bottom_count)
        state["bottomCards"] = [card.model_dump() for card in deal_result.bottomCards]
        players = state.get("players") or {}
        for player_id in player_ids:
            hand_cards = deal_result.playerHands.get(player_id, [])
            player = dict(players.get(player_id) or {})
            player["handCards"] = [card.model_dump() for card in hand_cards]
            player["handCount"] = len(hand_cards)
            players[player_id] = player
        state["players"] = players
        state["dealingRound"] = int(state.get("dealingRound") or 0) + 1
        state["phase"] = PHASE_DEALING
        state["phaseStep"] = "DEAL_DISPLAY"
        state["currentPlayerId"] = None
        self._clock.clear_turn_clock(state)
        deal_ms = animation_ms.get("dealing", 1000)
        state["phaseAutoAdvance"] = build_phase_auto_advance(
            deal_ms * 2,
            "DEALING",
        )
        self._events.append(
            context,
            "DOUDIZHU_DEAL_STARTED",
            None,
            {"playbackMs": deal_ms},
        )
        self._events.append(
            context,
            "DOUDIZHU_DEAL_FINISHED",
            None,
            {
                "playbackMs": deal_ms,
                "playerHandCounts": {
                    player_id: len(deal_result.playerHands.get(player_id, []))
                    for player_id in player_ids
                },
            },
        )

    def enter_laizi_reveal_display(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
        animation_ms: Dict[str, int],
    ) -> None:
        """
        独立确定癞子并生成展示事件，等待自动推进后再洗牌发牌。

        :param state: 当前状态。
        :param context: 事件上下文。
        :param animation_ms: 动画时长配置。
        :return: 无。
        """
        laizi_rank_code = generate_laizi_rank_code()
        state["laiziRankCode"] = laizi_rank_code
        state["laiziRankValue"] = rank_value_for_code(laizi_rank_code)
        state["laiziCardCodes"] = sorted(
            card.cardCode
            for card in DOUDIZHU_ONLINE_GAME_RULE_SEED.cardDefinitions
            if card.rankCode == laizi_rank_code
        )
        self._events.append(
            context,
            "DOUDIZHU_LAIZI_REVEALED",
            None,
            {
                "playbackMs": animation_ms.get("laiziReveal", 1200),
                "laiziRankCode": laizi_rank_code,
                "laiziRankValue": state.get("laiziRankValue"),
                "laiziCardCodes": state.get("laiziCardCodes"),
            },
        )
        state["phase"] = PHASE_LAIZI_REVEAL
        state["phaseStep"] = "LAIZI_REVEAL_DISPLAY"
        state["currentPlayerId"] = None
        self._clock.clear_turn_clock(state)
        state["phaseAutoAdvance"] = build_phase_auto_advance(
            animation_ms.get("laiziReveal", 1200),
            "LAIZI_REVEAL",
        )

    def reshuffle_and_redeal(
        self,
        state: Dict[str, Any],
        context: DoudizhuEventContext,
    ) -> None:
        """
        三人都不叫时重新发牌。

        :param state: 对局状态。
        :param context: 事件上下文。
        :return: 无。
        """
        player_ids = list(state.get("playerIds") or [])
        players = {}
        for seat_index, player_id in enumerate(player_ids):
            players[player_id] = empty_player_state(player_id, seat_index)
        state["players"] = players
        state["bottomCards"] = []
        state["bottomCardsRevealed"] = False
        state["laiziRankCode"] = None
        state["laiziRankValue"] = None
        state["laiziCardCodes"] = []
        state["landlordCandidatePlayerId"] = None
        state["landlordPlayerId"] = None
        clear_seat_action_feedback(state)
        state["globalMultiplier"] = 1
        state["multiplierDetails"] = []
        state["currentPlayerId"] = None
        self._clock.clear_turn_clock(state)
        state["callingStartPlayerId"] = None
        state["callingStartSeatIndex"] = None
        state["robPendingPlayerIds"] = []
        state["robRespondedPlayerIds"] = []
        self.start_dealing_round(state, context)
