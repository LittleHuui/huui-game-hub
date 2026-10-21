"""房间级 Outbox Redis Lua 脚本。"""

# 损坏外层只隔离为审计记录；不推断原动作，也不重新执行领域动作。
_PROTECTED_OUTBOX_RECORD_LUA = """
local function refreshOutboxReady(dueKey, leaseKey, readyKey, roomId, nowMs, readyTtl)
  local leaseTtl = redis.call('PTTL', leaseKey)
  local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
  local nextAt = nil
  if leaseTtl > 0 then nextAt = nowMs + leaseTtl
  elseif #nextIds >= 2 then nextAt = tonumber(nextIds[2]) end
  if nextAt then
    redis.call('ZADD', readyKey, nextAt, roomId)
    redis.call('EXPIRE', readyKey, readyTtl)
  else
    redis.call('ZREM', readyKey, roomId)
  end
end

local function readOutboxRecord(recordsKey, dueKey, leaseKey, outboxId, raw, roomId, nowMs, readyKey, readyTtl)
  local decoded, item = pcall(cjson.decode, raw)
  local valid = decoded and type(item) == 'table'
  local allowed = {outboxId=true, roomId=true, sourceCommitId=true, sourceVersion=true,
    taskType=true, payload=true, status=true, attemptCount=true, retryCount=true,
    recoveryCount=true, availableAt=true, nextAttemptAt=true, leaseUntil=true,
    lastFailureCode=true, lastFailureReason=true, createdAt=true, updatedAt=true, dedupeKey=true}
  local statuses = {PENDING=true, PROCESSING=true, RECOVERING=true, DONE=true, DISCARDED=true, FAILED=true}
  if valid then
    for key, value in pairs(item) do
      if not allowed[key] then valid = false end
    end
    for _, field in ipairs({'outboxId', 'roomId', 'sourceCommitId', 'taskType'}) do
      if type(item[field]) ~= 'string' or item[field] == '' then valid = false end
    end
    if item.outboxId ~= outboxId or item.roomId ~= roomId then valid = false end
    if type(item.status) ~= 'string' or not statuses[item.status] then valid = false end
    for _, field in ipairs({'sourceVersion', 'availableAt', 'createdAt', 'updatedAt'}) do
      local value = tonumber(item[field])
      if not value or value < 0 or value % 1 ~= 0 then valid = false end
    end
    for _, field in ipairs({'attemptCount', 'retryCount', 'recoveryCount'}) do
      local value = item[field] == nil and 0 or tonumber(item[field])
      if not value or value < 0 or value % 1 ~= 0 then valid = false
      else item[field] = value end
    end
    for _, field in ipairs({'nextAttemptAt', 'leaseUntil'}) do
      if item[field] == cjson.null then item[field] = nil end
      if item[field] ~= nil then
        local value = tonumber(item[field])
        if not value or value < 0 or value % 1 ~= 0 then valid = false end
      end
    end
    for _, field in ipairs({'lastFailureCode', 'lastFailureReason', 'dedupeKey'}) do
      if item[field] == cjson.null then item[field] = nil end
      if item[field] ~= nil and type(item[field]) ~= 'string' then valid = false end
    end
    if type(item.payload) ~= 'table' then valid = false
    else
      for key, value in pairs(item.payload) do
        if type(key) ~= 'string' then valid = false end
      end
    end
    if item.status == 'PROCESSING' and not tonumber(item.leaseUntil) then valid = false end
  end
  if valid then return item end
  local audit = {outboxId=outboxId, roomId=roomId, sourceCommitId='corrupt-record',
    sourceVersion=0, taskType='CORRUPT_RECORD', payload={rawRecord=raw}, status='FAILED',
    attemptCount=0, retryCount=0, recoveryCount=0, availableAt=nowMs,
    createdAt=nowMs, updatedAt=nowMs, lastFailureCode='OUTBOX_RECORD_CORRUPT',
    lastFailureReason='外层记录损坏，已隔离；禁止重放领域动作'}
  redis.call('HSET', recordsKey, outboxId, cjson.encode(audit))
  redis.call('ZREM', dueKey, outboxId)
  if redis.call('GET', leaseKey) == outboxId then redis.call('DEL', leaseKey) end
  refreshOutboxReady(dueKey, leaseKey, readyKey, roomId, nowMs, readyTtl)
  return audit
end
"""

