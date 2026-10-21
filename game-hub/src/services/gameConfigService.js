import * as gameConfigRepository from '../repositories/gameConfigRepository.js';
import { getGameFrontendModule } from '../games/gameModuleRegistry.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { canFetchRemote } from './remoteGate.js';

/**
 * 是否应从远端拉取游戏配置。
 * @param {{ networkMode?: string }} platform
 * @returns {boolean}
 */
function shouldLoadRemoteConfig(platform) {
  return (
    canFetchRemote() &&
    (platform.networkMode === 'online' || platform.networkMode === 'degraded')
  );
}

/**
 * 按 gameCode 加载并应用游戏配置（在线优先，失败或离线回退种子）。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function loadGameConfig(gameCode) {
  if (gameCode == null || String(gameCode).length === 0) {
    return;
  }
  const module = getGameFrontendModule(gameCode);
  const handler = module?.configHandler;
  if (!handler?.applySeed || !handler?.resolveSeed) {
    return;
  }
  const platform = usePlatformStore();
  if (shouldLoadRemoteConfig(platform)) {
    try {
      const data = await gameConfigRepository.fetchGameConfig(gameCode);
      if (typeof handler.applyRemote === 'function') {
        handler.applyRemote(data);
      } else {
        handler.applySeed(handler.resolveSeed(data));
      }
      return;
    } catch {
      // 远端失败统一回退模块种子配置。
    }
  }
  const seedRoot = typeof module.seedProvider === 'function' ? module.seedProvider() : null;
  if (!seedRoot) {
    return;
  }
  handler.applySeed(handler.resolveSeed(seedRoot));
}
