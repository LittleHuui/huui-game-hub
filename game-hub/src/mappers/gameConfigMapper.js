import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';
import { mapGamePropRuleToShopItem } from './propMapper.js';

/**
 * 按 gameCode 查找种子中的游戏配置。
 * @param {string} gameCode
 * @param {typeof GAME_SEED_CONFIG} [seedConfig]
 * @returns {object|null}
 */
export function getSeedGameConfig(gameCode, seedConfig = GAME_SEED_CONFIG) {
  const games = Array.isArray(seedConfig?.games) ? seedConfig.games : [];
  return games.find((g) => g && g.gameCode === gameCode) || null;
}

/**
 * 合并平台道具定义与游戏规则，生成商城商品列表。
 * @param {typeof GAME_SEED_CONFIG} seedConfig
 * @param {string} gameCode
 * @returns {import('../stores/shopStore.js').ShopItem[]}
 */
export function mergeGameProps(seedConfig, gameCode) {
  const game = getSeedGameConfig(gameCode, seedConfig);
  if (!game) {
    return [];
  }
  const propMap = {};
  for (const def of Array.isArray(seedConfig?.props) ? seedConfig.props : []) {
    if (def?.propCode) {
      propMap[def.propCode] = def;
    }
  }
  const items = [];
  for (const rule of Array.isArray(game.propRules) ? game.propRules : []) {
    if (!rule?.propCode || rule.enabled === false) {
      continue;
    }
    const definition = propMap[rule.propCode];
    if (!definition || definition.enabled === false) {
      continue;
    }
    const price =
      rule.price != null ? Number(rule.price) : definition.basePrice != null ? Number(definition.basePrice) : 0;
    items.push(
      mapGamePropRuleToShopItem(
        {
          ...rule,
          propName: definition.propName,
          price
        },
        definition
      )
    );
  }
  return items;
}
