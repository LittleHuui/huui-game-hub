/** UNO 对局事件：出牌（与后端 ``uno.card.played`` 一致） */
export const UNO_EVENT_CARD_PLAYED = 'uno.card.played';

/** 万能牌 cardCode（与规则种子 cardCode 一致） */
export const UNO_WILD_CARD_CODES = Object.freeze(['wild', 'wild_draw4']);

/** 万能牌 cardType（与规则引擎一致） */
export const UNO_WILD_CARD_TYPES = Object.freeze(['WILD', 'WILD_DRAW4']);

/** 万能牌 ruleKey（事件 payload.ruleKey） */
export const UNO_WILD_RULE_KEYS = Object.freeze(['WILD', 'WILD_DRAW4']);

/** 颜色选择器选项（展示用大写，提交用小写 chooseColor） */
export const UNO_COLOR_OPTIONS = Object.freeze([
  { key: 'RED', value: 'red' },
  { key: 'YELLOW', value: 'yellow' },
  { key: 'BLUE', value: 'blue' },
  { key: 'GREEN', value: 'green' }
]);
