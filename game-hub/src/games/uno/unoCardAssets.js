import { UNO_ASSET_CONFIG } from './unoAssetConfig.js';

/**
 * 按牌型编码获取正面图 URL。
 * @param {string} cardCode
 * @returns {string}
 */
export function getUnoCardImageUrl(cardCode) {
  const key = String(cardCode || '').trim();
  if (!key) {
    return '';
  }
  return UNO_ASSET_CONFIG.cards[key] || '';
}

/**
 * 获取牌背图 URL。
 * @returns {string}
 */
export function getUnoCardBackImageUrl() {
  return UNO_ASSET_CONFIG.cardBack;
}

/**
 * 将规则定义或运行时牌对象归一为 cardCode。
 * @param {{ cardCode?: string } | string | null | undefined} source
 * @returns {string}
 */
export function resolveUnoCardCode(source) {
  if (typeof source === 'string') {
    return source.trim();
  }
  if (source && typeof source === 'object' && typeof source.cardCode === 'string') {
    return source.cardCode.trim();
  }
  return '';
}