# 读取与恢复索引共用受保护解析；坏记录的 due/lease/ready 在读取时原子收敛。
READ_ROOM_OUTBOX_RECORDS_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local readyRoomsKey = KEYS[3]
local dispatchLeaseKey = KEYS[4]
local roomId = ARGV[1]
local outboxId = ARGV[2]
local nowMs = tonumber(ARGV[3])
local readyTtl = tonumber(ARGV[4])
local ids = outboxId ~= '' and {outboxId} or redis.call('HKEYS', recordsKey)
local records = {}
for _, id in ipairs(ids) do
  local raw = redis.call('HGET', recordsKey, id)
  if raw then
    table.insert(records, readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, id, raw, roomId, nowMs, readyRoomsKey, readyTtl))
  end
end
return cjson.encode(records)
"""

# Claim：恢复过期租约并领取 PENDING 记录。
CLAIM_ROOM_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local dedupeKey = KEYS[3]
local readyRoomsKey = KEYS[4]
local dispatchLeaseKey = KEYS[5]
local nowMs = tonumber(ARGV[1])
local leaseMs = tonumber(ARGV[2])
local scanLimit = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])
local roomId = ARGV[6]
local readyTtl = tonumber(ARGV[7])

local claimed = {}
local candidates = redis.call('ZRANGEBYSCORE', dueKey, '-inf', nowMs, 'LIMIT', 0, scanLimit)

local activeLease = redis.call('GET', dispatchLeaseKey)
if activeLease then
  local activeLeaseTtl = redis.call('PTTL', dispatchLeaseKey)
  if activeLeaseTtl and activeLeaseTtl > 0 then
    redis.call('ZADD', readyRoomsKey, nowMs + activeLeaseTtl, roomId)
    if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
  end
  return cjson.encode(claimed)
end

for i = 1, #candidates do
  local outboxId = candidates[i]
  local raw = redis.call('HGET', recordsKey, outboxId)
  if raw then
    local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
    local status = item.status

    if status == 'PROCESSING' then
      if item.leaseUntil and tonumber(item.leaseUntil) <= nowMs then
        item.recoveryCount = tonumber(item.recoveryCount or 0) + 1
        item.status = 'PENDING'
        item.leaseUntil = nil
        item.availableAt = nowMs
        item.updatedAt = nowMs
        redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
        redis.call('ZADD', dueKey, nowMs, outboxId)
        status = 'PENDING'
      end
    end

    if status == 'PENDING' and tonumber(item.availableAt or 0) <= nowMs then
      local acquired = redis.call('SET', dispatchLeaseKey, outboxId, 'NX', 'PX', leaseMs)
      if acquired then
        item.status = 'PROCESSING'
        item.attemptCount = tonumber(item.attemptCount or 0) + 1
        item.leaseUntil = nowMs + leaseMs
        item.updatedAt = nowMs
        redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
        table.insert(claimed, item)
      end
      break
    end
  end
end

local nextAttemptAt = nil
local dispatchLeaseTtl = redis.call('PTTL', dispatchLeaseKey)
if dispatchLeaseTtl and dispatchLeaseTtl > 0 then
  nextAttemptAt = nowMs + dispatchLeaseTtl
else
  local scheduledIds = redis.call('ZRANGE', dueKey, 0, -1, 'WITHSCORES')
  for index = 1, #scheduledIds, 2 do
    local scheduledId = scheduledIds[index]
    local scheduledRaw = redis.call('HGET', recordsKey, scheduledId)
    if scheduledRaw then
      local scheduledItem = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, scheduledId, scheduledRaw, roomId, nowMs, readyRoomsKey, readyTtl)
      local scheduledStatus = scheduledItem.status
      local candidateAt = nil
      if scheduledStatus == 'PENDING' then
        candidateAt = tonumber(scheduledItem.availableAt or scheduledItem.nextAttemptAt or 0)
      elseif scheduledStatus == 'PROCESSING' and scheduledItem.leaseUntil then
        candidateAt = tonumber(scheduledItem.leaseUntil)
      end
      if candidateAt and (not nextAttemptAt or candidateAt < nextAttemptAt) then
        nextAttemptAt = candidateAt
      end
    end
  end
end
if nextAttemptAt then
  redis.call('ZADD', readyRoomsKey, nextAttemptAt, roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end

if #claimed > 0 then
  redis.call('EXPIRE', recordsKey, ttl)
  redis.call('EXPIRE', dueKey, ttl)
  redis.call('EXPIRE', dedupeKey, ttl)
end
return cjson.encode(claimed)
"""

