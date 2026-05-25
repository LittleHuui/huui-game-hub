import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { getEnabledDifficulties, setGameDifficulties } from '../../services/gameDifficultyService.js';

export const SUDOKU_CODE = 'sudoku';
export const SUDOKU_MODE = 'classic';

/** 数独道具 propCode */
export const SUDOKU_PROP = {
  HINT: 'sudoku_hint_card'
};

/** @type {Record<string, number>} */
export const SUDOKU_GIVENS_BY_DIFFICULTY = {
  easy: 40,
  normal: 34,
  hard: 28,
  expert: 24
};

/**
 * @param {object} game
 * @returns {object}
 */
function firstEnabledDifficultyConfig(game) {
  const first = getEnabledDifficulties(SUDOKU_CODE)[0] || {};
  return {
    difficultyCode: first.difficultyCode || 'easy',
    difficultyName: first.difficultyName || '简单',
    ...(first.config || {})
  };
}

/**
 * @returns {object}
 */
function seedGame() {
  return getSeedGameConfig(SUDOKU_CODE, GAME_SEED_CONFIG) || {};
}

setGameDifficulties(SUDOKU_CODE, seedGame().difficulties);

export let SUDOKU_CONFIG = {
  gameCode: SUDOKU_CODE,
  gameName: '数独',
  featureFlags: {},
  difficulty: firstEnabledDifficultyConfig(seedGame()),
  propRules: seedGame().propRules || []
};

/**
 * @param {object} seedConfig
 * @param {object} remoteConfig
 * @returns {object}
 */
function mergeDifficultyConfig(seedConfig, remoteConfig) {
  const seed = seedConfig && typeof seedConfig === 'object' ? seedConfig : {};
  const remote = remoteConfig && typeof remoteConfig === 'object' ? remoteConfig : {};
  const seedModes = seed.modes && typeof seed.modes === 'object' ? seed.modes : {};
  const remoteModes = remote.modes && typeof remote.modes === 'object' ? remote.modes : {};
  const keys = new Set([...Object.keys(seedModes), ...Object.keys(remoteModes)]);
  const modes = {};
  for (const key of keys) {
    const seedMode = seedModes[key] || {};
    const remoteMode = remoteModes[key] || {};
    modes[key] = { ...seedMode, ...remoteMode };
    if (Array.isArray(remoteMode.propUseLimits) && remoteMode.propUseLimits.length > 0) {
      modes[key].propUseLimits = remoteMode.propUseLimits;
    } else if (Array.isArray(seedMode.propUseLimits) && seedMode.propUseLimits.length > 0) {
      modes[key].propUseLimits = seedMode.propUseLimits;
    }
  }
  return { ...seed, ...remote, modes };
}

/**
 * @param {object} raw
 * @returns {object}
 */
export function normalizeSudokuConfig(raw) {
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
      Array.isArray(game.difficulties) && game.difficulties.length ? game.difficulties : seedConfig.difficulties,
    propRules: Array.isArray(game.propRules) && game.propRules.length ? game.propRules : seedConfig.propRules
  };
  const seedDifficulties = Array.isArray(seedConfig.difficulties) ? seedConfig.difficulties : [];
  const remoteDifficulties = Array.isArray(base.difficulties) ? base.difficulties : [];
  const seedFirst = seedDifficulties[0] || {};
  const mergedDifficulties =
    remoteDifficulties.length > 0
      ? remoteDifficulties.map((d, index) => {
          const seedDiff = seedDifficulties[index] || seedFirst;
          return {
            ...seedDiff,
            ...d,
            config: mergeDifficultyConfig(seedDiff.config, d.config)
          };
        })
      : [
          {
            ...seedFirst,
            config: mergeDifficultyConfig(seedFirst.config, {})
          }
        ];
  setGameDifficulties(SUDOKU_CODE, mergedDifficulties);
  const firstDifficulty = mergedDifficulties.find((d) => d?.enabled !== false) || mergedDifficulties[0] || {};
  return {
    gameCode: base.gameCode || SUDOKU_CODE,
    gameName: base.gameName || '数独',
    featureFlags: base.config?.featureFlags || {},
    difficulty: {
      difficultyCode: firstDifficulty.difficultyCode || 'easy',
      difficultyName: firstDifficulty.difficultyName || '简单',
      ...(firstDifficulty.config || {})
    },
    propRules: base.propRules || []
  };
}

/**
 * @param {object} raw
 * @returns {object}
 */
export function applySudokuConfig(raw) {
  SUDOKU_CONFIG = normalizeSudokuConfig(raw);
  return SUDOKU_CONFIG;
}

/**
 * @returns {object}
 */
export function getSudokuDifficultyConfig() {
  return SUDOKU_CONFIG.difficulty;
}

/**
 * @param {string} difficultyCode
 * @returns {number}
 */
export function getGivensCountForDifficulty(difficultyCode) {
  const list = getEnabledDifficulties(SUDOKU_CODE);
  const match = list.find((d) => d?.difficultyCode === difficultyCode);
  if (match?.config?.givensCount != null) {
    const n = Number(match.config.givensCount);
    if (Number.isFinite(n)) {
      return n;
    }
  }
  return SUDOKU_GIVENS_BY_DIFFICULTY[difficultyCode] ?? SUDOKU_GIVENS_BY_DIFFICULTY.easy;
}

/**
 * @param {string} propCode
 * @returns {object|null}
 */
export function getSudokuPropRule(propCode) {
  return SUDOKU_CONFIG.propRules.find((r) => r?.propCode === propCode) || null;
}

/**
 * @param {unknown} limits
 * @param {string} propCode
 * @returns {number|null}
 */
function propUseLimitsLookup(limits, propCode) {
  if (!Array.isArray(limits) || !propCode) {
    return null;
  }
  const entry = limits.find((row) => row && typeof row === 'object' && row.propCode === propCode);
  if (entry == null || entry.maxUse == null) {
    return null;
  }
  const parsed = Number(entry.maxUse);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * @param {string} propCode
 * @returns {number|null}
 */
export function getSudokuModePropLimit(propCode) {
  const limits = getSudokuDifficultyConfig()?.modes?.[SUDOKU_MODE]?.propUseLimits;
  return propUseLimitsLookup(limits, propCode);
}

/**
 * 完成数独时的平台积分奖励。
 * @param {number} elapsedSec
 * @param {string} [difficultyCode]
 * @returns {number}
 */
export function getSudokuWinReward(elapsedSec, difficultyCode) {
  const code = difficultyCode || getSudokuDifficultyConfig()?.difficultyCode || 'easy';
  const match = getEnabledDifficulties(SUDOKU_CODE).find((d) => d?.difficultyCode === code);
  const settlement = match?.config?.settlement || getSudokuDifficultyConfig()?.settlement || {};
  const base = Number(settlement.rewardBase) || 300;
  const perSec = Number(settlement.rewardPerSecond) || 1;
  const minReward = Number(settlement.minReward) || 50;
  return Math.max(minReward, Math.round(base - elapsedSec * perSec));
}
