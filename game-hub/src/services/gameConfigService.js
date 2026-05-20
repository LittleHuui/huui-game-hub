import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';
import * as gameConfigRepository from '../repositories/gameConfigRepository.js';
import {
  applyMinesweeperServerConfig,
  getSeedGameConfig,
  mapGameSeedToMinesweeperConfig
} from '../mappers/gameConfigMapper.js';
import { applyMatch3Config } from '../games/match3/match3Config.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { canFetchRemote } from './remoteGate.js';

const MINESWEEPER = 'minesweeper';
const MATCH3 = 'match3';

/**
 * @typedef {object} GameConfigHandler
 * @property {() => Promise<void>} loadRemote
 * @property {() => void} applySeed
 */

/** @type {Record<string, GameConfigHandler>} */
const GAME_CONFIG_HANDLERS = {
  [MINESWEEPER]: {
    async loadRemote() {
      try {
        const data = await gameConfigRepository.fetchGameConfig(MINESWEEPER);
        applyMinesweeperServerConfig(data);
      } catch {
        applyMinesweeperSeedConfig();
      }
    },
    applySeed: applyMinesweeperSeedConfig
  },
  [MATCH3]: {
    async loadRemote() {
      try {
        const data = await gameConfigRepository.fetchGameConfig(MATCH3);
        applyMatch3Config(data);
      } catch {
        applyMatch3Config(getSeedGameConfig(MATCH3, GAME_SEED_CONFIG));
      }
    },
    applySeed() {
      applyMatch3Config(getSeedGameConfig(MATCH3, GAME_SEED_CONFIG));
    }
  }
};

/**
 * 应用种子配置到扫雷玩法常量。
 */
function applyMinesweeperSeedConfig() {
  const mapped = mapGameSeedToMinesweeperConfig(GAME_SEED_CONFIG);
  applyMinesweeperServerConfig(mapped);
}

/**
 * 是否应从远端拉取游戏配置。
 * @param {{ networkMode?: string }} platform
 * @returns {boolean}
 */
function shouldLoadRemoteConfig(platform) {
  return (
    canFetchRemote() &&
    (platform.networkMode === 'online' || platform.networkMode === 'degraded')
  );
}

/**
 * 按 gameCode 加载并应用游戏配置（在线优先，失败或离线回退种子）。
 * @param {string} gameCode
 * @returns {Promise<void>}
 */
export async function loadGameConfig(gameCode) {
  if (gameCode == null || String(gameCode).length === 0) {
    return;
  }
  const handler = GAME_CONFIG_HANDLERS[gameCode];
  if (!handler) {
    return;
  }
  const platform = usePlatformStore();
  if (shouldLoadRemoteConfig(platform)) {
    await handler.loadRemote();
    return;
  }
  handler.applySeed();
}
