import { remoteRepository } from './remoteRepository.js';

/**
 * 拉取游戏配置（原始远端数据）。
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export async function fetchGameConfig(gameCode) {
  return remoteRepository.getGameConfig(gameCode);
}

/**
 * 拉取游戏道具规则。
 * @param {string} gameCode
 * @returns {Promise<object>}
 */
export async function fetchGameProps(gameCode) {
  return remoteRepository.getGameProps(gameCode);
}

/**
 * 拉取平台道具定义（含描述、图标）。
 * @param {{ enabled?: boolean }} [params]
 * @returns {Promise<object>}
 */
export async function fetchPropDefinitions(params = {}) {
  return remoteRepository.getProps(params);
}

