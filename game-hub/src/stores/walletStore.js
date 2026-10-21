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
    walletLedgersByUser: {},
    /** 首屏展示缓存，完整事实流水仍保存在 walletLedgersByUser。 */
    displayPagesByUser: {}
  }),
  actions: {
    replaceAll(map) {
      this.walletLedgersByUser = map && typeof map === 'object' ? { ...map } : {};
      this.displayPagesByUser = {};
    },
    /** @param {string} userId */
    listForUser(userId) {
      return this.walletLedgersByUser[userId] || [];
    },
    setDisplayPage(userId, rows) {
      this.displayPagesByUser[userId] = rows;
    },
    displayPageForUser(userId) {
      return this.displayPagesByUser[userId] || this.listForUser(userId);
    }
  }
});
