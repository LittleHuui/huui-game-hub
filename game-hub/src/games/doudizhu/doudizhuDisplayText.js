/** 斗地主 actionType 按钮文案（仅展示） */
export const DOUDIZHU_ACTION_LABELS = Object.freeze({
  SHOW_CARDS: '明牌',
  SKIP_SHOW_CARDS: '不明',
  CALL_LANDLORD: '叫地主',
  PASS_CALL: '不叫',
  ROB_LANDLORD: '抢地主',
  PASS_ROB: '不抢',
  DOUBLE: '加倍',
  PASS_DOUBLE: '不加倍',
  PASS: '不出',
  PLAY_CARDS: '出牌'
});

/** 操作反馈的视觉语义：主动行动使用暖金，放弃行动使用冷银。 */
const DOUDIZHU_DECLINED_ACTION_TYPES = new Set([
  'SKIP_SHOW_CARDS',
  'PASS_CALL',
  'PASS_ROB',
  'PASS_DOUBLE',
  'PASS'
]);

/** 斗地主阶段展示文案 */
export const DOUDIZHU_PHASE_LABELS = Object.freeze({
  dealing: '发牌中',
  laizi_reveal: '癞子揭晓',
  showing: '明牌阶段',
  calling: '叫地主',
  robbing: '抢地主',
  landlord_confirm: '确认地主',
  doubling: '加倍',
  playing: '出牌',
  settlement: '结算中',
  finished: '已结束'
});

/** 牌型展示文案 */
export const DOUDIZHU_COMBO_LABELS = Object.freeze({
  SINGLE: '单牌',
  PAIR: '对子',
  TRIPLE: '三张',
  TRIPLE_WITH_SINGLE: '三带一',
  TRIPLE_WITH_PAIR: '三带二',
  STRAIGHT: '顺子',
  PAIR_STRAIGHT: '连对',
  AIRPLANE: '飞机',
  AIRPLANE_WITH_SINGLES: '飞机带单',
  AIRPLANE_WITH_PAIRS: '飞机带对',
  FOUR_WITH_TWO_SINGLES: '四带二单',
  FOUR_WITH_TWO_PAIRS: '四带二对',
  BOMB: '炸弹',
  LAIZI_BOMB: '癞子炸弹',
  ROCKET: '王炸'
});

/** 角色展示文案 */
export const DOUDIZHU_ROLE_LABELS = Object.freeze({
  landlord: '地主',
  farmer: '农民',
  LANDLORD: '地主',
  FARMER: '农民'
});

/** 春天类型展示 */
export const DOUDIZHU_SPRING_LABELS = Object.freeze({
  spring: '春天',
  anti_spring: '反春天',
  SPRING: '春天',
  ANTI_SPRING: '反春天'
});

/** 胜方阵营展示 */
export const DOUDIZHU_WINNER_ROLE_LABELS = Object.freeze({
  landlord: '地主胜',
  farmer: '农民胜'
});

/**
 * 根据动作及公开参数生成按钮、操作反馈共用文案。
 * @param {string} actionType
 * @param {object} [payload]
 * @returns {string}
 */
export function formatDoudizhuActionLabel(actionType, payload = {}) {
  const key = String(actionType || '').trim();
  if (key === 'CALL_LANDLORD' && Object.hasOwn(payload || {}, 'bidScore')) {
    const score = payload.bidScore;
    return Number.isInteger(score) && score >= 1 && score <= 3 ? `${score}分` : '';
  }
  return DOUDIZHU_ACTION_LABELS[key] || key;
}

/**
 * 展示服务端已确定的本局底分；未知值不从规则或倍率推算。
 * @param {unknown} value
 * @returns {string}
 */
export function formatDoudizhuBaseScore(value) {
  return Number.isSafeInteger(value) && value > 0 ? String(value) : '—';
}

/**
 * 获取操作反馈的视觉语义，不参与游戏规则判定。
 * @param {string} actionType
 * @returns {'affirmative'|'declined'}
 */
export function resolveDoudizhuActionFeedbackTone(actionType) {
  const key = String(actionType || '').trim();
  return DOUDIZHU_DECLINED_ACTION_TYPES.has(key) ? 'declined' : 'affirmative';
}

/**
 * 将阶段编码转为展示文案。
 * @param {string} phase
 * @returns {string}
 */
export function formatDoudizhuPhaseLabel(phase) {
  const key = String(phase || '').trim().toLowerCase();
  return DOUDIZHU_PHASE_LABELS[key] || key || '对局中';
}

/**
 * 将牌型编码转为展示文案。
 * @param {string} comboType
 * @returns {string}
 */
export function formatDoudizhuComboLabel(comboType) {
  const key = String(comboType || '').trim().toUpperCase();
  return DOUDIZHU_COMBO_LABELS[key] || key;
}

/**
 * 将角色编码转为展示文案。
 * @param {string} role
 * @returns {string}
 */
export function formatDoudizhuRoleLabel(role) {
  const key = String(role || '').trim();
  return DOUDIZHU_ROLE_LABELS[key] || key;
}

/**
 * 将胜方阵营转为展示文案。
 * @param {string} winnerRole
 * @returns {string}
 */
export function formatDoudizhuWinnerRoleLabel(winnerRole) {
  const key = String(winnerRole || '').trim().toLowerCase();
  return DOUDIZHU_WINNER_ROLE_LABELS[key] || key;
}

/**
 * 将春天类型转为展示文案。
 * @param {string|null|undefined} springType
 * @returns {string}
 */
export function formatDoudizhuSpringLabel(springType) {
  const key = String(springType || '').trim();
  if (!key) {
    return '';
  }
  const lower = key.toLowerCase();
  return DOUDIZHU_SPRING_LABELS[key] || DOUDIZHU_SPRING_LABELS[lower] || key;
}
