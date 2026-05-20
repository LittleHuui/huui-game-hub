import { usePlatformStore } from '../stores/platformStore.js';

/**
 * 校验 gameCode 非空。
 * @param {unknown} gameCode
 * @param {string} [context]
 * @returns {string}
 */
export function requireGameCode(gameCode, context) {
  const code = gameCode != null ? String(gameCode).trim() : '';
  if (!code) {
    const suffix = context ? `（${context}）` : '';
    throw new Error(`缺少 gameCode${suffix}`);
  }
  return code;
}

/**
 * 从 platform store 读取当前游戏 code（须已由目录/路由/boot 写入）。
 * @param {string} [context]
 * @returns {string}
 */
export function resolvePlatformGameCode(context = 'platform') {
  const platform = usePlatformStore();
  return requireGameCode(platform.currentGameCode, context);
}
