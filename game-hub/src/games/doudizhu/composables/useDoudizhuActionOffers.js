import { computed } from 'vue';
import {
  findPlayCardsOffer,
  getPlayCardsCapability,
  hasPlayCardsOffer,
  listButtonActionOptions
} from '../doudizhuActionOffersAdapter.js';

/**
 * 解析斗地主 ActionOffer 展示数据。
 * @param {import('vue').Ref<import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]>} actionOffersRef
 * @returns {{
 *   buttonActions: import('vue').ComputedRef<Array<{ actionType: string; actionId: string }>>;
 *   playCardsOffer: import('vue').ComputedRef<import('../../services/action-interaction/actionOfferUtils.js').ComposedActionOffer|null>;
 *   playCardsCapability: import('vue').ComputedRef<import('../../services/action-interaction/actionOfferUtils.js').ComposedActionCapability|null>;
 *   canPlayCards: import('vue').ComputedRef<boolean>;
 *   canTakeAction: import('vue').ComputedRef<boolean>;
 * }}
 */
export function useDoudizhuActionOffers(actionOffersRef) {
  const buttonActions = computed(() => listButtonActionOptions(actionOffersRef.value));
  const playCardsOffer = computed(() => findPlayCardsOffer(actionOffersRef.value));
  const playCardsCapability = computed(() => getPlayCardsCapability(actionOffersRef.value));
  const canPlayCards = computed(() => hasPlayCardsOffer(actionOffersRef.value));
  const canTakeAction = computed(
    () => buttonActions.value.length > 0 || canPlayCards.value
  );
  /**
   * Stateless composable reset hook.
   * @returns {void}
   */
  function reset() {}

  /**
   * Stateless composable dispose hook.
   * @returns {void}
   */
  function dispose() {}

  return {
    buttonActions,
    playCardsOffer,
    playCardsCapability,
    canPlayCards,
    canTakeAction,
    reset,
    dispose
  };
}
