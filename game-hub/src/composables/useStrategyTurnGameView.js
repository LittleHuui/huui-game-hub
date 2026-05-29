import { storeToRefs } from 'pinia';
import { useStrategyTurnGameViewStore } from '../stores/strategyTurnGameViewStore.js';

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
    publicState,
    privateState,
    legalActions,
    frameEvents,
    animationHint,
    playbackBusy
  } = storeToRefs(store);

  return {
    roomId,
    gameCode,
    phase,
    version,
    viewerPlayerId,
    currentPlayerId,
    isGameOver,
    publicState,
    privateState,
    legalActions,
    frameEvents,
    animationHint,
    playbackBusy
  };
}
