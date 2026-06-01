/** UNO 对局事件：出牌（与后端 ``uno.card.played`` 一致） */
export const UNO_EVENT_CARD_PLAYED = 'uno.card.played';

/** UNO 对局事件：玩家被禁用（与后端 ``uno.player.disabled`` 一致） */
export const UNO_EVENT_PLAYER_DISABLED = 'uno.player.disabled';

/** UNO 对局事件：摸牌（与后端 ``uno.cards.drawn`` 一致） */
export const UNO_EVENT_CARDS_DRAWN = 'uno.cards.drawn';

/** 万能牌 cardCode（与规则种子 cardCode 一致） */
export const UNO_WILD_CARD_CODES = Object.freeze(['wild', 'wild_draw4']);

/** 万能牌 cardType（与规则引擎一致） */
export const UNO_WILD_CARD_TYPES = Object.freeze(['WILD', 'WILD_DRAW4']);

/** 万能牌 ruleKey（事件 payload.ruleKey） */
export const UNO_WILD_RULE_KEYS = Object.freeze(['WILD', 'WILD_DRAW4']);

/** 颜色选择器选项（展示用 label，提交用小写 chooseColor，key 与后端协议一致） */
export const UNO_COLOR_OPTIONS = Object.freeze([
  { key: 'RED', value: 'red', label: '红' },
  { key: 'YELLOW', value: 'yellow', label: '黄' },
  { key: 'BLUE', value: 'blue', label: '蓝' },
  { key: 'GREEN', value: 'green', label: '绿' }
]);
