import * as gameRuleDefinitionRepository from '../../repositories/gameRuleDefinitionRepository.js';
import * as roomQueryService from '../../services/roomQueryService.js';
import * as roomGameService from '../../services/roomGameService.js';
import { canFetchRemote } from '../../services/remoteGate.js';
import { applyDoudizhuRuleDefinition, DOUDIZHU_CODE } from './doudizhuConfig.js';

/**
 * 加载斗地主在线规则定义种子（仅在线远端，无本地回退）。
 * @returns {Promise<object>}
 */
export async function loadRuleDefinition() {
  if (!canFetchRemote()) {
    throw new Error('斗地主仅支持在线模式，请切换数据模式后重试');
  }
  const data = await gameRuleDefinitionRepository.fetchRuleDefinition(DOUDIZHU_CODE);
  applyDoudizhuRuleDefinition(data);
  roomQueryService.applyRoomRuleContext(data);
  return data;
}

/**
 * 加载房间对局 GameView 并接入展示管线。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function loadRoomGameView(roomId, options = {}) {
  if (!canFetchRemote()) {
    throw new Error('斗地主仅支持在线模式，请切换数据模式后重试');
  }
  return roomGameService.loadRoomGameView(roomId, options);
}

/**
 * 提交对局操作。
 * @param {string} roomId
 * @param {{ submission: object; baseVersion: number; requestId?: string }} body
 * @returns {Promise<object>}
 */
export async function applyRoomGameAction(roomId, body) {
  if (!canFetchRemote()) {
    throw new Error('斗地主仅支持在线模式，请切换数据模式后重试');
  }
  return roomGameService.applyRoomGameAction(roomId, body);
}
