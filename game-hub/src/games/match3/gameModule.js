import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { applyMatch3Config } from './match3Config.js';

const GAME_CODE = 'match3';

/**
 * 从平台种子根解析 Match3 配置条目。
 * @param {object} seedRoot
 * @returns {object|null}
 */
function resolveMatch3Seed(seedRoot) {
  return getSeedGameConfig(GAME_CODE, seedRoot);
}

export const match3GameModule = {
  gameCode: GAME_CODE,
  implemented: true,
  route: { path: 'match3', name: 'match3', title: '幻彩碰撞' },
  capabilities: {
    leaderboard: true,
    inventory: true,
    shop: true,
    offline: true,
    onlineBattle: false
  },
  seedProvider: () => GAME_SEED_CONFIG,
  configHandler: {
    resolveSeed: resolveMatch3Seed,
    applySeed: applyMatch3Config,
    applyRemote: applyMatch3Config
  },
  displayMetadata: {
    logo: '🌈',
    name: '幻彩碰撞',
    subName: 'Color Crush',
    gameCategory: 'light-single',
    runtimeType: 'light-single',
    viewTemplate: 'light-single',
    modes: ['timed', 'endless']
  },
  playPageLoader: () => import('./Match3Page.vue')
};
