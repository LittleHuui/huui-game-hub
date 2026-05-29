import { remoteRepository } from './remoteRepository.js';

/**
 * 拉取在线游戏规则定义种子（远端）。
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export async function fetchRuleDefinition(gameCode) {
  return remoteRepository.getGameRuleDefinition(gameCode);
}
