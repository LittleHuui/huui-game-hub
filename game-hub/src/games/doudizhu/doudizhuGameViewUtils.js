/** 连续牌型的主体按点数升序展示，不参与牌型识别或手牌排列。 */
const ASCENDING_MAIN_COMBO_TYPES = new Set([
  'STRAIGHT',
  'PAIR_STRAIGHT',
  'AIRPLANE',
  'AIRPLANE_WITH_SINGLES',
  'AIRPLANE_WITH_PAIRS'
]);

/**
 * 归一化手牌对象。
 * @param {object|string|null|undefined} source
 * @returns {object}
 */
export function normalizeHandCard(source) {
  if (!source || typeof source !== 'object') {
    return {
      cardInstanceId: '',
      cardCode: '',
      displayLabel: '',
      displayColor: '',
      suitCode: '',
      suitLabel: '',
      rankCode: '',
      rankValue: 0,
      isJoker: false,
      isLaizi: false,
      image: ''
    };
  }
  const rankCode = String(source.rankCode || '').trim();
  const displayLabel = String(source.displayLabel || '').trim();
  return {
    cardInstanceId: String(source.cardInstanceId || source.id || '').trim(),
    cardCode: String(source.cardCode || source.code || '').trim(),
    displayLabel,
    displayColor: String(source.displayColor || '').trim().toUpperCase(),
    suitCode: String(source.suitCode || '').trim(),
    suitLabel: String(source.suitLabel || '').trim(),
    rankCode,
    rankValue: resolveDoudizhuRankValue(source.rankValue, rankCode || displayLabel),
    isJoker: Boolean(source.isJoker),
    isLaizi: Boolean(source.isLaizi),
    image: String(source.image || '').trim()
  };
}

/**
 * 解析斗地主牌面的展示点数，确保缺少数值字段的公开牌也能按点数聚合。
 * @param {number|string|null|undefined} rawValue
 * @param {string} rankCode
 * @returns {number}
 */
function resolveDoudizhuRankValue(rawValue, rankCode) {
  const numericValue = Number(rawValue);
  if (Number.isFinite(numericValue) && numericValue > 0) {
    return numericValue;
  }
  const normalized = String(rankCode || '').trim().toUpperCase();
  const ranks = {
    '3': 3,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    '10': 10,
    J: 11,
    Q: 12,
    K: 13,
    A: 14,
    '2': 15,
    SMALL_JOKER: 16,
    BIG_JOKER: 17,
    JOKER_SMALL: 16,
    JOKER_BIG: 17,
    小王: 16,
    大王: 17
  };
  return ranks[normalized] || 0;
}

/**
 * 按点数对手牌排序（降序，王最大），同点保持服务端给出的稳定顺序。
 * @param {object[]} cards
 * @returns {object[]}
 */
export function sortHandCards(cards) {
  return (cards || [])
    .map((card, index) => ({ card, index }))
    .sort((leftEntry, rightEntry) => {
      const leftValue = Number(leftEntry.card?.rankValue) || 0;
      const rightValue = Number(rightEntry.card?.rankValue) || 0;
      if (leftValue !== rightValue) {
        return rightValue - leftValue;
      }
      return leftEntry.index - rightEntry.index;
    })
    .map((entry) => entry.card);
}

/**
 * 按服务端归一牌型排列公开出牌：主体在前，连续主体升序，其余点数组降序，同点保持输入顺序。
 * 癞子仅使用服务端明确的替代点数；只返回展示数组，不修改牌实体、牌面或提交顺序。
 * @param {object[]} cards
 * @param {object|null} combo 服务端 lastPlay 牌型，normalizedRankValues 表示主体点数组。
 * @returns {object[]}
 */
export function groupDisplayCardsByRank(cards, combo = null) {
  const mainRankDirection = ASCENDING_MAIN_COMBO_TYPES.has(
    String(combo?.comboType || '').trim().toUpperCase()
  ) ? 1 : -1;
  const mainRanks = new Set(
    (Array.isArray(combo?.normalizedRankValues) ? combo.normalizedRankValues : [])
      .map(Number)
      .filter((value) => Number.isFinite(value) && value > 0)
  );
  const assignedRanks = new Map();
  const laiziUsage = Array.isArray(combo?.laiziUsage) ? combo.laiziUsage : [];
  laiziUsage.forEach((usage) => {
    const cardId = String(usage?.laiziCardInstanceId || '').trim();
    const rankValue = resolveDoudizhuRankValue(usage?.assignedRankValue, usage?.assignedRankCode);
    if (cardId && rankValue > 0) {
      assignedRanks.set(cardId, rankValue);
    }
  });
  return (cards || [])
    .map((card, index) => {
      const cardId = String(card?.cardInstanceId || '').trim();
      const rankValue = assignedRanks.get(cardId)
        ?? resolveDoudizhuRankValue(card?.rankValue, card?.rankCode || card?.displayLabel);
      return { card, index, rankValue, isMain: mainRanks.has(rankValue) };
    })
    .sort((left, right) => (
      Number(right.isMain) - Number(left.isMain)
      || (left.isMain ? mainRankDirection : -1) * (left.rankValue - right.rankValue)
      || left.index - right.index
    ))
    .map((entry) => entry.card);
}

