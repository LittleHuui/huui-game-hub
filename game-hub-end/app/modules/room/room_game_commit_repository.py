"""房间对局 Redis 原子提交仓库。"""

import json
import logging
from typing import Optional

from pydantic import ValidationError

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.room_game_commit_schemas import (
    ActionRequestRecord,
    RoomGameCommit,
    RoomGameCommitResult,
)
from app.modules.room.runtime_snapshot_codec import RuntimeSnapshotCodec, runtime_snapshot_codec
from app.modules.room.room_membership_index_bindings import prepare_member_index_bindings
from app.modules.room.room_membership_index_lua import MEMBERSHIP_FACTS_LUA

logger = logging.getLogger(__name__)

_COMMIT_LUA = MEMBERSHIP_FACTS_LUA + """
local requireMeta = ARGV[10] == '1'
if requireMeta then
  local meta = redis.call('GET', KEYS[3])
  if not meta then
    return cjson.encode({status='ROOM_NOT_FOUND'})
  end
end

if ARGV[5] ~= 'SKIP' then
  local existing = redis.call('GET', KEYS[4])
  if existing then
    local parsed = cjson.decode(existing)
    if parsed.requestHash == ARGV[5] then
      return cjson.encode({
        status='REPLAY',
        committedVersion=tonumber(parsed.committedGameVersion or 0)
      })
    else
      return cjson.encode({status='REQUEST_CONFLICT'})
    end
  end
end

local currentGameVersion = tonumber(redis.call('GET', KEYS[1]) or '0')
if tonumber(ARGV[1]) ~= currentGameVersion then
  return cjson.encode({status='VERSION_CONFLICT', currentVersion=currentGameVersion})
end

if ARGV[11] ~= 'SKIP' then
  local currentRoomVersion = tonumber(redis.call('GET', KEYS[5]) or '0')
  if tonumber(ARGV[11]) ~= currentRoomVersion then
    return cjson.encode({status='VERSION_CONFLICT', currentVersion=currentGameVersion})
  end
end
local memberBindings = cjson.decode(ARGV[17])
if not hasCompleteMemberBindings(KEYS[10], memberBindings) then
  return cjson.encode({status='VERSION_CONFLICT', currentVersion=currentGameVersion})
end

if ARGV[3] == 'DELETE' then
  redis.call('DEL', KEYS[2])
elseif ARGV[3] ~= 'SKIP' then
  redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[9])
end

if ARGV[4] ~= 'SKIP' then
  redis.call('SET', KEYS[3], ARGV[4], 'EX', ARGV[9])
end

redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[9])

if ARGV[12] ~= 'SKIP' then
  redis.call('SET', KEYS[5], ARGV[12], 'EX', ARGV[9])
end

local memberUpserts = cjson.decode(ARGV[13])
local memberDeletes = cjson.decode(ARGV[14])
if KEYS[10] and (next(memberUpserts) ~= nil or #memberDeletes > 0) then
  for playerId, member in pairs(memberUpserts) do
    redis.call('HSET', KEYS[10], playerId, cjson.encode(member))
  end
  for index = 1, #memberDeletes do
    redis.call('HDEL', KEYS[10], memberDeletes[index])
  end
end
redis.call('EXPIRE', KEYS[10], ARGV[9])
local changedPlayerIds = {}
for playerId, _ in pairs(memberUpserts) do table.insert(changedPlayerIds, playerId) end
for _, playerId in ipairs(memberDeletes) do table.insert(changedPlayerIds, playerId) end
applyMemberIndexChanges(KEYS[3], KEYS[10], ARGV[15], memberBindings, changedPlayerIds)
renewOwnedMemberIndexes(KEYS[3], KEYS[10], ARGV[15], memberBindings)

if ARGV[5] ~= 'SKIP' and ARGV[6] ~= '' then
  redis.call('SET', KEYS[4], ARGV[6], 'EX', ARGV[7])
end

if ARGV[8] ~= '[]' and ARGV[8] ~= '' then
  local newItems = cjson.decode(ARGV[8])
  local nextReadyAt = nil
  for index = 1, #newItems do
    local item = newItems[index]
    local outboxId = item.outboxId
    local dedupe = item.dedupeKey
    if dedupe then
      local existingId = redis.call('HGET', KEYS[8], dedupe)
      if existingId then
        local existingRaw = redis.call('HGET', KEYS[6], existingId)
        if existingRaw then
          local existingItem = cjson.decode(existingRaw)
          if existingItem.status ~= 'DONE' and existingItem.status ~= 'DISCARDED' and existingItem.status ~= 'FAILED' then
            outboxId = nil
            local existingAvailableAt = tonumber(existingItem.nextAttemptAt or existingItem.availableAt or item.availableAt)
            if existingAvailableAt and (not nextReadyAt or existingAvailableAt < nextReadyAt) then
              nextReadyAt = existingAvailableAt
            end
          end
        end
      end
    end
    if outboxId then
      redis.call('HSET', KEYS[6], outboxId, cjson.encode(item))
      if dedupe then
        redis.call('HSET', KEYS[8], dedupe, outboxId)
      end
      redis.call('ZADD', KEYS[7], item.availableAt, outboxId)
      local availableAt = tonumber(item.availableAt)
      if availableAt and (not nextReadyAt or availableAt < nextReadyAt) then
        nextReadyAt = availableAt
      end
    end
  end
  redis.call('EXPIRE', KEYS[6], ARGV[9])
  redis.call('EXPIRE', KEYS[7], ARGV[9])
  redis.call('EXPIRE', KEYS[8], ARGV[9])
  if nextReadyAt then
    redis.call('ZADD', KEYS[9], nextReadyAt, ARGV[15])
    redis.call('EXPIRE', KEYS[9], ARGV[16])
  end
end

return cjson.encode({status='COMMITTED', committedVersion=tonumber(ARGV[2])})
"""

