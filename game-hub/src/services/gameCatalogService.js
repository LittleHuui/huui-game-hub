import { GAME_SEED_CONFIG } from '../constants/gameSeedConfig.js';
import { GAME_REGISTRY } from '../constants/gameRegistry.js';
import { usePlatformStore } from '../stores/platformStore.js';
import { canFetchRemote } from './remoteGate.js';

/** 当前已有前端玩法实现的游戏。未实现游戏仍可进入占位页。 */
const IMPLEMENTED_GAME_CODES = new Set(['minesweeper', 'match3']);

/**
 * 将种子或服务端游戏条目转为顶栏展示结构。
 * @param {object} raw
 * @returns {object|null}
 */
function mapCatalogEntry(raw) {
  if (!raw || !raw.gameCode) {
    return null;
  }
  const code = raw.gameCode;
  const reg = GAME_REGISTRY[code] || {};
  return {
    code,
    name: raw.gameName || reg.name || code,
    subName: raw.gameSubName || reg.subName || '',
    logo: reg.logo || '🎮',
    supportOnline: raw.supportOnline ?? reg.supportOnline ?? false,
    enabled: raw.enabled !== false,
    sortNo: raw.sortNo != null ? Number(raw.sortNo) : 999,
    playable: raw.enabled !== false,
    implemented: IMPLEMENTED_GAME_CODES.has(code),
    capabilities: reg.capabilities || {}
  };
}

/**
 * 过滤 enabled 并按 sortNo 升序。
 * @param {object[]} games
 * @returns {object[]}
 */
export function normalizeCatalogGames(games) {
  return (Array.isArray(games) ? games : [])
    .map(mapCatalogEntry)
    .filter((g) => g && g.enabled)
    .sort((a, b) => a.sortNo - b.sortNo);
}

/**
 * 解析当前应使用的游戏列表原始数据。
 * @returns {object[]}
 */
function resolveRawGames() {
  const platform = usePlatformStore();
  const bootGames = platform.bootGames;
  if (canFetchRemote() && Array.isArray(bootGames) && bootGames.length > 0) {
    return bootGames;
  }
  return GAME_SEED_CONFIG.games;
}

/**
 * 将游戏目录写入 platform store。
 * @param {object[]} games
 */
export function applyGameCatalog(games) {
  const platform = usePlatformStore();
  const list = normalizeCatalogGames(games);
  platform.setGameCatalog(list);
  if (list.length > 0 && !list.some((g) => g.code === platform.currentGameCode)) {
    const firstPlayable = list.find((g) => g.playable && g.implemented) || list.find((g) => g.playable) || list[0];
    platform.setCurrentGame(firstPlayable.code);
  }
}

/**
 * 按当前数据模式加载游戏目录。
 * @returns {Promise<object[]>}
 */
export async function loadGameCatalog() {
  const raw = resolveRawGames();
  applyGameCatalog(raw);
  return usePlatformStore().gameCatalog;
}
