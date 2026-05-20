import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';

/** @type {Record<string, object[]>} */
const difficultiesCache = {};

/**
 * 从种子配置查找游戏条目。
 * @param {string} gameCode
 * @returns {object|null}
 */
function getSeedGame(gameCode) {
  const games = Array.isArray(GAME_SEED_CONFIG?.games) ? GAME_SEED_CONFIG.games : [];
  return games.find((g) => g && g.gameCode === gameCode) || null;
}

/**
 * 规整单条难度配置。
 * @param {object} raw
 * @returns {object|null}
 */
function normalizeDifficulty(raw) {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const difficultyCode = raw.difficultyCode;
  if (!difficultyCode) {
    return null;
  }
  return {
    difficultyCode,
    difficultyName: raw.difficultyName || difficultyCode,
    enabled: raw.enabled === true,
    sortNo: raw.sortNo != null ? Number(raw.sortNo) : 999,
    config: raw.config && typeof raw.config === 'object' ? raw.config : {}
  };
}

/**
 * 过滤 enabled=true 并按 sortNo 升序。
 * @param {object[]} list
 * @returns {object[]}
 */
function filterAndSort(list) {
  return (Array.isArray(list) ? list : [])
    .map(normalizeDifficulty)
    .filter((d) => d && d.enabled === true)
    .sort((a, b) => a.sortNo - b.sortNo);
}

/**
 * 写入当前生效的难度列表（种子或服务端配置加载后调用）。
 * @param {string} gameCode
 * @param {object[]} difficulties
 */
export function setGameDifficulties(gameCode, difficulties) {
  if (!gameCode) {
    return;
  }
  difficultiesCache[gameCode] = filterAndSort(difficulties);
}

/**
 * 清除缓存，回退到种子配置。
 * @param {string} [gameCode]
 */
export function clearGameDifficulties(gameCode) {
  if (gameCode) {
    delete difficultiesCache[gameCode];
    return;
  }
  for (const key of Object.keys(difficultiesCache)) {
    delete difficultiesCache[key];
  }
}

/**
 * 解析当前游戏的难度列表（优先缓存，否则种子）。
 * @param {string} gameCode
 * @returns {object[]}
 */
function resolveDifficulties(gameCode) {
  const cached = difficultiesCache[gameCode];
  if (Array.isArray(cached) && cached.length > 0) {
    return cached.map((d) => ({ ...d, config: { ...d.config } }));
  }
  const game = getSeedGame(gameCode);
  return filterAndSort(game?.difficulties).map((d) => ({ ...d, config: { ...d.config } }));
}

/**
 * 获取已启用且按 sortNo 排序的难度列表。
 * @param {string} gameCode
 * @returns {{ difficultyCode: string; difficultyName: string; enabled: boolean; sortNo: number; config: object }[]}
 */
export function getEnabledDifficulties(gameCode) {
  return resolveDifficulties(gameCode);
}

/**
 * 默认难度：启用列表中 sortNo 最小项。
 * @param {string} gameCode
 * @returns {string}
 */
export function getDefaultDifficultyCode(gameCode) {
  return getEnabledDifficulties(gameCode)[0]?.difficultyCode || '';
}

/**
 * 难度展示名。
 * @param {string} gameCode
 * @param {string} difficultyCode
 * @returns {string}
 */
export function getDifficultyName(gameCode, difficultyCode) {
  if (!difficultyCode) {
    return '未知难度';
  }
  const found = getEnabledDifficulties(gameCode).find((d) => d.difficultyCode === difficultyCode);
  if (found) {
    return found.difficultyName;
  }
  const game = getSeedGame(gameCode);
  const all = Array.isArray(game?.difficulties) ? game.difficulties : [];
  const raw = all.find((d) => d?.difficultyCode === difficultyCode);
  return raw?.difficultyName || difficultyCode;
}

/**
 * 难度选择器选项（value / label）。
 * @param {string} gameCode
 * @returns {{ value: string; label: string }[]}
 */
export function toDifficultySelectorOptions(gameCode) {
  return getEnabledDifficulties(gameCode).map((d) => ({
    value: d.difficultyCode,
    label: d.difficultyName
  }));
}

/**
 * 当前难度是否在启用列表中。
 * @param {string} gameCode
 * @param {string} difficultyCode
 * @returns {boolean}
 */
export function isDifficultyEnabled(gameCode, difficultyCode) {
  return getEnabledDifficulties(gameCode).some((d) => d.difficultyCode === difficultyCode);
}
