import { computed, onUnmounted, ref, watch } from 'vue';
import { matchEnumeratedActions } from '../../../services/enumeratedActionMatcher.js';
import { buildPlayCardMatcherSelection } from '../unoActionOffersAdapter.js';

/**
 * UNO 手牌枚举匹配与选牌状态。
 * @param {object} input
 * @param {import('vue').Ref<import('../../../services/action-interaction/actionOfferUtils.js').ActionOffer[]>} input.actionOffersRef
 * @param {import('vue').ComputedRef<object[]>} input.handCardsRef
 * @param {import('vue').ComputedRef<boolean>} input.interactionDisabledRef
 * @returns {{
 *   selectedCardIds: import('vue').Ref<string[]>;
 *   hintCursor: import('vue').Ref<number>;
 *   matchState: import('vue').Ref<import('../../../services/enumeratedActionMatcher.js').EnumeratedActionMatcherResult|null>;
 *   selectableItemIds: import('vue').ComputedRef<string[]>;
 *   disabledItemIds: import('vue').ComputedRef<string[]>;
 *   determinedAction: import('vue').ComputedRef<object|null>;
 *   enumeratedSelection: import('vue').ComputedRef<{ selection: object }>;
 * }}
 */
export function useUnoCardMatching(input) {
  const { actionOffersRef, handCardsRef, interactionDisabledRef } = input;
  const selectedCardIds = ref([]);
  const hintCursor = ref(0);
  /** @type {import('vue').Ref<import('../../services/enumeratedActionMatcher.js').EnumeratedActionMatcherResult|null>} */
  const matchState = ref(null);

  const enumeratedSelection = computed(() => {
    if (interactionDisabledRef.value) {
      return { selection: { candidates: [], matchFields: ['cardInstanceId'] } };
    }
    return buildPlayCardMatcherSelection(actionOffersRef.value);
  });

  const refreshMatchState = () => {
    if (!enumeratedSelection.value?.selection) {
      matchState.value = null;
      return;
    }
    matchState.value = matchEnumeratedActions({
      handCards: handCardsRef.value,
      selectedCardIds: selectedCardIds.value,
      enumeratedSelection: enumeratedSelection.value,
      hintCursor: hintCursor.value
    });
  };

  const stopMatchingWatch = watch(
    [handCardsRef, selectedCardIds, enumeratedSelection, hintCursor],
    refreshMatchState,
    { immediate: true, deep: true }
  );

  const selectableItemIds = computed(
    () => matchState.value?.selectableCardIds || []
  );
  const disabledItemIds = computed(() => matchState.value?.disabledCardIds || []);
  const determinedAction = computed(() => matchState.value?.determinedAction || null);

  /**
   * 清空选牌和提示状态。
   * @returns {void}
   */
  function reset() {
    selectedCardIds.value = [];
    hintCursor.value = 0;
    matchState.value = null;
  }

  /**
   * 停止匹配观察。
   * @returns {void}
   */
  function dispose() {
    stopMatchingWatch();
    reset();
  }

  onUnmounted(dispose);

  return {
    selectedCardIds,
    hintCursor,
    matchState,
    selectableItemIds,
    disabledItemIds,
    determinedAction,
    enumeratedSelection,
    reset,
    dispose
  };
}
