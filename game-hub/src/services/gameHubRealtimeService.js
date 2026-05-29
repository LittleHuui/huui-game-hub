import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';
import { useRoomStore } from '../stores/roomStore.js';
import * as realtimeService from './realtimeService.js';
import * as toastService from './toastService.js';

/** @type {boolean} */
let globalHandlersBound = false;

/**
 * 注册全局实时消息处理器（进入在线大厅后调用一次）。
 */
export function ensureGlobalRealtimeHandlers() {
  if (globalHandlersBound) {
    return;
  }
  globalHandlersBound = true;
  realtimeService.on(REALTIME_MESSAGE_TYPES.ROOM_INVITE, handleRoomInvite);
}

/**
 * 处理房间邀请推送（不依赖房间订阅）。
 * @param {object} message
 */
function handleRoomInvite(message) {
  const payload = message?.payload && typeof message.payload === 'object' ? message.payload : {};
  const roomId = String(payload.roomId || '').trim();
  if (!roomId) {
    return;
  }
  const store = useRoomStore();
  store.setPendingInvite({
    roomId,
    roomName: String(payload.roomName || '').trim() || '房间',
    gameCode: String(payload.gameCode || '').trim(),
    inviterNickname: String(payload.inviterNickname || '').trim() || '玩家'
  });
  toastService.push('收到房间邀请', 'info');
}
