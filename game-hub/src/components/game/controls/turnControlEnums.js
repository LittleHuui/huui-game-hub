/** 策略回合制 legalActions.actionType 平台常量（与后端规则引擎约定一致） */
export const STRATEGY_TURN_ACTION_TYPE = Object.freeze({
  DRAW_CARD: 'DRAW_CARD',
  PLAY_CARD: 'PLAY_CARD',
  PASS_TURN: 'PASS_TURN'
});

/** TurnActionBar 本地 UI 按钮 key（非后端 actionType） */
export const TURN_ACTION_BAR_KEY = Object.freeze({
  DRAW: 'draw',
  PLAY: 'play',
  UI_ACTION_HINT: 'hint',
  END_TURN: 'endTurn'
});
