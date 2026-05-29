import * as gameRuleDefinitionRepository from '../../repositories/gameRuleDefinitionRepository.js';
import * as roomService from '../../services/roomService.js';
import { canFetchRemote } from '../../services/remoteGate.js';
import { applyUnoRuleDefinition, UNO_CODE } from './unoConfig.js';

/**
 * 加载 UNO 在线规则定义种子（仅在线远端，无本地回退）。
 * @returns {Promise<object>}
 */
export async function loadRuleDefinition() {
  if (!canFetchRemote()) {
    throw new Error('UNO 仅支持在线模式，请切换数据模式后重试');
  }
  const data = await gameRuleDefinitionRepository.fetchRuleDefinition(UNO_CODE);
  applyUnoRuleDefinition(data);
  roomService.applyRoomRuleContext(data);
  return data;
}

/**
 * 加载房间对局 GameView 并接入展示管线。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function loadRoomGameView(roomId) {
  if (!canFetchRemote()) {
    throw new Error('UNO 仅支持在线模式，请切换数据模式后重试');
  }
  return roomService.loadRoomGameView(roomId);
}

/**
 * 提交对局操作。
 * @param {string} roomId
 * @param {{ actionId: string; baseVersion: number; clientSeq?: number }} body
 * @returns {Promise<object>}
 */
export async function applyRoomGameAction(roomId, body) {
  if (!canFetchRemote()) {
    throw new Error('UNO 仅支持在线模式，请切换数据模式后重试');
  }
  return roomService.applyRoomGameAction(roomId, body);
}
