import { cloneBoard, collapseBoard, fillBoardControlled, findMatches, hasAvailableMove, removeMatches, scoreMatches } from './match3Engine.js';

const MAX_RESOLUTION_STEPS = 40;

/** 执行棋盘动画及消除时序，所有等待受对局取消控制。
 * @param {object} context
 * @returns {object}
 */
export function createMatch3Animation(context) {
  const { clientConfig, CELL_GAP, board, animationConfig, cellVisuals, nextFrame, wait, roundCompletion, isResolutionStale, gameConfig, score, animating, boardResolving, chainHint, moves, comboMax } = context;

  /**
   * @returns {number}
   */
  function cellStride() {
    return Number(clientConfig.value?.cellSize || 44) + CELL_GAP;
  }

  /**
   * @param {object[][]} grid
   * @returns {boolean}
   */
  function hasEmptyCells(grid) {
    return grid.some((row) => row.some((cell) => !cell));
  }

  /**
   * @param {{ row: number; col: number }} from
   * @param {{ row: number; col: number }} to
   * @param {boolean} revert
   * @returns {Promise<void>}
   */
  async function playSwapAnimation(from, to, revert) {
    const gen = roundCompletion.generation;
    const a = board.value[from.row]?.[from.col];
    const b = board.value[to.row]?.[to.col];
    if (!a || !b) {
      return;
    }
    const stride = cellStride();
    const dx = (to.col - from.col) * stride;
    const dy = (to.row - from.row) * stride;
    const ms = animationConfig.value.swapMs;

    cellVisuals.value = {
      [a.id]: { translateX: 0, translateY: 0 },
      [b.id]: { translateX: 0, translateY: 0 }
    };
    if (!await nextFrame() || isResolutionStale(gen)) return;
    cellVisuals.value = {
      [a.id]: { translateX: dx, translateY: dy },
      [b.id]: { translateX: -dx, translateY: -dy }
    };
    if (!await wait(ms) || isResolutionStale(gen)) return;

    if (revert) {
      cellVisuals.value = {
        [a.id]: { translateX: 0, translateY: 0 },
        [b.id]: { translateX: 0, translateY: 0 }
      };
      if (!await wait(ms) || isResolutionStale(gen)) return;
    }
    cellVisuals.value = {};
  }

  /**
   * @param {object[]} cells
   * @returns {Promise<void>}
   */
  async function playRemoveAnimation(cells) {
    const gen = roundCompletion.generation;
    const ms = animationConfig.value.removeMs;
    const visuals = {};
    for (const cell of cells || []) {
      if (cell?.id) {
        visuals[cell.id] = { effect: 'removing', translateX: 0, translateY: 0 };
      }
    }
    cellVisuals.value = visuals;
    if (!await wait(ms) || isResolutionStale(gen)) return;
    cellVisuals.value = {};
  }

  /**
   * @param {object[]} drops
   * @param {object[][]} nextBoard
   * @returns {Promise<void>}
   */
  async function playFallAnimation(drops, nextBoard) {
    const gen = roundCompletion.generation;
    const ms = animationConfig.value.dropMs;
    const stride = cellStride();
    const visuals = {};
    for (const drop of drops || []) {
      const fromRow = drop.from?.row ?? drop.fromRow;
      const toRow = drop.to?.row ?? drop.toRow;
      const deltaY = (fromRow - toRow) * stride;
      visuals[drop.id] = { translateX: 0, translateY: deltaY };
    }
    board.value = cloneBoard(nextBoard);
    cellVisuals.value = visuals;
    if (!await nextFrame() || isResolutionStale(gen)) return;
    const cleared = {};
    for (const id of Object.keys(visuals)) {
      cleared[id] = { translateX: 0, translateY: 0 };
    }
    cellVisuals.value = cleared;
    if (!await wait(ms) || isResolutionStale(gen)) return;
    cellVisuals.value = {};
  }

  /**
   * @param {object[][]} working
   * @returns {Promise<object[][]>}
   */
  async function playCollapseAndFill(working) {
    const gen = roundCompletion.generation;
    const collapsed = collapseBoard(working);
    if (collapsed.drops.length) {
      await playFallAnimation(collapsed.drops, collapsed.board);
      if (isResolutionStale(gen)) return working;
      working = collapsed.board;
    } else if (hasEmptyCells(working)) {
      board.value = cloneBoard(collapsed.board);
      working = collapsed.board;
    }
    const filled = fillBoardControlled(working, gameConfig.value, score.value);
    if (filled.spawns.length) {
      await playFallAnimation(filled.spawns, filled.board);
      if (isResolutionStale(gen)) return working;
      working = filled.board;
    } else {
      board.value = cloneBoard(filled.board);
      working = filled.board;
    }
    return working;
  }

  /**
   * 连锁消除动画（下落、补满与计分）
   * @param {object[][]} startBoard
   * @param {boolean} countMove
   * @returns {Promise<{ deadBoard: boolean; comboCount: number; scoreDelta: number }>}
   */
  async function animateBoardResolution(startBoard, countMove) {
    const gen = roundCompletion.generation;
    animating.value = true;
    boardResolving.value = true;
    let working = cloneBoard(startBoard);
    let fillScore = score.value;
    let scoreDelta = 0;
    let comboCount = 0;

    try {
      for (let guard = 0; guard < MAX_RESOLUTION_STEPS; guard++) {
        if (isResolutionStale(gen)) {
          return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
        }

        const matches = findMatches(working);
        if (matches.length) {
          comboCount++;
          chainHint.value = comboCount > 1 ? `连锁 x${comboCount}` : '';
          await wait(animationConfig.value.chainDelayMs);
          if (isResolutionStale(gen)) {
            return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
          }
          scoreDelta += scoreMatches(matches, gameConfig.value, comboCount);

          const removed = removeMatches(working, matches);
          await playRemoveAnimation(removed.removedCells);
          if (isResolutionStale(gen)) {
            return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
          }
          working = removed.board;
          board.value = cloneBoard(working);

          const collapsed = collapseBoard(working);
          if (collapsed.drops.length) {
            await playFallAnimation(collapsed.drops, collapsed.board);
            if (isResolutionStale(gen)) {
              return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
            }
            working = collapsed.board;
          } else {
            board.value = cloneBoard(collapsed.board);
            working = collapsed.board;
          }

          fillScore = score.value + scoreDelta;
          const filled = fillBoardControlled(working, gameConfig.value, fillScore);
          if (filled.spawns.length) {
            await playFallAnimation(filled.spawns, filled.board);
            if (isResolutionStale(gen)) {
              return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
            }
            working = filled.board;
          } else {
            board.value = cloneBoard(filled.board);
            working = filled.board;
          }
          continue;
        }

        if (hasEmptyCells(working)) {
          working = await playCollapseAndFill(working);
          if (isResolutionStale(gen)) {
            return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
          }
          continue;
        }
        break;
      }

      if (isResolutionStale(gen)) {
        return { deadBoard: false, comboCount: 0, scoreDelta: 0, aborted: true };
      }

      board.value = working;
      const deadBoard = !hasAvailableMove(working);
      if (countMove) {
        moves.value++;
      }
      score.value += scoreDelta;
      comboMax.value = Math.max(comboMax.value, comboCount);
      chainHint.value = '';
      cellVisuals.value = {};

      return {
        deadBoard,
        comboCount,
        scoreDelta,
        aborted: false
      };
    } finally {
      if (!isResolutionStale(gen)) {
        boardResolving.value = false;
        animating.value = false;
      }
    }
  }

  return {
    cellStride,
    hasEmptyCells,
    playSwapAnimation,
    playRemoveAnimation,
    playFallAnimation,
    playCollapseAndFill,
    animateBoardResolution
  };
}
