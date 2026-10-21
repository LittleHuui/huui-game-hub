"""终局收敛 Redis 原子提交仓库。"""

import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from app.common.error_code import ErrorCode
from app.common.exceptions import BizException
from app.core.redis.redis_client import RedisClient, redis_client
from app.core.redis.redis_keys import RedisKeys
from app.modules.room.room_membership_index_bindings import (
    append_member_index_bindings,
    prepare_member_index_bindings,
)
from app.modules.room.room_membership_index_lua import MEMBERSHIP_FACTS_LUA

logger = logging.getLogger(__name__)

_CLEANUP_DERIVED_LUA = MEMBERSHIP_FACTS_LUA + """
local roomId = ARGV[1]
local expectedRoomVersion = tonumber(ARGV[2])
local rawMeta = redis.call('GET', KEYS[1])
local memberships = cjson.decode(ARGV[3])
if rawMeta then
  local meta = decodeObject(rawMeta)
  if not meta then return -1 end
  local roomVersion = tonumber(redis.call('GET', KEYS[2]) or '0')
  if meta.status ~= 'waiting' or roomVersion ~= expectedRoomVersion then
    return 0
  end
end
for _, item in ipairs(memberships) do
  item.keepActive = false
  if rawMeta then
    local kind = readMembershipKind(KEYS[1], KEYS[4], roomId, item.playerId)
    if kind == 'INVALID' then return -1 end
    item.keepActive = kind == 'ACTIVE'
  end
end
redis.call('SREM', KEYS[3], roomId)
for _, item in ipairs(memberships) do
  if not item.keepActive then deleteOwnedIndex(KEYS[item.activeKeyIndex], roomId) end
  if item.shellKeyIndex > 0 then deleteOwnedIndex(KEYS[item.shellKeyIndex], roomId) end
end
renewOwnedMemberIndexes(KEYS[1], KEYS[4], roomId, memberships)
return 1
"""

