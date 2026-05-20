import { defineStore } from 'pinia';

/**
 * @typedef {object} ShopItem
 * @property {string} propCode
 * @property {string} name
 * @property {string} description
 * @property {string} icon
 * @property {number} price
 * @property {number|null} maxUsePerMatch
 * @property {number|null} sortNo
 * @property {string|null} effectType
 */

export const useShopStore = defineStore('shop', {
  state: () => ({
    /** @type {Record<string, ShopItem[]>} */
    itemsByGame: {},
    /** @type {Record<string, boolean>} */
    loadedFromApi: {}
  }),
  getters: {
    /**
     * @returns {(gameCode: string) => ShopItem[]}
     */
    itemsForGame: (state) => (gameCode) => state.itemsByGame[gameCode] || [],
    /**
     * @returns {(gameCode: string, propCode: string) => ShopItem|undefined}
     */
    findItem() {
      return (gameCode, propCode) =>
        (this.itemsByGame[gameCode] || []).find((i) => i.propCode === propCode);
    }
  },
  actions: {
    /**
     * @param {string} gameCode
     * @param {ShopItem[]} items
     * @param {boolean} [fromApi]
     */
    setItems(gameCode, items, fromApi = false) {
      this.itemsByGame = {
        ...this.itemsByGame,
        [gameCode]: Array.isArray(items) ? [...items] : []
      };
      if (fromApi) {
        this.loadedFromApi = { ...this.loadedFromApi, [gameCode]: true };
      }
    }
  }
});
