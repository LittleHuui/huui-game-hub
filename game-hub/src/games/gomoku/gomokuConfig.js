import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { setGameDifficulties } from '../../services/gameDifficultyService.js';

export const GOMOKU_CODE = 'gomoku';
export const GOMOKU_MODE = 'classic';

/**
 * @returns {object}
 */
function seedGame() {
  return getSeedGameConfig(GOMOKU_CODE, GAME_SEED_CONFIG) || {};
}

setGameDifficulties(GOMOKU_CODE, seedGame().difficulties || []);

export let GOMOKU_CONFIG = {
  gameCode: GOMOKU_CODE,
  gameName: '五子棋',
  featureFlags: seedGame().config?.featureFlags || {},
  propRules: seedGame().propRules || []
};

/**
 * 应用平台基础配置种子。
 * @param {object} raw
 * @returns {object}
 */
export function applyGomokuConfig(raw) {
  const seedConfig = seedGame();
  const game = raw && typeof raw === 'object' ? raw : seedConfig;
  const base = {
    ...seedConfig,
    ...game,
    config: {
      ...(seedConfig.config || {}),
      ...(game.config || {})
    },
    difficulties:
      Array.isArray(game.difficulties) && game.difficulties.length
        ? game.difficulties
        : seedConfig.difficulties,
    propRules:
      Array.isArray(game.propRules) && game.propRules.length ? game.propRules : seedConfig.propRules
  };
  const difficulties = Array.isArray(base.difficulties) ? base.difficulties : [];
  setGameDifficulties(GOMOKU_CODE, difficulties);
  GOMOKU_CONFIG = {
    gameCode: base.gameCode || GOMOKU_CODE,
    gameName: base.gameName || '五子棋',
    featureFlags: base.config?.featureFlags || {},
    propRules: base.propRules || []
  };
  return GOMOKU_CONFIG;
}

/**
 * 从平台种子根解析五子棋配置条目。
 * @param {object} seedRoot
 * @returns {object|null}
 */
export function resolveGomokuSeed(seedRoot) {
  return getSeedGameConfig(GOMOKU_CODE, seedRoot);
}
