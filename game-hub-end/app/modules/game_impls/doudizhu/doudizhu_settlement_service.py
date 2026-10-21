"""斗地主结算阶段服务。"""

from typing import Any, Dict, Optional

from app.modules.game_impls.doudizhu.doudizhu_clock_service import DoudizhuClockService
from app.modules.game_impls.doudizhu.doudizhu_constants import (
    ANTI_SPRING,
    PHASE_FINISHED,
    PHASE_SETTLEMENT,
    SPRING,
    WINNER_FARMER,
    WINNER_LANDLORD,
)
from app.modules.game_impls.doudizhu.doudizhu_event_factory import (
    DoudizhuEventContext,
    DoudizhuEventFactory,
)
from app.modules.game_impls.doudizhu.doudizhu_score_rule import (
    DoudizhuScoreInput,
    build_settlement,
)
from app.modules.game_impls.doudizhu.doudizhu_state_helpers import (
    animation_durations,
    apply_global_multiplier,
    build_phase_auto_advance,
)


class DoudizhuSettlementService(object):
    """处理斗地主终局结算与结算展示推进。"""

    def __init__(
        self,
        event_factory: DoudizhuEventFactory = None,
        clock_service: DoudizhuClockService = None,
    ) -> None:
        """
        初始化结算服务。

        :param event_factory: 事件工厂，可空则使用默认实例。
        :param clock_service: 计时服务，可空则使用默认实例。
        :return: 无。
        """
        self._events = event_factory or DoudizhuEventFactory()
        self._clock = clock_service or DoudizhuClockService()

    def advance_settlement(self, state: Dict[str, Any]) -> None:
        """
        结算展示结束后进入终局阶段。

        :param state: 当前状态。
        :return: 无。
        """
        state["phase"] = PHASE_FINISHED
        state["currentPlayerId"] = None
        self._clock.clear_turn_clock(state)
        state["phaseAutoAdvance"] = None

    def enter_settlement_phase(
        self,
        state: Dict[str, Any],
        winner_player_id: str,
        context: DoudizhuEventContext,
    ) -> None:
        """
        进入结算阶段并生成结算数据。

        :param state: 对局状态。
        :param winner_player_id: 出完牌的玩家 ID。
        :param context: 事件上下文。
        :return: 无。
        """
        rule_config = state.get("ruleConfig") or {}
        animation_ms = animation_durations(rule_config)
        landlord_id = str(state.get("landlordPlayerId") or "")
        landlord_won = winner_player_id == landlord_id
        winner_role = WINNER_LANDLORD if landlord_won else WINNER_FARMER
        spring_type = self.detect_spring_type(state, landlord_won)
        if spring_type is not None:
            multiplier = int(rule_config.get("springMultiplier", 2))
            apply_global_multiplier(
                state,
                spring_type,
                None,
                multiplier,
                "DOUDIZHUSPRING",
            )
            state["springType"] = spring_type
            self._events.append(
                context,
                "DOUDIZHUSPRING",
                None,
                {
                    "springType": spring_type,
                    "globalMultiplier": state.get("globalMultiplier"),
                },
            )
        state["winnerRole"] = winner_role
        settlement = build_settlement(
            DoudizhuScoreInput(
                player_ids=list(state.get("playerIds") or []),
                landlord_player_id=landlord_id,
                winner_role=winner_role,
                global_multiplier=int(state.get("globalMultiplier") or 1),
                base_score=int(rule_config.get("baseScore", 1)),
                spring_type=spring_type,
                multiplier_details={"entries": list(state.get("multiplierDetails") or [])},
            )
        )
        state["settlement"] = settlement.model_dump()
        state["phase"] = PHASE_SETTLEMENT
        state["currentPlayerId"] = None
        self._clock.clear_turn_clock(state)
        state["phaseAutoAdvance"] = build_phase_auto_advance(
            animation_ms.get("settlement", 2200),
            "SETTLEMENT",
        )
        self._events.append(
            context,
            "DOUDIZHU_SETTLEMENT_STARTED",
            winner_player_id,
            {
                "playbackMs": animation_ms.get("settlement", 2200),
                "winnerRole": winner_role,
                "settlement": state.get("settlement"),
            },
        )

    def detect_spring_type(
        self,
        state: Dict[str, Any],
        landlord_won: bool,
    ) -> Optional[str]:
        """
        检测春天或反春天。

        :param state: 对局状态。
        :param landlord_won: 地主是否获胜。
        :return: 春天类型或 ``None``。
        """
        rule_config = state.get("ruleConfig") or {}
        if not bool(rule_config.get("enableSpring", True)):
            return None
        players = state.get("players") or {}
        landlord_id = str(state.get("landlordPlayerId") or "")
        if landlord_won:
            for player_id, player_raw in players.items():
                if player_id == landlord_id:
                    continue
                if int(player_raw.get("playCount") or 0) != 0:
                    return None
            return SPRING
        landlord_raw = players.get(landlord_id) or {}
        if int(landlord_raw.get("playCount") or 0) == 1:
            return ANTI_SPRING
        return None
