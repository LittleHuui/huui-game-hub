import { usePlatformStore } from '../stores/platformStore.js';
import { useSettingStore } from '../stores/settingStore.js';
import { useRankingStore } from '../stores/rankingStore.js';
import { remoteRepository } from '../repositories/remoteRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import { persistAllLocal } from '../repositories/localPersistRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import * as gameCatalogService from './gameCatalogService.js';
import * as gameLifecycleService from './gameLifecycleService.js';
import * as toastService from './toastService.js';
import { canFetchRemote } from './remoteGate.js';

/**
 * 按数据模式更新 platform.networkMode。
 * @param {'auto'|'local'|'remote'} mode
 * @param {boolean} remoteAvailable
 */
function applyNetworkModeForRepository(mode, remoteAvailable) {
  const platform = usePlatformStore();
  if (mode === 'local') {
    platform.networkMode = 'offline';
    return;
  }
  if (!remoteAvailable) {
    platform.networkMode = 'offline';
    return;
  }
  if (mode === 'remote') {
    platform.networkMode = 'online';
    return;
  }
  if (platform.networkMode === 'unknown' || platform.networkMode === 'offline') {
    platform.networkMode = 'online';
  }
}

/**
 * 探测接口是否可用。
 * @returns {Promise<boolean>}
 */
async function probeRemoteAvailable() {
  try {
    await remoteRepository.healthCheck();
    return true;
  } catch {
    return false;
  }
}

/**
 * 构建当前游戏的 activateGame 参数。
 * @param {string} gameCode
 * @returns {import('./gameLifecycleService.js').ActivateGameOptions}
 */
function buildActivateOptions(gameCode) {
  const platform = usePlatformStore();
  if (gameCode === 'minesweeper') {
    return {
      difficultyCode: platform.minesweeperDifficulty || 'easy',
      includeLeaderboard: true,
      includeInventory: true
    };
  }
  return { includeLeaderboard: true, includeInventory: true };
}

/**
 * 切换数据模式并重新激活当前游戏。
 * @param {'auto'|'local'|'remote'} nextMode
 * @returns {Promise<{ success: boolean; networkMode: string }>}
 */
export async function switchRepositoryMode(nextMode) {
  const platform = usePlatformStore();
  const settingStore = useSettingStore();
  const ranking = useRankingStore();

  if (nextMode === 'remote') {
    const ok = await probeRemoteAvailable();
    platform.remoteAvailable = ok;
    if (!ok) {
      toastService.push('接口不可用，无法切换到接口模式', 'warning');
      return { success: false, networkMode: platform.networkMode };
    }
  } else if (nextMode === 'auto') {
    platform.remoteAvailable = await probeRemoteAvailable();
  } else {
    platform.remoteAvailable = false;
  }

  settingStore.setRepositoryMode(nextMode);
  applyNetworkModeForRepository(nextMode, platform.remoteAvailable);

  if (nextMode === 'local' || !canFetchRemote()) {
    ranking.clear();
  }

  const evt = userRepository.buildSystemSettingPendingEvent();
  if (evt) {
    syncRepository.appendPendingEvent(evt);
  }
  persistAllLocal();

  await gameCatalogService.loadGameCatalog();

  const gameCode = platform.currentGameCode || 'minesweeper';
  await gameLifecycleService.activateGame(gameCode, buildActivateOptions(gameCode));

  return { success: true, networkMode: platform.networkMode };
}

/** @deprecated 使用 switchRepositoryMode */
export const switchDataMode = switchRepositoryMode;
