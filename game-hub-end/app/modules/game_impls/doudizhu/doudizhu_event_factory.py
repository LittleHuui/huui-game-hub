"""斗地主领域事件工厂。"""

from typing import Any, Dict, List, Optional

from app.modules.strategy_turn.schemas import DomainEventDraft


class DoudizhuEventContext(object):
    """斗地主事件收集上下文。"""

    def __init__(self) -> None:
        """初始化空事件列表。"""
        self.events = []


class DoudizhuEventFactory(object):
    """生成斗地主领域事件草稿。"""

    def build_context(self) -> DoudizhuEventContext:
        """
        构建空事件上下文。

        :return: 事件上下文。
        """
        return DoudizhuEventContext()

    def append(
        self,
        context: DoudizhuEventContext,
        event_type: str,
        player_id: Optional[str],
        payload: Dict[str, Any],
    ) -> None:
        """
        向上下文追加一条领域事件草稿。

        :param context: 事件上下文。
        :param event_type: 事件类型。
        :param player_id: 关联玩家 ID。
        :param payload: 事件载荷。
        :return: 无。
        """
        context.events.append(
            DomainEventDraft(
                eventType=event_type,
                playerId=player_id,
                payload=dict(payload or {}),
            )
        )

    def collect(self, context: Optional[DoudizhuEventContext]) -> List[DomainEventDraft]:
        """
        读取上下文已收集的事件草稿。

        :param context: 事件上下文；为空时返回空列表。
        :return: 领域事件草稿列表。
        """
        if context is None:
            return []
        return self._normalize_drafts(context.events)

    def _normalize_drafts(self, raw_events: List[Any]) -> List[DomainEventDraft]:
        """
        将原始事件列表规范化为领域事件草稿。

        :param raw_events: 原始事件列表。
        :return: 领域事件草稿列表。
        """
        drafts = []
        for item in raw_events or []:
            if isinstance(item, DomainEventDraft):
                drafts.append(item)
                continue
            if isinstance(item, dict):
                drafts.append(
                    DomainEventDraft(
                        eventType=str(item.get("eventType") or ""),
                        playerId=item.get("playerId"),
                        payload=dict(item.get("payload") or {}),
                    )
                )
        return drafts