# Claim Ready Rooms：读取到期房间；实际领取与 ready 索引迁移由房间 Claim 脚本原子完成。
CLAIM_READY_ROOMS_LUA = """
local readyRoomsKey = KEYS[1]
local nowMs = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])

if not nowMs then
  return cjson.encode({})
end

if not limit or limit <= 0 then
  return cjson.encode({})
end

local roomIds = redis.call('ZRANGEBYSCORE', readyRoomsKey, '-inf', nowMs, 'LIMIT', 0, limit)
if #roomIds == 0 then
  return cjson.encode({})
end
return cjson.encode(roomIds)
"""

# Mark Ready Room：写入或刷新房间下一次可执行时间。
MARK_ROOM_READY_LUA = """
local readyRoomsKey = KEYS[1]
local roomId = ARGV[1]
local nextAttemptAt = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])

if not roomId or roomId == '' or not nextAttemptAt then
  return 0
end

redis.call('ZADD', readyRoomsKey, nextAttemptAt, roomId)
if ttl and ttl > 0 then
  redis.call('EXPIRE', readyRoomsKey, ttl)
end
return 1
"""

# Remove Ready Room：从 ready 索引中删除房间。
REMOVE_ROOM_READY_LUA = """
local readyRoomsKey = KEYS[1]
local roomId = ARGV[1]

if not roomId or roomId == '' then
  return 0
end

redis.call('ZREM', readyRoomsKey, roomId)
return 1
"""

# Ack：标记 DONE 并从 due 索引移除。
ACK_ROOM_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local readyRoomsKey = KEYS[3]
local dispatchLeaseKey = KEYS[4]
local outboxId = ARGV[1]
local nowMs = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local roomId = ARGV[4]
local readyTtl = tonumber(ARGV[5])

local raw = redis.call('HGET', recordsKey, outboxId)
if not raw then
  return 0
end
local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
if item.taskType == 'CORRUPT_RECORD' then return 0 end
item.status = 'DONE'
item.leaseUntil = nil
item.updatedAt = nowMs
redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
redis.call('ZREM', dueKey, outboxId)
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
redis.call('EXPIRE', recordsKey, ttl)
redis.call('EXPIRE', dueKey, ttl)
if redis.call('GET', dispatchLeaseKey) == outboxId then redis.call('DEL', dispatchLeaseKey) end
return 1
"""

# Retry：临时失败后退避重试；是否耗尽由 Dispatcher/Service 决策。
RETRY_ROOM_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local readyRoomsKey = KEYS[3]
local dispatchLeaseKey = KEYS[4]
local outboxId = ARGV[1]
local nowMs = tonumber(ARGV[2])
local backoffMs = tonumber(ARGV[3])
local failureCode = ARGV[4]
local reason = ARGV[5]
local ttl = tonumber(ARGV[6])
local roomId = ARGV[7]
local readyTtl = tonumber(ARGV[8])

local raw = redis.call('HGET', recordsKey, outboxId)
if not raw then
  return 0
end
local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
if item.taskType == 'CORRUPT_RECORD' then return 0 end
item.leaseUntil = nil
item.lastFailureCode = failureCode
item.lastFailureReason = reason
item.updatedAt = nowMs
item.retryCount = tonumber(item.retryCount or 0) + 1
item.status = 'PENDING'
item.availableAt = nowMs + backoffMs
item.nextAttemptAt = item.availableAt
redis.call('ZADD', dueKey, item.availableAt, outboxId)
redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
redis.call('EXPIRE', recordsKey, ttl)
redis.call('EXPIRE', dueKey, ttl)
if redis.call('GET', dispatchLeaseKey) == outboxId then redis.call('DEL', dispatchLeaseKey) end
return 1
"""

