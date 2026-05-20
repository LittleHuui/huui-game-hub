import { hasGameCapability } from '../constants/gameRegistry.js';
import { useRankingStore } from '../stores/rankingStore.js';
import * as gameConfigService from './gameConfigService.js';
import * as inventoryService from './inventoryService.js';
import * as rankingService from './rankingService.js';
import * as shopService from './shopService.js';
import { canFetchRemote } from './remoteGate.js';

/**
 * @typedef {object} ActivateGameOptions
 * @property {string} [difficultyCode]
 * @property {string} [mode]
 * @property {boolean} [includeLeaderboard]
 * @property {boolean} [includeInventory]
 */

/**
 * 校验激活参数：排行榜/背包刷新须由调用方显式传入 mode / difficultyCode。
 * @param {ActivateGameOptions} options
 * @returns {{ mode?: string; difficultyCode?: string; includeLeaderboard: boolean; includeInventory: boolean }}
 */
function resolveActivateOptions(options) {
  return {
    mode: options.mode,
    difficultyCode: options.difficultyCode,
    includeLeaderboard: options.includeLeaderboard === true,
    includeInventory: options.includeInventory === true
  };
}

/**
 * 加载游戏配置。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function loadGameConfig(gameCode) {
  await gameConfigService.loadGameConfig(gameCode);
}

/**
 * 加载游戏商城。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function loadGameShop(gameCode) {
  if (gameCode == null || String(gameCode).length === 0) {
    return;
  }
  if (!hasGameCapability(gameCode, 'shop')) {
    return;
  }
  await shopService.loadGameShop(gameCode);
}

/**
 * 刷新游戏背包（需 inventory 能力且可拉取远端）。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function refreshGameBag(gameCode) {
  if (gameCode == null || String(gameCode).length === 0) {
    return;
  }
  if (!hasGameCapability(gameCode, 'inventory')) {
    return;
  }
  await inventoryService.refreshGameBag(gameCode);
}

/**
 * 刷新排行榜；离线时清空 store。
 * @param {string} gameCode
 * @param {string} mode
 * @param {string} difficultyCode
 * @returns {Promise<void>}
 */
export async function refreshRanking(gameCode, mode, difficultyCode) {
  const ranking = useRankingStore();
  if (!hasGameCapability(gameCode, 'leaderboard')) {
    return;
  }
  if (!canFetchRemote()) {
    ranking.clear();
    return;
  }
  if (!mode || !difficultyCode) {
    throw new Error('刷新排行榜需要 mode 与 difficultyCode');
  }
  await rankingService.refreshGameLeaderboard(gameCode, difficultyCode, mode);
}

/**
 * 激活游戏：配置 → 商城 → 背包 → 排行榜（按 options 裁剪）。
 * @param {string} gameCode
 * @param {ActivateGameOptions} [options]
 * @returns {Promise<void>}
 */
export async function activateGame(gameCode, options = {}) {
  if (gameCode == null || String(gameCode).length === 0) {
    throw new Error('缺少 gameCode');
  }

  const { mode, difficultyCode, includeLeaderboard, includeInventory } = resolveActivateOptions(
    options
  );

  await loadGameConfig(gameCode);
  await loadGameShop(gameCode);

  if (includeInventory) {
    await refreshGameBag(gameCode);
  }

  if (includeLeaderboard) {
    await refreshRanking(gameCode, mode, difficultyCode);
  }
}
