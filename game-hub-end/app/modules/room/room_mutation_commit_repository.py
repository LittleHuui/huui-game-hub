"""Room 聚合 Redis Lua 原子提交仓库。"""

import json

from pydantic import ValidationError

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.room_membership_index_bindings import prepare_member_index_bindings
from app.modules.room.room_membership_index_lua import MEMBERSHIP_FACTS_LUA
from app.modules.room.room_mutation_commit_schemas import (
    RoomMutationCommit,
    RoomMutationCommitResult,
)

_ROOM_MUTATION_LUA = MEMBERSHIP_FACTS_LUA + """
local metaKey = KEYS[1]
local playersKey = KEYS[2]
local roomVersionKey = KEYS[3]
local runtimeKey = KEYS[4]
local gameVersionKey = KEYS[5]
local eventsKey = KEYS[6]
local presenceKey = KEYS[7]

local expectedVersion = tonumber(ARGV[1])
local nextVersion = tonumber(ARGV[2])
local metaPayload = ARGV[3]
local upserts = cjson.decode(ARGV[4])
local deletes = cjson.decode(ARGV[5])
local ttl = tonumber(ARGV[6])
local deleteRoom = ARGV[7] == '1'
local roomId = ARGV[8]
local claimPlayerId = ARGV[9]
local changedPlayerIds = cjson.decode(ARGV[10])
local hasGameIndex = ARGV[11] == '1'
local memberBindings = cjson.decode(ARGV[12])

local metaExists = redis.call('EXISTS', metaKey)
if expectedVersion >= 0 and metaExists == 0 then
  return cjson.encode({status='ROOM_NOT_FOUND'})
end
local currentVersion = tonumber(redis.call('GET', roomVersionKey) or '0')
if expectedVersion >= 0 and currentVersion ~= expectedVersion then
  return cjson.encode({
    status='VERSION_CONFLICT',
    currentRoomVersion=currentVersion
  })
end
if expectedVersion < 0 and (metaExists == 1 or currentVersion ~= 0) then
  return cjson.encode({
    status='VERSION_CONFLICT',
    currentRoomVersion=currentVersion
  })
end

if not hasCompleteMemberBindings(playersKey, memberBindings) then
  return cjson.encode({status='VERSION_CONFLICT', currentRoomVersion=currentVersion})
end

if claimPlayerId ~= '' then
  local indexedRoomId = redis.call('GET', KEYS[9])
  if indexedRoomId and indexedRoomId ~= roomId then
    return cjson.encode({status='PLAYER_ALREADY_IN_ROOM'})
  end
end

if deleteRoom then
  for _, item in ipairs(memberBindings) do
    deleteOwnedIndex(KEYS[item.activeKeyIndex], roomId)
    if item.shellKeyIndex > 0 then deleteOwnedIndex(KEYS[item.shellKeyIndex], roomId) end
  end
  redis.call('DEL', metaKey)
  redis.call('DEL', playersKey)
  redis.call('DEL', roomVersionKey)
  redis.call('DEL', runtimeKey)
  redis.call('DEL', gameVersionKey)
  redis.call('DEL', eventsKey)
  redis.call('DEL', presenceKey)
  if hasGameIndex then redis.call('SREM', KEYS[8], roomId) end
  return cjson.encode({
    status='COMMITTED',
    committedRoomVersion=nextVersion
  })
end

redis.call('SET', metaKey, metaPayload, 'EX', ttl)
for index = 1, #upserts do
  local item = upserts[index]
  redis.call('HSET', playersKey, item.playerId, cjson.encode(item.member))
end
for index = 1, #deletes do
  redis.call('HDEL', playersKey, deletes[index])
end
redis.call('EXPIRE', playersKey, ttl)
redis.call('SET', roomVersionKey, tostring(nextVersion), 'EX', ttl)
if hasGameIndex then
  redis.call('SADD', KEYS[8], roomId)
  if redis.call('TTL', KEYS[8]) < ttl then redis.call('EXPIRE', KEYS[8], ttl) end
end
if claimPlayerId ~= '' then
  redis.call('SET', KEYS[9], roomId, 'EX', ttl)
end
applyMemberIndexChanges(metaKey, playersKey, roomId, memberBindings, changedPlayerIds)
renewOwnedMemberIndexes(metaKey, playersKey, roomId, memberBindings)
return cjson.encode({
  status='COMMITTED',
  committedRoomVersion=nextVersion
})
"""


class RoomMutationCommitRepository(object):
    """通过单实例 Redis Lua 提交 Room 聚合与成员占用索引。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        """初始化 Room 聚合提交仓库。"""
        self._redis = redis

    async def commit(self, commit: RoomMutationCommit) -> RoomMutationCommitResult:
        """
        原子提交 Room 聚合变更。
        :param commit: Room 聚合提交意图。
        :return: 提交结果。
        """
        room_id = str(commit.roomId).strip()
        game_code = str(commit.nextMeta.get("gameCode") or "").strip()
        keys = [
            RedisKeys.room_meta(room_id),
            RedisKeys.room_players(room_id),
            RedisKeys.room_room_version(room_id),
            RedisKeys.room_runtime(room_id),
            RedisKeys.room_game_version(room_id),
            RedisKeys.room_events(room_id),
            RedisKeys.room_presence(room_id),
            RedisKeys.game_rooms(game_code) if game_code else RedisKeys.room_meta(room_id),
        ]
        if commit.claimPlayerId:
            keys.append(RedisKeys.player_room(commit.claimPlayerId))
        changed_player_ids = list(dict.fromkeys(
            [item.playerId for item in commit.memberUpserts] + commit.memberDeletes,
        ))
        member_bindings = await prepare_member_index_bindings(
            self._redis, keys, room_id, game_code, changed_player_ids,
        )
        upserts = [item.model_dump() for item in commit.memberUpserts]
        args = [
            str(int(commit.expectedRoomVersion)),
            str(int(commit.nextRoomVersion)),
            json.dumps(commit.nextMeta, ensure_ascii=False, separators=(",", ":")),
            json.dumps(upserts, ensure_ascii=False, separators=(",", ":")),
            json.dumps(commit.memberDeletes, ensure_ascii=False, separators=(",", ":")),
            str(int(commit.ttlSeconds)),
            "1" if commit.deleteRoom else "0",
            room_id,
            commit.claimPlayerId or "",
            json.dumps(changed_player_ids),
            "1" if game_code else "0",
            member_bindings,
        ]
        raw = await self._redis.eval_raw(_ROOM_MUTATION_LUA, len(keys), keys, args)
        try:
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")
            return RoomMutationCommitResult.model_validate(json.loads(str(raw)))
        except (TypeError, ValueError, ValidationError) as exc:
            raise BizException(
                ErrorCode.SYSTEM_ERROR,
                message="Room 聚合原子提交结果无效",
            ) from exc


room_mutation_commit_repository = RoomMutationCommitRepository()
