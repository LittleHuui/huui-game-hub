"""UNO 规则上下文与领域事件构造。"""

from typing import Any, Dict

from app.modules.game_impls.uno.schemas import UnoRuleContext, UnoRuntimeState
from app.modules.strategy_turn.schemas import DomainEventDraft


def build_rule_context(
    runtime_state: UnoRuntimeState,
    room_config: Dict[str, Any],
    acting_player_id: str,
) -> UnoRuleContext:
    """构建本次动作的规则上下文及独立事件集合。"""
    return UnoRuleContext(
        runtimeState=runtime_state,
        runtimeRule={},
        roomConfig=room_config,
        actingPlayerId=acting_player_id,
        newEvents=[],
    )


def append_domain_event(
    context: UnoRuleContext,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """向 UNO 规则上下文追加一条领域事件草稿。"""
    context.newEvents.append(
        DomainEventDraft(
            eventType=event_type,
            playerId=context.actingPlayerId,
            payload=dict(payload or {}),
        )
    )
