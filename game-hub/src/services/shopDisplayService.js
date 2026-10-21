import { useShopStore } from '../stores/shopStore.js';
import { resolvePropDisplayName } from '../utils/resolvePropDisplayName.js';

/**
 * 从 shop store 解析道具展示名。
 * @param {string} propCode
 * @param {string} [gameCode]
 * @returns {string}
 */
export function resolvePropDisplayNameFromShop(propCode, gameCode) {
  const shopStore = useShopStore();
  return resolvePropDisplayName(propCode, gameCode, {
    findShopItem: (gc, pc) => shopStore.findItem(gc, pc),
    shopItemsByGame: shopStore.itemsByGame
  });
}
