import { ref } from 'vue';
import {
  CLEAR_ANIMATION_MS,
  MERGE_ANIMATION_MS,
  MOVE_ANIMATION_MS,
  getGame2048AnimationCssVars,
  nextFrame,
  postSlideAnimationWaitMs
} from './game2048Animation.js';

/**
 * Creates animation state and cancellation helpers for 2048 board transitions.
 * @returns {object}
 */
export function use2048Animation() {
  const slideOffsets = ref({});
  const newTileIds = ref({});
  const mergedTileIds = ref({});
  const clearingTileId = ref(null);
  const boardAnimationStyle = getGame2048AnimationCssVars();
  let generation = 0;

  /**
   * Waits for a fixed animation delay.
   * @param {number} ms
   * @returns {Promise<void>}
   */
  function wait(ms) {
    return new Promise((resolve) => {
      setTimeout(resolve, ms);
    });
  }

  /**
   * Starts a new cancellable animation generation.
   * @returns {number}
   */
  function nextGeneration() {
    generation += 1;
    return generation;
  }

  /**
   * Cancels all pending animation continuations.
   * @returns {void}
   */
  function cancelAnimations() {
    generation += 1;
    slideOffsets.value = {};
    newTileIds.value = {};
    mergedTileIds.value = {};
    clearingTileId.value = null;
  }

  /**
   * Checks whether an async animation continuation belongs to an older generation.
   * @param {number} gen
   * @returns {boolean}
   */
  function isMoveStale(gen) {
    return gen !== generation;
  }

  /**
   * Builds pixel offsets for slide animation from engine slide metadata.
   * @param {Array<{ id: number, fromRow: number, fromCol: number, toRow: number, toCol: number }>} slides
   * @param {number} stridePx
   * @returns {Record<number, { dx: number, dy: number }>}
   */
  function buildSlidePixelOffsets(slides, stridePx) {
    const map = {};
    for (const slide of slides || []) {
      map[slide.id] = {
        dx: (slide.toCol - slide.fromCol) * stridePx,
        dy: (slide.toRow - slide.fromRow) * stridePx
      };
    }
    return map;
  }

  /**
   * Marks merged tile ids for merge pulse animation.
   * @param {Array<{ id: number }>} merges
   * @returns {void}
   */
  function markMergedTileIds(merges) {
    const marks = {};
    for (const merge of merges || []) {
      marks[merge.id] = true;
    }
    mergedTileIds.value = marks;
  }

  return {
    slideOffsets,
    newTileIds,
    mergedTileIds,
    clearingTileId,
    boardAnimationStyle,
    MOVE_ANIMATION_MS,
    MERGE_ANIMATION_MS,
    CLEAR_ANIMATION_MS,
    nextFrame,
    postSlideAnimationWaitMs,
    wait,
    nextGeneration,
    cancelAnimations,
    isMoveStale,
    buildSlidePixelOffsets,
    markMergedTileIds
  };
}
