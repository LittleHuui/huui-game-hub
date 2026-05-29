import { STRATEGY_TURN_ACTION_TYPE } from './turnControlEnums.js';

/**
 * 判断 legalActions 中是否包含指定操作类型。
 * @param {Array<{ actionType?: string }>|null|undefined} legalActions
 * @param {string} actionType
 * @returns {boolean}
 */
export function hasStrategyTurnActionType(legalActions, actionType) {
  const type = String(actionType || '').trim();
  if (!type) {
    return false;
  }
  return (legalActions || []).some(
    (item) => item && String(item.actionType || '').trim() === type
  );
}

/**
 * 筛选指定类型的合法操作列表。
 * @param {Array<object>|null|undefined} legalActions
 * @param {string} actionType
 * @returns {object[]}
 */
export function filterStrategyTurnActionsByType(legalActions, actionType) {
  const type = String(actionType || '').trim();
  if (!type) {
    return [];
  }
  return (legalActions || []).filter(
    (item) => item && String(item.actionType || '').trim() === type
  );
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
