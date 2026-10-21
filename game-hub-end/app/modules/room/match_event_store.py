"""完整对局事件归档存储。"""

from typing import List

from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.modules.strategy_turn.schemas import GameEvent


class MatchEventStore(object):
    """在 Runtime 裁剪之外保存完整事件序列。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        """初始化事件归档存储。"""
        self._redis = redis

    async def archive(
        self,
        room_id: str,
        events: List[GameEvent],
        ttl_seconds: int = 86400,
    ) -> None:
        """
        按 sequence 幂等合并完整事件。
        :param room_id: 房间 ID。
        :param events: 当前快照保留的事件。
        :param ttl_seconds: 归档 TTL。
        """
        key = RedisKeys.room_events(room_id)
        existing = await self._redis.get_json(key)
        rows = existing if isinstance(existing, list) else []
        by_sequence = {
            int(row.get("sequence")): row
            for row in rows
            if isinstance(row, dict) and row.get("sequence") is not None
        }
        for event in events:
            by_sequence[int(event.sequence)] = event.model_dump()
        ordered = [by_sequence[index] for index in sorted(by_sequence)]
        await self._redis.set_json(key, ordered, int(ttl_seconds))

    async def load(self, room_id: str) -> List[GameEvent]:
        """
        加载完整事件归档。
        :param room_id: 房间 ID。
        :return: 全量事件。
        """
        raw = await self._redis.get_json(RedisKeys.room_events(room_id))
        if not isinstance(raw, list):
            return []
        return [GameEvent.model_validate(item) for item in raw]


match_event_store = MatchEventStore()
