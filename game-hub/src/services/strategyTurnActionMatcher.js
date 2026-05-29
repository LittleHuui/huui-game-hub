/** @typedef {'single' | 'multiple' | 'click' | 'drag'} StrategyTurnSelectionMode */

/**
 * @typedef {object} StrategyTurnSelectionRequiredGroup
 * @property {string} [groupKey]
 * @property {object[]} items
 * @property {number} [minPick]
 * @property {number} [maxPick]
 */

/**
 * @typedef {object} StrategyTurnSelectionCandidate
 * @property {object} [action]
 * @property {StrategyTurnSelectionMode} [mode]
 * @property {object[]} [items]
 * @property {string[]} [matchFields]
 * @property {string[]} [ignoreFields]
 * @property {StrategyTurnSelectionRequiredGroup[]} [requiredGroups]
 */

/**
 * @typedef {object} StrategyTurnLegalActionsSelection
 * @property {StrategyTurnSelectionCandidate[]} candidates
 * @property {string[]} [matchFields]
 * @property {string[]} [ignoreFields]
 * @property {StrategyTurnSelectionRequiredGroup[]} [requiredGroups]
 */

/**
 * @typedef {object} StrategyTurnActionMatcherInput
 * @property {object[]} handCards
 * @property {string[]} selectedCardIds
 * @property {{ selection?: StrategyTurnLegalActionsSelection }} legalActions
 * @property {number} [hintCursor]
 */

/**
 * @typedef {object} StrategyTurnActionMatcherResult
 * @property {StrategyTurnSelectionCandidate[]} activeCandidates
 * @property {string[]} selectableCardIds
 * @property {string[]} disabledCardIds
 * @property {object|null} determinedAction
 * @property {string[]} suggestedSelection
 * @property {number} nextHintCursor
 */

const DEFAULT_MATCH_FIELDS = ['cardInstanceId', 'id'];
const DEFAULT_ID_FIELDS = ['cardInstanceId', 'id'];

const EMPTY_RESULT = Object.freeze({
  activeCandidates: [],
  selectableCardIds: [],
  disabledCardIds: [],
  determinedAction: null,
  suggestedSelection: [],
  nextHintCursor: 0
});

/**
 * 规范化字符串 ID 列表。
 * @param {string[]|null|undefined} ids
 * @returns {string[]}
 */
function normalizeIdList(ids) {
  if (!Array.isArray(ids)) {
    return [];
  }
  const seen = new Set();
  const normalized = [];
  ids.forEach((raw) => {
    const id = String(raw || '').trim();
    if (!id || seen.has(id)) {
      return;
    }
    seen.add(id);
    normalized.push(id);
  });
  return normalized;
}

/**
 * 合并候选与全局的字段配置。
 * @param {StrategyTurnSelectionCandidate} candidate
 * @param {StrategyTurnLegalActionsSelection} selection
 * @returns {{ matchFields: string[]; ignoreFields: string[]; requiredGroups: StrategyTurnSelectionRequiredGroup[] }}
 */
function resolveFieldConfig(candidate, selection) {
  const matchFields = [
    ...(candidate.matchFields || []),
    ...(selection.matchFields || [])
  ];
  const ignoreFields = new Set([
    ...(selection.ignoreFields || []),
    ...(candidate.ignoreFields || [])
  ]);
  const requiredGroups = [
    ...(selection.requiredGroups || []),
    ...(candidate.requiredGroups || [])
  ];
  const resolvedMatchFields = matchFields.length > 0 ? matchFields : [...DEFAULT_MATCH_FIELDS];
  return {
    matchFields: resolvedMatchFields,
    ignoreFields: [...ignoreFields],
    requiredGroups
  };
}

/**
 * 从对象中按字段优先级解析 ID。
 * @param {object} item
 * @param {string[]} idFields
 * @returns {string}
 */
function resolveItemId(item, idFields) {
  if (!item || typeof item !== 'object') {
    return '';
  }
  const fields = idFields.length > 0 ? idFields : DEFAULT_ID_FIELDS;
  for (const field of fields) {
    const value = item[field];
    if (value != null && String(value).trim()) {
      return String(value).trim();
    }
  }
  return '';
}

/**
 * 比较手牌与候选项在指定字段上是否一致。
 * @param {object} handCard
 * @param {object} selectionItem
 * @param {string[]} matchFields
 * @param {string[]} ignoreFields
 * @returns {boolean}
 */