ACTION_REQUEST_TTL_SECONDS = 86400


class RoomGameCommitRepository(object):
    """通过 Redis Lua 实现房间对局 CAS 原子提交。"""

    def __init__(
        self,
        redis: RedisClient = redis_client,
        codec: RuntimeSnapshotCodec = runtime_snapshot_codec,
    ) -> None:
        """
        初始化原子提交仓库。

        :param redis: Redis 客户端。
        :param codec: 运行时快照编解码器。
        """
        self._redis = redis
        self._codec = codec

    async def load_request_record(
        self,
        room_id: str,
        player_id: str,
        request_id: str,
    ) -> Optional[ActionRequestRecord]:
        """
        读取玩家动作请求幂等记录。

        :param room_id: 房间 ID。
        :param player_id: 玩家 ID。
        :param request_id: 请求 ID。
        :return: 请求记录；不存在时返回 ``None``。
        """
        normalized_room_id = str(room_id or "").strip()
        normalized_player_id = str(player_id or "").strip()
        normalized_request_id = str(request_id or "").strip()
        if not normalized_room_id or not normalized_player_id or not normalized_request_id:
            return None
        raw = await self._redis.get_json(
            RedisKeys.room_action_request(
                normalized_room_id,
                normalized_player_id,
                normalized_request_id,
            ),
        )
        if raw is None:
            return None
        try:
            return ActionRequestRecord.model_validate(raw)
        except ValidationError:
            logger.warning(
                "invalid action request record, roomId=%s playerId=%s requestId=%s",
                normalized_room_id,
                normalized_player_id,
                normalized_request_id,
            )
            return None

    async def commit(self, commit: RoomGameCommit) -> RoomGameCommitResult:
        """
        原子提交房间对局状态变化。

        :param commit: 提交意图。
        :return: 提交结果。
        :raises BizException: Lua 执行失败或返回不可解析结果。
        """
        normalized_room_id = str(commit.roomId or "").strip()
        request_key = RedisKeys.room_action_request(normalized_room_id, "SKIP", "SKIP")
        keys = [
            RedisKeys.room_game_version(normalized_room_id),
            RedisKeys.room_runtime(normalized_room_id),
            RedisKeys.room_meta(normalized_room_id),
            request_key,
            RedisKeys.room_room_version(normalized_room_id),
            RedisKeys.room_outbox_records(normalized_room_id),
            RedisKeys.room_outbox_due(normalized_room_id),
            RedisKeys.room_outbox_dedupe(normalized_room_id),
            RedisKeys.outbox_ready_rooms(normalized_room_id),
        ]
        keys.append(RedisKeys.room_players(normalized_room_id))
        room_meta = commit.nextRoomMeta
        if room_meta is None:
            room_meta = await self._redis.get_json_strict(RedisKeys.room_meta(normalized_room_id))
        member_bindings = await prepare_member_index_bindings(
            self._redis, keys, normalized_room_id,
            str((room_meta or {}).get("gameCode") or "").strip(),
            list(commit.memberUpserts) + commit.memberDeletes,
        )
        runtime_payload = "SKIP"
        if commit.deleteRuntime:
            runtime_payload = "DELETE"
        elif commit.nextRuntimeSnapshot is not None:
            runtime_payload = json.dumps(
                self._codec.encode(commit.nextRuntimeSnapshot),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        meta_payload = "SKIP"
        if commit.nextRoomMeta is not None:
            meta_payload = json.dumps(
                commit.nextRoomMeta,
                ensure_ascii=False,
                separators=(",", ":"),
            )
        request_hash = "SKIP"
        request_record_payload = ""
        request_record_ttl = str(ACTION_REQUEST_TTL_SECONDS)
        if commit.requestRecord is not None:
            record = commit.requestRecord
            request_key = RedisKeys.room_action_request(
                normalized_room_id,
                record.playerId,
                record.requestId,
            )
            keys[3] = request_key
            request_hash = str(record.requestHash or "").strip()
            request_record_payload = json.dumps(
                record.model_dump(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            ttl_ms = max(int(record.expiresAt) - int(record.createdAt), 1000)
            request_record_ttl = str(max(int(ttl_ms / 1000), 1))
        outbox_payload = json.dumps(
            [item.model_dump() for item in commit.outboxRecords],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        expected_room_version = "SKIP"
        next_room_version = "SKIP"
        if commit.expectedRoomVersion is not None:
            expected_room_version = str(int(commit.expectedRoomVersion))
        if commit.nextRoomVersion is not None:
            next_room_version = str(int(commit.nextRoomVersion))
        args = [
            str(int(commit.expectedGameVersion)),
            str(int(commit.nextGameVersion)),
            runtime_payload,
            meta_payload,
            request_hash,
            request_record_payload,
            request_record_ttl,
            outbox_payload,
            str(int(commit.ttlSeconds)),
            "1",
            expected_room_version,
            next_room_version,
            json.dumps(commit.memberUpserts, ensure_ascii=False, separators=(",", ":")),
            json.dumps(commit.memberDeletes, ensure_ascii=False, separators=(",", ":")),
            normalized_room_id,
            "86400",
            member_bindings,
        ]
        raw_result = await self._redis.eval_raw(_COMMIT_LUA, len(keys), keys, args)
        if raw_result is None:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="房间对局原子提交失败")
        return self._parse_commit_result(raw_result)

    def _parse_commit_result(self, raw_result: object) -> RoomGameCommitResult:
        """
        解析 Lua 返回的提交结果 JSON。

        :param raw_result: Lua 原始返回值。
        :return: 结构化提交结果。
        """
        try:
            if isinstance(raw_result, (bytes, bytearray)):
                raw_result = raw_result.decode("utf-8")
            if not isinstance(raw_result, str):
                raise ValueError("invalid commit result type")
            payload = json.loads(raw_result)
            return RoomGameCommitResult.model_validate(payload)
        except (TypeError, ValueError, ValidationError) as exc:
            raise BizException(
                ErrorCode.SYSTEM_ERROR,
                message="房间对局原子提交结果无效",
            ) from exc


room_game_commit_repository = RoomGameCommitRepository()