_FINALIZE_LUA = MEMBERSHIP_FACTS_LUA + """
local metaKey = KEYS[1]
local runtimeKey = KEYS[2]
local eventsKey = KEYS[3]
local presenceKey = KEYS[4]
local gameVersionKey = KEYS[5]
local roomVersionKey = KEYS[6]
local playersKey = KEYS[7]
local outboxRecordsKey = KEYS[8]
local outboxDueKey = KEYS[9]
local outboxDedupeKey = KEYS[10]
local outboxReadyRoomsKey = KEYS[11]

local expectedGameVersion = tonumber(ARGV[1])
local expectedRoomVersion = tonumber(ARGV[2])
local nextRoomVersion = tonumber(ARGV[3])
local metaPayload = ARGV[4]
local ttl = tonumber(ARGV[5])
local removePlayerIdsJson = ARGV[6]
local requireSettlementDone = ARGV[7]
local dissolveRoom = ARGV[8]
local cleanupOutboxId = ARGV[9]
local cleanupPayload = ARGV[10]
local cleanupAvailableAt = tonumber(ARGV[11])
local cleanupDedupeKey = ARGV[12]
local commitId = ARGV[13]
local memberBindings = cjson.decode(ARGV[14])

local metaRaw = redis.call('GET', metaKey)
if not metaRaw then
  return cjson.encode({status='ROOM_NOT_FOUND'})
end
local meta = cjson.decode(metaRaw)
if meta.status ~= 'playing' then
  return cjson.encode({status='ALREADY_FINALIZED'})
end

local runtimeRaw = redis.call('GET', runtimeKey)
if requireSettlementDone == '1' and not runtimeRaw then
  return cjson.encode({status='SETTLEMENT_NOT_READY'})
end
if runtimeRaw and requireSettlementDone == '1' then
  local runtime = cjson.decode(runtimeRaw)
  local terminalMetadata = runtime.terminalMetadata
  if terminalMetadata then
    local settlementId = terminalMetadata.settlementId
    local settlementStatus = terminalMetadata.settlementStatus
    if settlementId and settlementId ~= '' then
      if settlementStatus == 'PENDING' or settlementStatus == nil or settlementStatus == '' then
        return cjson.encode({status='SETTLEMENT_NOT_READY'})
      end
    end
  end
end

local currentGameVersion = tonumber(redis.call('GET', gameVersionKey) or '0')
if currentGameVersion ~= expectedGameVersion then
  return cjson.encode({status='VERSION_CONFLICT', currentVersion=currentGameVersion})
end
local currentRoomVersion = tonumber(redis.call('GET', roomVersionKey) or '0')
if currentRoomVersion ~= expectedRoomVersion then
  return cjson.encode({status='ROOM_VERSION_CONFLICT', currentRoomVersion=currentRoomVersion})
end
if not hasCompleteMemberBindings(playersKey, memberBindings) then
  return cjson.encode({status='ROOM_VERSION_CONFLICT', currentRoomVersion=currentRoomVersion})
end

local removeIds = cjson.decode(removePlayerIdsJson)
if dissolveRoom == '1' then
  redis.call('DEL', metaKey)
  redis.call('DEL', runtimeKey)
  redis.call('DEL', eventsKey)
  redis.call('DEL', presenceKey)
  redis.call('DEL', gameVersionKey)
  redis.call('DEL', roomVersionKey)
  redis.call('DEL', playersKey)
else
  redis.call('DEL', runtimeKey)
  redis.call('DEL', eventsKey)
  redis.call('DEL', presenceKey)
  redis.call('SET', metaKey, metaPayload, 'EX', ttl)
  redis.call('SET', roomVersionKey, tostring(nextRoomVersion), 'EX', ttl)
  redis.call('SET', gameVersionKey, '0', 'EX', ttl)
  for index = 1, #removeIds do
    redis.call('HDEL', playersKey, removeIds[index])
  end
  redis.call('EXPIRE', playersKey, ttl)
  renewOwnedMemberIndexes(metaKey, playersKey, meta.roomId, memberBindings)
end
if cleanupOutboxId and cleanupOutboxId ~= '' and cleanupDedupeKey and cleanupDedupeKey ~= '' then
  local existingOutboxId = redis.call('HGET', outboxDedupeKey, cleanupDedupeKey)
  if not existingOutboxId then
    local cleanupPayloadDecoded = cjson.decode(cleanupPayload)
    local cleanupRecord = {
      outboxId = cleanupOutboxId,
      roomId = cleanupPayloadDecoded.roomId,
      sourceCommitId = commitId,
      sourceVersion = expectedGameVersion,
      taskType = 'TERMINAL_DERIVED_CLEANUP',
      payload = cleanupPayloadDecoded,
      status = 'PENDING',
      attemptCount = 0,
      retryCount = 0,
      recoveryCount = 0,
      availableAt = cleanupAvailableAt,
      nextAttemptAt = cleanupAvailableAt,
      leaseUntil = cjson.null,
      lastFailureCode = cjson.null,
      lastFailureReason = cjson.null,
      createdAt = cleanupAvailableAt,
      updatedAt = cleanupAvailableAt,
      dedupeKey = cleanupDedupeKey
    }
    redis.call('HSET', outboxRecordsKey, cleanupOutboxId, cjson.encode(cleanupRecord))
    redis.call('HSET', outboxDedupeKey, cleanupDedupeKey, cleanupOutboxId)
    redis.call('ZADD', outboxDueKey, cleanupAvailableAt, cleanupOutboxId)
    redis.call('ZADD', outboxReadyRoomsKey, cleanupAvailableAt, cleanupPayloadDecoded.roomId)
    redis.call('EXPIRE', outboxRecordsKey, ttl)
    redis.call('EXPIRE', outboxDueKey, ttl)
    redis.call('EXPIRE', outboxDedupeKey, ttl)
    redis.call('EXPIRE', outboxReadyRoomsKey, ttl)
  end
end
return cjson.encode({status='COMMITTED'})
"""


class TerminalFinalizeCommitResult(object):
    """终局原子提交结果。"""

    def __init__(
        self,
        status: str,
        current_version: Optional[int] = None,
        current_room_version: Optional[int] = None,
    ) -> None:
        self.status = status
        self.currentVersion = current_version
        self.currentRoomVersion = current_room_version


