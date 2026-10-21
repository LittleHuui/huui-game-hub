"""五子棋领域事件构造。"""

from typing import Any, Dict, List

from app.modules.strategy_turn.schemas import DomainEventDraft


def make_action_event(
    event_type: str,
    player_id: str,
    payload: Dict[str, Any],
) -> List[DomainEventDraft]:
    """构造五子棋动作事件草稿列表，不写入游戏状态。"""
    return [
        DomainEventDraft(
            eventType=event_type,
            playerId=player_id,
            payload=dict(payload or {}),
        )
    ]
