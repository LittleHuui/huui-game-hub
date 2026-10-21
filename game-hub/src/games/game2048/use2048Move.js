import {
  hasReached2048Tiles,
  isGameOverTiles,
  moveTiles,
  spawnRandomTileOnTiles
} from './game2048Engine.js';

/**
 * Creates the 2048 move input and animation flow.
 * @param {{ state: object, animation: object, boardComponentRef: import('vue').Ref<object|null>, resultModal: object, startGame: Function, settleGame: Function }} deps
 * @returns {{ handleMoveInput: Function, handleMove: Function }}
 */
export function use2048Move({
  state,
  animation,
  boardComponentRef,
  resultModal,
  startGame,
  settleGame
}) {
  /**
   * Accepts a direction input, auto-starting the idle board when allowed.
   * @param {'up'|'down'|'left'|'right'} direction
   * @returns {Promise<void>}
   */
  async function handleMoveInput(direction) {
    if (
      state.isPaused.value ||
      state.isOperationLocked.value ||
      state.isPropSelecting.value ||
      resultModal.visible ||
      state.gameStatus.value === 'ended' ||
      state.gameStatus.value === 'settling'
    ) {
      return;
    }
    if (state.gameStatus.value === 'idle' && !(await startGame())) {
      return;
    }
    if (state.gameStatus.value === 'playing') {
      await handleMove(direction);
    }
  }

  /**
   * Executes one 2048 move and its animation sequence.
   * @param {'up'|'down'|'left'|'right'} direction
   * @returns {Promise<void>}
   */
  async function handleMove(direction) {
    if (!state.canAcceptMoveInput.value) {
      return;
    }
    const gen = animation.nextGeneration();
    const beforeTiles = state.tiles.value;
    const result = moveTiles(beforeTiles, direction);
    if (!result.moved) {
      return;
    }
    state.isMoving.value = true;
    animation.mergedTileIds.value = {};
    animation.newTileIds.value = {};
    try {
      animation.slideOffsets.value = {};
      await animation.nextFrame();
      if (animation.isMoveStale(gen)) return;
      const stridePx = boardComponentRef.value?.getCellStridePx?.() ?? 0;
      animation.slideOffsets.value = animation.buildSlidePixelOffsets(result.slides, stridePx);
      await animation.wait(animation.MOVE_ANIMATION_MS);
      if (animation.isMoveStale(gen)) return;
      animation.slideOffsets.value = {};
      state.tiles.value = result.tiles;
      state.score.value += result.scoreDelta;
      state.moves.value += 1;
      state.reached2048Flag.value ||= hasReached2048Tiles(state.tiles.value);
      await playMergeAndSpawn(result, gen);
      if (animation.isMoveStale(gen)) return;
      if (isGameOverTiles(state.tiles.value)) {
        await settleGame(true);
        return;
      }
      state.gameMessage.value = '继续滑动合成更大数字';
    } finally {
      if (!animation.isMoveStale(gen)) {
        state.isMoving.value = false;
      }
    }
  }

  /**
   * Plays merge marks and random spawn animation after a valid move.
   * @param {{ merges?: Array<object> }} result
   * @param {number} gen
   * @returns {Promise<void>}
   */
  async function playMergeAndSpawn(result, gen) {
    if ((result.merges || []).length > 0) {
      animation.markMergedTileIds(result.merges);
      await animation.wait(animation.MERGE_ANIMATION_MS);
      if (animation.isMoveStale(gen)) return;
      animation.mergedTileIds.value = {};
    }
    const spawnResult = spawnRandomTileOnTiles(state.tiles.value);
    state.tiles.value = spawnResult.tiles;
    if (spawnResult.spawn) {
      animation.newTileIds.value = { [spawnResult.spawn.id]: true };
      await animation.wait(animation.postSlideAnimationWaitMs(false));
      if (!animation.isMoveStale(gen)) {
        animation.newTileIds.value = {};
      }
    }
  }

  return { handleMoveInput, handleMove };
}
