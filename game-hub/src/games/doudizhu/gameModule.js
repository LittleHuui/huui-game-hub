import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { applyDoudizhuConfig } from './doudizhuConfig.js';

const GAME_CODE = 'doudizhu';

/**
 * 从平台种子根解析斗地主配置条目。
 * @param {object} seedRoot
 * @returns {object|null}
 */
function resolveDoudizhuSeed(seedRoot) {
  return getSeedGameConfig(GAME_CODE, seedRoot);
}

export const doudizhuGameModule = {
  gameCode: GAME_CODE,
  implemented: true,
  roomConfigFieldOrder: ['enableLaizi', 'allowSingleAttachment'],
  route: {
    path: 'games/doudizhu/play/:roomId',
    name: 'doudizhu-play',
    title: '斗地主对战'
  },
  capabilities: {
    leaderboard: false,
    inventory: false,
    shop: false,
    offline: false,
    onlineBattle: true
  },
  seedProvider: () => GAME_SEED_CONFIG,
  configHandler: {
    resolveSeed: resolveDoudizhuSeed,
    applySeed: applyDoudizhuConfig,
    applyRemote: applyDoudizhuConfig
  },
  displayMetadata: {
    logo: '🃏',
    name: '斗地主',
    subName: 'Doudizhu',
    gameCategory: 'strategy-turn',
    runtimeType: 'strategy-turn-multiplayer',
    viewTemplate: 'strategy-turn-multiplayer',
    modes: ['classic']
  },
  playPageLoader: () => import('./DoudizhuPlayPage.vue')
};
