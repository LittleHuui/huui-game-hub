import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';
import * as gameConfigRepository from '../repositories/gameConfigRepository.js';
import {
  applyMinesweeperServerConfig,
  getSeedGameConfig,
  mapGameSeedToMinesweeperConfig
} from '../mappers/gameConfigMapper.js';
import { applyMatch3Config } from '../games/match3/match3Config.js';
import { canFetchRemote } from './remoteGate.js';

const MINESWEEPER = 'minesweeper';
const MATCH3 = 'match3';

/**
 * 应用种子配置到扫雷玩法常量。
 */
function applyMinesweeperSeedConfig() {
  const mapped = mapGameSeedToMinesweeperConfig(GAME_SEED_CONFIG);
  applyMinesweeperServerConfig(mapped);
}

/**
 * 本地 / 离线：仅使用种子配置。
 */
function loadMinesweeperFromSeed() {
  applyMinesweeperSeedConfig();
}

/**
 * @param {string} gameCode
 * @returns {object|null}
 */
function loadGameFromSeed(gameCode) {
  return getSeedGameConfig(gameCode, GAME_SEED_CONFIG);
}

/**
 * 拉取服务端扫雷配置并应用；失败时回退种子配置。
 * @returns {Promise<void>}
 */
export async function loadMinesweeperConfig() {
  try {
    const data = await gameConfigRepository.fetchGameConfig(MINESWEEPER);
    applyMinesweeperServerConfig(data);
  } catch {
    applyMinesweeperSeedConfig();
  }
}

/**
 * 按网络模式决定使用服务端配置或种子配置。
 * @param {{ networkMode?: string }} [platform]
 * @returns {Promise<void>}
 */
export async function loadMinesweeperIfOnline(platform) {
  if (canFetchRemote() && (platform?.networkMode === 'online' || platform?.networkMode === 'degraded')) {
    await loadMinesweeperConfig();
    return;
  }
  loadMinesweeperFromSeed();
}

/**
 * 加载并应用 Match3 配置，在线失败时回退种子配置。
 * @returns {Promise<void>}
 */
export async function loadMatch3Config() {
  try {
    const data = await gameConfigRepository.fetchGameConfig(MATCH3);
    applyMatch3Config(data);
  } catch {
    applyMatch3Config(loadGameFromSeed(MATCH3));
  }
}

/**
 * 按网络模式决定使用远端或种子 Match3 配置。
 * @param {{ networkMode?: string }} [platform]
 * @returns {Promise<void>}
 */
export async function loadMatch3IfOnline(platform) {
  if (canFetchRemote() && (platform?.networkMode === 'online' || platform?.networkMode === 'degraded')) {
    await loadMatch3Config();
    return;
  }
  applyMatch3Config(loadGameFromSeed(MATCH3));
}
