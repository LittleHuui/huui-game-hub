import { defineStore } from 'pinia';

/**
 * @typedef {object} WalletLedger
 * @property {string} clientId
 * @property {string|null} serverId
 * @property {string} userId
 * @property {string} deviceId
 * @property {string} gameCode
 * @property {'gain'|'cost'|'refund'} type
 * @property {string} reason
 * @property {number} amount
 * @property {number} createdAt
 * @property {number} updatedAt
 * @property {number|null} syncedAt
 * @property {'pending'|'synced'|'failed'} syncStatus
 * @property {Record<string, unknown>} payload
 */

export const useWalletStore = defineStore('wallet', {
  state: () => ({
    /** @type {Record<string, WalletLedger[]>} */
    walletLedgersByUser: {}
  }),
  actions: {
    replaceAll(map) {
      this.walletLedgersByUser = map && typeof map === 'object' ? { ...map } : {};
    },
    /** @param {string} userId */
    listForUser(userId) {
      return this.walletLedgersByUser[userId] || [];
    }
  }
});
