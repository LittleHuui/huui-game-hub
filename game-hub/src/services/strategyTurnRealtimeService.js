import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';
import { mapRoomDetail } from '../mappers/roomMapper.js';
import { mapStrategyTurnGameView } from '../mappers/strategyTurnGameViewMapper.js';
import { useRoomStore } from '../stores/roomStore.js';
import * as realtimeService from './realtimeService.js';
import * as strategyTurnGameViewService from './strategyTurnGameViewService.js';

/** @type {boolean} */
let roomHandlersBound = false;
/** @type {string} */
let subscribedRoomId = '';
/** @type {number} */
let subscribeRefCount = 0;
/** @type {((gameCode: string) => void)|null} */
let roomListRefreshHandler = null;

/**
 * 注册房间级实时消息处理器（仅一次）。
 */
export function ensureRoomRealtimeHandlersBound() {
  if (roomHandlersBound) {
    return;
  }
  roomHandlersBound = true;
  realtimeService.on(REALTIME_MESSAGE_TYPES.GAME_VIEW_UPDATED, handleGameViewUpdated);
  realtimeService.on(REALTIME_MESSAGE_TYPES.ROOM_UPDATED, handleRoomUpdated);
  realtimeService.on(REALTIME_MESSAGE_TYPES.ROOM_LIST_UPDATED, handleRoomListUpdated);
}

/**
 * 注册同 gameCode 房间列表变更时的刷新回调（由 roomService 注入）。
 * @param {(gameCode: string) => void|null} handler
 */
export function setRoomListRefreshHandler(handler) {
  roomListRefreshHandler = typeof handler === 'function' ? handler : null;
}

/**
 * 处理 GameView 推送。
 * @param {object} message
 */
function handleGameViewUpdated(message) {
  const roomId = String(message?.payload?.roomId || '').trim();
  if (!subscribedRoomId || roomId !== subscribedRoomId) {
    return;
  }
  const raw = message?.payload?.gameView;
  if (!raw || typeof raw !== 'object') {
    return;
  }
  try {
    const gameView = mapStrategyTurnGameView(raw);
    strategyTurnGameViewService.acceptGameView(gameView);
  } catch {
    // 忽略无效推送
  }
}

/**
 * 处理房间元信息推送。
 * @param {object} message
 */
function handleRoomListUpdated(message) {
  const gameCode = String(message?.payload?.gameCode || '').trim();
  if (!gameCode || !roomListRefreshHandler) {
    return;
  }
  const activeGameCode = String(useRoomStore().activeGameCode || '').trim();
  if (activeGameCode && gameCode === activeGameCode) {
    roomListRefreshHandler(activeGameCode);
  }
}

/**
 * 处理房间元信息推送。
 * @param {object} message
 */
function handleRoomUpdated(message) {
  const roomId = String(message?.payload?.roomId || '').trim();
  const room = mapRoomDetail(message?.payload?.room);
  if (!room) {
    return;
  }
  const store = useRoomStore();
  const gameCode = String(room.gameCode || message?.payload?.gameCode || '').trim();
  if (subscribedRoomId && roomId === subscribedRoomId) {
    store.applyRoomIfNewer(room);
  }
  const activeGameCode = String(store.activeGameCode || '').trim();
  if (roomListRefreshHandler && activeGameCode && gameCode === activeGameCode) {
    roomListRefreshHandler(activeGameCode);
  }
}

/**
 * 订阅指定房间的实时推送。
 * @param {string} roomId
 * @returns {() => void} 取消订阅函数
 */
export function subscribeRoomChannel(roomId) {
  ensureRoomRealtimeHandlersBound();
  const normalized = String(roomId || '').trim();
  if (!normalized) {
    return () => {};
  }
  if (subscribedRoomId === normalized) {
    subscribeRefCount += 1;
    return () => unsubscribeRoomChannel(normalized);
  }
  subscribedRoomId = normalized;
  subscribeRefCount = 1;
  return () => unsubscribeRoomChannel(normalized);
}

/**
 * 取消房间实时订阅。
 * @param {string} roomId
 */
export function unsubscribeRoomChannel(roomId) {
  const normalized = String(roomId || '').trim();
  if (!normalized || subscribedRoomId !== normalized) {
    return;
  }
  subscribeRefCount -= 1;
  if (subscribeRefCount <= 0) {
    subscribedRoomId = '';
    subscribeRefCount = 0;
    strategyTurnGameViewService.resetGameViewState();
  }
}

/**
 * 当前订阅的房间 ID。
 * @returns {string}
 */
export function getSubscribedRoomId() {
  return subscribedRoomId;
}
