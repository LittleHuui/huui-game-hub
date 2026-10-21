import { defineStore } from 'pinia';
import { shareUnchangedStructure } from '../utils/structuralShare.js';

const EMPTY_SNAPSHOT = Object.freeze({
  roomId: '',
  gameCode: '',
  phase: '',
  version: 0,
  viewerPlayerId: '',
  currentPlayerId: '',
  isGameOver: false,
  terminalMetadata: null,
  publicState: {},
  privateState: {},
  actionOffers: [],
  frameEvents: [],
  playbackBusy: false,
  syncStatus: 'IDLE',
  syncError: ''
});

/**
 * 将无效对象归一为稳定的空对象。
 * @param {unknown} value
 * @returns {object}
 */
function normalizeObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

/**
 * 将无效数组归一为稳定的空数组。
 * @param {unknown} value
 * @returns {object[]}
 */
function normalizeArray(value) {
  return Array.isArray(value) ? value : [];
}

export const useStrategyTurnGameViewStore = defineStore('strategyTurnGameView', {
  state: () => ({
    roomId: '',
    gameCode: '',
    phase: '',
    version: 0,
    viewerPlayerId: '',
    currentPlayerId: '',
    isGameOver: false,
    terminalMetadata: null,
    publicState: {},
    privateState: {},
    actionOffers: [],
    frameEvents: [],
    playbackBusy: false,
    syncStatus: 'IDLE',
    syncError: ''
  }),
  actions: {
    /**
     * 写入展示快照（由 strategyTurnGameViewService 调用）。
     * @param {object} snapshot
     */
    setDisplaySnapshot(snapshot) {
      const payload = snapshot && typeof snapshot === 'object' ? snapshot : EMPTY_SNAPSHOT;
      this.roomId = String(payload.roomId || '');
      this.gameCode = String(payload.gameCode || '');
      this.phase = String(payload.phase || '');
      this.version = Number(payload.version) || 0;
      this.viewerPlayerId = String(payload.viewerPlayerId || '');
      this.currentPlayerId = String(payload.currentPlayerId || '');
      this.isGameOver = Boolean(payload.isGameOver);
      const terminalMetadata =
        payload.terminalMetadata && typeof payload.terminalMetadata === 'object'
          ? payload.terminalMetadata
          : null;
      this.terminalMetadata = terminalMetadata
        ? shareUnchangedStructure(this.terminalMetadata, terminalMetadata)
        : null;
      this.publicState = shareUnchangedStructure(
        this.publicState,
        normalizeObject(payload.publicState)
      );
      this.privateState = shareUnchangedStructure(
        this.privateState,
        normalizeObject(payload.privateState)
      );
      this.actionOffers = shareUnchangedStructure(
        this.actionOffers,
        normalizeArray(payload.actionOffers)
      );
      this.frameEvents = shareUnchangedStructure(
        this.frameEvents,
        normalizeArray(payload.frameEvents)
      );
      this.playbackBusy = Boolean(payload.playbackBusy);
      this.syncStatus = String(payload.syncStatus || 'IDLE');
      this.syncError = String(payload.syncError || '');
    },
    /**
     * 重置为初始展示态。
     */
    clearDisplaySnapshot() {
      this.setDisplaySnapshot(EMPTY_SNAPSHOT);
    }
  }
});
