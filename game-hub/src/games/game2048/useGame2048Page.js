import './game2048.css';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import Game2048Board from './components/Game2048Board.vue';
import { LightSingleGameLayout } from '../../game-templates/light-single/index.js';
import {
  GameMatchStatsPanel,
  GameResultModal,
  GameShopPanel,
  GameRankingPanel,
  GameInventoryPanel
} from '../../components/game/index.js';
import { game2048Module } from './gameModule.js';
import {
  GAME2048_CODE,
  GAME2048_MODE,
  GAME2048_PROP,
  getGame2048DifficultyConfig
} from './game2048Config.js';
import { useGamePropQuantities } from '../../composables/useGamePropQuantities.js';
import { useGameSwitchLock } from '../../composables/useGameSwitchLock.js';
import { usePageVisibilityPause } from '../../composables/usePageVisibilityPause.js';
import { createGameSession } from '../../services/gameSessionService.js';
import { activateGame } from '../../services/gameLifecycleService.js';
import * as toastService from '../../services/toastService.js';
import { usePlatformStore } from '../../stores/platformStore.js';
import { getDefaultDifficultyCode } from '../../services/gameDifficultyService.js';
import { createGame2048Service } from './Game2048Service.js';
import { use2048Animation } from './use2048Animation.js';
import { use2048GameState } from './use2048GameState.js';
import { use2048Input } from './use2048Input.js';
import { use2048Move } from './use2048Move.js';
import { use2048Persistence } from './use2048Persistence.js';
import { use2048Presentation } from './use2048Presentation.js';
import { use2048Prop } from './use2048Prop.js';
import { use2048ResultFlow } from './use2048ResultFlow.js';

export const pageComponents = {
  Game2048Board,
  LightSingleGameLayout,
  GameMatchStatsPanel,
  GameResultModal,
  GameShopPanel,
  GameRankingPanel,
  GameInventoryPanel
};

/**
 * Composes the 2048 page state, services, animation and lifecycle handlers.
 * @returns {object}
 */
