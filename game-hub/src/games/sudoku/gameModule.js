import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { applySudokuConfig } from './sudokuConfig.js';

const GAME_CODE = 'sudoku';

/**
 * 从平台种子根解析数独配置条目。
 * @param {object} seedRoot
 * @returns {object|null}
 */
function resolveSudokuSeed(seedRoot) {
  return getSeedGameConfig(GAME_CODE, seedRoot);
}

export const sudokuGameModule = {
  gameCode: GAME_CODE,
  implemented: true,
  route: { path: 'sudoku', name: 'sudoku', title: '数独' },
  capabilities: {
    leaderboard: true,
    inventory: true,
    shop: true,
    offline: true,
    onlineBattle: false
  },
  seedProvider: () => GAME_SEED_CONFIG,
  configHandler: {
    resolveSeed: resolveSudokuSeed,
    applySeed: applySudokuConfig,
    applyRemote: applySudokuConfig
  },
  displayMetadata: {
    logo: '🧩',
    name: '数独',
    subName: 'Sudoku',
    gameCategory: 'light-single',
    runtimeType: 'light-single',
    viewTemplate: 'light-single',
    modes: ['classic']
  },
  playPageLoader: () => import('./SudokuPage.vue')
};