# Recover：短重试耗尽后进入恢复周期，保留同一 Outbox 记录。
RECOVER_ROOM_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local readyRoomsKey = KEYS[3]
local dispatchLeaseKey = KEYS[4]
local outboxId = ARGV[1]
local nowMs = tonumber(ARGV[2])
local backoffMs = tonumber(ARGV[3])
local failureCode = ARGV[4]
local reason = ARGV[5]
local ttl = tonumber(ARGV[6])
local roomId = ARGV[7]
local readyTtl = tonumber(ARGV[8])

local raw = redis.call('HGET', recordsKey, outboxId)
if not raw then
  return 0
end
local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
if item.taskType == 'CORRUPT_RECORD' then return 0 end
item.status = 'PENDING'
item.leaseUntil = nil
item.retryCount = 0
item.recoveryCount = tonumber(item.recoveryCount or 0) + 1
item.lastFailureCode = failureCode
item.lastFailureReason = reason
item.availableAt = nowMs + backoffMs
item.nextAttemptAt = item.availableAt
item.updatedAt = nowMs
redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
redis.call('ZADD', dueKey, item.availableAt, outboxId)
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
redis.call('EXPIRE', recordsKey, ttl)
redis.call('EXPIRE', dueKey, ttl)
if redis.call('GET', dispatchLeaseKey) == outboxId then redis.call('DEL', dispatchLeaseKey) end
return 1
"""

# Settlement Retry：结算失败终局尚未提交前始终保持可调度。
RETRY_GAME_SETTLEMENT_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local readyRoomsKey = KEYS[3]
local dispatchLeaseKey = KEYS[4]
local outboxId = ARGV[1]
local nowMs = tonumber(ARGV[2])
local backoffMs = tonumber(ARGV[3])
local reason = ARGV[4]
local ttl = tonumber(ARGV[5])
local roomId = ARGV[6]
local readyTtl = tonumber(ARGV[7])

local raw = redis.call('HGET', recordsKey, outboxId)
if not raw then
  return 0
end
local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
if item.taskType == 'CORRUPT_RECORD' then return 0 end
item.status = 'PENDING'
item.leaseUntil = nil
item.retryCount = tonumber(item.retryCount or 0) + 1
item.lastFailureReason = reason
item.availableAt = nowMs + backoffMs
item.nextAttemptAt = item.availableAt
item.updatedAt = nowMs
redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
redis.call('ZADD', dueKey, item.availableAt, outboxId)
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
redis.call('EXPIRE', recordsKey, ttl)
redis.call('EXPIRE', dueKey, ttl)
if redis.call('GET', dispatchLeaseKey) == outboxId then redis.call('DEL', dispatchLeaseKey) end
return 1
"""

# Discard：业务过期或状态已变化，不再重试。
DISCARD_ROOM_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local dedupeKey = KEYS[3]
local readyRoomsKey = KEYS[4]
local dispatchLeaseKey = KEYS[5]
local outboxId = ARGV[1]
local nowMs = tonumber(ARGV[2])
local reason = ARGV[3]
local ttl = tonumber(ARGV[4])
local roomId = ARGV[5]
local readyTtl = tonumber(ARGV[6])

