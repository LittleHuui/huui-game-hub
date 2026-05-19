import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';
import * as gameConfigRepository from '../repositories/gameConfigRepository.js';
import { mergeGameProps } from '../mappers/gameConfigMapper.js';
import { pageItems } from '../mappers/sharedMapper.js';
import { mapGamePropRuleToShopItem } from '../mappers/propMapper.js';
import { useShopStore } from '../stores/shopStore.js';
import { canFetchRemote } from './remoteGate.js';

const MINESWEEPER = 'minesweeper';

/**
 * 拉取道具定义并转为 propCode → 定义 映射。
 * @returns {Promise<Record<string, object>>}
 */
async function fetchDefinitionMap() {
  const data = await gameConfigRepository.fetchPropDefinitions({ enabled: true });
  const list = Array.isArray(data) ? data : pageItems(data);
  const map = {};
  for (const row of list) {
    if (row && row.propCode) {
      map[row.propCode] = row;
    }
  }
  return map;
}

/**
 * 将规则列表写入商城 store。
 * @param {string} gameCode
 * @param {object[]} rules
 * @param {Record<string, object>} [definitionMap]
 * @param {boolean} [fromApi]
 */
export function applyGamePropRules(gameCode, rules, definitionMap = {}, fromApi = false) {
  const list = (Array.isArray(rules) ? rules : [])
    .filter((r) => r && r.propCode && r.enabled !== false)
    .map((r) => mapGamePropRuleToShopItem(r, definitionMap[r.propCode]));
  const items = list.length ? list : mergeGameProps(GAME_SEED_CONFIG, gameCode);
  setGameShopItems(gameCode, items, fromApi);
}

/**
 * 直接写入游戏商城商品。
 * @param {string} gameCode
 * @param {import('../stores/shopStore.js').ShopItem[]} items
 * @param {boolean} [fromApi]
 */
export function setGameShopItems(gameCode, items, fromApi = false) {
  const shopStore = useShopStore();
  shopStore.setItems(gameCode, items, fromApi);
}

/**
 * 直接写入扫雷商城商品。
 * @param {import('../stores/shopStore.js').ShopItem[]} items
 * @param {boolean} [fromApi]
 */
export function setMinesweeperShopItems(items, fromApi = false) {
  setGameShopItems(MINESWEEPER, items, fromApi);
}

/**
 * 从 GET /games/{gameCode}/props 加载游戏商城。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function loadGameShopFromApi(gameCode) {
  const rulesRaw = await gameConfigRepository.fetchGameProps(gameCode);
  const rules = Array.isArray(rulesRaw) ? rulesRaw : pageItems(rulesRaw);
  let definitionMap = {};
  try {
    definitionMap = await fetchDefinitionMap();
  } catch {
    /* 描述可选 */
  }
  applyGamePropRules(gameCode, rules, definitionMap, true);
}

/**
 * 从 GET /games/{gameCode}/props 加载扫雷商城。
 * @returns {Promise<void>}
 */
export async function loadMinesweeperShopFromApi() {
  await loadGameShopFromApi(MINESWEEPER);
}

/**
 * 应用种子合并后的默认游戏商城。
 * @param {string} gameCode
 */
export function applySeedGameShop(gameCode) {
  const items = mergeGameProps(GAME_SEED_CONFIG, gameCode);
  setGameShopItems(gameCode, items, false);
}

/**
 * 应用种子合并后的默认商城。
 */
export function applySeedMinesweeperShop() {
  applySeedGameShop(MINESWEEPER);
}

/**
 * 在线时拉取游戏商城；失败则使用种子合并结果。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function loadGameShop(gameCode) {
  if (!canFetchRemote()) {
    applySeedGameShop(gameCode);
    return;
  }
  try {
    await loadGameShopFromApi(gameCode);
  } catch {
    applySeedGameShop(gameCode);
  }
}

/**
 * 在线时拉取商城；失败则使用种子合并结果。
 * @returns {Promise<void>}
 */
export async function loadMinesweeperShop() {
  await loadGameShop(MINESWEEPER);
}

/**
 * @param {{ networkMode?: string }} [_platform]
 * @returns {Promise<void>}
 */
export async function loadMinesweeperShopIfOnline(_platform) {
  await loadMinesweeperShop();
}
