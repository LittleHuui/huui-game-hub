import { findGameSettingDefinition } from '../../constants/gameSettingDefinitions.js';

const meta = findGameSettingDefinition('minesweeper', 'highlightAroundCells');

/** 扫雷页设置项元数据（与顶栏统一定义同源） */
export const MINESWEEPER_PAGE_SETTING_HIGHLIGHT_AROUND = Object.freeze({
  key: meta?.key || 'highlightAroundCells',
  label: meta?.label || '周围格高亮',
  description: meta?.description || ''
});
