import { computed, ref } from 'vue';
import { createInitialTiles, getMaxTileFromTiles } from './game2048Engine.js';
import { GAME2048_PROP, getGame2048ModePropLimit } from './game2048Config.js';
import { createGameTimer } from '../../composables/createGameTimer.js';

/**
 * Creates reactive runtime state for the 2048 page.
 * @param {{ propQuantities: import('vue').ComputedRef<Record<string, number>>, resultModal: object }} deps
 * @returns {object}
 */
export function use2048GameState({ propQuantities, resultModal }) {
  const tiles = ref(createInitialTiles());
  const activeTool = ref('');
  const gameStatus = ref('idle');
  const score = ref(0);
  const moves = ref(0);
  const scorePenalty = ref(0);
  const clearCellUses = ref(0);
  const reached2048Flag = ref(false);
  const elapsedSec = ref(0);
  const gameMessage = ref('点击开始对局，或直接在棋盘用方向键 / WASD / 滑动开始');
  const matchSessionId = ref(null);
  const currentMatchPropUses = ref([]);
  const usedClearCell = ref(0);
  const isMoving = ref(false);
  const isSettling = ref(false);
  const isStarting = ref(false);
  const isPaused = ref(false);

  const gameTimer = createGameTimer({
    onTick: () => {
      if (!isPaused.value && gameStatus.value === 'playing') {
        elapsedSec.value++;
      }
    }
  });

  const maxTile = computed(() => getMaxTileFromTiles(tiles.value));
  const isGameInProgress = computed(
    () => gameStatus.value === 'playing' || gameStatus.value === 'paused'
  );
  const isPropSelecting = computed(() => activeTool.value === GAME2048_PROP.CLEAR_CELL);
  const isOperationLocked = computed(
    () => isStarting.value || isMoving.value || isSettling.value
  );
  const canAcceptMoveInput = computed(
    () =>
      gameStatus.value === 'playing' &&
      !isPaused.value &&
      !isOperationLocked.value &&
      !isPropSelecting.value &&
      !isResultModalVisible()
  );
  const moveInputLocked = computed(
    () =>
      gameStatus.value === 'ended' ||
      gameStatus.value === 'settling' ||
      isPaused.value ||
      isOperationLocked.value ||
      isPropSelecting.value ||
      isResultModalVisible()
  );
  const canRestartGame = computed(
    () => !isOperationLocked.value && gameStatus.value !== 'settling'
  );
  const canPlayAgain = computed(
    () => gameStatus.value === 'ended' && !isOperationLocked.value
  );
  const canEndGame = computed(
    () =>
      (gameStatus.value === 'playing' || gameStatus.value === 'settling') &&
      !isOperationLocked.value
  );

  /**
   * Returns the per-match prop usage limit.
   * @param {string} propCode
   * @returns {number}
   */
  function propLimit(propCode) {
    const fromMode = getGame2048ModePropLimit(propCode);
    return fromMode != null ? fromMode : 0;
  }

  /**
   * Returns remaining prop usage count for the current match.
   * @param {string} propCode
   * @returns {number}
   */
  function propRemaining(propCode) {
    return Math.max(0, propLimit(propCode) - usedClearCell.value);
  }

  /**
   * Returns owned prop quantity.
   * @param {string} propCode
   * @returns {number}
   */
  function propQuantity(propCode) {
    return propQuantities.value[propCode] || 0;
  }

  const canUseClearCell = computed(
    () =>
      !isPaused.value &&
      !isOperationLocked.value &&
      gameStatus.value === 'playing' &&
      propRemaining(GAME2048_PROP.CLEAR_CELL) > 0
  );

  /**
   * Stops the page timer.
   * @returns {void}
   */
  function stopTimer() {
    gameTimer.stop();
  }

  /**
   * Starts the page timer from the current elapsed value.
   * @returns {void}
   */
  function startTimer() {
    stopTimer();
    gameTimer.start();
  }

  /**
   * Resets mutable match runtime state while keeping the preview board lifecycle explicit.
   * @param {string} [message]
   * @returns {void}
   */
  function resetRuntime(message) {
    stopTimer();
    activeTool.value = '';
    gameStatus.value = 'idle';
    score.value = 0;
    moves.value = 0;
    scorePenalty.value = 0;
    clearCellUses.value = 0;
    reached2048Flag.value = false;
    elapsedSec.value = 0;
    matchSessionId.value = null;
    currentMatchPropUses.value = [];
    usedClearCell.value = 0;
    isMoving.value = false;
    isSettling.value = false;
    isStarting.value = false;
    isPaused.value = false;
    gameMessage.value = message || '在棋盘用方向键 / WASD / 滑动即可开始对局';
  }

  /**
   * Creates a new preview board and resets match runtime state.
   * @param {string} [message]
   * @returns {void}
   */
  function setupBoard(message) {
    tiles.value = createInitialTiles();
    resetRuntime(message);
  }

  /**
   * Returns whether the composed result modal is currently visible.
   * @returns {boolean}
   */
  function isResultModalVisible() {
    return Boolean(resultModal?.value?.visible ?? resultModal?.visible);
  }

  return {
    tiles,
    activeTool,
    gameStatus,
    score,
    moves,
    scorePenalty,
    clearCellUses,
    reached2048Flag,
    elapsedSec,
    gameMessage,
    matchSessionId,
    currentMatchPropUses,
    usedClearCell,
    isMoving,
    isSettling,
    isStarting,
    isPaused,
    maxTile,
    isGameInProgress,
    isPropSelecting,
    isOperationLocked,
    canAcceptMoveInput,
    moveInputLocked,
    canRestartGame,
    canPlayAgain,
    canEndGame,
    canUseClearCell,
    propLimit,
    propRemaining,
    propQuantity,
    startTimer,
    stopTimer,
    resetRuntime,
    setupBoard
  };
}
