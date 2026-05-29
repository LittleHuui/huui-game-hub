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
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function createRoom(payload, serviceId) {
  const raw = await roomApi.createRoom(payload, serviceId);
  return mapRoomDetail(raw);
}

/**
 * 查询房间详情（远端）。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function fetchRoom(roomId) {
  const raw = await roomApi.getRoom(roomId);
  return mapRoomDetail(raw);
}

/**
 * 查询当前用户跨游戏活跃房间。
 * @param {string} serviceId
 * @returns {Promise<object|null>}
 */
export async function fetchMyActiveRoom(serviceId) {
  const raw = await roomApi.fetchMyActiveRoom(serviceId);
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  return raw.room ? mapRoomDetail(raw.room) : null;
}

/**
 * 查询当前用户在指定游戏下的托管空壳房间。
 * @param {string} gameCode
 * @param {string} serviceId
 * @returns {Promise<object|null>}
 */
export async function fetchMyManagedShell(gameCode, serviceId) {
  const raw = await roomApi.fetchMyManagedShell(gameCode, serviceId);
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  return raw.room ? mapRoomDetail(raw.room) : null;
}

/**
 * 加入房间（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function joinRoom(roomId, serviceId) {
  const raw = await roomApi.joinRoom(roomId, serviceId);
  return mapRoomDetail(raw);
}

/**
 * 恢复托管席位并重连房间（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function rejoinManagedRoom(roomId, serviceId) {
  const raw = await roomApi.rejoinManagedRoom(roomId, serviceId);
  return mapRoomDetail(raw);
}

/**
 * 开启在线托管（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function startManagedMode(roomId, serviceId) {
  const raw = await roomApi.startManagedMode(roomId, serviceId);
  return mapRoomDetail(raw);
}

/**
 * 取消在线托管（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function stopManagedMode(roomId, serviceId) {
  const raw = await roomApi.stopManagedMode(roomId, serviceId);
  return mapRoomDetail(raw);
}

/**
 * 在等待中的房间内添加 AI 玩家（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function addRoomAi(roomId, serviceId) {
  const raw = await roomApi.addRoomAi(roomId, serviceId);
  return mapRoomDetail(raw);
}

/**
 * 房主移除房间成员（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @param {string} targetPlayerId
 * @returns {Promise<object>}
 */
export async function removeRoomMember(roomId, serviceId, targetPlayerId) {
  const raw = await roomApi.removeRoomMember(roomId, serviceId, {
    targetPlayerId: String(targetPlayerId || '').trim()
  });
  return mapRoomDetail(raw);
}

/**
 * 房主更新 waiting 房间配置（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @param {{ maxPlayers?: number; roomConfig?: object }} payload
 * @returns {Promise<object>}
 */
export async function updateRoomConfig(roomId, serviceId, payload) {
  const raw = await roomApi.updateRoomConfig(roomId, serviceId, payload);
  return mapRoomDetail(raw);
}

/**
 * 离开房间（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<{ roomId: string; gameCode: string; dissolved: boolean; room: object|null }>}
 */
export async function leaveRoom(roomId, serviceId) {
  const raw = await roomApi.leaveRoom(roomId, serviceId);
  return mapRoomLeave(raw);
}

/**
 * 开始房间对局（远端），返回 GameView 领域对象。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function startRoomGame(roomId, serviceId) {
  const raw = await roomApi.startRoomGame(roomId, serviceId);
  return mapStrategyTurnGameView(raw);
}

/**
 * 查询房间对局视图（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @returns {Promise<object>}
 */
export async function fetchRoomGameView(roomId, serviceId) {
  const raw = await roomApi.fetchRoomGameView(roomId, serviceId);
  return mapStrategyTurnGameView(raw);
}

/**
 * 提交房间对局操作（远端）。
 * @param {string} roomId
 * @param {string} serviceId
 * @param {{ actionId: string; baseVersion?: number; clientSeq?: number }} body
 * @returns {Promise<object>}
 */
export async function applyRoomGameAction(roomId, serviceId, body) {
  const raw = await roomApi.applyRoomGameAction(roomId, serviceId, body);
  return mapStrategyTurnGameView(raw);
}
