import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { getEnabledDifficulties, setGameDifficulties } from '../../services/gameDifficultyService.js';

export const GAME2048_CODE = '2048';
export const GAME2048_MODE = 'classic';

/** 2048 道具 propCode */
export const GAME2048_PROP = {
  CLEAR_CELL: 'game2048_clear_cell'
};

/**
 * @param {object} game
 * @returns {object}
 */
function firstEnabledDifficultyConfig(game) {
  const first = getEnabledDifficulties(GAME2048_CODE)[0] || {};
  return {
    difficultyCode: first.difficultyCode || 'standard',
    difficultyName: first.difficultyName || '标准',
    ...(first.config || {})
  };
}

/**
 * @returns {object}
 */
function seedGame() {
  return getSeedGameConfig(GAME2048_CODE, GAME_SEED_CONFIG) || {};
}

setGameDifficulties(GAME2048_CODE, seedGame().difficulties);

export let GAME2048_CONFIG = {
  gameCode: GAME2048_CODE,
  gameName: '数字方舟',
  featureFlags: {},
  difficulty: firstEnabledDifficultyConfig(seedGame()),
  propRules: seedGame().propRules || []
};

/**
 * 合并难度玩法配置。
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
 * 规整 2048 配置。
 * @param {object} raw
 * @returns {object}
 */
export function normalizeGame2048Config(raw) {
  const fallback = seedGame();
  const game = raw && typeof raw === 'object' ? raw : fallback;
  const base = {
    ...fallback,
    ...game,
    config: {
      ...(fallback.config || {}),
      ...(game.config || {})
    },
    difficulties:
      Array.isArray(game.difficulties) && game.difficulties.length ? game.difficulties : fallback.difficulties,
    propRules: Array.isArray(game.propRules) && game.propRules.length ? game.propRules : fallback.propRules
  };
  const fallbackDifficulties = Array.isArray(fallback.difficulties) ? fallback.difficulties : [];
  const remoteDifficulties = Array.isArray(base.difficulties) ? base.difficulties : [];
  const seedFirst = fallbackDifficulties[0] || {};
  const mergedDifficulties =
    remoteDifficulties.length > 0
      ? remoteDifficulties.map((d, index) => {
          const seedDiff = fallbackDifficulties[index] || seedFirst;
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
  setGameDifficulties(GAME2048_CODE, mergedDifficulties);
  const firstDifficulty = mergedDifficulties.find((d) => d?.enabled !== false) || mergedDifficulties[0] || {};
  return {
    gameCode: base.gameCode || GAME2048_CODE,
    gameName: base.gameName || '数字方舟',
    featureFlags: base.config?.featureFlags || {},
    difficulty: {
      difficultyCode: firstDifficulty.difficultyCode || 'standard',
      difficultyName: firstDifficulty.difficultyName || '标准',
      ...(firstDifficulty.config || {})
    },
    propRules: base.propRules || []
  };
}

/**
 * 应用 2048 配置。
 * @param {object} raw
 * @returns {object}
 */
export function applyGame2048Config(raw) {
  GAME2048_CONFIG = normalizeGame2048Config(raw);
  return GAME2048_CONFIG;
}

/**
 * 获取当前难度配置。
 * @returns {object}
 */
export function getGame2048DifficultyConfig() {
  return GAME2048_CONFIG.difficulty;
}

/**
 * 获取道具规则。
 * @param {string} propCode
 * @returns {object|null}
 */
export function getGame2048PropRule(propCode) {
  return GAME2048_CONFIG.propRules.find((r) => r?.propCode === propCode) || null;
}

/**
 * 从 propUseLimits 解析单道具上限。
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
 * 读取 classic 模式下单道具本局上限。
 * @param {string} propCode
 * @returns {number|null}
 */
export function getGame2048ModePropLimit(propCode) {
  const limits = getGame2048DifficultyConfig()?.modes?.[GAME2048_MODE]?.propUseLimits;
  return propUseLimitsLookup(limits, propCode);
}
