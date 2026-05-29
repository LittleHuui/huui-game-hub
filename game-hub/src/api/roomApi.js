import { apiUrl, requestJson } from './request.js';

const HUB = '/api/game-hub';

/**
 * 按游戏编码查询房间列表。
 * @param {string} gameCode
 * @returns {Promise<object[]>}
 */
export function listRooms(gameCode) {
  const query = new URLSearchParams({ gameCode: String(gameCode || '').trim() });
  return requestJson('GET', apiUrl(`${HUB}/rooms?${query.toString()}`));
}

/**
 * 创建房间。
 * @param {{ gameCode: string; mode: string; expireSeconds?: number; roomName?: string; roomConfig?: object }} payload
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function createRoom(payload, serviceId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms`), payload, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 查询房间详情。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function getRoom(roomId) {
  return requestJson('GET', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}`));
}

/**
 * 查询当前用户跨游戏活跃房间。
 * @param {string} serviceId
 * @returns {Promise<{ room: object|null }>}
 */
export function fetchMyActiveRoom(serviceId) {
  return requestJson('GET', apiUrl(`${HUB}/rooms/my-active`), null, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 查询当前用户在指定游戏下的托管空壳房间。
 * @param {string} gameCode
 * @param {string} serviceId
 * @returns {Promise<{ room: object|null }>}
 */
export function fetchMyManagedShell(gameCode, serviceId) {
  const query = new URLSearchParams({ gameCode: String(gameCode || '').trim() });
  return requestJson('GET', apiUrl(`${HUB}/rooms/my-managed-shell?${query.toString()}`), null, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 加入房间。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function joinRoom(roomId, serviceId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/join`), null, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 恢复托管席位并重连房间。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function rejoinManagedRoom(roomId, serviceId) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/rejoin`),
    null,
    8000,
    {
      'X-Game-Hub-User-Id': serviceId
    }
  );
}

/**
 * 开启在线托管。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function startManagedMode(roomId, serviceId) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/managed/start`),
    null,
    8000,
    {
      'X-Game-Hub-User-Id': serviceId
    }
  );
}

/**
 * 取消在线托管。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function stopManagedMode(roomId, serviceId) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/managed/stop`),
    null,
    8000,
    {
      'X-Game-Hub-User-Id': serviceId
    }
  );
}

/**
 * 在等待中的房间内添加一名平台代管 AI 玩家。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function addRoomAi(roomId, serviceId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/ai`), null, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 房主在等待中的房间内移除成员。
 * @param {string} roomId
 * @param {string} serviceId
 * @param {{ targetPlayerId: string }} body
 * @returns {Promise<object>}
 */
export function removeRoomMember(roomId, serviceId, body) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/members/remove`),
    body,
    8000,
    {
      'X-Game-Hub-User-Id': serviceId
    }
  );
}

/**
 * 房主在等待中的房间内更新配置。
 * @param {string} roomId
 * @param {string} serviceId
 * @param {{ maxPlayers?: number; roomConfig?: object }} body
 * @returns {Promise<object>}
 */
export function updateRoomConfig(roomId, serviceId, body) {
  return requestJson(
    'PATCH',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/config`),
    body,
    8000,
    {
      'X-Game-Hub-User-Id': serviceId
    }
  );
}

/**
 * 离开房间。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function leaveRoom(roomId, serviceId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/leave`), null, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 房主开始房间对局。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function startRoomGame(roomId, serviceId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/start`), null, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 查询房间对局视图。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export function fetchRoomGameView(roomId, serviceId) {
  return requestJson('GET', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/view`), null, 8000, {
    'X-Game-Hub-User-Id': serviceId
  });
}

/**
 * 提交房间对局操作。
 * @param {string} roomId
 * @param {string} serviceId
 * @param {{ actionId: string; baseVersion?: number; clientSeq?: number }} body
 * @returns {Promise<object>}
 */
export function applyRoomGameAction(roomId, serviceId, body) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/actions`),
    body,
    8000,
    {
      'X-Game-Hub-User-Id': serviceId
    }
  );
}
