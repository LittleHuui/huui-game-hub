/** 操作按钮语义类型（映射为统一 CSS，勿在业务页散落 class） */
export const GAME_ACTION_TYPE = Object.freeze({
  PRIMARY: 'primary',
  SECONDARY: 'secondary',
  DANGER: 'danger',
  WARNING: 'warning',
  SUCCESS: 'success',
  GHOST: 'ghost',
  PAUSE: 'pause',
  RESUME: 'resume'
});

/** 操作按钮尺寸 */
export const GAME_ACTION_SIZE = Object.freeze({
  SM: 'sm',
  MD: 'md',
  LG: 'lg'
});

/** 配置控件类型 */
export const GAME_CONTROL_TYPE = Object.freeze({
  SELECT: 'select',
  RADIO: 'radio',
  SWITCH: 'switch',
  CUSTOM: 'custom'
});

/** 对局统计卡片色调 */
export const GAME_STAT_TONE = Object.freeze({
  ACCENT: 'accent',
  PRIMARY: 'primary',
  INFO: 'info',
  SUCCESS: 'success',
  WARNING: 'warning',
  DANGER: 'danger',
  MUTED: 'muted',
  NEUTRAL: 'neutral'
});
