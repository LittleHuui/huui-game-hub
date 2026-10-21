import { storeToRefs } from 'pinia';
import { useStrategyTurnGameViewStore } from '../stores/strategyTurnGameViewStore.js';
import * as gameViewService from '../services/strategyTurnGameViewService.js';

/**
 * 读取策略回合 GameView 展示快照（来自 Pinia store）。
 */
export function useStrategyTurnGameView() {
  const store = useStrategyTurnGameViewStore();
  const {
    roomId,
    gameCode,
    phase,
    version,
    viewerPlayerId,
    currentPlayerId,
    isGameOver,
    terminalMetadata,
    publicState,
    privateState,
    actionOffers,
    frameEvents,
    playbackBusy,
    syncStatus,
    syncError
  } = storeToRefs(store);

  /**
   * 清空当前房间的展示快照。
   * 页面卸载由房间生命周期统一处理，读取视图本身不影响共享传输状态。
   * @returns {void}
   */
  function reset() {
    gameViewService.resetGameViewState();
  }

  return {
    roomId,
    gameCode,
    phase,
    version,
    viewerPlayerId,
    currentPlayerId,
    isGameOver,
    terminalMetadata,
    publicState,
    privateState,
    actionOffers,
    frameEvents,
    playbackBusy,
    syncStatus,
    syncError,
    reload: gameViewService.requestAuthoritativeReload,
    reset
  };
}
