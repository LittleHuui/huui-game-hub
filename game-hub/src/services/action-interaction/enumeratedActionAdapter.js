/**
 * 构造 ENUMERATED 动作提交体。
 * @param {string} actionType
 * @param {string} actionId
 * @returns {{ actionType: string; input: { kind: 'ENUMERATED'; actionId: string } }}
 */
export function buildEnumeratedSubmission(actionType, actionId) {
  const type = String(actionType || '').trim();
  const id = String(actionId || '').trim();
  if (!type) {
    throw new Error('缺少 actionType');
  }
  if (!id) {
    throw new Error('缺少 actionId');
  }
  return {
    actionType: type,
    input: {
      kind: 'ENUMERATED',
      actionId: id
    }
  };
}

/**
 * 从 ENUMERATED Offer 读取 options。
 * @param {import('./actionOfferUtils.js').EnumeratedActionOffer|null|undefined} offer
 * @returns {import('./actionOfferUtils.js').EnumeratedActionOption[]}
 */
export function readOptions(offer) {
  if (!offer || offer.interactionMode !== 'ENUMERATED') {
    return [];
  }
  return Array.isArray(offer.options) ? offer.options : [];
}

/**
 * 按 actionId 查找枚举选项。
 * @param {import('./actionOfferUtils.js').EnumeratedActionOffer|null|undefined} offer
 * @param {string} actionId
 * @returns {import('./actionOfferUtils.js').EnumeratedActionOption|null}
 */
export function findOptionByActionId(offer, actionId) {
  const id = String(actionId || '').trim();
  if (!id) {
    return null;
  }
  return readOptions(offer).find((item) => String(item?.actionId || '').trim() === id) || null;
}

/**
 * 按 actionType 与 selection 字段匹配枚举选项。
 * @param {import('./actionOfferUtils.js').ActionOffer[]|null|undefined} offers
 * @param {string} actionType
 * @param {object} selectionCriteria
 * @returns {import('./actionOfferUtils.js').EnumeratedActionOption|null}
 */
export function findOptionBySelection(offers, actionType, selectionCriteria) {
  const offer = (offers || []).find(
    (item) =>
      item?.interactionMode === 'ENUMERATED' &&
      String(item?.actionType || '').trim() === String(actionType || '').trim()
  );
  if (!offer || offer.interactionMode !== 'ENUMERATED') {
    return null;
  }
  const criteria = selectionCriteria && typeof selectionCriteria === 'object' ? selectionCriteria : {};
  return (
    readOptions(offer).find((option) => {
      const selection =
        option.selection && typeof option.selection === 'object' ? option.selection : {};
      return Object.keys(criteria).every((key) => {
        const left = selection[key];
        const right = criteria[key];
        if (left != null && typeof left === 'object' && right != null && typeof right === 'object') {
          return JSON.stringify(left) === JSON.stringify(right);
        }
        return String(left ?? '').trim() === String(right ?? '').trim();
      });
    }) || null
  );
}

/**
 * 构造 ENUMERATED 动作提交（Adapter 入口）。
 * @param {string} actionType
 * @param {string} actionId
 * @returns {{ actionType: string; input: { kind: 'ENUMERATED'; actionId: string } }}
 */
export function buildSubmission(actionType, actionId) {
  return buildEnumeratedSubmission(actionType, actionId);
}

/**
 * 将 ENUMERATED Offer 的 options 转为 enumeratedActionMatcher 所需的 selection 结构。
 * @param {import('./actionOfferUtils.js').EnumeratedActionOffer|null|undefined} offer
 * @param {(option: import('./actionOfferUtils.js').EnumeratedActionOption) => object|null} [mapOptionToCandidate]
 * @returns {{ selection: { candidates: object[]; matchFields: string[] } }}
 */
export function buildMatcherSelection(offer, mapOptionToCandidate) {
  const options = readOptions(offer);
  const mapper =
    typeof mapOptionToCandidate === 'function'
      ? mapOptionToCandidate
      : defaultMapOptionToCandidate;
  const candidates = options.map((option) => mapper(option)).filter((item) => item != null);
  const matchFields =
    candidates.find((item) => Array.isArray(item.matchFields) && item.matchFields.length > 0)
      ?.matchFields || ['cardInstanceId'];
  return {
    selection: {
      candidates,
      matchFields
    }
  };
}

/**
 * 默认将枚举选项映射为 matcher 候选项（action-only）。
 * @param {import('./actionOfferUtils.js').EnumeratedActionOption} option
 * @returns {object|null}
 */
function defaultMapOptionToCandidate(option) {
  if (!option || typeof option !== 'object') {
    return null;
  }
  const actionId = String(option.actionId || '').trim();
  if (!actionId) {
    return null;
  }
  return {
    mode: 'click',
    items: [],
    action: {
      actionId,
      payload: option.payload && typeof option.payload === 'object' ? { ...option.payload } : {}
    }
  };
}

export const EnumeratedActionAdapter = Object.freeze({
  readDisplayOptions: readOptions,
  readOptions,
  findOptionByActionId,
  findOptionBySelection,
  buildSubmission,
  buildMatcherSelection,
  buildEnumeratedSubmission
});
