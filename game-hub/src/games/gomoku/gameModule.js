import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { applyGomokuConfig, resolveGomokuSeed } from './gomokuConfig.js';

export const gomokuGameModule = {
  gameCode: 'gomoku',
  implemented: true,
  route: { path: 'games/gomoku/play/:roomId', name: 'gomoku-play', title: '五子棋对战' },
  capabilities: {
    leaderboard: false,
    inventory: false,
    shop: false,
    offline: false,
    onlineBattle: true
  },
  seedProvider: () => GAME_SEED_CONFIG,
  configHandler: {
    resolveSeed: resolveGomokuSeed,
    applySeed: applyGomokuConfig,
    applyRemote: applyGomokuConfig
  },
  displayMetadata: {
    logo: '⚫',
    name: '五子棋',
    subName: 'Gomoku',
    gameCategory: 'strategy-turn',
    runtimeType: 'strategy-turn-multiplayer',
    viewTemplate: 'strategy-turn-multiplayer',
    modes: ['classic']
  },
  playPageLoader: () => import('./GomokuPlayPage.vue')
};
