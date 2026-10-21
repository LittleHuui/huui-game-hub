import {
  findOfferByActionType,
  getComposedCapability
} from '../../services/action-interaction/actionOfferUtils.js';
import {
  getAdapterForOffer,
  isComposedOffer,
  isEnumeratedOffer
} from '../../services/action-interaction/actionInteractionAdapterRegistry.js';
import { EnumeratedActionAdapter } from '../../services/action-interaction/enumeratedActionAdapter.js';

/** 斗地主按钮类 actionType（无选牌） */
export const DOUDIZHU_BUTTON_ACTION_TYPES = Object.freeze([
  'SHOW_CARDS',
  'SKIP_SHOW_CARDS',
  'CALL_LANDLORD',
  'PASS_CALL',
  'ROB_LANDLORD',
  'PASS_ROB',
  'DOUBLE',
  'PASS_DOUBLE',
  'PASS'
]);

const PLAY_CARDS_ACTION_TYPE = 'PLAY_CARDS';

/**
 * 查找 COMPOSED 出牌 Offer。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @returns {import('../../services/action-interaction/actionOfferUtils.js').ComposedActionOffer|null}
 */
export function findPlayCardsOffer(actionOffers) {
  const offer = findOfferByActionType(actionOffers, PLAY_CARDS_ACTION_TYPE);
  if (!isComposedOffer(offer)) {
    return null;
  }
  return offer;
}

/**
 * 读取 PLAY_CARDS capability。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @returns {import('../../services/action-interaction/actionOfferUtils.js').ComposedActionCapability|null}
 */
export function getPlayCardsCapability(actionOffers) {
  return getComposedCapability(findPlayCardsOffer(actionOffers));
}

/**
 * 是否存在 PLAY_CARDS COMPOSED Offer。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @returns {boolean}
 */
export function hasPlayCardsOffer(actionOffers) {
  const offer = findOfferByActionType(actionOffers, PLAY_CARDS_ACTION_TYPE);
  return isComposedOffer(offer);
}

/**
 * 查找 ENUMERATED Offer。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @param {string} actionType
 * @returns {import('../../services/action-interaction/actionOfferUtils.js').EnumeratedActionOffer|null}
 */
export function findEnumeratedOffer(actionOffers, actionType) {
  const offer = findOfferByActionType(actionOffers, actionType);
  if (!isEnumeratedOffer(offer)) {
    return null;
  }
  return offer;
}

/**
 * 构建按钮区可见操作（保持后端 Offer 顺序）。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @returns {Array<{ actionType: string; actionId: string; payload?: object; selection?: object }>}
 */
export function listButtonActionOptions(actionOffers) {
  const result = [];
  (actionOffers || []).forEach((offer) => {
    if (!isEnumeratedOffer(offer)) {
      return;
    }
    const actionType = String(offer.actionType || '').trim();
    if (!DOUDIZHU_BUTTON_ACTION_TYPES.includes(actionType)) {
      return;
    }
    getAdapterForOffer(offer).readDisplayOptions(offer).forEach((option) => {
      result.push({
        actionType,
        actionId: option.actionId,
        payload: option.payload,
        selection: option.selection
      });
    });
  });
  return result;
}

/**
 * 查找首个指定类型的 ENUMERATED 选项。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @param {string} actionType
 * @returns {{ actionType: string; actionId: string }|null}
 */
export function findFirstEnumeratedOption(actionOffers, actionType) {
  const offer = findEnumeratedOffer(actionOffers, actionType);
  if (!offer) {
    return null;
  }
  const option = EnumeratedActionAdapter.readOptions(offer)[0];
  if (!option) {
    return null;
  }
  return {
    actionType: offer.actionType,
    actionId: option.actionId
  };
}

/**
 * 判断是否允许选牌。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @returns {boolean}
 */
export function isCardSelectionAllowed(actionOffers) {
  return hasPlayCardsOffer(actionOffers);
}
