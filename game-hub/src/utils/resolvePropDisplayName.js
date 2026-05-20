import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';
import { mergeGameProps } from '../mappers/gameConfigMapper.js';
import { useShopStore } from '../stores/shopStore.js';

/**
 * 从平台种子道具定义解析展示名。
 * @param {string} propCode
 * @returns {string}
 */
function nameFromSeedDefinitions(propCode) {
  const defs = Array.isArray(GAME_SEED_CONFIG?.props) ? GAME_SEED_CONFIG.props : [];
  const def = defs.find((d) => d?.propCode === propCode);
  return def?.propName || '';
}

/**
 * 从种子商城合并结果解析展示名。
 * @param {string} gameCode
 * @param {string} propCode
 * @returns {string}
 */
function nameFromSeedShop(gameCode, propCode) {
  const items = mergeGameProps(GAME_SEED_CONFIG, gameCode);
  const item = items.find((i) => i.propCode === propCode);
  return item?.name || '';
}

/**
 * 判断是否为可用的道具展示名（非 propCode 占位）。
 * @param {string|undefined} name
 * @param {string} propCode
 * @returns {boolean}
 */
function isUsableDisplayName(name, propCode) {
  return Boolean(name && name !== propCode);
}

/**
 * 解析道具展示名：优先商城/规则，其次种子配置，最后回退 propCode。
 * @param {string} propCode
 * @param {string} [gameCode]
 * @returns {string}
 */
export function resolvePropDisplayName(propCode, gameCode) {
  const code = String(propCode || '').trim();
  if (!code) {
    return '';
  }

  const shopStore = useShopStore();

  if (gameCode) {
    const item = shopStore.findItem(gameCode, code);
    if (isUsableDisplayName(item?.name, code)) {
      return item.name;
    }
    const seedShopName = nameFromSeedShop(gameCode, code);
    if (isUsableDisplayName(seedShopName, code)) {
      return seedShopName;
    }
  }

  for (const loadedGameCode of Object.keys(shopStore.itemsByGame)) {
    const item = shopStore.findItem(loadedGameCode, code);
    if (isUsableDisplayName(item?.name, code)) {
      return item.name;
    }
  }

  const seedDefName = nameFromSeedDefinitions(code);
  if (seedDefName) {
    return seedDefName;
  }

  return code;
}
