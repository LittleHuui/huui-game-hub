/** 难度：行、列、雷数 */
export const MINESWEEPER_PRESETS = {
  easy: { rows: 9, cols: 9, mines: 10, label: '初级', scoreWin: 100 },
  medium: { rows: 16, cols: 16, mines: 40, label: '中级', scoreWin: 300 },
  hard: { rows: 16, cols: 30, mines: 100, label: '高级', scoreWin: 800 }
};

/** 本局提示卡次数上限 */
export const HINT_LIMIT_BY_DIFFICULTY = {
  easy: 2,
  medium: 3,
  hard: 5
};

/** 客户端布局配置（仅展示，不改变规则） */
export let clientLayoutConfigs = [];

/**
 * @param {unknown} list
 */
export function setClientLayoutConfigs(list) {
  clientLayoutConfigs = Array.isArray(list) ? list : [];
}
