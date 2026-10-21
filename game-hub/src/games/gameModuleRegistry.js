import { minesweeperGameModule } from './minesweeper/gameModule.js';
import { match3GameModule } from './match3/gameModule.js';
import { game2048Module } from './game2048/gameModule.js';
import { sudokuGameModule } from './sudoku/gameModule.js';
import { unoGameModule } from './uno/gameModule.js';
import { gomokuGameModule } from './gomoku/gameModule.js';
import { doudizhuGameModule } from './doudizhu/gameModule.js';

const modules = [
  minesweeperGameModule,
  match3GameModule,
  game2048Module,
  sudokuGameModule,
  unoGameModule,
  gomokuGameModule,
  doudizhuGameModule
];

export const GAME_FRONTEND_MODULES = Object.freeze(
  Object.fromEntries(modules.map((module) => [module.gameCode, Object.freeze(module)]))
);

/**
 * 读取指定游戏的前端模块。
 * @param {string} gameCode
 * @returns {object|null}
 */
export function getGameFrontendModule(gameCode) {
  return GAME_FRONTEND_MODULES[String(gameCode || '').trim()] || null;
}

/**
 * 列出全部已注册前端游戏模块。
 * @returns {object[]}
 */
export function listGameFrontendModules() {
  return [...modules];
}

/**
 * 读取游戏展示元数据。
 * @param {string} gameCode
 * @returns {object|null}
 */
export function getGameDisplayMetadata(gameCode) {
  const module = getGameFrontendModule(gameCode);
  if (!module) {
    return null;
  }
  return Object.freeze({
    gameCode: module.gameCode,
    ...(module.displayMetadata || {})
  });
}

/**
 * 判断游戏是否具备指定能力。
 * @param {string} gameCode
 * @param {string} capability
 * @returns {boolean}
 */
export function hasGameCapability(gameCode, capability) {
  return getGameFrontendModule(gameCode)?.capabilities?.[capability] === true;
}

/**
 * 解析在线对战页路由。
 * @param {string} gameCode
 * @param {string} roomId
 * @returns {{ name: string, params: object }|null}
 */
export function resolveGamePlayRoute(gameCode, roomId) {
  const module = getGameFrontendModule(gameCode);
  if (!module || !hasGameCapability(gameCode, 'onlineBattle')) {
    return null;
  }
  const routeName = module.route?.name;
  const normalizedRoomId = String(roomId || '').trim();
  if (!routeName || !normalizedRoomId) {
    return null;
  }
  return {
    name: routeName,
    params: { roomId: normalizedRoomId }
  };
}
