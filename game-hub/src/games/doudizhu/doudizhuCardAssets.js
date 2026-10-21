/**
 * 解析牌面图片 URL（缺失时返回空字符串，由 CSS 兜底）。
 * @param {string} imagePath
 * @returns {string}
 */
export function resolveDoudizhuCardImageUrl(imagePath) {
  const path = String(imagePath || '').trim();
  if (!path) {
    return '';
  }
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return normalized;
}

/**
 * 获取牌背图 URL。
 * @param {string} [cardBackImage]
 * @returns {string}
 */
export function resolveDoudizhuCardBackUrl(cardBackImage) {
  const path = String(cardBackImage || 'games/doudizhu/cards/card_back.png').trim();
  return resolveDoudizhuCardImageUrl(path);
}

/**
 * 将牌对象归一为 cardCode。
 * @param {{ cardCode?: string } | string | null | undefined} source
 * @returns {string}
 */
export function resolveDoudizhuCardCode(source) {
  if (typeof source === 'string') {
    return source.trim();
  }
  if (source && typeof source === 'object' && typeof source.cardCode === 'string') {
    return source.cardCode.trim();
  }
  return '';
}
