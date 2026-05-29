import { defineStore } from 'pinia';

const EMPTY_SNAPSHOT = Object.freeze({
  roomId: '',
  gameCode: '',
  phase: '',
  version: 0,
  viewerPlayerId: '',
  currentPlayerId: '',
  isGameOver: false,
  publicState: {},
  privateState: {},
  legalActions: [],
  frameEvents: [],
  animationHint: '',
  playbackBusy: false
});

export const useStrategyTurnGameViewStore = defineStore('strategyTurnGameView', {
  state: () => ({
    roomId: '',
    gameCode: '',
    phase: '',
    version: 0,
    viewerPlayerId: '',
    currentPlayerId: '',
    isGameOver: false,
    publicState: {},
    privateState: {},
    legalActions: [],
    frameEvents: [],
    animationHint: '',
    playbackBusy: false
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
      this.publicState =
        payload.publicState && typeof payload.publicState === 'object' ? payload.publicState : {};
      this.privateState =
        payload.privateState && typeof payload.privateState === 'object' ? payload.privateState : {};
      this.legalActions = Array.isArray(payload.legalActions) ? payload.legalActions : [];
      this.frameEvents = Array.isArray(payload.frameEvents) ? payload.frameEvents : [];
      this.animationHint = String(payload.animationHint || '');
      this.playbackBusy = Boolean(payload.playbackBusy);
    },
    /**
     * 重置为初始展示态。
     */
    clearDisplaySnapshot() {
      this.setDisplaySnapshot(EMPTY_SNAPSHOT);
    }
  }
});
