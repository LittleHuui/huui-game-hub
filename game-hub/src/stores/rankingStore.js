import { defineStore } from 'pinia';

/** 排行榜仅展示服务端返回；离线不展示真实榜。 */
export const useRankingStore = defineStore('ranking', {
  state: () => ({
    /** @type {null | { minesweeper?: { easy?: object[]; medium?: object[]; hard?: object[] } }} */
    summary: null,
    lastFetchedAt: 0
  }),
  actions: {
    setSummary(s) {
      this.summary = s;
      this.lastFetchedAt = Date.now();
    },
    makeBucketKey(difficultyCode, mode = 'single') {
      return `${mode || 'single'}::${difficultyCode}`;
    },
    setDifficultyItems(gameCode, difficultyCode, items, mode = 'single') {
      const base = this.summary && typeof this.summary === 'object' ? { ...this.summary } : {};
      const game = base[gameCode] && typeof base[gameCode] === 'object' ? { ...base[gameCode] } : {};
      game[this.makeBucketKey(difficultyCode, mode)] = Array.isArray(items) ? items : [];
      if ((mode || 'single') === 'single') {
        game[difficultyCode] = Array.isArray(items) ? items : [];
      }
      base[gameCode] = game;
      this.summary = base;
      this.lastFetchedAt = Date.now();
    },
    clear() {
      this.summary = null;
    },
    listForDifficulty(gameCode, difficulty, mode = 'single') {
      if (!this.summary || !this.summary[gameCode]) {
        return [];
      }
      const g = this.summary[gameCode];
      const bucket = g && (g[this.makeBucketKey(difficulty, mode)] || g[difficulty]);
      return Array.isArray(bucket) ? bucket : [];
    }
  }
});