export function useGame2048Page() {
  const session = createGameSession({ gameCode: GAME2048_CODE });
  const platform = usePlatformStore();
  const propQuantities = useGamePropQuantities(GAME2048_CODE);
  const boardComponentRef = ref(null);
  const difficultyCode = computed(
    () => getGame2048DifficultyConfig().difficultyCode || getDefaultDifficultyCode(GAME2048_CODE)
  );
  const gameConfig = computed(() => getGame2048DifficultyConfig());
  const displayMetadata = game2048Module.displayMetadata;
  const resultModalRef = ref(null);
  const state = use2048GameState({ propQuantities, resultModal: resultModalRef });
  const animation = use2048Animation();
  const gameService = createGame2048Service({ session, gameConfig, difficultyCode });
  const resultFlow = use2048ResultFlow({
    state,
    gameService,
    getPayload: () => ({
      maxTile: state.maxTile.value,
      moves: state.moves.value,
      reached2048: state.reached2048Flag.value,
      clearCellUses: state.clearCellUses.value,
      scorePenalty: state.scorePenalty.value
    })
  });
  resultModalRef.value = resultFlow.resultModal;
  const persistence = use2048Persistence({ gameService, state });
  const rewardScorePreview = computed(() => gameService.rewardForScore(state.score.value));
  const presentation = use2048Presentation({
    state,
    displayMetadata,
    rewardScorePreview,
    formatDurationMmSs: resultFlow.formatDurationMmSs
  });

  useGameSwitchLock(state.isGameInProgress);
  usePageVisibilityPause({
    shouldPause: () => state.gameStatus.value === 'playing' && !state.isPaused.value,
    pause: pauseGame
  });

  const move = use2048Move({
    state,
    animation,
    boardComponentRef,
    resultModal: resultFlow.resultModal,
    startGame,
    settleGame
  });
  const prop = use2048Prop({
    state,
    animation,
    boardComponentRef,
    persistence,
    showToast,
    settleGame
  });
  const { onWindowKeydown } = use2048Input({
    moveInputLocked: state.moveInputLocked,
    handleMoveInput: move.handleMoveInput
  });

  /**
   * Shows a toast through the shared toast service.
   * @param {string} message
   * @param {string} [level]
   * @returns {void}
   */
  function showToast(message, level = 'info') {
    toastService.push(message, level);
  }

  /**
   * Pauses the current active match.
   * @returns {void}
   */
  function pauseGame() {
    if (state.gameStatus.value !== 'playing' || state.isPaused.value) {
      return;
    }
    state.isPaused.value = true;
    state.activeTool.value = '';
    state.gameMessage.value = '游戏已暂停';
  }

  /**
   * Resumes the paused match.
   * @returns {void}
   */
  function resumeGame() {
    if (!state.isPaused.value) {
      return;
    }
    state.isPaused.value = false;
    if (state.gameStatus.value === 'playing') {
      state.gameMessage.value = '对局已继续';
    }
  }

  /**
   * Routes layout action bar events to page handlers.
   * @param {string} actionKey
   * @returns {void}
   */
  function onLayoutAction(actionKey) {
    const handlers = {
      playAgain,
      restart: restartGame,
      pause: pauseGame,
      resume: resumeGame,
      end: endCurrentGame
    };
    handlers[actionKey]?.();
  }

  /**
   * Starts a match from the idle board state.
   * @returns {Promise<boolean>}
   */
  async function startGame() {
    if (state.gameStatus.value !== 'idle') {
      return state.gameStatus.value === 'playing';
    }
    if (state.isStarting.value) {
      return false;
    }
    state.isStarting.value = true;
    try {
      resultFlow.resultModal.visible = false;
      persistence.ensureSession();
      state.gameStatus.value = 'playing';
      state.startTimer();
      state.gameMessage.value = '对局已开始，滑动棋盘继续';
      return true;
    } finally {
      state.isStarting.value = false;
    }
  }

  /**
   * Prepares a fresh idle board after a completed match.
   * @returns {Promise<void>}
   */
  async function playAgain() {
    if (!state.canPlayAgain.value) return showToast('请等待当前操作完成', 'warning');
    animation.cancelAnimations();
    resultFlow.resultModal.visible = false;
    state.setupBoard('滑动棋盘开始新对局');
    state.matchSessionId.value = session.newMatchSessionId();
    state.currentMatchPropUses.value = [];
    boardComponentRef.value?.focusBoard?.();
  }

  /**
   * Restarts the active match immediately.
   * @returns {Promise<void>}
   */
  async function restartGame() {
    if (!state.canRestartGame.value) return showToast('请等待当前操作完成', 'warning');
    animation.cancelAnimations();
    resultFlow.resultModal.visible = false;
    state.setupBoard('已重新开始，滑动棋盘继续');
    state.matchSessionId.value = session.newMatchSessionId();
    state.currentMatchPropUses.value = [];
    state.gameStatus.value = 'playing';
    state.startTimer();
    boardComponentRef.value?.focusBoard?.();
  }

  /**
   * Ends the current match manually.
   * @returns {Promise<void>}
   */
  async function endCurrentGame() {
    if (state.gameStatus.value === 'idle') return showToast('尚未开始对局', 'info');
    if (state.gameStatus.value === 'ended' || state.gameStatus.value === 'settling') return;
    if (state.isOperationLocked.value) return showToast('请等待当前操作完成', 'warning');
    await settleGame(false);
  }

  /**
   * Cancels animations and delegates match settlement.
   * @param {boolean} naturalGameOver
   * @returns {Promise<void>}
   */
  async function settleGame(naturalGameOver) {
    animation.cancelAnimations();
    await resultFlow.settleGame(naturalGameOver);
  }

  /**
   * Handles result modal button actions.
   * @param {string} actionKey
   * @returns {void}
   */
  function onResultModalAction(actionKey) {
    if (actionKey === 'restart') {
      playAgain();
    } else if (actionKey === 'close') {
      resultFlow.resultModal.visible = false;
    }
  }

  onMounted(async () => {
    platform.setCurrentGame(GAME2048_CODE);
    await activateGame(GAME2048_CODE, {
      difficultyCode: difficultyCode.value,
      mode: GAME2048_MODE,
      includeInventory: true
    });
    state.setupBoard();
    window.addEventListener('keydown', onWindowKeydown);
    boardComponentRef.value?.focusBoard?.();
  });

  onBeforeUnmount(() => {
    animation.cancelAnimations();
    state.stopTimer();
    window.removeEventListener('keydown', onWindowKeydown);
  });

  return {
    GAME2048_CODE,
    GAME2048_MODE,
    GAME2048_PROP,
    session,
    platform,
    propQuantities,
    boardComponentRef,
    difficultyCode,
    ...state,
    slideOffsets: animation.slideOffsets,
    newTileIds: animation.newTileIds,
    mergedTileIds: animation.mergedTileIds,
    clearingTileId: animation.clearingTileId,
    resultModal: resultFlow.resultModal,
    gameConfig,
    rewardScorePreview,
    boardAnimationStyle: animation.boardAnimationStyle,
    ...presentation,
    displayMetadata,
    onLayoutAction,
    showToast,
    resumeGame,
    wait: animation.wait,
    ensureSession: persistence.ensureSession,
    rewardForScore: () => gameService.rewardForScore(state.score.value),
    recordPropUsage: persistence.recordPropUsage,
    isMoveStale: animation.isMoveStale,
    buildSlidePixelOffsets: animation.buildSlidePixelOffsets,
    markMergedTileIds: animation.markMergedTileIds,
    handleMoveInput: move.handleMoveInput,
    startGame,
    handleMove: move.handleMove,
    useProp: prop.useProp,
    handleClearCellSelect: prop.handleClearCellSelect,
    playAgain,
    restartGame,
    endCurrentGame,
    settleGame,
    openResultModal: resultFlow.openResultModal,
    onResultModalAction,
    formatDurationMmSs: resultFlow.formatDurationMmSs,
    onWindowKeydown
  };
}
