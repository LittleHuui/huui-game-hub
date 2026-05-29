/**
 * 将后端 legalActions 列表转为 strategyTurnActionMatcher 所需的 selection 结构。
 * @param {object[]|null|undefined} legalActionsList
 * @returns {{ selection: { candidates: object[]; matchFields: string[] } }}
 */
export function buildMatcherLegalActions(legalActionsList) {
  const list = Array.isArray(legalActionsList) ? legalActionsList : [];
  const candidates = list
    .map((action) => mapLegalActionToCandidate(action))
    .filter((item) => item != null);
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
 * 从候选项解析关联的合法操作。
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
 * @param {object} action
 * @returns {object|null}
 */
function mapLegalActionToCandidate(action) {
  if (!action || typeof action !== 'object') {
    return null;
  }
  const actionType = String(action.actionType || '').trim();
  const actionId = String(action.actionId || '').trim();
  if (!actionId || actionType !== 'PLAY_CARD') {
    return null;
  }
  const payload = action.payload && typeof action.payload === 'object' ? action.payload : {};
  const selection = action.selection && typeof action.selection === 'object' ? action.selection : null;
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

  const wrappedAction = {
    actionId,
    actionType,
    playerId: String(action.playerId || '').trim(),
    payload: { ...payload }
  };

  return {
    mode: 'single',
    items,
    matchFields,
    requiredGroups,
    action: wrappedAction
  };
}
