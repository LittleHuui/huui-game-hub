import { defineStore } from 'pinia';

/** 排行榜仅展示服务端返回；离线不展示真实榜。 */
export const useRankingStore = defineStore('ranking', {
  state: () => ({
    /** @type {null | Record<string, Record<string, object[]>>} */
    summary: null,
    lastFetchedAt: 0
  }),
  actions: {
    setSummary(s) {
      this.summary = s;
      this.lastFetchedAt = Date.now();
    },
    makeBucketKey(difficultyCode, mode) {
      if (!mode || String(mode).trim() === '') {
        throw new Error('缺少 mode');
      }
      if (!difficultyCode || String(difficultyCode).trim() === '') {
        throw new Error('缺少 difficultyCode');
      }
      return `${mode}::${difficultyCode}`;
    },
    setDifficultyItems(gameCode, difficultyCode, items, mode) {
      const base = this.summary && typeof this.summary === 'object' ? { ...this.summary } : {};
      const game = base[gameCode] && typeof base[gameCode] === 'object' ? { ...base[gameCode] } : {};
      game[this.makeBucketKey(difficultyCode, mode)] = Array.isArray(items) ? items : [];
      base[gameCode] = game;
      this.summary = base;
      this.lastFetchedAt = Date.now();
    },
    clear() {
      this.summary = null;
    },
    listForDifficulty(gameCode, difficultyCode, mode) {
      if (!mode || !difficultyCode) {
        return [];
      }
      if (!this.summary || !this.summary[gameCode]) {
        return [];
      }
      const g = this.summary[gameCode];
      const bucket = g[this.makeBucketKey(difficultyCode, mode)];
      return Array.isArray(bucket) ? bucket : [];
    }
  }
});
