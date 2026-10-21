import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import {
  applyMinesweeperServerConfig,
  mapGameSeedToMinesweeperConfig
} from './minesweeperConfigMapper.js';

export const minesweeperGameModule = {
  gameCode: 'minesweeper',
  implemented: true,
  route: { path: 'minesweeper', name: 'minesweeper', title: '雷区突围' },
  capabilities: {
    leaderboard: true,
    inventory: true,
    shop: true,
    offline: true,
    onlineBattle: false
  },
  seedProvider: () => GAME_SEED_CONFIG,
  configHandler: {
    resolveSeed: mapGameSeedToMinesweeperConfig,
    applySeed: applyMinesweeperServerConfig,
    applyRemote: applyMinesweeperServerConfig
  },
  displayMetadata: {
    logo: '💣',
    name: '雷区突围',
    subName: 'Mine Rush',
    gameCategory: 'light-single',
    runtimeType: 'light-single',
    viewTemplate: 'light-single',
    modes: ['single']
  },
  playPageLoader: () => import('./MinesweeperPage.vue')
};
