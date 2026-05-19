import { hasGameCapability } from '../constants/gameRegistry.js';
import { usePlatformStore } from '../stores/platformStore.js';
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
 * @property {boolean} [forceReload]
 */

/**
 * 激活游戏并加载配置、商城、背包与排行榜（按 options 裁剪）。
 * @param {string} gameCode
 * @param {ActivateGameOptions} [options]
 * @returns {Promise<void>}
 */
export async function activateGame(gameCode, options = {}) {
  if (gameCode == null || String(gameCode).length === 0) {
    return;
  }

  const {
    difficultyCode,
    mode = 'single',
    includeLeaderboard = true,
    includeInventory = true
  } = options;

  const platform = usePlatformStore();
  const ranking = useRankingStore();

  if (gameCode === 'minesweeper') {
    await gameConfigService.loadMinesweeperIfOnline(platform);
    await shopService.loadMinesweeperShop();

    if (includeInventory && hasGameCapability(gameCode, 'inventory')) {
      await inventoryService.refreshMinesweeperBag();
    }

    if (includeLeaderboard && hasGameCapability(gameCode, 'leaderboard')) {
      if (difficultyCode && canFetchRemote()) {
        await rankingService.refreshGameLeaderboard(gameCode, difficultyCode);
      } else if (!canFetchRemote()) {
        ranking.clear();
      }
    }
    return;
  }

  if (gameCode === 'match3') {
    await gameConfigService.loadMatch3IfOnline(platform);
    await shopService.loadGameShop(gameCode);

    if (includeInventory && hasGameCapability(gameCode, 'inventory')) {
      await inventoryService.refreshGameBag(gameCode);
    }
  }

  if (hasGameCapability(gameCode, 'leaderboard') && includeLeaderboard && difficultyCode && canFetchRemote()) {
    await rankingService.refreshGameLeaderboard(gameCode, difficultyCode, mode);
  } else if (!canFetchRemote()) {
    ranking.clear();
  }
}
