import { computed, onUnmounted, ref, watch } from 'vue';
import { isWildHandCard } from '../unoGameViewUtils.js';
import {
  countWildColorCandidates,
  findPlayActionByChooseColor
} from '../unoActionOffersAdapter.js';

/**
 * 管理 UNO 手牌选择、提示游标和 Wild 颜色选择。
 * @param {object} input
 * @returns {object}
 */
export function useUnoHandInteraction(input) {
  const colorPickerVisible = ref(false);
  let disposed = false;
  let suppressHintCursorReset = false;

  const selectedWildColorCandidateCount = computed(() => {
    const instanceId = String(input.selectedCardIdsRef.value?.[0] || '').trim();
    const handCard = input.handCardsRef.value.find((card) => card.cardInstanceId === instanceId);
    return handCard && isWildHandCard(handCard)
      ? countWildColorCandidates(
          input.matchStateRef.value?.activeCandidates,
          input.selectedCardIdsRef.value
        )
      : 0;
  });

  /**
   * 更新手牌选择。
   * @param {string[]} ids
   * @returns {void}
   */
  function selectCards(ids) {
    if (disposed || input.disabledRef.value) return;
    input.selectedCardIdsRef.value = Array.isArray(ids) ? [...ids] : [];
  }

  /**
   * 选择下一条本地提示。
   * @returns {void}
   */
  function applyHint() {
    const suggested = input.matchStateRef.value?.suggestedSelection;
    if (Array.isArray(suggested) && suggested.length) {
      suppressHintCursorReset = true;
      input.selectedCardIdsRef.value = [...suggested];
    }
    if (input.matchStateRef.value?.nextHintCursor != null) {
      input.hintCursorRef.value = input.matchStateRef.value.nextHintCursor;
    }
  }

  /**
   * 在 Wild 存在多个合法颜色候选时打开颜色选择器。
   * @returns {boolean}
   */
  function openColorPickerIfNeeded() {
    if (selectedWildColorCandidateCount.value <= 1) return false;
    colorPickerVisible.value = true;
    return true;
  }

  /**
   * 关闭颜色选择器。
   * @returns {void}
   */
  function cancelColorPicker() {
    colorPickerVisible.value = false;
  }

  /**
   * 将颜色选择映射回服务端提供的 actionId。
   * @param {string} color
   * @returns {object|null}
   */
  function chooseColor(color) {
    colorPickerVisible.value = false;
    const normalized = String(color || '').trim();
    if (!normalized || disposed) return null;
    return findPlayActionByChooseColor(
      input.matchStateRef.value?.activeCandidates,
      normalized,
      input.selectedCardIdsRef.value
    ) || null;
  }

  /**
   * 重置选择相关瞬时状态。
   * @returns {void}
   */
  function reset() {
    input.selectedCardIdsRef.value = [];
    input.hintCursorRef.value = 0;
    colorPickerVisible.value = false;
  }

  /**
   * 释放交互状态。
   * @returns {void}
   */
  function dispose() {
    disposed = true;
    reset();
  }

  watch(input.selectedCardIdsRef, () => {
    if (suppressHintCursorReset) {
      suppressHintCursorReset = false;
      return;
    }
    input.hintCursorRef.value = 0;
  });
  onUnmounted(dispose);

  return {
    colorPickerVisible,
    selectedWildColorCandidateCount,
    selectCards,
    applyHint,
    openColorPickerIfNeeded,
    cancelColorPicker,
    chooseColor,
    reset,
    dispose
  };
}
