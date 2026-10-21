import { computed, onUnmounted, ref, watch } from 'vue';
import { isCardSelectionAllowed } from '../doudizhuActionOffersAdapter.js';

/**
 * 管理斗地主手牌受控选择状态。
 * @param {object} input
 * @param {import('vue').Ref<object[]>} input.handCardsRef
 * @param {import('vue').ComputedRef<import('../../services/action-interaction/actionOfferUtils.js').ComposedActionCapability|null>} input.capabilityRef
 * @param {import('vue').ComputedRef<boolean>} input.interactionDisabledRef
 * @returns {{
 *   selectedCardIds: import('vue').Ref<string[]>;
 *   selectableItemIds: import('vue').ComputedRef<string[]>;
 *   disabledItemIds: import('vue').ComputedRef<string[]>;
 *   clearSelection: () => void;
 * }}
 */
export function useDoudizhuCardSelection(input) {
  const { handCardsRef, capabilityRef, interactionDisabledRef, actionOffersRef } = input;
  const selectedCardIds = ref([]);

  const handItemIds = computed(() =>
    (handCardsRef.value || [])
      .map((card) => String(card?.cardInstanceId || '').trim())
      .filter(Boolean)
  );

  const selectableItemIds = computed(() => {
    if (interactionDisabledRef.value || !isCardSelectionAllowed(actionOffersRef?.value)) {
      return [];
    }
    return handItemIds.value;
  });

  const disabledItemIds = computed(() => {
    const capability = capabilityRef.value;
    const maxPick = Number(capability?.maxPick) || 0;
    const selected = selectedCardIds.value;
    if (!maxPick || selected.length < maxPick) {
      return [];
    }
    const selectedSet = new Set(selected);
    return handItemIds.value.filter((id) => !selectedSet.has(id));
  });

  /**
   * 清空选牌。
   */
  function clearSelection() {
    selectedCardIds.value = [];
  }

  const stopHandWatch = watch(handItemIds, (nextIds, prevIds) => {
    if (JSON.stringify(nextIds) === JSON.stringify(prevIds)) {
      return;
    }
    selectedCardIds.value = selectedCardIds.value.filter((id) => nextIds.includes(id));
  });

  /**
   * 停止选牌观察并清空选择。
   * @returns {void}
   */
  function dispose() {
    stopHandWatch();
    clearSelection();
  }

  onUnmounted(dispose);

  return {
    selectedCardIds,
    selectableItemIds,
    disabledItemIds,
    clearSelection,
    reset: clearSelection,
    dispose
  };
}
