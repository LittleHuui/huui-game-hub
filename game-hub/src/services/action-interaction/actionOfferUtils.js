/** @typedef {'ENUMERATED' | 'COMPOSED'} ActionInteractionMode */

/**
 * @typedef {object} EnumeratedActionOption
 * @property {string} actionId
 * @property {object} [payload]
 * @property {object} [selection]
 */

/**
 * @typedef {object} EnumeratedActionOffer
 * @property {string} actionType
 * @property {'ENUMERATED'} interactionMode
 * @property {EnumeratedActionOption[]} options
 */

/**
 * @typedef {object} ComposedActionCapability
 * @property {string} [selectionSource]
 * @property {string} [selectionMode]
 * @property {number} [minPick]
 * @property {number} [maxPick]
 * @property {boolean} [supportsPreview]
 * @property {boolean} [supportsSuggestions]
 */

/**
 * @typedef {object} ComposedActionOffer
 * @property {string} actionType
 * @property {'COMPOSED'} interactionMode
 * @property {ComposedActionCapability} capability
 */

/** @typedef {EnumeratedActionOffer | ComposedActionOffer} ActionOffer */

const KNOWN_INTERACTION_MODES = Object.freeze(['ENUMERATED', 'COMPOSED']);

/**
 * 校验并规范化单个 ActionOffer。
 * @param {object} raw
 * @returns {ActionOffer}
 */
export function mapActionOffer(raw) {
  if (!raw || typeof raw !== 'object') {
    throw new Error('ActionOffer 数据无效');
  }
  const actionType = String(raw.actionType || '').trim();
  if (!actionType) {
    throw new Error('ActionOffer.actionType 无效');
  }
  const interactionMode = String(raw.interactionMode || '').trim();
  if (!KNOWN_INTERACTION_MODES.includes(interactionMode)) {
    throw new Error(`ActionOffer.interactionMode 未知: ${interactionMode}`);
  }
  if (interactionMode === 'ENUMERATED') {
    if (!Array.isArray(raw.options)) {
      throw new Error(`ActionOffer[${actionType}] 缺少 options`);
    }
    const options = raw.options.map((item, index) => {
      if (!item || typeof item !== 'object') {
        throw new Error(`ActionOffer[${actionType}].options[${index}] 无效`);
      }
      const actionId = String(item.actionId || '').trim();
      if (!actionId) {
        throw new Error(`ActionOffer[${actionType}].options[${index}].actionId 无效`);
      }
      return {
        actionId,
        payload: item.payload && typeof item.payload === 'object' ? { ...item.payload } : {},
        selection:
          item.selection && typeof item.selection === 'object' ? { ...item.selection } : {}
      };
    });
    return {
      actionType,
      interactionMode: 'ENUMERATED',
      options
    };
  }
  const capability = raw.capability;
  if (!capability || typeof capability !== 'object') {
    throw new Error(`ActionOffer[${actionType}] 缺少 capability`);
  }
  return {
    actionType,
    interactionMode: 'COMPOSED',
    capability: {
      selectionSource: String(capability.selectionSource || '').trim(),
      selectionMode: String(capability.selectionMode || '').trim(),
      minPick: Number.isFinite(Number(capability.minPick)) ? Math.max(0, Number(capability.minPick)) : 0,
      maxPick: Number.isFinite(Number(capability.maxPick)) ? Math.max(0, Number(capability.maxPick)) : 0,
      supportsPreview: Boolean(capability.supportsPreview),
      supportsSuggestions: Boolean(capability.supportsSuggestions)
    }
  };
}

/**
 * 校验并映射 ActionOffer 列表。
 * @param {object[]|null|undefined} rawList
 * @returns {ActionOffer[]}
 */
export function mapActionOffers(rawList) {
  if (!Array.isArray(rawList)) {
    return [];
  }
  return rawList.map((item) => mapActionOffer(item));
}

/**
 * 按 actionType 查找首个 Offer。
 * @param {ActionOffer[]|null|undefined} offers
 * @param {string} actionType
 * @returns {ActionOffer|null}
 */
export function findOfferByActionType(offers, actionType) {
  const type = String(actionType || '').trim();
  if (!type) {
    return null;
  }
  return (offers || []).find((item) => String(item?.actionType || '').trim() === type) || null;
}

/**
 * 判断是否存在指定 actionType 的 Offer。
 * @param {ActionOffer[]|null|undefined} offers
 * @param {string} actionType
 * @returns {boolean}
 */
export function hasOfferByActionType(offers, actionType) {
  return findOfferByActionType(offers, actionType) != null;
}

/**
 * 按 interactionMode 筛选 Offer。
 * @param {ActionOffer[]|null|undefined} offers
 * @param {ActionInteractionMode} mode
 * @returns {ActionOffer[]}
 */
export function filterOffersByMode(offers, mode) {
  const normalized = String(mode || '').trim();
  if (!normalized) {
    return [];
  }
  return (offers || []).filter(
    (item) => String(item?.interactionMode || '').trim() === normalized
  );
}

/**
 * 读取 ENUMERATED Offer 的 options。
 * @param {ActionOffer|null|undefined} offer
 * @returns {EnumeratedActionOption[]}
 */
export function getEnumeratedOptions(offer) {
  if (!offer || offer.interactionMode !== 'ENUMERATED') {
    return [];
  }
  return Array.isArray(offer.options) ? offer.options : [];
}

/**
 * 读取 COMPOSED Offer 的 capability。
 * @param {ActionOffer|null|undefined} offer
 * @returns {ComposedActionCapability|null}
 */
export function getComposedCapability(offer) {
  if (!offer || offer.interactionMode !== 'COMPOSED') {
    return null;
  }
  return offer.capability && typeof offer.capability === 'object' ? offer.capability : null;
}
