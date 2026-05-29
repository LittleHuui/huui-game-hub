import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { getEnabledDifficulties, setGameDifficulties } from '../../services/gameDifficultyService.js';

export const UNO_CODE = 'uno';
export const UNO_MODE = 'classic';

/** @type {object|null} */
let ruleDefinitionSnapshot = null;

/**
 * @returns {object}
 */
function seedGame() {
  return getSeedGameConfig(UNO_CODE, GAME_SEED_CONFIG) || {};
}

setGameDifficulties(UNO_CODE, seedGame().difficulties || []);

export let UNO_CONFIG = {
  gameCode: UNO_CODE,
  gameName: 'UNO',
  featureFlags: seedGame().config?.featureFlags || {},
  propRules: seedGame().propRules || []
};

/**
 * 应用平台基础配置种子。
 * @param {object} raw
 * @returns {object}
 */
export function applyUnoConfig(raw) {
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
  setGameDifficulties(UNO_CODE, difficulties);
  UNO_CONFIG = {
    gameCode: base.gameCode || UNO_CODE,
    gameName: base.gameName || 'UNO',
    featureFlags: base.config?.featureFlags || {},
    propRules: base.propRules || []
  };
  return UNO_CONFIG;
}

/**
 * 写入在线规则定义快照。
 * @param {object} raw
 * @returns {object}
 */
export function applyUnoRuleDefinition(raw) {
  ruleDefinitionSnapshot = raw && typeof raw === 'object' ? { ...raw } : null;
  return ruleDefinitionSnapshot;
}

/**
 * 读取当前规则定义快照。
 * @returns {object|null}
 */
export function getUnoRuleDefinition() {
  return ruleDefinitionSnapshot;
}

/**
 * 默认难度编码（供 activateGame 使用）。
 * @returns {string}
 */
export function getDefaultUnoDifficultyCode() {
  const first = getEnabledDifficulties(UNO_CODE)[0] || {};
  return first.difficultyCode || 'standard';
}
