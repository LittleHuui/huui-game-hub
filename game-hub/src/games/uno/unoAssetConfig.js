/**
 * UNO PNG 资源配置（cardCode 与后端规则种子一致）。
 */

const cardImageModules = import.meta.glob('../../assets/games/uno/cards/*.png', {
  eager: true,
  import: 'default'
});

/** @type {Record<string, string>} */
const allCards = {};

for (const [modulePath, url] of Object.entries(cardImageModules)) {
  const fileName = modulePath.split('/').pop() || '';
  const key = fileName.replace(/\.png$/i, '').trim().toLowerCase();
  if (!key) {
    continue;
  }
  allCards[key] = String(url || '');
}

const cardBack = allCards.card_back || '';
const faceCards = Object.freeze(
  Object.fromEntries(Object.entries(allCards).filter(([key]) => key !== 'card_back'))
);

/**
 * 将后端相对资源路径或 cardCode 解析为可访问的 Vite 资源 URL。
 * @param {string} pathOrCode 例如 games/uno/cards/red_7.png 或 red_7
 * @returns {string}
 */
export function resolveUnoCardAssetUrl(pathOrCode) {
  const raw = String(pathOrCode || '').trim();
  if (!raw) {
    return '';
  }
  const normalized = raw
    .replace(/^\/+/, '')
    .replace(/^assets\//, '')
    .replace(/^games\/uno\/cards\//, '')
    .replace(/\.png$/i, '')
    .replace(/\.svg$/i, '');
  if (!normalized) {
    return '';
  }
  if (normalized === 'card_back') {
    return cardBack;
  }
  return faceCards[normalized] || '';
}

export const UNO_ASSET_CONFIG = Object.freeze({
  cardBack,
  cards: Object.freeze(faceCards)
});
