import * as roomApi from '../api/roomApi.js';
import { mapRoomDetail, mapRoomLeave, mapRoomListItem } from '../mappers/roomMapper.js';
import { mapStrategyTurnGameView } from '../mappers/strategyTurnGameViewMapper.js';

/**
 * 查询房间列表（远端）。
 * @param {string} gameCode
 * @returns {Promise<object[]>}
 */
export async function fetchRoomList(gameCode) {
  const raw = await roomApi.listRooms(gameCode);
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.map((item) => mapRoomListItem(item)).filter(Boolean);
}

/**
 * 创建房间（远端）。
 * @param {{ gameCode: string; mode: string; expireSeconds?: number; roomName?: string; roomConfig?: object }} payload
 * @returns {Promise<object>}
 */
export async function createRoom(payload) {
  const raw = await roomApi.createRoom(payload);
  return mapRoomDetail(raw);
}

/**
 * 查询房间详情（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function fetchRoom(roomId, options = {}) {
  const raw = await roomApi.getRoom(roomId, options);
  return mapRoomDetail(raw);
}

/**
 * 查询当前用户跨游戏活跃房间。
 * @param {{signal?: AbortSignal}} [options] 页面取消信号，透传至请求层。
 * @returns {Promise<object|null>}
 */
export async function fetchMyActiveRoom(options = {}) {
  const raw = await roomApi.fetchMyActiveRoom(options);
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  return raw.room ? mapRoomDetail(raw.room) : null;
}

/**
 * 查询当前用户在指定游戏下的托管空壳房间。
 * @param {string} gameCode
 * @returns {Promise<object|null>}
 */
export async function fetchMyManagedShell(gameCode) {
  const raw = await roomApi.fetchMyManagedShell(gameCode);
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  return raw.room ? mapRoomDetail(raw.room) : null;
}

/**
 * 加入房间（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function joinRoom(roomId) {
  const raw = await roomApi.joinRoom(roomId);
  return mapRoomDetail(raw);
}

/**
 * 恢复托管席位并重连房间（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function rejoinManagedRoom(roomId) {
  const raw = await roomApi.rejoinManagedRoom(roomId);
  return mapRoomDetail(raw);
}

/**
 * 开启在线托管（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function startManagedMode(roomId) {
  const raw = await roomApi.startManagedMode(roomId);
  return mapRoomDetail(raw);
}

/**
 * 取消在线托管（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function stopManagedMode(roomId) {
  const raw = await roomApi.stopManagedMode(roomId);
  return mapRoomDetail(raw);
}

/**
 * 在等待中的房间内添加 AI 玩家（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function addRoomAi(roomId) {
  const raw = await roomApi.addRoomAi(roomId);
  return mapRoomDetail(raw);
}

/**
 * 房主移除房间成员（远端）。
 * @param {string} roomId
 * @param {string} targetPlayerId
 * @returns {Promise<object>}
 */
export async function removeRoomMember(roomId, targetPlayerId) {
  const raw = await roomApi.removeRoomMember(roomId, {
    targetPlayerId: String(targetPlayerId || '').trim()
  });
  return mapRoomDetail(raw);
}

/**
 * 房主更新 waiting 房间配置（远端）。
 * @param {string} roomId
 * @param {{ maxPlayers?: number; roomConfig?: object }} payload
 * @returns {Promise<object>}
 */
export async function updateRoomConfig(roomId, payload) {
  const raw = await roomApi.updateRoomConfig(roomId, payload);
  return mapRoomDetail(raw);
}

/**
 * 离开房间（远端）。
 * @param {string} roomId
 * @returns {Promise<{ roomId: string; gameCode: string; dissolved: boolean; room: object|null }>}
 */
export async function leaveRoom(roomId) {
  const raw = await roomApi.leaveRoom(roomId);
  return mapRoomLeave(raw);
}

/**
 * 开始房间对局（远端），返回 GameView 领域对象。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function startRoomGame(roomId) {
  const raw = await roomApi.startRoomGame(roomId);
  return mapStrategyTurnGameView(raw);
}

/**
 * 查询房间对局视图（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function fetchRoomGameView(roomId, options = {}) {
  const raw = await roomApi.fetchRoomGameView(roomId, options);
  return mapStrategyTurnGameView(raw);
}

/**
 * 提交房间对局操作（远端）。
 * @param {string} roomId
 * @param {{ baseVersion: number; requestId: string; submission: object }} body
 * @returns {Promise<object>}
 */
export async function applyRoomGameAction(roomId, body, options = {}) {
  const raw = await roomApi.applyRoomGameAction(roomId, body, options);
  return mapStrategyTurnGameView(raw);
}

/**
 * 预览房间对局操作（远端，不映射 GameView）。
 * @param {string} roomId
 * @param {{ baseVersion: number; submission: object }} body
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export async function previewRoomGameAction(roomId, body, options = {}) {
  return roomApi.previewRoomGameAction(roomId, body, options);
}

/**
 * 查询房间对局动作提示（远端，不映射 GameView）。
 * @param {string} roomId
 * @param {{ baseVersion: number; actionType: string; cursor?: string|null; limit?: number }} body
 * @param {{signal?: AbortSignal}} [options]
 * @returns {Promise<object>}
 */
export async function fetchRoomActionSuggestions(roomId, body, options = {}) {
  return roomApi.fetchRoomActionSuggestions(roomId, body, options);
}
