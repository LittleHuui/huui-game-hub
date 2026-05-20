import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';
import { getEnabledDifficulties, setGameDifficulties } from '../../services/gameDifficultyService.js';

const MATCH3 = 'match3';
const DEFAULT_CLIENT = 'pc';

/** Match3 道具 propCode（仅游戏层使用） */
export const MATCH3_PROP = {
  SHUFFLE: 'match3_shuffle',
  BOMB: 'match3_bomb'
};

/**
 * 取当前启用难度中的首项并展开 config。
 * @param {string} gameCode
 * @returns {object}
 */
function firstEnabledDifficultyConfig(gameCode) {
  const first = getEnabledDifficulties(gameCode)[0] || {};
  return {
    difficultyCode: first.difficultyCode || '',
    difficultyName: first.difficultyName || '',
    ...(first.config || {})
  };
}

/**
 * @param {object} game
 * @returns {object}
 */
function firstClientConfig(game) {
  const list = Array.isArray(game?.clientConfigs) ? game.clientConfigs : [];
  const pc = list.find((c) => c?.clientType === DEFAULT_CLIENT && c.enabled !== false) || list[0] || {};
  return {
    difficultyCode: pc.difficultyCode || getEnabledDifficulties(MATCH3)[0]?.difficultyCode || '',
    clientType: pc.clientType || DEFAULT_CLIENT,
    enabled: pc.enabled !== false,
    ...(pc.config || {})
  };
}

/**
 * @returns {object}
 */
function seedGame() {
  return getSeedGameConfig(MATCH3, GAME_SEED_CONFIG) || {};
}

setGameDifficulties(MATCH3, seedGame().difficulties);

export let MATCH3_GAME_CONFIG = {
  gameCode: MATCH3,
  gameName: '幻彩碰撞',
  featureFlags: {},
  difficulty: firstEnabledDifficultyConfig(MATCH3),
  client: firstClientConfig(seedGame()),
  propRules: seedGame().propRules || []
};

/**
 * 将远端或种子配置规整为 Match3 前端可直接消费的结构。
 * @param {object} raw
 * @returns {object}
 */
export function normalizeMatch3Config(raw) {
  const fallback = seedGame();
  const game = raw && typeof raw === 'object' ? raw : fallback;
  const base = {
    ...fallback,
    ...game,
    config: {
      ...(fallback.config || {}),
      ...(game.config || {})
    },
    difficulties: Array.isArray(game.difficulties) && game.difficulties.length ? game.difficulties : fallback.difficulties,
    clientConfigs:
      Array.isArray(game.clientConfigs) && game.clientConfigs.length ? game.clientConfigs : fallback.clientConfigs,
    propRules: Array.isArray(game.propRules) && game.propRules.length ? game.propRules : fallback.propRules
  };
  const fallbackDifficulties = Array.isArray(fallback.difficulties) ? fallback.difficulties : [];
  const remoteDifficulties = Array.isArray(base.difficulties) ? base.difficulties : [];
  const seedFirst = fallbackDifficulties[0] || {};
  const remoteFirst =
    remoteDifficulties.find((d) => d?.enabled !== false) || remoteDifficulties[0] || {};
  const mergedFirst = {
    ...seedFirst,
    ...remoteFirst,
    config: mergeDifficultyConfig(seedFirst.config, remoteFirst.config)
  };
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
      : [{ ...mergedFirst }];
  setGameDifficulties(MATCH3, mergedDifficulties);
  const firstDifficulty = mergedDifficulties.find((d) => d?.enabled !== false) || mergedDifficulties[0] || {};
  return {
    gameCode: base.gameCode || MATCH3,
    gameName: base.gameName || '幻彩碰撞',
    featureFlags: base.config?.featureFlags || {},
    difficulty: {
      difficultyCode: firstDifficulty.difficultyCode || '',
      difficultyName: firstDifficulty.difficultyName || '',
      ...(firstDifficulty.config || {})
    },
    client: firstClientConfig(base),
    propRules: base.propRules || []
  };
}

/**
 * 应用 Match3 配置。
 * @param {object} raw
 * @returns {object}
 */
export function applyMatch3Config(raw) {
  MATCH3_GAME_CONFIG = normalizeMatch3Config(raw);
  return MATCH3_GAME_CONFIG;
}

/**
 * 获取当前 Match3 难度配置。
 * @returns {object}
 */
export function getMatch3DifficultyConfig() {
  return MATCH3_GAME_CONFIG.difficulty;
}

/**
 * 获取当前 Match3 PC 客户端配置。
 * @returns {object}
 */
export function getMatch3ClientConfig() {
  return MATCH3_GAME_CONFIG.client;
}

/**
 * 获取指定道具规则。
 * @param {string} propCode
 * @returns {object|null}
 */
export function getMatch3PropRule(propCode) {
  return MATCH3_GAME_CONFIG.propRules.find((r) => r?.propCode === propCode) || null;
}

/**
 * 判断 propUseLimits 是否为有效配置（仅非空数组）。
 * @param {unknown} limits
 * @returns {boolean}
 */
function hasUsablePropUseLimits(limits) {
  return Array.isArray(limits) && limits.length > 0;
}

/**
 * 从 propUseLimits 数组 `{ propCode, maxUse }[]` 解析单道具上限。
 * @param {unknown} limits
 * @param {string} propCode
 * @returns {number|null}
 */
function propUseLimitsLookup(limits, propCode) {
  if (!Array.isArray(limits) || propCode == null || propCode === '') {
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
 * 合并模式配置：远端覆盖种子，但保留种子中的 propUseLimits（远端未配置时）。
 * @param {object} seedModes
 * @param {object} remoteModes
 * @returns {object}
 */
function mergeModes(seedModes, remoteModes) {
  const seed = seedModes && typeof seedModes === 'object' ? seedModes : {};
  const remote = remoteModes && typeof remoteModes === 'object' ? remoteModes : {};
  const keys = new Set([...Object.keys(seed), ...Object.keys(remote)]);
  const merged = {};
  for (const key of keys) {
    const seedMode = seed[key] || {};
    const remoteMode = remote[key] || {};
    merged[key] = { ...seedMode, ...remoteMode };
    if (hasUsablePropUseLimits(remoteMode.propUseLimits)) {
      merged[key].propUseLimits = remoteMode.propUseLimits;
    } else if (hasUsablePropUseLimits(seedMode.propUseLimits)) {
      merged[key].propUseLimits = seedMode.propUseLimits;
    } else {
      delete merged[key].propUseLimits;
    }
  }
  return merged;
}

/**
 * 合并难度玩法配置。
 * @param {object} seedConfig
 * @param {object} remoteConfig
 * @returns {object}
 */
function mergeDifficultyConfig(seedConfig, remoteConfig) {
  const seed = seedConfig && typeof seedConfig === 'object' ? seedConfig : {};
  const remote = remoteConfig && typeof remoteConfig === 'object' ? remoteConfig : {};
  return {
    ...seed,
    ...remote,
    modes: mergeModes(seed.modes, remote.modes)
  };
}

/**
 * 读取指定模式下单道具的本局使用上限。
 * @param {string} mode
 * @param {string} propCode
 * @returns {number|null}
 */
export function getMatch3ModePropLimit(mode, propCode) {
  const modes = getMatch3DifficultyConfig()?.modes;
  if (!modes || typeof modes !== 'object') {
    return null;
  }
  const limits = modes[mode]?.propUseLimits;
  return propUseLimitsLookup(limits, propCode);
}
