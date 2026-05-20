import { defineStore } from 'pinia';

/**
 * @typedef {object} InventoryLedger
 * @property {string} clientId
 * @property {string|null} serverId
 * @property {string} userId
 * @property {string} deviceId
 * @property {string} gameCode
 * @property {string} propCode
 * @property {'gain'|'cost'} type
 * @property {number} amount
 * @property {string} reason
 * @property {number} createdAt
 * @property {number} updatedAt
 * @property {number|null} syncedAt
 * @property {'pending'|'synced'|'failed'} syncStatus
 * @property {Record<string, unknown>} payload
 */

export const useInventoryStore = defineStore('inventory', {
  state: () => ({
    /** @type {Record<string, InventoryLedger[]>} */
    inventoryLedgersByUser: {},
    /** @type {Record<string, Record<string, Record<string, number>>>} userId → gameCode → propCode → qty */
    bagByUser: {}
  }),
  actions: {
    /**
     * @param {Record<string, InventoryLedger[]>} ledgers
     * @param {Record<string, Record<string, Record<string, number>>>} [bags]
     */
    replaceAll(ledgers, bags) {
      this.inventoryLedgersByUser = ledgers && typeof ledgers === 'object' ? { ...ledgers } : {};
      this.bagByUser = bags && typeof bags === 'object' ? { ...bags } : {};
    },
    listForUser(userId) {
      return this.inventoryLedgersByUser[userId] || [];
    },
    /**
     * 服务端 user_prop_bag 快照（按游戏）。
     * @param {string} userId
     * @param {string} gameCode
     * @returns {Record<string, number>|null}
     */
    bagForGame(userId, gameCode) {
      const byGame = this.bagByUser[userId];
      if (!byGame || !gameCode) {
        return null;
      }
      const bag = byGame[gameCode];
      return bag && typeof bag === 'object' ? bag : null;
    },
    /**
     * @param {string} userId
     * @param {Record<string, Record<string, number>>} byGame propCode 数量按 gameCode 分组
     */
    setBagForUser(userId, byGame) {
      if (!userId) {
        return;
      }
      this.bagByUser = {
        ...this.bagByUser,
        [userId]: byGame && typeof byGame === 'object' ? { ...byGame } : {}
      };
    },
    /**
     * @param {string} userId
     * @param {string} gameCode
     * @param {Record<string, number>} quantities
     */
    setBagForGame(userId, gameCode, quantities) {
      if (!userId || !gameCode) {
        return;
      }
      const prev = this.bagByUser[userId] || {};
      this.bagByUser = {
        ...this.bagByUser,
        [userId]: {
          ...prev,
          [gameCode]: quantities && typeof quantities === 'object' ? { ...quantities } : {}
        }
      };
    }
  }
});
