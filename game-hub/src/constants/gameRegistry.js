/** 游戏注册表：集中声明各游戏的前端能力与展示元信息。 */
export const GAME_REGISTRY = {
  minesweeper: {
    code: 'minesweeper',
    logo: '💣',
    name: '雷区突围',
    subName: 'Mine Rush',
    /** 前端页面模板（不导出到 seed） */
    viewTemplate: 'light-single',
    supportOnline: false,
    modes: ['single'],
    capabilities: {
      leaderboard: true,
      inventory: true,
      shop: true,
      offline: true
    }
  },
  match3: {
    code: 'match3',
    logo: '🌈',
    name: '幻彩碰撞',
    subName: 'Color Crush',
    /** 前端页面模板（不导出到 seed） */
    viewTemplate: 'light-single',
    supportOnline: false,
    modes: ['timed', 'endless'],
    capabilities: {
      leaderboard: true,
      inventory: true,
      shop: true,
      offline: true,
      onlineBattle: false
    }
  },
  2048: {
    code: '2048',
    logo: '🔢',
    name: '数字方舟',
    subName: '2048 Ark',
    /** 前端页面模板（不导出到 seed） */
    viewTemplate: 'light-single',
    supportOnline: false,
    modes: ['classic'],
    capabilities: {
      leaderboard: true,
      inventory: true,
      shop: true,
      offline: true,
      onlineBattle: false
    }
  },
  sudoku: {
    code: 'sudoku',
    logo: '🧩',
    name: '数独',
    subName: 'Sudoku',
    viewTemplate: 'light-single',
    supportOnline: false,
    modes: ['classic'],
    capabilities: {
      leaderboard: true,
      inventory: true,
      shop: true,
      offline: true,
      onlineBattle: false
    }
  }
};

/**
 * 获取游戏注册配置。
 * @param {string} gameCode
 * @returns {object|null}
 */
export function getGameConfig(gameCode) {
  if (gameCode == null || String(gameCode).length === 0) {
    return null;
  }
  return GAME_REGISTRY[gameCode] || null;
}

/**
 * 判断游戏是否具备指定能力。
 * @param {string} gameCode
 * @param {string} capability
 * @returns {boolean}
 */
export function hasGameCapability(gameCode, capability) {
  const game = getGameConfig(gameCode);
  if (!game || !game.capabilities) {
    return false;
  }
  return game.capabilities[capability] === true;
}
