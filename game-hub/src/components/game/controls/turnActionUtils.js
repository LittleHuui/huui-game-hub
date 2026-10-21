import { STRATEGY_TURN_ACTION_TYPE } from './turnControlEnums.js';
import {
  findOfferByActionType,
  hasOfferByActionType
} from '../../../services/action-interaction/actionOfferUtils.js';
import {
  getAdapterForOffer,
  isEnumeratedOffer
} from '../../../services/action-interaction/actionInteractionAdapterRegistry.js';

/**
 * 判断 actionOffers 中是否包含指定 actionType 的 Offer。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @param {string} actionType
 * @returns {boolean}
 */
export function hasActionOfferType(actionOffers, actionType) {
  return hasOfferByActionType(actionOffers, actionType);
}

/**
 * 读取指定 actionType 的 ENUMERATED Offer options。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @param {string} actionType
 * @returns {import('../../services/action-interaction/actionOfferUtils.js').EnumeratedActionOption[]}
 */
export function getEnumeratedOptionsByActionType(actionOffers, actionType) {
  const offer = findOfferByActionType(actionOffers, actionType);
  if (!isEnumeratedOffer(offer)) {
    return [];
  }
  return getAdapterForOffer(offer).readDisplayOptions(offer);
}

/**
 * 操作栏按钮默认文案。
 * @param {string} actionType
 * @returns {string}
 */
export function resolveStrategyTurnActionLabel(actionType) {
  switch (String(actionType || '').trim()) {
    case STRATEGY_TURN_ACTION_TYPE.DRAW_CARD:
      return '摸牌';
    case STRATEGY_TURN_ACTION_TYPE.PLAY_CARD:
      return '出牌';
    case STRATEGY_TURN_ACTION_TYPE.PASS_TURN:
      return '结束回合';
    default:
      return '操作';
  }
}
