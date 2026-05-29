import * as gameRuleDefinitionRepository from '../repositories/gameRuleDefinitionRepository.js';
import * as roomService from './roomService.js';
import { canFetchRemote } from './remoteGate.js';
import { getGameConfig } from '../constants/gameRegistry.js';

/**
 * 读取在线房间默认模式（约定取注册表首个 mode）。
 * @param {string} gameCode
 * @returns {string}
 */
export function resolveOnlineRoomMode(gameCode) {
  const game = getGameConfig(gameCode);
  return String(game?.modes?.[0] || '').trim() || 'classic';
}

/**
 * 拉取指定游戏规则定义，并写入房间通用上下文。
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export async function loadOnlineRuleDefinition(gameCode) {
  const normalized = String(gameCode || '').trim();
  if (!normalized) {
    throw new Error('缺少 gameCode');
  }
  if (!canFetchRemote()) {
    throw new Error('当前为本地模式，在线房间不可用');
  }
  const data = await gameRuleDefinitionRepository.fetchRuleDefinition(normalized);
  roomService.applyRoomRuleContext(data);
  return data;
}
