"""成员派生索引的原子事实核对、重建与归属清理。"""

MEMBERSHIP_FACTS_LUA = """
local function decodeObject(raw)
  if not raw then return nil end
  local ok, value = pcall(cjson.decode, raw)
  if not ok or type(value) ~= 'table' or not string.match(raw, '^%s*{') then
    return nil
  end
  return value
end

local function classifyMembershipRoom(meta, roomId)
  if not meta or meta.roomId ~= roomId or type(meta.status) ~= 'string' then
    return 'INVALID'
  end
  if meta.gameCode == nil or meta.gameCode == cjson.null then meta.gameCode = '' end
  if type(meta.gameCode) ~= 'string' then return 'INVALID' end
  if meta.status ~= 'waiting' and meta.status ~= 'playing' then
    return 'STALE'
  end
  return 'ACTIVE'
end

local function classifyMembership(meta, rawMember, roomId, playerId)
  local roomStatus = classifyMembershipRoom(meta, roomId)
  if roomStatus ~= 'ACTIVE' then return roomStatus end
  if not rawMember then return 'STALE' end
  local member = decodeObject(rawMember)
  if not member or member.playerId ~= playerId
      or type(member.isAi) ~= 'boolean' or type(member.isManaged) ~= 'boolean' then
    return 'INVALID'
  end
  local shell = member.isManaged and member.managedMode == 'shell'
  if member.isAi then return 'STALE' end
  if shell then
    -- shell 索引按游戏定位；缺少游戏编码的席位既不建空索引，也不占 active。
    return meta.status == 'playing' and meta.gameCode ~= '' and 'SHELL' or 'STALE'
  end
  return 'ACTIVE'
end

local function readMembershipKind(metaKey, playersKey, roomId, playerId)
  local rawMeta = redis.call('GET', metaKey)
  if not rawMeta then return 'STALE' end
  local meta = decodeObject(rawMeta)
  local rawMember = redis.call('HGET', playersKey, playerId)
  return classifyMembership(meta, rawMember, roomId, playerId), meta
end

local function readMembership(metaKey, playersKey, roomId, playerId, kind, gameCode)
  local status, meta = readMembershipKind(metaKey, playersKey, roomId, playerId)
  if status == 'INVALID' then return status end
  if kind == 'active' and status == 'ACTIVE' then return 'ACTIVE', meta end
  if kind == 'shell' and status == 'SHELL' and meta.gameCode == gameCode then return 'ACTIVE', meta end
  return 'STALE'
end

local function deleteOwnedIndex(key, roomId)
  if redis.call('GET', key) ~= roomId then return 0 end
  return redis.call('DEL', key)
end

local function hasCompleteMemberBindings(playersKey, bindings)
  local bound = {}
  for _, item in ipairs(bindings) do bound[item.playerId] = true end
  for _, playerId in ipairs(redis.call('HKEYS', playersKey)) do
    if not bound[playerId] then return false end
  end
  return true
end

local function renewOwnedMemberIndexes(metaKey, playersKey, roomId, bindings)
  local meta = decodeObject(redis.call('GET', metaKey))
  if classifyMembershipRoom(meta, roomId) ~= 'ACTIVE' then return end
  local ttl = math.min(redis.call('TTL', metaKey), redis.call('TTL', playersKey))
  if ttl < 1 then return end
  for _, item in ipairs(bindings) do
    local kind = readMembershipKind(metaKey, playersKey, roomId, item.playerId)
    local index = 0
    if kind == 'ACTIVE' then index = item.activeKeyIndex end
    if kind == 'SHELL' then index = item.shellKeyIndex end
    if index > 0 and redis.call('GET', KEYS[index]) == roomId then
      redis.call('EXPIRE', KEYS[index], ttl)
    end
  end
end

local function applyMemberIndexChanges(metaKey, playersKey, roomId, bindings, changedPlayerIds)
  local changed = {}
  for _, playerId in ipairs(changedPlayerIds) do changed[playerId] = true end
  local ttl = math.min(redis.call('TTL', metaKey), redis.call('TTL', playersKey))
  for _, item in ipairs(bindings) do
    if changed[item.playerId] then
      local kind = readMembershipKind(metaKey, playersKey, roomId, item.playerId)
      if kind ~= 'INVALID' then
        if kind ~= 'ACTIVE' then deleteOwnedIndex(KEYS[item.activeKeyIndex], roomId) end
        if item.shellKeyIndex > 0 then
          if kind ~= 'SHELL' then
            deleteOwnedIndex(KEYS[item.shellKeyIndex], roomId)
          elseif ttl > 0 then
            local owner = redis.call('GET', KEYS[item.shellKeyIndex])
            if not owner or owner == roomId then
              redis.call('SET', KEYS[item.shellKeyIndex], roomId, 'EX', ttl)
            end
          end
        end
      end
    end
  end
end
"""

LIST_MEMBERSHIP_CANDIDATES_LUA = MEMBERSHIP_FACTS_LUA + """
local rawMeta = redis.call('GET', KEYS[1])
if not rawMeta then return cjson.encode({status='STALE'}) end
local meta = decodeObject(rawMeta)
local roomStatus = classifyMembershipRoom(meta, ARGV[1])
if roomStatus ~= 'ACTIVE' then return cjson.encode({status=roomStatus}) end
local members = {}
for _, playerId in ipairs(redis.call('HKEYS', KEYS[2])) do
  local kind = classifyMembership(meta, redis.call('HGET', KEYS[2], playerId), ARGV[1], playerId)
  if kind == 'INVALID' then return cjson.encode({status='INVALID'}) end
  if kind == 'ACTIVE' or kind == 'SHELL' then
    table.insert(members, {playerId=playerId, kind=kind})
  end
end
return cjson.encode({status='ACTIVE', gameCode=meta.gameCode, members=members})
"""

RESOLVE_MEMBERSHIP_LUA = MEMBERSHIP_FACTS_LUA + """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then
  return cjson.encode({status='CHANGED'})
end
local status, meta = readMembership(KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3], ARGV[4])
if status == 'STALE' then
  redis.call('DEL', KEYS[1])
  return cjson.encode({status='STALE'})
end
if status ~= 'ACTIVE' then return cjson.encode({status=status}) end
local version = tonumber(redis.call('GET', KEYS[4]))
if not version or version < 1 or version ~= math.floor(version) then
  return cjson.encode({status='INVALID'})
end
local members = {}
for _, raw in ipairs(redis.call('HVALS', KEYS[3])) do
  local member = decodeObject(raw)
  if not member then return cjson.encode({status='INVALID'}) end
  table.insert(members, member)
end
return cjson.encode({status='ACTIVE', meta=meta, members=members, roomVersion=version})
"""

REBUILD_MEMBERSHIP_LUA = MEMBERSHIP_FACTS_LUA + """
local status, meta = readMembership(KEYS[2], KEYS[3], ARGV[1], ARGV[2], ARGV[3], ARGV[4])
if status ~= 'ACTIVE' then return 0 end
local owner = redis.call('GET', KEYS[1])
if owner and owner ~= ARGV[1] then return 0 end
local ttl = math.min(tonumber(ARGV[5]), redis.call('TTL', KEYS[2]), redis.call('TTL', KEYS[3]))
if ttl < 1 then return 0 end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ttl)
deleteOwnedIndex(KEYS[4], ARGV[1])
return 1
"""

DELETE_OWNED_MEMBERSHIP_LUA = MEMBERSHIP_FACTS_LUA + """
return deleteOwnedIndex(KEYS[1], ARGV[1])
"""
