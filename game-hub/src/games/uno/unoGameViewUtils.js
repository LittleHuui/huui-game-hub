import {
  UNO_EVENT_CARD_PLAYED,
  UNO_WILD_CARD_CODES,
  UNO_WILD_CARD_TYPES,
  UNO_WILD_RULE_KEYS
} from './unoGameConstants.js';

/**
 * 从事件列表中筛出有效出牌事件。
 * @param {object[]} events
 * @returns {object[]}
 */
export function filterCardPlayedEvents(events) {
  if (!Array.isArray(events)) {
    return [];
  }
  return events.filter((event) => {
    if (!event || typeof event !== 'object') {
      return false;
    }
    return String(event.eventType || '').trim() === UNO_EVENT_CARD_PLAYED;
  });
}

/**
 * 将出牌事件转为弃牌区展示项。
 * @param {object} event
 * @returns {{ cardCode: string; playerId: string; ruleKey: string }|null}
 */
export function mapCardPlayedEventToDiscardItem(event) {
  const payload = event?.payload && typeof event.payload === 'object' ? event.payload : {};
  const cardCode = String(payload.cardCode || '').trim();
  if (!cardCode) {
    return null;
  }
  return {
    cardCode,
    playerId: String(event.playerId || '').trim(),
    ruleKey: String(payload.ruleKey || '').trim()
  };
}

/**
 * 取最近若干条有效出牌展示项。
 * @param {object[]} events
 * @param {number} limit
 * @returns {Array<{ cardCode: string; playerId: string; ruleKey: string }>}
 */
export function resolveRecentCardPlayedItems(events, limit = 2) {
  const played = filterCardPlayedEvents(events);
  const items = [];
  for (let index = played.length - 1; index >= 0 && items.length < limit; index -= 1) {
    const mapped = mapCardPlayedEventToDiscardItem(played[index]);
    if (mapped) {
      items.unshift(mapped);
    }
  }
  return items;
}

/**
 * 归一化手牌对象。
 * @param {object|string|null|undefined} source
 * @returns {{ cardInstanceId: string; cardCode: string; cardType: string }}
 */
export function normalizeHandCard(source) {
  if (typeof source === 'string') {
    const cardCode = source.trim();
    return { cardInstanceId: cardCode, cardCode, cardType: '' };
  }
  if (!source || typeof source !== 'object') {
    return { cardInstanceId: '', cardCode: '', cardType: '' };
  }
  return {
    cardInstanceId: String(source.cardInstanceId || source.id || '').trim(),
    cardCode: String(source.cardCode || source.code || '').trim(),
    cardType: String(source.cardType || '').trim()
  };
}

/**
 * 判断手牌是否为万能牌（需选色）。
 * @param {{ cardType?: string; cardCode?: string }} card
 * @returns {boolean}
 */
export function isWildHandCard(card) {
  const cardType = String(card?.cardType || '').trim().toUpperCase();
  if (UNO_WILD_CARD_TYPES.includes(cardType)) {
    return true;
  }
  const cardCode = String(card?.cardCode || '').trim().toLowerCase();
  return UNO_WILD_CARD_CODES.includes(cardCode);
}

/**
 * 判断出牌事件是否为万能牌型。
 * @param {{ ruleKey?: string }} item
 * @returns {boolean}
 */
export function isWildRuleKey(ruleKey) {
  const normalized = String(ruleKey || '').trim();
  return UNO_WILD_RULE_KEYS.includes(normalized);
}

/**
 * 在合法操作中查找出牌动作。
 * @param {object[]} legalActions
 * @param {string} cardInstanceId
 * @param {string} [chooseColor]
 * @returns {object|null}
 */
export function findPlayCardLegalAction(legalActions, cardInstanceId, chooseColor) {
  const instanceId = String(cardInstanceId || '').trim();
  if (!instanceId) {
    return null;
  }
  const color = chooseColor != null ? String(chooseColor).trim().toLowerCase() : '';
  return (
    (legalActions || []).find((item) => {
      if (!item || String(item.actionType || '').trim() !== 'PLAY_CARD') {
        return false;
      }
      const payload = item.payload && typeof item.payload === 'object' ? item.payload : {};
      if (String(payload.cardInstanceId || '').trim() !== instanceId) {
        return false;
      }
      if (!color) {
        return !payload.chooseColor;
      }
      return String(payload.chooseColor || '').trim().toLowerCase() === color;
    }) || null
  );
}
