import { defineStore } from 'pinia';

export const useHistoryStore = defineStore('history', {
  state: () => ({
    /** @type {Record<string, object[]>} */
    matchRecordsByUser: {},
    /** @type {Record<string, object[]>} */
    scoreRecordsByUser: {},
    /** @type {Record<string, object[]>} */
    purchaseRecordsByUser: {},
    /** @type {Record<string, object[]>} */
    propUsageRecordsByUser: {},
    /** @type {object[]} */
    pendingEvents: []
  }),
  actions: {
    replaceMatches(map) {
      this.matchRecordsByUser = map && typeof map === 'object' ? { ...map } : {};
    },
    replaceScores(map) {
      this.scoreRecordsByUser = map && typeof map === 'object' ? { ...map } : {};
    },
    replacePurchases(map) {
      this.purchaseRecordsByUser = map && typeof map === 'object' ? { ...map } : {};
    },
    replacePropUsage(map) {
      this.propUsageRecordsByUser = map && typeof map === 'object' ? { ...map } : {};
    },
    setPending(list) {
      this.pendingEvents = Array.isArray(list) ? [...list] : [];
    },
    matchesForUser(userId) {
      return this.matchRecordsByUser[userId] || [];
    },
    purchasesForUser(userId) {
      return this.purchaseRecordsByUser[userId] || [];
    },
    propUsageForUser(userId) {
      return this.propUsageRecordsByUser[userId] || [];
    }
  }
});
