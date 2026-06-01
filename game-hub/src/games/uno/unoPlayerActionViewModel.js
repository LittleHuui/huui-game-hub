import {
  UNO_EVENT_CARD_PLAYED,
  UNO_EVENT_CARDS_DRAWN,
  UNO_EVENT_PLAYER_DISABLED
} from './unoGameConstants.js';

/** @typedef {'cardPlayed'|'disabled'|'draw'|'rank'} UnoPlayerActionType */

/**
 * @typedef {object} UnoPlayerActionViewModel
 * @property {UnoPlayerActionType} type
 * @property {string} [cardCode]
 * @property {number} [count]
 * @property {number} [rank]
 */

export const UNO_PLAYER_ACTION_TYPE = Object.freeze({
  CARD_PLAYED: 'cardPlayed',
  DISABLED: 'disabled',
  DRAW: 'draw',
  RANK: 'rank'
});

/**
 * 创建空的玩家动作映射。
 * @returns {Record<string, UnoPlayerActionViewModel>}
 */
export function createEmptyUnoPlayerActionMap() {
  return {};
}

/**
 * 将单条帧事件合并进玩家动作映射（就地修改）。
 * @param {Record<string, UnoPlayerActionViewModel>} actionMap
 * @param {object|null|undefined} event
 */
export function applyUnoPlayerActionEvent(actionMap, event) {
  if (!event || typeof event !== 'object' || !actionMap) {
    return;
  }

  const eventType = String(event.eventType || '').trim();
  const playerId = String(event.playerId || '').trim();
  const payload = event.payload && typeof event.payload === 'object' ? event.payload : {};

  if (eventType === UNO_EVENT_CARD_PLAYED) {
    const cardCode = String(payload.cardCode || '').trim();
    if (!playerId || !cardCode) {
      return;
    }
    actionMap[playerId] = {
      type: UNO_PLAYER_ACTION_TYPE.CARD_PLAYED,
      cardCode
    };
    return;
  }

  if (eventType === UNO_EVENT_CARDS_DRAWN) {
    const count = Number(payload.count);
    if (!playerId || !Number.isFinite(count) || count <= 0) {
      return;
    }
    actionMap[playerId] = {
      type: UNO_PLAYER_ACTION_TYPE.DRAW,
      count
    };
    return;
  }

  if (eventType === UNO_EVENT_PLAYER_DISABLED) {
    const disabledPlayerId = String(payload.disabledPlayerId || '').trim();
    if (!disabledPlayerId) {
      return;
    }
    actionMap[disabledPlayerId] = {
      type: UNO_PLAYER_ACTION_TYPE.DISABLED
    };
  }
}

/**
 * 批量合并帧事件。
 * @param {Record<string, UnoPlayerActionViewModel>} actionMap
 * @param {object[]} events
 * @returns {Record<string, UnoPlayerActionViewModel>}
 */
export function applyUnoPlayerActionEvents(actionMap, events) {
  const nextMap = { ...actionMap };
  if (!Array.isArray(events)) {
    return nextMap;
  }
  for (const event of events) {
    applyUnoPlayerActionEvent(nextMap, event);
  }
  return nextMap;
}

/**
 * 在玩家回合开始时，清理该玩家上一轮动作展示（已完赛名次展示除外）。
 * @param {Record<string, UnoPlayerActionViewModel>} actionMap
 * @param {object|null|undefined} publicState
 * @returns {Record<string, UnoPlayerActionViewModel>}
 */
export function clearUnoPlayerActionForCurrentTurn(actionMap, publicState) {
  const currentPlayerId = String(publicState?.currentPlayerId || '').trim();
  if (!currentPlayerId || !actionMap || !actionMap[currentPlayerId]) {
    return actionMap || {};
  }

  const players = Array.isArray(publicState?.players) ? publicState.players : [];
  const currentPlayer = players.find(
    (item) => String(item?.playerId || '').trim() === currentPlayerId
  );
  const isFinished = Boolean(currentPlayer?.isFinished);
  const finishRank = Number(currentPlayer?.finishRank);

  // 已完赛玩家的名次展示不清理。
  if (isFinished && Number.isFinite(finishRank) && finishRank > 0) {
    return actionMap;
  }

  const nextMap = { ...actionMap };
  delete nextMap[currentPlayerId];
  return nextMap;
}

/**
 * 在对局未结束时，用已完成玩家的名次覆盖其动作展示。
 * @param {Record<string, UnoPlayerActionViewModel>} actionMap
 * @param {object|null|undefined} publicState
 * @param {boolean} isGameOver
 * @returns {Record<string, UnoPlayerActionViewModel>}
 */
export function buildUnoPlayerActionMap(actionMap, publicState, isGameOver) {
  const map = { ...actionMap };
  if (isGameOver) {
    return map;
  }

  const players = publicState?.players;
  if (!Array.isArray(players)) {
    return map;
  }

  for (const player of players) {
    const playerId = String(player?.playerId || '').trim();
    const finishRank = Number(player?.finishRank);
    const isFinished = Boolean(player?.isFinished);
    if (!playerId || !isFinished || !Number.isFinite(finishRank) || finishRank <= 0) {
      continue;
    }
    map[playerId] = {
      type: UNO_PLAYER_ACTION_TYPE.RANK,
      rank: finishRank
    };
  }

  return map;
}
