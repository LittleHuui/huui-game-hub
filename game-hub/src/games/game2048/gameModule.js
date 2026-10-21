import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { applyGame2048Config } from './game2048Config.js';

const GAME_CODE = '2048';

/**
 * 从平台种子根解析 2048 配置条目。
 * @param {object} seedRoot
 * @returns {object|null}
 */
function resolveGame2048Seed(seedRoot) {
  return getSeedGameConfig(GAME_CODE, seedRoot);
}

export const game2048Module = {
  gameCode: GAME_CODE,
  implemented: true,
  route: { path: '2048', name: '2048', title: '数字方舟' },
  capabilities: {
    leaderboard: true,
    inventory: true,
    shop: true,
    offline: true,
    onlineBattle: false
  },
  seedProvider: () => GAME_SEED_CONFIG,
  configHandler: {
    resolveSeed: resolveGame2048Seed,
    applySeed: applyGame2048Config,
    applyRemote: applyGame2048Config
  },
  displayMetadata: {
    logo: '🔢',
    name: '数字方舟',
    subName: '2048 Ark',
    gameCategory: 'light-single',
    runtimeType: 'light-single',
    viewTemplate: 'light-single',
    modes: ['classic']
  },
  playPageLoader: () => import('./Game2048Page.vue')
};
