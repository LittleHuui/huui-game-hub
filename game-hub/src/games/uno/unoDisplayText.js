import { UNO_COLOR_OPTIONS } from './unoGameConstants.js';

/** 牌型 / 规则键展示文案（仅前端展示，协议字段仍为英文） */
export const UNO_CARD_TYPE_LABELS = Object.freeze({
  NUMBER: '数字牌',
  DISABLE: '禁用',
  REVERSE: '反转',
  DRAW_TWO: '+2',
  WILD: '万用牌',
  WILD_DRAW4: '+4'
});

/**
 * 将花色协议值或键转为中文展示文案。
 * @param {string} color
 * @returns {string}
 */
export function resolveUnoColorLabel(color) {
  const normalized = String(color || '').trim();
  if (!normalized) {
    return '';
  }
  const lower = normalized.toLowerCase();
  const upper = normalized.toUpperCase();
  const matched = UNO_COLOR_OPTIONS.find((item) => item.value === lower || item.key === upper);
  return matched ? matched.label : normalized;
}

/**
 * 将牌型或规则键转为中文展示文案。
 * @param {string} cardTypeOrRuleKey
 * @returns {string}
 */
export function formatUnoCardTypeLabel(cardTypeOrRuleKey) {
  const normalized = String(cardTypeOrRuleKey || '').trim().toUpperCase();
  if (!normalized) {
    return '';
  }
  return UNO_CARD_TYPE_LABELS[normalized] || normalized;
}
