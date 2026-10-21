import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { applyUnoConfig } from './unoConfig.js';

const GAME_CODE = 'uno';

/**
 * 从平台种子根解析 UNO 配置条目。
 * @param {object} seedRoot
 * @returns {object|null}
 */
function resolveUnoSeed(seedRoot) {
  return getSeedGameConfig(GAME_CODE, seedRoot);
}

export const unoGameModule = {
  gameCode: GAME_CODE,
  implemented: true,
  roomConfigFieldOrder: ['finishMode', 'remainingRealPlayerCountToEnd', 'appendDeckSetWhenDrawPileEmpty', 'appendDeckSetCount'],
  route: { path: 'games/uno/play/:roomId', name: 'uno-play', title: 'UNO 对战' },
  capabilities: {
    leaderboard: false,
    inventory: false,
    shop: false,
    offline: false,
    onlineBattle: true
  },
  seedProvider: () => GAME_SEED_CONFIG,
  configHandler: {
    resolveSeed: resolveUnoSeed,
    applySeed: applyUnoConfig,
    applyRemote: applyUnoConfig
  },
  displayMetadata: {
    logo: '🃏',
    name: 'UNO',
    subName: 'UNO',
    gameCategory: 'strategy-turn',
    runtimeType: 'strategy-turn-multiplayer',
    viewTemplate: 'strategy-turn-multiplayer',
    modes: ['classic']
  },
  playPageLoader: () => import('./UnoPlayPage.vue')
};
