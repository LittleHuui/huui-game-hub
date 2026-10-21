import { EnumeratedActionAdapter } from './enumeratedActionAdapter.js';
import { ComposedActionAdapter } from './composedActionAdapter.js';

/** @typedef {'ENUMERATED' | 'COMPOSED'} InteractionModeKey */

/** @type {Record<InteractionModeKey, object>} */
const ADAPTER_REGISTRY = Object.freeze({
  ENUMERATED: EnumeratedActionAdapter,
  COMPOSED: ComposedActionAdapter
});

/**
 * 按 interactionMode 取得 Adapter。
 * @param {string} interactionMode
 * @returns {object}
 */
export function getActionInteractionAdapter(interactionMode) {
  const mode = String(interactionMode || '').trim();
  const adapter = ADAPTER_REGISTRY[/** @type {InteractionModeKey} */ (mode)];
  if (!adapter) {
    throw new Error(`未知 interactionMode: ${mode}`);
  }
  return adapter;
}

/**
 * 根据 Offer 自动解析 Adapter。
 * @param {import('./actionOfferUtils.js').ActionOffer|null|undefined} offer
 * @returns {object}
 */
export function getAdapterForOffer(offer) {
  if (!offer || typeof offer !== 'object') {
    throw new Error('ActionOffer 无效');
  }
  return getActionInteractionAdapter(offer.interactionMode);
}

/**
 * 判断 Offer 是否由枚举适配器处理。
 * @param {import('./actionOfferUtils.js').ActionOffer|null|undefined} offer
 * @returns {boolean}
 */
export function isEnumeratedOffer(offer) {
  return Boolean(offer) && getAdapterForOffer(offer) === EnumeratedActionAdapter;
}

/**
 * 判断 Offer 是否由构造适配器处理。
 * @param {import('./actionOfferUtils.js').ActionOffer|null|undefined} offer
 * @returns {boolean}
 */
export function isComposedOffer(offer) {
  return Boolean(offer) && getAdapterForOffer(offer) === ComposedActionAdapter;
}

export { EnumeratedActionAdapter, ComposedActionAdapter };
