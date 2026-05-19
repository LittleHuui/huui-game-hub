import { GAME_SEED_CONFIG } from '../../constants/gameSeedConfig.js';
import { getSeedGameConfig } from '../../mappers/gameConfigMapper.js';

const MATCH3 = 'match3';
const DEFAULT_DIFFICULTY = 'normal';
const DEFAULT_CLIENT = 'pc';

/**
 * @param {object} game
 * @returns {object}
 */
function firstDifficultyConfig(game) {
  const list = Array.isArray(game?.difficulties) ? game.difficulties : [];
  const normal = list.find((d) => d?.difficultyCode === DEFAULT_DIFFICULTY) || list[0] || {};
  return {
    difficultyCode: normal.difficultyCode || DEFAULT_DIFFICULTY,
    difficultyName: normal.difficultyName || '普通',
    ...(normal.config || {})
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
    difficultyCode: pc.difficultyCode || DEFAULT_DIFFICULTY,
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

export let MATCH3_GAME_CONFIG = {
  gameCode: MATCH3,
  gameName: '幻彩碰撞',
  featureFlags: {},
  difficulty: firstDifficultyConfig(seedGame()),
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
  return {
    gameCode: base.gameCode || MATCH3,
    gameName: base.gameName || '幻彩碰撞',
    featureFlags: base.config?.featureFlags || {},
    difficulty: firstDifficultyConfig(base),
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
