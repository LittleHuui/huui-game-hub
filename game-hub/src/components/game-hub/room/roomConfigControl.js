import { GAME_CONTROL_TYPE } from '../../game/controls/gameControlEnums.js';

/**
 * 将房间配置字段与当前草稿值映射为公共控件描述。
 * @param {{ key: string; controlType: string; label: string; options?: Array }} field
 * @param {unknown} value
 * @returns {{ key: string; type: string; label: string; value: unknown; options?: Array }}
 */
export function toRoomConfigControl(field, value) {
  if (field.controlType === 'switch') {
    return {
      key: field.key,
      type: GAME_CONTROL_TYPE.SWITCH,
      label: field.label,
      value: Boolean(value)
    };
  }
  if (field.controlType === 'radio') {
    return {
      key: field.key,
      type: GAME_CONTROL_TYPE.RADIO,
      label: field.label,
      value,
      options: field.options || []
    };
  }
  if (field.controlType === 'select') {
    return {
      key: field.key,
      type: GAME_CONTROL_TYPE.SELECT,
      label: field.label,
      value,
      options: field.options || []
    };
  }
  return {
    key: field.key,
    type: GAME_CONTROL_TYPE.CUSTOM,
    label: field.label,
    value
  };
}