function itemsFieldMatch(handCard, selectionItem, matchFields, ignoreFields) {
  const ignoreSet = new Set(ignoreFields);
  const fields = matchFields.filter((field) => field && !ignoreSet.has(field));
  if (fields.length === 0) {
    return false;
  }
  return fields.every((field) => {
    const left = handCard[field];
    const right = selectionItem[field];
    return String(left ?? '').trim() === String(right ?? '').trim();
  });
}

/**
 * 将手牌列表索引为 ID → 牌对象。
 * @param {object[]} handCards
 * @param {string[]} idFields
 * @returns {Map<string, object>}
 */
function indexHandCards(handCards, idFields) {
  const map = new Map();
  (handCards || []).forEach((card) => {
    if (!card || typeof card !== 'object') {
      return;
    }
    const id = resolveItemId(card, idFields);
    if (!id || map.has(id)) {
      return;
    }
    map.set(id, card);
  });
  return map;
}

/**
 * 根据已选 ID 取手牌对象列表。
 * @param {string[]} selectedCardIds
 * @param {Map<string, object>} handCardMap
 * @returns {object[]}
 */
function pickSelectedHandCards(selectedCardIds, handCardMap) {
  return selectedCardIds
    .map((id) => handCardMap.get(id))
    .filter((card) => card && typeof card === 'object');
}

/**
 * 回溯判断已选手牌能否一一匹配候选项。
 * @param {object[]} selectedCards
 * @param {object[]} items
 * @param {string[]} matchFields
 * @param {string[]} ignoreFields
 * @returns {boolean}
 */
function canAssignSelectionToItems(selectedCards, items, matchFields, ignoreFields) {
  if (selectedCards.length === 0) {
    return items.length === 0;
  }
  if (selectedCards.length > items.length) {
    return false;
  }

  /**
   * @param {number} cardIndex
   * @param {Set<number>} usedItemIndexes
   * @returns {boolean}
   */
  function backtrack(cardIndex, usedItemIndexes) {
    if (cardIndex >= selectedCards.length) {
      return true;
    }
    const handCard = selectedCards[cardIndex];
    for (let itemIndex = 0; itemIndex < items.length; itemIndex += 1) {
      if (usedItemIndexes.has(itemIndex)) {
        continue;
      }
      if (!itemsFieldMatch(handCard, items[itemIndex], matchFields, ignoreFields)) {
        continue;
      }
      usedItemIndexes.add(itemIndex);
      if (backtrack(cardIndex + 1, usedItemIndexes)) {
        return true;
      }
      usedItemIndexes.delete(itemIndex);
    }
    return false;
  }

  return backtrack(0, new Set());
}

/**
 * 统计某分组内已选牌数量。
 * @param {object[]} selectedCards
 * @param {StrategyTurnSelectionRequiredGroup} group
 * @param {string[]} matchFields
 * @param {string[]} ignoreFields
 * @returns {number}
 */
function countGroupSelection(selectedCards, group, matchFields, ignoreFields) {
  const groupItems = Array.isArray(group.items) ? group.items : [];
  let count = 0;
  selectedCards.forEach((handCard) => {
    const matched = groupItems.some((item) =>
      itemsFieldMatch(handCard, item, matchFields, ignoreFields)
    );
    if (matched) {
      count += 1;
    }
  });
  return count;
}

/**
 * 判断分组约束是否满足（partial 允许未达 minPick）。
 * @param {object[]} selectedCards
 * @param {StrategyTurnSelectionRequiredGroup[]} requiredGroups
 * @param {string[]} matchFields
 * @param {string[]} ignoreFields
 * @param {boolean} requireMinPick
 * @returns {boolean}
 */
function satisfiesRequiredGroups(
  selectedCards,
  requiredGroups,
  matchFields,
  ignoreFields,
  requireMinPick
) {
  if (!requiredGroups.length) {
    return true;
  }
  return requiredGroups.every((group) => {
    const minPick = Number.isFinite(group.minPick) ? Math.max(0, group.minPick) : 1;
    const maxPick = Number.isFinite(group.maxPick)
      ? Math.max(minPick, group.maxPick)
      : (Array.isArray(group.items) ? group.items.length : 0);
    const count = countGroupSelection(selectedCards, group, matchFields, ignoreFields);
    if (count > maxPick) {
      return false;
    }
    if (requireMinPick && count < minPick) {
      return false;
    }
    return true;
  });
}

/**
 * 解析候选对应的提交动作。
 * @param {StrategyTurnSelectionCandidate} candidate
 * @returns {object|null}
 */
