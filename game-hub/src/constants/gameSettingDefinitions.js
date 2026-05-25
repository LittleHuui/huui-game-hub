/** 顶栏设置面板：各游戏可配置项统一定义（无当前游戏过滤） */
export const GAME_SETTING_DEFINITIONS = Object.freeze([
  Object.freeze({
    gameCode: 'minesweeper',
    gameName: '扫雷',
    settings: Object.freeze([
      Object.freeze({
        key: 'highlightAroundCells',
        label: '周围格高亮',
        type: 'switch',
        defaultValue: true,
        description: '鼠标悬停在已翻开且带数字的格子上时，为周围 8 格叠加浅色描边。'
      })
    ])
  }),
  Object.freeze({
    gameCode: 'sudoku',
    gameName: '数独',
    settings: Object.freeze([
      Object.freeze({
        key: 'filterUnavailableNumbers',
        label: '过滤不可选数字',
        type: 'switch',
        defaultValue: false,
        description: '开启后，小弹窗会禁用同行、同列、同宫已有正式数字。'
      })
    ])
  })
]);

/**
 * 查找某游戏某设置项元数据。
 * @param {string} gameCode
 * @param {string} key
 * @returns {{ key: string; label: string; type: string; defaultValue: boolean; description?: string }|null}
 */
export function findGameSettingDefinition(gameCode, key) {
  if (!gameCode || !key) {
    return null;
  }
  const group = GAME_SETTING_DEFINITIONS.find((g) => g.gameCode === gameCode);
  if (!group) {
    return null;
  }
  return group.settings.find((s) => s.key === key) || null;
}
