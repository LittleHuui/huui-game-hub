import { findGameSettingDefinition } from '../../constants/gameSettingDefinitions.js';

const meta = findGameSettingDefinition('sudoku', 'filterUnavailableNumbers');

/** 数独页设置项元数据（与顶栏统一定义同源） */
export const SUDOKU_PAGE_SETTING_FILTER_UNAVAILABLE = Object.freeze({
  key: meta?.key || 'filterUnavailableNumbers',
  label: meta?.label || '过滤不可选数字',
  description: meta?.description || ''
});
