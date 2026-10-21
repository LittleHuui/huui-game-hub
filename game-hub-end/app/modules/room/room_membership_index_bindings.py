"""成员索引脚本的显式键绑定，预读仅用于确定键集合。"""

import json
from typing import List

from app.core.redis.redis_client import RedisClient
from app.core.redis.redis_keys import RedisKeys


def append_member_index_bindings(
    keys: List[str], game_code: str, player_ids: List[str],
) -> str:
    """将成员索引追加到 KEYS，返回 Lua 使用的一基键位置。"""
    bindings = []
    for player_id in dict.fromkeys(player_ids):
        keys.append(RedisKeys.player_room(player_id))
        item = {"playerId": player_id, "activeKeyIndex": len(keys), "shellKeyIndex": 0}
        if game_code:
            keys.append(RedisKeys.player_managed_shell_room(player_id, game_code))
            item["shellKeyIndex"] = len(keys)
        bindings.append(item)
    return json.dumps(bindings, ensure_ascii=False, separators=(",", ":"))


async def prepare_member_index_bindings(
    redis: RedisClient, keys: List[str], room_id: str, game_code: str,
    changed_player_ids: List[str],
) -> str:
    """预绑定现有及变更成员；原子脚本再次校验完整集合后才可写入。"""
    members = await redis.hgetall_json_strict(RedisKeys.room_players(room_id))
    return append_member_index_bindings(keys, game_code, list(members) + changed_player_ids)
