import { computed, onUnmounted } from 'vue';
import { EnumeratedActionAdapter } from '../../../services/action-interaction/enumeratedActionAdapter.js';
import { getAdapterForOffer } from '../../../services/action-interaction/actionInteractionAdapterRegistry.js';
import {
  findOfferByActionType,
  hasOfferByActionType
} from '../../../services/action-interaction/actionOfferUtils.js';

/**
 * 管理五子棋落子、悔棋请求和接受/拒绝动作。
 * @param {object} input
 * @returns {object}
 */
export function useGomokuInteraction(input) {
  let disposed = false;
  const hasRequestUndo = computed(() =>
    hasOfferByActionType(input.actionOffersRef.value, 'REQUEST_UNDO')
  );
  const hasResign = computed(() =>
    hasOfferByActionType(input.actionOffersRef.value, 'RESIGN')
  );

  /**
   * 读取指定类型的第一个枚举动作。
   * @param {string} actionType
   * @returns {object|null}
   */
  function findAction(actionType) {
    const offer = findOfferByActionType(input.actionOffersRef.value, actionType);
    if (!offer) return null;
    const option = getAdapterForOffer(offer).readDisplayOptions(offer)[0];
    return option ? { actionType: offer.actionType, actionId: option.actionId } : null;
  }

  /**
   * 提交指定类型的枚举动作。
   * @param {string} actionType
   * @returns {Promise<void>}
   */
  async function submitByType(actionType) {
    if (disposed || input.disabledRef.value) return;
    const action = findAction(actionType);
    if (action) await input.submit(action.actionType, action.actionId);
  }

  /**
   * 提交棋盘落子。
   * @param {number} row
   * @param {number} col
   * @returns {Promise<void>}
   */
  async function placeStone(row, col) {
    if (disposed || input.disabledRef.value) return;
    const option = EnumeratedActionAdapter.findOptionBySelection(
      input.actionOffersRef.value,
      'PLACE_STONE',
      { type: 'BOARD_CELL', config: { row, col } }
    );
    if (option) await input.submit('PLACE_STONE', option.actionId);
  }

  /**
   * 重置交互状态。
   * @returns {void}
   */
  function reset() {}

  /**
   * 释放交互状态。
   * @returns {void}
   */
  function dispose() {
    disposed = true;
  }

  onUnmounted(dispose);
  return {
    hasRequestUndo,
    hasResign,
    placeStone,
    requestUndo: () => submitByType('REQUEST_UNDO'),
    acceptUndo: () => submitByType('ACCEPT_UNDO'),
    rejectUndo: () => submitByType('REJECT_UNDO'),
    resign: () => submitByType('RESIGN'),
    reset,
    dispose
  };
}