function resolveCandidateAction(candidate) {
  if (!candidate || typeof candidate !== 'object') {
    return null;
  }
  if (candidate.action && typeof candidate.action === 'object') {
    return { ...candidate.action };
  }
  const {
    mode: _mode,
    items: _items,
    matchFields: _matchFields,
    ignoreFields: _ignoreFields,
    requiredGroups: _requiredGroups,
    ...action
  } = candidate;
  if (!Object.keys(action).length) {
    return null;
  }
  return { ...action };
}

/**
 * 判断候选项集合与当前选牌是否构成完整匹配。
 * @param {StrategyTurnSelectionCandidate} candidate
 * @param {object[]} selectedCards
 * @param {StrategyTurnLegalActionsSelection} selection
 * @returns {boolean}
 */
function isFullCandidateMatch(candidate, selectedCards, selection) {
  const mode = String(candidate.mode || 'single').trim();
  const items = Array.isArray(candidate.items) ? candidate.items : [];
  const { matchFields, ignoreFields, requiredGroups } = resolveFieldConfig(candidate, selection);

  if (mode === 'click') {
    return selectedCards.length === 0;
  }

  if (!canAssignSelectionToItems(selectedCards, items, matchFields, ignoreFields)) {
    return false;
  }
  if (!satisfiesRequiredGroups(selectedCards, requiredGroups, matchFields, ignoreFields, true)) {
    return false;
  }

  if (mode === 'single') {
    return selectedCards.length === 1 && items.length === 1;
  }
  if (mode === 'multiple' || mode === 'drag') {
    return selectedCards.length === items.length && items.length > 0;
  }
  return selectedCards.length > 0;
}

/**
 * 判断候选项与当前选牌是否构成部分匹配。
 * @param {StrategyTurnSelectionCandidate} candidate
 * @param {object[]} selectedCards
 * @param {StrategyTurnLegalActionsSelection} selection
 * @returns {boolean}
 */
function isPartialCandidateMatch(candidate, selectedCards, selection) {
  const mode = String(candidate.mode || 'single').trim();
  const items = Array.isArray(candidate.items) ? candidate.items : [];

  if (mode === 'click') {
    return selectedCards.length === 0;
  }
  if (selectedCards.length === 0) {
    return items.length > 0 || mode === 'click';
  }

  const { matchFields, ignoreFields, requiredGroups } = resolveFieldConfig(candidate, selection);
  if (!canAssignSelectionToItems(selectedCards, items, matchFields, ignoreFields)) {
    return false;
  }
  return satisfiesRequiredGroups(selectedCards, requiredGroups, matchFields, ignoreFields, false);
}

/**
 * 计算候选与当前选牌的匹配得分（越高越优）。
 * @param {StrategyTurnSelectionCandidate} candidate
 * @param {object[]} selectedCards
 * @param {StrategyTurnLegalActionsSelection} selection
 * @returns {number}
 */
function scoreCandidateMatch(candidate, selectedCards, selection) {
  if (!isPartialCandidateMatch(candidate, selectedCards, selection)) {
    return 0;
  }
  if (isFullCandidateMatch(candidate, selectedCards, selection)) {
    return 1000 + selectedCards.length;
  }
  return selectedCards.length;
}

/**
 * 从候选项提取建议选牌 ID。
 * @param {StrategyTurnSelectionCandidate} candidate
 * @param {Map<string, object>} handCardMap
 * @param {StrategyTurnLegalActionsSelection} selection
 * @returns {string[]}
 */
function buildSuggestedSelection(candidate, handCardMap, selection) {
  const mode = String(candidate.mode || 'single').trim();
  if (mode === 'click') {
    return [];
  }
  const items = Array.isArray(candidate.items) ? candidate.items : [];
  const { matchFields, ignoreFields } = resolveFieldConfig(candidate, selection);
  const idFields = matchFields.filter((field) => !ignoreFields.includes(field));
  const suggested = [];
  const usedIds = new Set();

  items.forEach((item) => {
    for (const [cardId, handCard] of handCardMap.entries()) {
      if (usedIds.has(cardId)) {
        continue;
      }
      if (!itemsFieldMatch(handCard, item, matchFields, ignoreFields)) {
        continue;
      }
      suggested.push(cardId);
      usedIds.add(cardId);
      break;
    }
  });

  if (suggested.length > 0) {
    return suggested;
  }

  return items
    .map((item) => resolveItemId(item, idFields.length > 0 ? idFields : DEFAULT_ID_FIELDS))
    .filter((id) => id && handCardMap.has(id));
}

