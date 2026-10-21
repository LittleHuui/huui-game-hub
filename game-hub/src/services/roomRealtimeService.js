import { useRoomStore } from '../stores/roomStore.js';
import { requireServerUserId, assertRoomRemoteAvailable } from './roomAccessService.js';
import * as onlineService from './onlineService.js';
import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';
import * as realtimeService from './realtimeService.js';
import * as strategyTurnRealtimeService from './strategyTurnRealtimeService.js';
import * as toastService from './toastService.js';

export async function loadInviteCandidates(roomId) {
  assertRoomRemoteAvailable();
  const store = useRoomStore();
  const room = store.currentRoom;
  if (!room || room.roomId !== roomId) {
    throw new Error('房间信息未加载');
  }
  if (room.memberCount >= room.maxPlayers) {
    return [];
  }
  const currentUserId = requireServerUserId();
  const memberIds = new Set((room.members || []).map((item) => item.playerId));
  const users = await onlineService.loadOnlineUsers({ silent: true, throwOnError: true });
  return users.filter((user) => {
    const serviceId = String(user?.serviceId || '').trim();
    if (!serviceId || serviceId === currentUserId) {
      return false;
    }
    return !memberIds.has(serviceId);
  });
}

export function bindRoomRealtime(roomId) {
  return strategyTurnRealtimeService.subscribeRoomChannel(roomId);
}

export function unbindRoomRealtime(roomId) {
  strategyTurnRealtimeService.unsubscribeRoomChannel(roomId);
}

export function bindRoomPresencePong(roomId, gameCode, isActive) {
  const normalizedRoomId = String(roomId || '').trim();
  const normalizedGameCode = String(gameCode || '').trim();
  if (!normalizedRoomId || !normalizedGameCode) {
    return () => {};
  }
  const checkActive = typeof isActive === 'function' ? isActive : () => true;
  const handler = (message) => {
    const payload = message?.payload && typeof message.payload === 'object' ? message.payload : {};
    const pingRoomId = String(payload.roomId || '').trim();
    const pingGameCode = String(payload.gameCode || '').trim();
    const sequence = Number(payload.sequence);
    if (!checkActive()) {
      return;
    }
    if (!pingRoomId || pingRoomId !== normalizedRoomId || pingGameCode !== normalizedGameCode) {
      return;
    }
    if (!Number.isFinite(sequence) || sequence <= 0) {
      return;
    }
    realtimeService.send(REALTIME_MESSAGE_TYPES.ROOM_PRESENCE_PONG, {
      roomId: normalizedRoomId,
      gameCode: normalizedGameCode,
      sequence,
      receivedAt: Date.now()
    });
  };
  realtimeService.on(REALTIME_MESSAGE_TYPES.ROOM_PRESENCE_PING, handler);
  return () => realtimeService.off(REALTIME_MESSAGE_TYPES.ROOM_PRESENCE_PING, handler);
}

export function sendRoomInvite(roomId, target) {
  const store = useRoomStore();
  const room = store.currentRoom;
  if (!room || room.roomId !== roomId) {
    throw new Error('房间信息未加载');
  }
  if (room.status !== 'waiting') {
    throw new Error('房间已开始，无法邀请');
  }
  if (room.memberCount >= room.maxPlayers) {
    throw new Error('房间已满，无法继续邀请');
  }
  const targetServiceId = String(target?.serviceId || '').trim();
  if (!targetServiceId) {
    throw new Error('缺少被邀请用户');
  }
  const sent = realtimeService.send(REALTIME_MESSAGE_TYPES.ROOM_INVITE, {
    targetServiceId,
    roomId: room.roomId
  });
  if (!sent) {
    throw new Error('实时通道未连接，无法发送邀请');
  }
  const nickname = String(target?.nickname || '').trim() || '玩家';
  toastService.push(`已向 ${nickname} 发送邀请`, 'info');
}
