import { defineStore } from 'pinia';
import { mapMatchRecord } from '../mappers/matchMapper.js';
import { mapScoreRecord } from '../mappers/scoreMapper.js';
import { recentHistoryRecords } from '../utils/historySort.js';

/**
 * @param {object[]} rows
 * @param {(row: object) => object} mapper
 * @returns {object[]}
 */
function sanitizeRecordList(rows, mapper) {
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.map((row) => {
    const mapped = mapper(row);
    return {
      ...mapped,
      syncStatus: row.syncStatus || mapped.syncStatus || 'pending'
    };
  });
}

/**
 * @param {Record<string, object[]>} map
 * @param {(row: object) => object} mapper
 * @returns {Record<string, object[]>}
 */
function sanitizeRecordMap(map, mapper) {
  if (!map || typeof map !== 'object') {
    return {};
  }
  const next = {};
  for (const [uid, rows] of Object.entries(map)) {
    next[uid] = sanitizeRecordList(rows, mapper);
  }
  return next;
}

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
      this.matchRecordsByUser = sanitizeRecordMap(map, mapMatchRecord);
    },
    replaceScores(map) {
      this.scoreRecordsByUser = sanitizeRecordMap(map, mapScoreRecord);
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
      const rows = this.matchRecordsByUser[userId] || [];
      return recentHistoryRecords(rows, 50);
    },
    purchasesForUser(userId) {
      const rows = this.purchaseRecordsByUser[userId] || [];
      return recentHistoryRecords(rows, 50);
    },
    propUsageForUser(userId) {
      const rows = this.propUsageRecordsByUser[userId] || [];
      return recentHistoryRecords(rows, 50);
    }
  }
});
