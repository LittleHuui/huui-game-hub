import { defineStore } from 'pinia';
import { GAME_REGISTRY } from '../constants/gameRegistry.js';

export const usePlatformStore = defineStore('platform', {
  state: () => ({
    currentGameCode: 'minesweeper',
    currentGameMode: 'single',
    bootStatus: 'syncing',
    networkMode: 'unknown',
    /** 最近一次 health 探测是否成功 */
    remoteAvailable: false,
    syncMessage: '正在同步云存档...',
    /** boot/context 返回的 games，在线时优先用于目录 */
    bootGames: null,
    /** 顶栏展示用的游戏目录（已过滤 enabled、排序） */
    gameCatalog: [],
    /** 扫雷当前难度（供数据源切换等跨页面编排使用） */
    minesweeperDifficulty: 'easy'
  }),
  getters: {
    /**
     * 当前游戏定义（目录 + 注册表能力合并）。
     * @param {object} state
     * @returns {object}
     */
    currentGameDef(state) {
      const fromCatalog = state.gameCatalog.find((g) => g.code === state.currentGameCode);
      if (fromCatalog) {
        return fromCatalog;
      }
      const reg = GAME_REGISTRY[state.currentGameCode];
      if (reg) {
        return {
          code: reg.code,
          name: reg.name,
          subName: reg.subName,
          logo: reg.logo,
          supportOnline: reg.supportOnline,
          enabled: true,
          sortNo: 0,
          playable: state.currentGameCode === 'minesweeper',
          capabilities: reg.capabilities || {}
        };
      }
      return state.gameCatalog[0] || null;
    },
    isPlayable(state) {
      return state.bootStatus === 'ready';
    }
  },
  actions: {
    setBoot(syncing, message) {
      this.bootStatus = syncing ? 'syncing' : this.bootStatus;
      if (message) {
        this.syncMessage = message;
      }
    },
    markReady(networkMode, message) {
      this.bootStatus = 'ready';
      this.networkMode = networkMode;
      if (message) {
        this.syncMessage = message;
      }
    },
    markError(message) {
      this.bootStatus = 'error';
      if (message) {
        this.syncMessage = message;
      }
    },
    /**
     * 在线模式等待用户登录。
     * @param {string} [message]
     */
    markWaitingLogin(message) {
      this.bootStatus = 'waitingLogin';
      this.networkMode = 'online';
      this.remoteAvailable = true;
      if (message) {
        this.syncMessage = message;
      }
    },
    /**
     * 写入 boot 返回的游戏列表。
     * @param {object[]|null} games
     */
    setBootGames(games) {
      this.bootGames = Array.isArray(games) ? games : null;
    },
    /**
     * 写入顶栏游戏目录。
     * @param {object[]} list
     */
    setGameCatalog(list) {
      this.gameCatalog = Array.isArray(list) ? list : [];
    },
    setCurrentGame(code) {
      if (this.gameCatalog.some((g) => g.code === code)) {
        this.currentGameCode = code;
        return;
      }
      if (GAME_REGISTRY[code]) {
        this.currentGameCode = code;
      }
    },
    /**
     * 同步扫雷当前难度，供 activateGame 等编排使用。
     * @param {string} difficultyCode
     */
    setMinesweeperDifficulty(difficultyCode) {
      if (difficultyCode) {
        this.minesweeperDifficulty = difficultyCode;
      }
    }
  }
});
