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
    inventoryLedgersByUser: {}
  }),
  actions: {
    replaceAll(map) {
      this.inventoryLedgersByUser = map && typeof map === 'object' ? { ...map } : {};
    },
    listForUser(userId) {
      return this.inventoryLedgersByUser[userId] || [];
    }
  }
});