class TerminalFinalizeCommitRepository(object):
    """终局收敛 Redis 原子提交。"""

    def __init__(self, redis: RedisClient = redis_client) -> None:
        """
        初始化终局原子提交仓库。

        :param redis: Redis 客户端。
        """
        self._redis = redis

    async def cleanup_derived_indexes(
        self,
        room_id: str,
        terminal_room_version: int,
        game_code: str,
        player_ids: List[str],
    ) -> bool:
        """校验终局代际，保留留房真人占用并清理所属的失效索引。"""
        keys = [
            RedisKeys.room_meta(room_id),
            RedisKeys.room_room_version(room_id),
            RedisKeys.playing_rooms(),
            RedisKeys.room_players(room_id),
        ]
        memberships = append_member_index_bindings(keys, game_code, player_ids)
        result = await self._redis.eval_raw(
            _CLEANUP_DERIVED_LUA, len(keys), keys,
            [room_id, str(terminal_room_version), memberships],
        )
        if int(result or 0) < 0:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="终局成员事实损坏，不能清理索引")
        return int(result or 0) == 1

    async def commit_finalize(
        self,
        room_id: str,
        expected_game_version: int,
        expected_room_version: int,
        next_room_version: int,
        next_meta: Dict[str, Any],
        member_ids_to_remove: List[str],
        require_settlement_done: bool,
        dissolve_room: bool = False,
        cleanup_payload: Optional[Dict[str, Any]] = None,
        cleanup_outbox_id: Optional[str] = None,
        cleanup_dedupe_key: Optional[str] = None,
        cleanup_available_at: Optional[int] = None,
        commit_id: Optional[str] = None,
        ttl_seconds: int = 86400,
    ) -> TerminalFinalizeCommitResult:
        """
        原子执行终局收敛：校验、清 Runtime、更新 meta 与版本、移除成员。

        :param room_id: 房间 ID。
        :param expected_game_version: 期望对局版本。
        :param next_room_version: 下一版房间元数据版本。
        :param next_meta: 下一版房间元信息。
        :param member_ids_to_remove: 需移除的成员 ID 列表。
        :param require_settlement_done: 是否要求结算已完成。
        :param ttl_seconds: key 过期秒数。
        :return: 提交结果。
        """
        normalized_room_id = str(room_id or "").strip()
        if int(expected_room_version) < 0:
            raise ValueError("expected_room_version 必须为非负整数")
        if int(expected_game_version) < 0:
            raise ValueError("expected_game_version 必须为非负整数")
        keys = [
            RedisKeys.room_meta(normalized_room_id),
            RedisKeys.room_runtime(normalized_room_id),
            RedisKeys.room_events(normalized_room_id),
            RedisKeys.room_presence(normalized_room_id),
            RedisKeys.room_game_version(normalized_room_id),
            RedisKeys.room_room_version(normalized_room_id),
            RedisKeys.room_players(normalized_room_id),
            RedisKeys.room_outbox_records(normalized_room_id),
            RedisKeys.room_outbox_due(normalized_room_id),
            RedisKeys.room_outbox_dedupe(normalized_room_id),
            RedisKeys.outbox_ready_rooms(normalized_room_id),
        ]
        remove_ids = []
        for player_id in member_ids_to_remove or []:
            normalized_player_id = str(player_id or "").strip()
            if normalized_player_id:
                remove_ids.append(normalized_player_id)
        member_bindings = await prepare_member_index_bindings(
            self._redis, keys, normalized_room_id, str(next_meta.get("gameCode") or "").strip(), [],
        )
        args = [
            str(int(expected_game_version)),
            str(int(expected_room_version)),
            str(int(next_room_version)),
            json.dumps(next_meta, ensure_ascii=False, separators=(",", ":")),
            str(int(ttl_seconds)),
            json.dumps(remove_ids, ensure_ascii=False, separators=(",", ":")),
            "1" if require_settlement_done else "0",
            "1" if dissolve_room else "0",
            str(cleanup_outbox_id or ""),
            json.dumps(cleanup_payload or {}, ensure_ascii=False, separators=(",", ":")),
            str(int(cleanup_available_at or 0)),
            str(cleanup_dedupe_key or ""),
            str(commit_id or ""),
            member_bindings,
        ]
        raw_result = await self._redis.eval_raw(_FINALIZE_LUA, len(keys), keys, args)
        return self._parse_result(raw_result)

    def _parse_result(self, raw_result: object) -> TerminalFinalizeCommitResult:
        """
        解析 Lua 返回结果。

        :param raw_result: Lua 原始返回值。
        :return: 结构化结果。
        """
        try:
            if isinstance(raw_result, (bytes, bytearray)):
                raw_result = raw_result.decode("utf-8")
            if not isinstance(raw_result, str):
                raise ValueError("invalid finalize result type")
            payload = json.loads(raw_result)
            status = str(payload.get("status", "")).strip()
            current_version = payload.get("currentVersion")
            current_room_version = payload.get("currentRoomVersion")
            if current_version is not None:
                current_version = int(current_version)
            if current_room_version is not None:
                current_room_version = int(current_room_version)
            return TerminalFinalizeCommitResult(
                status,
                current_version,
                current_room_version,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise BizException(ErrorCode.SYSTEM_ERROR, message="终局原子提交结果无效") from exc


terminal_finalize_commit_repository = TerminalFinalizeCommitRepository()
