import {
  applyScorePenalty,
  calcClearPenalty,
  clearTile,
  isGameOverTiles
} from './game2048Engine.js';
import { GAME2048_PROP } from './game2048Config.js';

/**
 * Creates prop selection and application handlers for 2048.
 * @param {{ state: object, animation: object, boardComponentRef: import('vue').Ref<object|null>, persistence: object, showToast: Function, settleGame: Function }} deps
 * @returns {{ useProp: Function, handleClearCellSelect: Function }}
 */
export function use2048Prop({
  state,
  animation,
  boardComponentRef,
  persistence,
  showToast,
  settleGame
}) {
  /**
   * Toggles or activates a 2048 prop.
   * @param {string} propCode
   * @returns {void}
   */
  function useProp(propCode) {
    if (state.isPaused.value) return showToast('游戏已暂停', 'warning');
    if (state.gameStatus.value === 'ended' || state.gameStatus.value === 'settling') {
      return showToast('对局已结束，无法使用道具', 'warning');
    }
    if (propCode !== GAME2048_PROP.CLEAR_CELL) {
      return;
    }
    if (!state.canUseClearCell.value) {
      return showToast(
        state.gameStatus.value === 'idle' ? '请先开始一局再使用道具' : '请等待当前操作完成',
        'warning'
      );
    }
    if (state.propQuantity(propCode) <= 0) return showToast('道具数量不足', 'warning');
    if (state.propRemaining(propCode) <= 0) return showToast('本局清除锤使用次数已达上限', 'warning');
    state.activeTool.value =
      state.activeTool.value === GAME2048_PROP.CLEAR_CELL ? '' : GAME2048_PROP.CLEAR_CELL;
    state.gameMessage.value = state.activeTool.value ? '点击要清除的非空格子' : '已取消清除锤';
    boardComponentRef.value?.focusBoard?.();
  }

  /**
   * Applies the clear-cell prop to a board position.
   * @param {{ row: number, col: number }} pos
   * @returns {Promise<void>}
   */
  async function handleClearCellSelect(pos) {
    if (
      state.isPaused.value ||
      !state.isPropSelecting.value ||
      state.gameStatus.value !== 'playing' ||
      state.isOperationLocked.value
    ) {
      return;
    }
    const cleared = clearTile(state.tiles.value, pos.row, pos.col);
    if (!cleared.ok) return showToast('只能清除非空格子', 'warning');
    state.isMoving.value = true;
    animation.clearingTileId.value = cleared.removedId;
    await animation.wait(animation.CLEAR_ANIMATION_MS);
    state.tiles.value = cleared.tiles;
    animation.clearingTileId.value = null;
    const penalty = calcClearPenalty(cleared.clearedValue, state.score.value);
    state.score.value = applyScorePenalty(state.score.value, penalty);
    state.scorePenalty.value += penalty;
    state.clearCellUses.value += 1;
    state.usedClearCell.value += 1;
    state.activeTool.value = '';
    persistence.recordPropUsage(GAME2048_PROP.CLEAR_CELL, `清除 ${cleared.clearedValue}`);
    state.isMoving.value = false;
    state.gameMessage.value = `清除锤已使用，扣除 ${penalty} 分`;
    if (isGameOverTiles(state.tiles.value)) {
      await settleGame(true);
    }
  }

  return { useProp, handleClearCellSelect };
}
