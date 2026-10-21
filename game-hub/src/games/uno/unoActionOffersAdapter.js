import { findOfferByActionType, hasOfferByActionType } from '../../services/action-interaction/actionOfferUtils.js';
import { isEnumeratedOffer } from '../../services/action-interaction/actionInteractionAdapterRegistry.js';
import { EnumeratedActionAdapter } from '../../services/action-interaction/enumeratedActionAdapter.js';

const PLAY_CARD_ACTION_TYPE = 'PLAY_CARD';

/**
 * @param {object[]} requiredGroups
 * @returns {object[]}
 */
function convertRequiredGroups(requiredGroups) {
  if (!Array.isArray(requiredGroups)) {
    return [];
  }
  return requiredGroups
    .map((group) => {
      if (!group || typeof group !== 'object') {
        return null;
      }
      const matchValue =
        group.matchValue && typeof group.matchValue === 'object' ? group.matchValue : null;
      if (!matchValue) {
        return null;
      }
      const count = Number.isFinite(Number(group.count)) ? Math.max(1, Number(group.count)) : 1;
      return {
        groupType: String(group.groupType || '').trim() || undefined,
        minPick: count,
        maxPick: count,
        items: [matchValue]
      };
    })
    .filter((item) => item != null);
}

/**
 * 将 PLAY_CARD 枚举选项映射为 matcher 候选项。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').EnumeratedActionOption} option
 * @returns {object|null}
 */
function mapPlayCardOptionToCandidate(option) {
  if (!option || typeof option !== 'object') {
    return null;
  }
  const actionId = String(option.actionId || '').trim();
  if (!actionId) {
    return null;
  }
  const payload = option.payload && typeof option.payload === 'object' ? option.payload : {};
  const selection = option.selection && typeof option.selection === 'object' ? option.selection : null;
  if (!selection) {
    return null;
  }
  const selectionMode = String(selection.mode || '').trim();
  if (selectionMode === 'ACTION_ONLY') {
    return null;
  }
  const matchPolicy =
    selection.matchPolicy && typeof selection.matchPolicy === 'object' ? selection.matchPolicy : {};
  const matchFields = Array.isArray(matchPolicy.matchFields)
    ? matchPolicy.matchFields.filter((field) => String(field || '').trim())
    : ['cardInstanceId'];
  const requiredGroups = convertRequiredGroups(selection.requiredGroups);
  let items = requiredGroups.flatMap((group) => group.items || []);
  if (!items.length) {
    const cardInstanceId = String(payload.cardInstanceId || '').trim();
    if (cardInstanceId) {
      items = [{ cardInstanceId }];
    }
  }
  if (!items.length) {
    return null;
  }
  return {
    mode: 'single',
    items,
    matchFields,
    requiredGroups,
    action: {
      actionId,
      actionType: PLAY_CARD_ACTION_TYPE,
      payload: { ...payload }
    }
  };
}

/**
 * 从 actionOffers 构建 PLAY_CARD 的 matcher selection。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @returns {{ selection: { candidates: object[]; matchFields: string[] } }}
 */
export function buildPlayCardMatcherSelection(actionOffers) {
  const offer = findOfferByActionType(actionOffers, PLAY_CARD_ACTION_TYPE);
  if (!isEnumeratedOffer(offer)) {
    return { selection: { candidates: [], matchFields: ['cardInstanceId'] } };
  }
  return EnumeratedActionAdapter.buildMatcherSelection(offer, mapPlayCardOptionToCandidate);
}

/**
 * 从候选项解析关联动作。
 * @param {object} candidate
 * @returns {object|null}
 */
export function resolveCandidateAction(candidate) {
  if (!candidate || typeof candidate !== 'object') {
    return null;
  }
  if (candidate.action && typeof candidate.action === 'object') {
    return { ...candidate.action };
  }
  return null;
}

/**
 * 筛选带指定花色且匹配当前选牌的出牌候选项。
 * @param {object[]} candidates
 * @param {string} chooseColor
 * @param {string[]} selectedCardIds
 * @returns {object|null}
 */
export function findPlayActionByChooseColor(candidates, chooseColor, selectedCardIds) {
  const color = String(chooseColor || '').trim().toLowerCase();
  if (!color) {
    return null;
  }
  const cardInstanceId = String(selectedCardIds?.[0] || '').trim();
  for (const candidate of candidates || []) {
    const action = resolveCandidateAction(candidate);
    if (!action) {
      continue;
    }
    const payload = action.payload && typeof action.payload === 'object' ? action.payload : {};
    if (String(payload.chooseColor || '').trim().toLowerCase() !== color) {
      continue;
    }
    if (cardInstanceId) {
      const items = Array.isArray(candidate.items) ? candidate.items : [];
      const matchesCard = items.some(
        (item) => String(item?.cardInstanceId || '').trim() === cardInstanceId
      );
      if (!matchesCard) {
        continue;
      }
    }
    return action;
  }
  return null;
}

/**
 * 统计当前选牌对应的万用牌颜色候选项数量。
 * @param {object[]} candidates
 * @param {string[]} [selectedCardIds]
 * @returns {number}
 */
export function countWildColorCandidates(candidates, selectedCardIds) {
  const cardInstanceId = String(selectedCardIds?.[0] || '').trim();
  let count = 0;
  for (const candidate of candidates || []) {
    const action = resolveCandidateAction(candidate);
    if (!action) {
      continue;
    }
    const payload = action.payload && typeof action.payload === 'object' ? action.payload : {};
    if (!String(payload.chooseColor || '').trim()) {
      continue;
    }
    if (cardInstanceId) {
      const items = Array.isArray(candidate.items) ? candidate.items : [];
      const matchesCard = items.some(
        (item) => String(item?.cardInstanceId || '').trim() === cardInstanceId
      );
      if (!matchesCard) {
        continue;
      }
    }
    count += 1;
  }
  return count;
}

/**
 * 是否存在 PLAY_CARD Offer。
 * @param {import('../../services/action-interaction/actionOfferUtils.js').ActionOffer[]|null|undefined} actionOffers
 * @returns {boolean}
 */
export function hasPlayCardOffer(actionOffers) {
  return hasOfferByActionType(actionOffers, PLAY_CARD_ACTION_TYPE);
}