local raw = redis.call('HGET', recordsKey, outboxId)
if not raw then
  return 0
end
local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
if item.taskType == 'CORRUPT_RECORD' then return 0 end
item.status = 'DISCARDED'
item.leaseUntil = nil
item.lastFailureReason = reason
item.updatedAt = nowMs
redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
redis.call('ZREM', dueKey, outboxId)
if item.dedupeKey then
  redis.call('HDEL', dedupeKey, item.dedupeKey)
end
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
redis.call('EXPIRE', recordsKey, ttl)
redis.call('EXPIRE', dueKey, ttl)
redis.call('EXPIRE', dedupeKey, ttl)
if redis.call('GET', dispatchLeaseKey) == outboxId then redis.call('DEL', dispatchLeaseKey) end
return 1
"""

# Fail：合同错误或非法 payload，保留记录供排查。
FAIL_ROOM_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local readyRoomsKey = KEYS[3]
local dispatchLeaseKey = KEYS[4]
local outboxId = ARGV[1]
local nowMs = tonumber(ARGV[2])
local reason = ARGV[3]
local ttl = tonumber(ARGV[4])
local roomId = ARGV[5]
local readyTtl = tonumber(ARGV[6])

local raw = redis.call('HGET', recordsKey, outboxId)
if not raw then
  return 0
end
local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
if item.taskType == 'CORRUPT_RECORD' then return 0 end
item.status = 'FAILED'
item.leaseUntil = nil
item.lastFailureCode = reason
item.lastFailureReason = reason
item.updatedAt = nowMs
redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
redis.call('ZREM', dueKey, outboxId)
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
redis.call('EXPIRE', recordsKey, ttl)
redis.call('EXPIRE', dueKey, ttl)
if redis.call('GET', dispatchLeaseKey) == outboxId then redis.call('DEL', dispatchLeaseKey) end
return 1
"""

# Cleanup：删除已到保留期的终态记录并同步清理 due/dedupe。
CLEANUP_ROOM_OUTBOX_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local dedupeKey = KEYS[3]
local readyRoomsKey = KEYS[4]
local dispatchLeaseKey = KEYS[5]
local nowMs = tonumber(ARGV[1])
local doneRetentionMs = tonumber(ARGV[2])
local failedRetentionMs = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])
local roomId = ARGV[5]
local readyTtl = tonumber(ARGV[6])

local allFields = redis.call('HKEYS', recordsKey)
local removed = 0
for i = 1, #allFields do
  local outboxId = allFields[i]
  local raw = redis.call('HGET', recordsKey, outboxId)
  if raw then
    local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
    local status = item.status
    local updatedAt = tonumber(item.updatedAt or 0)
    local shouldRemove = false
    if status == 'DONE' or status == 'DISCARDED' then
      if updatedAt + doneRetentionMs <= nowMs then
        shouldRemove = true
      end
    elseif status == 'FAILED' then
      if updatedAt + failedRetentionMs <= nowMs then
        shouldRemove = true
      end
    end
    if shouldRemove then
      redis.call('HDEL', recordsKey, outboxId)
      redis.call('ZREM', dueKey, outboxId)
      if item.dedupeKey then
        redis.call('HDEL', dedupeKey, item.dedupeKey)
      end
      removed = removed + 1
    end
  end
end
if removed > 0 then
  redis.call('EXPIRE', recordsKey, ttl)
  redis.call('EXPIRE', dueKey, ttl)
  redis.call('EXPIRE', dedupeKey, ttl)
