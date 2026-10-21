import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { getEnabledDifficulties, setGameDifficulties } from '../../services/gameDifficultyService.js';

export const DOUDIZHU_CODE = 'doudizhu';
export const DOUDIZHU_MODE = 'classic';

/** @type {object|null} */
let ruleDefinitionSnapshot = null;

/**
 * @returns {object}
 */
function seedGame() {
  return getSeedGameConfig(DOUDIZHU_CODE, GAME_SEED_CONFIG) || {};
}

setGameDifficulties(DOUDIZHU_CODE, seedGame().difficulties || []);

export let DOUDIZHU_CONFIG = {
  gameCode: DOUDIZHU_CODE,
  gameName: '斗地主',
  featureFlags: seedGame().config?.featureFlags || {},
  propRules: seedGame().propRules || []
};

/**
 * 应用平台基础配置种子。
 * @param {object} raw
 * @returns {object}
 */
export function applyDoudizhuConfig(raw) {
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
  setGameDifficulties(DOUDIZHU_CODE, difficulties);
  DOUDIZHU_CONFIG = {
    gameCode: base.gameCode || DOUDIZHU_CODE,
    gameName: base.gameName || '斗地主',
    featureFlags: base.config?.featureFlags || {},
    propRules: base.propRules || []
  };
  return DOUDIZHU_CONFIG;
}

/**
 * 写入在线规则定义快照。
 * @param {object} raw
 * @returns {object|null}
 */
export function applyDoudizhuRuleDefinition(raw) {
  ruleDefinitionSnapshot = raw && typeof raw === 'object' ? { ...raw } : null;
  return ruleDefinitionSnapshot;
}

/**
 * 读取当前规则定义快照。
 * @returns {object|null}
 */
export function getDoudizhuRuleDefinition() {
  return ruleDefinitionSnapshot;
}

/**
 * 默认难度编码（供 activateGame 使用）。
 * @returns {string}
 */
export function getDefaultDoudizhuDifficultyCode() {
  const first = getEnabledDifficulties(DOUDIZHU_CODE)[0] || {};
  return first.difficultyCode || 'classic';
}
