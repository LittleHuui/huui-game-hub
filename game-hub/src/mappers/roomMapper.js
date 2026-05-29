/**
 * 将房间列表 API 项映射为 UI 领域对象。
 * @param {object} raw
 * @returns {object}
 */
export function mapRoomListItem(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const roomId = String(raw.roomId || '').trim();
  if (!roomId) {
    return null;
  }
  return {
    roomId,
    roomName: String(raw.roomName || '').trim() || roomId,
    ownerPlayerId: String(raw.ownerPlayerId || '').trim(),
    ownerNickname: String(raw.ownerNickname || '').trim() || '未知房主',
    memberCount: Number(raw.memberCount) || 0,
    maxPlayers: Number(raw.maxPlayers) || 0,
    aiCount: Number(raw.aiCount) || 0,
    status: String(raw.status || 'waiting'),
    gameCode: String(raw.gameCode || '').trim(),
    mode: String(raw.mode || '').trim()
  };
}

/**
 * 将离开房间 API 响应映射为 UI 领域对象。
 * @param {object} raw
 * @returns {object|null}
 */
export function mapRoomLeave(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const roomId = String(raw.roomId || '').trim();
  if (!roomId) {
    return null;
  }
  return {
    roomId,
    gameCode: String(raw.gameCode || '').trim(),
    dissolved: Boolean(raw.dissolved),
    room: raw.room ? mapRoomDetail(raw.room) : null
  };
}

/**
 * 将房间详情 API 响应映射为 UI 领域对象。
 * @param {object} raw
 * @returns {object}
 */
export function mapRoomDetail(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const base = mapRoomListItem(raw);
  if (!base) {
    return null;
  }
  const members = Array.isArray(raw.members) ? raw.members : [];
  return {
    ...base,
    version: Number(raw.version) || 0,
    members: members.map((member) => ({
      playerId: String(member?.playerId || '').trim(),
      nickname: String(member?.nickname || '').trim() || '玩家',
      avatar: member?.avatar ?? null,
      joinedAt: Number(member?.joinedAt) || 0,
      isAi: Boolean(member?.isAi),
      isManaged: Boolean(member?.isManaged),
      managedMode: member?.managedMode || null,
      managedReason: member?.managedReason || null,
      managedAt: member?.managedAt ?? null
    })),
    roomConfig:
      raw.roomConfig && typeof raw.roomConfig === 'object' ? { ...raw.roomConfig } : {},
    allowAi: raw.allowAi !== false,
    maxAiCount: Number(raw.maxAiCount) || 0,
    createdAt: Number(raw.createdAt) || 0,
    updatedAt: Number(raw.updatedAt) || 0
  };
}
