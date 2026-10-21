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
 * @returns {Promise<object>}
 */
export function createRoom(payload) {
  return requestJson('POST', apiUrl(`${HUB}/rooms`), payload);
}

/**
 * 查询房间详情。
 * @param {string} roomId
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export function getRoom(roomId, options = {}) {
  return requestJson(
    'GET',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}`),
    undefined,
    undefined,
    undefined,
    options
  );
}

/**
 * 查询当前用户跨游戏活跃房间。
 * @param {{signal?: AbortSignal}} [options] 页面取消信号。
 * @returns {Promise<{ room: object|null }>}
 */
export function fetchMyActiveRoom(options = {}) {
  return requestJson('GET', apiUrl(`${HUB}/rooms/my-active`), undefined, undefined, undefined, options);
}

/**
 * 查询当前用户在指定游戏下的托管空壳房间。
 * @param {string} gameCode
 * @returns {Promise<{ room: object|null }>}
 */
export function fetchMyManagedShell(gameCode) {
  const query = new URLSearchParams({ gameCode: String(gameCode || '').trim() });
  return requestJson('GET', apiUrl(`${HUB}/rooms/my-managed-shell?${query.toString()}`));
}

/**
 * 加入房间。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function joinRoom(roomId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/join`));
}

/**
 * 恢复托管席位并重连房间。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function rejoinManagedRoom(roomId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/rejoin`));
}

/**
 * 开启在线托管。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function startManagedMode(roomId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/managed/start`));
}

/**
 * 取消在线托管。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function stopManagedMode(roomId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/managed/stop`));
}

/**
 * 在等待中的房间内添加一名平台代管 AI 玩家。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function addRoomAi(roomId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/ai`));
}

/**
 * 移除房间成员。
 * @param {string} roomId
 * @param {{ targetPlayerId: string }} body
 * @returns {Promise<object>}
 */
export function removeRoomMember(roomId, body) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/members/remove`), body);
}

/**
 * 房主在等待中的房间内更新配置。
 * @param {string} roomId
 * @param {{ maxPlayers?: number; roomConfig?: object }} body
 * @returns {Promise<object>}
 */
export function updateRoomConfig(roomId, body) {
  return requestJson('PATCH', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/config`), body);
}

/**
 * 离开房间。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function leaveRoom(roomId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/leave`));
}

/**
 * 房主开始房间对局。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export function startRoomGame(roomId) {
  return requestJson('POST', apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/start`));
}

/**
 * 查询房间对局视图。
 * @param {string} roomId
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export function fetchRoomGameView(roomId, options = {}) {
  return requestJson(
    'GET',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/view`),
    undefined,
    undefined,
    undefined,
    options
  );
}

/**
 * 提交房间对局操作。
 * @param {string} roomId
 * @param {{ baseVersion: number; requestId: string; submission: object }} body
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export function applyRoomGameAction(roomId, body, options = {}) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/actions`),
    body,
    undefined,
    undefined,
    options
  );
}

/**
 * 预览房间对局操作（只读，不修改 GameView）。
 * @param {string} roomId
 * @param {{ baseVersion: number; submission: object }} body
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export function previewRoomGameAction(roomId, body, options = {}) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/action-preview`),
    body,
    undefined,
    undefined,
    options
  );
}

/**
 * 查询房间对局动作提示（只读，不修改 GameView）。
 * @param {string} roomId
 * @param {{ baseVersion: number; actionType: string; cursor?: string|null; limit?: number }} body
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export function fetchRoomActionSuggestions(roomId, body, options = {}) {
  return requestJson(
    'POST',
    apiUrl(`${HUB}/rooms/${encodeURIComponent(roomId)}/action-suggestions`),
    body,
    undefined,
    undefined,
    options
  );
}