/**
 * 判断加入一张牌后是否仍与某候选部分兼容。
 * @param {string} cardId
 * @param {string[]} selectedCardIds
 * @param {StrategyTurnSelectionCandidate[]} candidates
 * @param {Map<string, object>} handCardMap
 * @param {StrategyTurnLegalActionsSelection} selection
 * @returns {boolean}
 */
function canSelectCard(cardId, selectedCardIds, candidates, handCardMap, selection) {
  if (!handCardMap.has(cardId)) {
    return false;
  }
  const nextSelection = [...selectedCardIds, cardId];
  const selectedCards = pickSelectedHandCards(nextSelection, handCardMap);
  return candidates.some((candidate) => isPartialCandidateMatch(candidate, selectedCards, selection));
}

/**
 * 计算提示游标对应候选下标。
 * @param {StrategyTurnSelectionCandidate[]} candidates
 * @param {object[]} selectedCards
 * @param {StrategyTurnLegalActionsSelection} selection
 * @param {number} hintCursor
 * @returns {{ suggestedSelection: string[]; nextHintCursor: number }}
 */
function resolveHint(candidates, selectedCards, selection, hintCursor, handCardMap) {
  if (!candidates.length) {
    return { suggestedSelection: [], nextHintCursor: 0 };
  }

  const cursor = Number.isFinite(hintCursor) && hintCursor >= 0 ? Math.floor(hintCursor) : 0;

  if (selectedCards.length === 0) {
    const index = cursor % candidates.length;
    return {
      suggestedSelection: buildSuggestedSelection(candidates[index], handCardMap, selection),
      nextHintCursor: cursor + 1
    };
  }

  let bestIndex = 0;
  let bestScore = -1;
  candidates.forEach((candidate, index) => {
    const score = scoreCandidateMatch(candidate, selectedCards, selection);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });

  const offset = cursor % candidates.length;
  const index = (bestIndex + offset) % candidates.length;
  return {
    suggestedSelection: buildSuggestedSelection(candidates[index], handCardMap, selection),
    nextHintCursor: cursor + 1
  };
}

/**
 * 策略回合通用候选动作匹配。
 * @param {StrategyTurnActionMatcherInput} input
 * @returns {StrategyTurnActionMatcherResult}
 */
export function matchStrategyTurnActions(input) {
  const selection = input?.legalActions?.selection;
  if (!selection || typeof selection !== 'object') {
    return { ...EMPTY_RESULT };
  }

  const candidates = Array.isArray(selection.candidates) ? selection.candidates : [];
  const globalIdFields = selection.matchFields?.length
    ? selection.matchFields
    : DEFAULT_MATCH_FIELDS;
  const handCardMap = indexHandCards(input?.handCards || [], globalIdFields);
  const allHandIds = [...handCardMap.keys()];

  if (!candidates.length) {
    return {
      ...EMPTY_RESULT,
      disabledCardIds: allHandIds,
      nextHintCursor: Number(input?.hintCursor) || 0
    };
  }

  const selectedCardIds = normalizeIdList(input?.selectedCardIds);
  const selectedCards = pickSelectedHandCards(selectedCardIds, handCardMap);

  const activeCandidates = candidates.filter((candidate) =>
    isPartialCandidateMatch(candidate, selectedCards, selection)
  );

  const fullMatches = activeCandidates.filter((candidate) =>
    isFullCandidateMatch(candidate, selectedCards, selection)
  );

  let determinedAction = null;
  if (fullMatches.length === 1) {
    determinedAction = resolveCandidateAction(fullMatches[0]);
  }

  const selectableCardIds = allHandIds.filter((cardId) => {
    if (selectedCardIds.includes(cardId)) {
      return true;
    }
    return canSelectCard(cardId, selectedCardIds, candidates, handCardMap, selection);
  });

  const selectableSet = new Set(selectableCardIds);
  const disabledCardIds = allHandIds.filter((cardId) => !selectableSet.has(cardId));

  const hint = resolveHint(
    candidates,
    selectedCards,
    selection,
    input?.hintCursor,
    handCardMap
  );

  return {
    activeCandidates,
    selectableCardIds,
    disabledCardIds,
    determinedAction,
    suggestedSelection: hint.suggestedSelection,
    nextHintCursor: hint.nextHintCursor
  };
}