/**
 * 构建公开出牌的牌面展示模型，原牌与服务端逐张替代点数保持分离。
 * @param {object[]} cards 公开出牌实体。
 * @param {object|null} combo 服务端归一牌型，包含按实例 ID 标识的 laiziUsage。
 * @returns {{ card: object; assignedRankCode: string }[]}
 */
export function buildPlayedCardDisplays(cards, combo = null) {
  const normalizedCards = (Array.isArray(cards) ? cards : [])
    .map(normalizeHandCard)
    .filter((card) => card.cardInstanceId);
  const assignedRanks = new Map();
  const laiziUsage = Array.isArray(combo?.laiziUsage) ? combo.laiziUsage : [];
  laiziUsage.forEach((usage) => {
    const cardId = String(usage?.laiziCardInstanceId || '').trim();
    const rankCode = String(usage?.assignedRankCode || '').trim().toUpperCase();
    const rankValue = resolveDoudizhuRankValue(null, rankCode);
    if (cardId && rankValue >= 3 && rankValue <= 15) {
      assignedRanks.set(cardId, rankCode);
    }
  });
  return groupDisplayCardsByRank(normalizedCards, combo).map((card) => ({
    card,
    assignedRankCode: card.isLaizi && !card.isJoker
      ? assignedRanks.get(card.cardInstanceId) || ''
      : ''
  }));
}

/**
 * 解析 viewer 视角下的对手座位布局。
 * @param {object[]} players
 * @param {string} viewerPlayerId
 * @returns {{ left: object|null; right: object|null }}
 */
export function resolveOpponentLayout(players, viewerPlayerId) {
  const list = Array.isArray(players) ? players : [];
  const viewerId = String(viewerPlayerId || '').trim();
  const viewer = list.find((item) => String(item?.playerId || '').trim() === viewerId);
  const viewerSeat = Number.isFinite(Number(viewer?.seatIndex)) ? Number(viewer.seatIndex) : 0;
  const opponents = list
    .filter((item) => String(item?.playerId || '').trim() !== viewerId)
    .map((item) => {
      const seat = Number.isFinite(Number(item?.seatIndex)) ? Number(item.seatIndex) : 0;
      const relativeSeat = (seat - viewerSeat + 3) % 3;
      return { ...item, relativeSeat };
    })
    .sort((left, right) => left.relativeSeat - right.relativeSeat);
  const left = opponents.find((item) => item.relativeSeat === 2) || null;
  const right = opponents.find((item) => item.relativeSeat === 1) || null;
  return { left, right };
}

/**
 * 归一化上一手出牌信息。
 * @param {object|null|undefined} lastPlay
 * @returns {object|null}
 */
export function normalizeLastPlay(lastPlay) {
  if (!lastPlay || typeof lastPlay !== 'object') {
    return null;
  }
  const cardInstanceIds = Array.isArray(lastPlay.cardInstanceIds)
    ? lastPlay.cardInstanceIds.map((id) => String(id || '').trim()).filter(Boolean)
    : [];
  return {
    comboType: String(lastPlay.comboType || '').trim(),
    cardInstanceIds,
    mainRankCode: String(lastPlay.mainRankCode || '').trim(),
    cardCount: Number(lastPlay.cardCount) || cardInstanceIds.length
  };
}

/**
 * 从公开玩家列表查找玩家。
 * @param {object[]} players
 * @param {string} playerId
 * @returns {object|null}
 */
export function findPublicPlayer(players, playerId) {
  const id = String(playerId || '').trim();
  if (!id || !Array.isArray(players)) {
    return null;
  }
  return players.find((item) => String(item?.playerId || '').trim() === id) || null;
}

/**
 * 判断当前阶段是否允许选手牌。
 * @param {string} phase
 * @returns {boolean}
 */
export function isPlayingPhase(phase) {
  return String(phase || '').trim().toLowerCase() === 'playing';
}

/**
 * 将 ID 集合规范化为排序后的唯一数组（用于匹配比较）。
 * @param {string[]} ids
 * @returns {string[]}
 */
export function normalizeCardIdSet(ids) {
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
  normalized.sort();
  return normalized;
}

/**
 * 判断两个 cardInstanceId 集合是否完全一致。
 * @param {string[]} left
 * @param {string[]} right
 * @returns {boolean}
 */
export function isSameCardIdSet(left, right) {
  const a = normalizeCardIdSet(left);
  const b = normalizeCardIdSet(right);
  if (a.length !== b.length) {
    return false;
  }
  return a.every((id, index) => id === b[index]);
}
