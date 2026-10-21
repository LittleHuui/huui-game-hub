import { usePlatformStore } from '../stores/platformStore.js';
import { requireGameCode } from '../utils/requireGameCode.js';

/**
 * 从 platform store 读取当前游戏 code。
 * @param {string} [context]
 * @returns {string}
 */
export function resolvePlatformGameCode(context = 'platform') {
  const platform = usePlatformStore();
  return requireGameCode(platform.currentGameCode, context);
}