end
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
return removed
"""

# Clear：房间解散时清空全部 Outbox 结构。
CLEAR_ROOM_OUTBOX_LUA = """
redis.call('DEL', KEYS[1])
redis.call('DEL', KEYS[2])
redis.call('DEL', KEYS[3])
redis.call('ZREM', KEYS[4], ARGV[1])
redis.call('DEL', KEYS[5])
return 1
"""

# Recover：将租约已过期的 PROCESSING 记录恢复为 PENDING。
RECOVER_ROOM_OUTBOX_LEASES_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local readyRoomsKey = KEYS[3]
local dispatchLeaseKey = KEYS[4]
local nowMs = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local roomId = ARGV[3]
local readyTtl = tonumber(ARGV[4])

local allFields = redis.call('HKEYS', recordsKey)
local recovered = 0
for i = 1, #allFields do
  local outboxId = allFields[i]
  local raw = redis.call('HGET', recordsKey, outboxId)
  if raw then
    local item = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, outboxId, raw, roomId, nowMs, readyRoomsKey, readyTtl)
    if item.status == 'PROCESSING' and item.leaseUntil and tonumber(item.leaseUntil) <= nowMs then
      item.recoveryCount = tonumber(item.recoveryCount or 0) + 1
      item.status = 'PENDING'
      item.leaseUntil = nil
      item.availableAt = nowMs
      item.updatedAt = nowMs
      redis.call('HSET', recordsKey, outboxId, cjson.encode(item))
      redis.call('ZADD', dueKey, nowMs, outboxId)
      if redis.call('GET', dispatchLeaseKey) == outboxId then redis.call('DEL', dispatchLeaseKey) end
      recovered = recovered + 1
    end
  end
end
if recovered > 0 then
  redis.call('EXPIRE', recordsKey, ttl)
  redis.call('EXPIRE', dueKey, ttl)
end
local nextIds = redis.call('ZRANGE', dueKey, 0, 0, 'WITHSCORES')
if #nextIds >= 2 then
  redis.call('ZADD', readyRoomsKey, tonumber(nextIds[2]), roomId)
  if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
else
  redis.call('ZREM', readyRoomsKey, roomId)
end
return recovered
"""

ENQUEUE_ROOM_OUTBOX_IF_ABSENT_LUA = _PROTECTED_OUTBOX_RECORD_LUA + """
local recordsKey = KEYS[1]
local dueKey = KEYS[2]
local dedupeKey = KEYS[3]
local readyRoomsKey = KEYS[4]
local dispatchLeaseKey = KEYS[5]
local outboxId = ARGV[1]
local dedupeKeyValue = ARGV[2]
local recordPayload = ARGV[3]
local availableAt = tonumber(ARGV[4])
local roomId = ARGV[5]
local ttl = tonumber(ARGV[6])
local readyTtl = tonumber(ARGV[7])

if not outboxId or outboxId == '' or not dedupeKeyValue or dedupeKeyValue == '' then
  return 0
end
local existing = redis.call('HGET', dedupeKey, dedupeKeyValue)
if existing then
  local existingRaw = redis.call('HGET', recordsKey, existing)
  if existingRaw then
    local existingItem = readOutboxRecord(recordsKey, dueKey, dispatchLeaseKey, existing, existingRaw, roomId, availableAt, readyRoomsKey, readyTtl)
    if existingItem.taskType == 'CORRUPT_RECORD' then return 2 end
    local status = existingItem.status
    if status == 'PENDING' or status == 'PROCESSING' or status == 'RECOVERING' then
      redis.call('ZADD', readyRoomsKey, tonumber(existingItem.nextAttemptAt or existingItem.availableAt or availableAt), roomId)
      if readyTtl and readyTtl > 0 then redis.call('EXPIRE', readyRoomsKey, readyTtl) end
      return 2
    end
  end
end
redis.call('HSET', recordsKey, outboxId, recordPayload)
redis.call('HSET', dedupeKey, dedupeKeyValue, outboxId)
redis.call('ZADD', dueKey, availableAt, outboxId)
redis.call('ZADD', readyRoomsKey, availableAt, roomId)
redis.call('EXPIRE', recordsKey, ttl)
redis.call('EXPIRE', dueKey, ttl)
redis.call('EXPIRE', dedupeKey, ttl)
redis.call('EXPIRE', readyRoomsKey, readyTtl)
return 1
"""
