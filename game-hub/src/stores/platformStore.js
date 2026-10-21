import { defineStore } from 'pinia';
import {
  getGameDisplayMetadata,
  getGameFrontendModule
} from '../games/gameModuleRegistry.js';

export const usePlatformStore = defineStore('platform', {
  state: () => ({
    currentGameCode: '',
    currentGameMode: '',
    bootStatus: 'syncing',
    networkMode: 'unknown',
    /** 最近一次依赖就绪探测是否成功 */
    remoteAvailable: false,
    syncMessage: '正在同步云存档...',
    /** boot/context 返回的 games，在线时优先用于目录 */
    bootGames: null,
    /** 顶栏展示用的游戏目录（已过滤 enabled、排序） */
    gameCatalog: [],
    /** 对局进行中禁止顶栏切换游戏 */
    gameSwitchLocked: false,
    gameSwitchLockReason: ''
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
      const module = getGameFrontendModule(state.currentGameCode);
      const metadata = getGameDisplayMetadata(state.currentGameCode);
      if (module && metadata) {
        const caps = module.capabilities || {};
        return {
          code: module.gameCode,
          name: metadata.name,
          subName: metadata.subName,
          logo: metadata.logo,
          supportOnline: caps.onlineBattle === true,
          enabled: true,
          sortNo: 0,
          playable: caps.offline === true || caps.leaderboard === true || caps.shop === true,
          capabilities: caps
        };
      }
      return null;
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
    /**
     * 选择已注册游戏并写入其默认模式。
     * @param {string} code
     * @returns {void}
     */
    setCurrentGame(code) {
      const module = getGameFrontendModule(code);
      if (!module) {
        return;
      }
      this.currentGameCode = code;
      const metadata = getGameDisplayMetadata(code);
      this.currentGameMode = metadata?.modes?.[0] || '';
    },
    /**
     * 锁定顶栏游戏切换（对局进行中）。
     * @param {string} [reason]
     */
    lockGameSwitch(reason = '') {
      this.gameSwitchLocked = true;
      if (reason) {
        this.gameSwitchLockReason = reason;
      }
    },
    /**
     * 解除顶栏游戏切换锁。
     * @returns {void}
     */
    unlockGameSwitch() {
      this.gameSwitchLocked = false;
      this.gameSwitchLockReason = '';
    }
  }
});
