import * as roomRepository from '../repositories/roomRepository.js';
import * as userRepository from '../repositories/userRepository.js';
import { useRoomStore } from '../stores/roomStore.js';
import { canFetchRemote } from './remoteGate.js';
import * as onlineService from './onlineService.js';
import { REALTIME_MESSAGE_TYPES } from '../constants/realtimeMessageTypes.js';
import * as realtimeService from './realtimeService.js';
import * as strategyTurnGameViewService from './strategyTurnGameViewService.js';
import * as strategyTurnRealtimeService from './strategyTurnRealtimeService.js';
import * as toastService from './toastService.js';

/** @type {number} */
let roomActionClientSeq = 0;

strategyTurnRealtimeService.setRoomListRefreshHandler((gameCode) => {
  void refreshRoomList(gameCode).catch(() => {});
});

/**
 * 解析当前用户服务端 ID，用于房间 join/leave。
 * @returns {string}
 */
function requireServerUserId() {
  const serviceId = userRepository.resolveServerUserId();
  if (!serviceId) {
    throw new Error('未登录，无法操作房间');
  }
  return serviceId;
}

/**
 * 读取当前用户服务端 ID（未登录时返回空字符串）。
 * @returns {string}
 */
export function getCurrentPlayerId() {
  return userRepository.resolveServerUserId() || '';
}

/**
 * 校验是否允许发起房间远端请求。
 */
function assertRoomRemoteAvailable() {
  if (!canFetchRemote()) {
    throw new Error('当前无法访问房间服务');
  }
}

/**
 * 将规则定义中的房间上下文写入 store。
 * @param {object|null|undefined} ruleDefinition
 */
export function applyRoomRuleContext(ruleDefinition) {
  const store = useRoomStore();
  const payload = ruleDefinition && typeof ruleDefinition === 'object' ? ruleDefinition : {};
  store.setRoomRuleContext({
    roomRule: payload.roomRule || null,
    roomConfigSchema: payload.roomConfigSchema || null
  });
}

/**
 * 按游戏编码刷新房间列表并写入 store。
 * @param {string} gameCode
 * @returns {Promise<object[]>}
 */
export async function refreshRoomList(gameCode) {
  assertRoomRemoteAvailable();
  if (!gameCode) {
    throw new Error('缺少 gameCode');
  }
  const store = useRoomStore();
  store.setActiveGameCode(gameCode);
  store.setRoomsLoading(true);
  store.setRoomsError('');
  try {
    const rooms = await roomRepository.fetchRoomList(gameCode);
    store.setRooms(rooms);
    return rooms;
  } catch (err) {
    store.setRooms([]);
    const message = err?.message || '加载房间列表失败';
    store.setRoomsError(message);
    throw err;
  } finally {
    store.setRoomsLoading(false);
  }
}

/**
 * 查询当前用户跨游戏活跃房间。
 * @returns {Promise<object|null>}
 */
export async function loadMyActiveRoom() {
  assertRoomRemoteAvailable();
  const serviceId = requireServerUserId();
  return roomRepository.fetchMyActiveRoom(serviceId);
}

/**
 * 查询当前用户在指定游戏下的托管空壳房间。
 * @param {string} gameCode
 * @returns {Promise<object|null>}
 */
export async function loadMyManagedShell(gameCode) {
  assertRoomRemoteAvailable();
  if (!gameCode) {
    throw new Error('缺少 gameCode');
  }
  const serviceId = requireServerUserId();
  return roomRepository.fetchMyManagedShell(gameCode, serviceId);
}

/**
 * 查询房间详情并写入 store。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function loadRoomDetail(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const store = useRoomStore();
  store.setCurrentRoomLoading(true);
  store.setCurrentRoomError('');
  try {
    const room = await roomRepository.fetchRoom(roomId);
    if (!room) {
      throw new Error('房间不存在');
    }
    store.setCurrentRoom(room);
    return room;
  } catch (err) {
    store.setCurrentRoom(null);
    const message = err?.message || '加载房间失败';
    store.setCurrentRoomError(message);
    throw err;
  } finally {
    store.setCurrentRoomLoading(false);
  }
}

/**
 * 创建房间并将当前用户作为房主。
 * @param {{ gameCode: string; mode: string; roomName?: string; roomConfig?: object; expireSeconds?: number }} options
 * @returns {Promise<object>}
 */
export async function createRoom(options) {
  assertRoomRemoteAvailable();
  const { gameCode, mode, roomName, roomConfig, expireSeconds } = options || {};
  if (!gameCode) {
    throw new Error('缺少 gameCode');
  }
  if (!mode) {
    throw new Error('缺少 mode');
  }
  const serviceId = requireServerUserId();
  /** @type {{ gameCode: string; mode: string; expireSeconds?: number; roomName?: string; roomConfig?: object }} */
  const payload = { gameCode, mode };
  if (expireSeconds != null) {
    payload.expireSeconds = expireSeconds;
  }
  if (roomName != null && String(roomName).trim()) {
    payload.roomName = String(roomName).trim();
  }
  if (roomConfig && typeof roomConfig === 'object') {
    payload.roomConfig = roomConfig;
  }
  const room = await roomRepository.createRoom(payload, serviceId);
  const store = useRoomStore();
  store.setCurrentRoom(room);
  if (store.activeGameCode === gameCode) {
    try {
      await refreshRoomList(gameCode);
    } catch {
      // 列表刷新失败不阻断创建
    }
  }
  return room;
}

/**
 * 当前用户加入房间。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function joinRoom(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  const raw = await roomRepository.joinRoom(roomId, serviceId);
  const store = useRoomStore();
  store.setCurrentRoom(raw);
  if (raw.gameCode) {
    try {
      await refreshRoomList(raw.gameCode);
    } catch {
      // 列表刷新失败不阻断加入
    }
  }
  return raw;
}

/**
 * 恢复托管席位并重连房间。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function rejoinManagedRoom(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  const raw = await roomRepository.rejoinManagedRoom(roomId, serviceId);
  const store = useRoomStore();
  store.setCurrentRoom(raw);
  if (raw.gameCode) {
    try {
      await refreshRoomList(raw.gameCode);
    } catch {
      // 列表刷新失败不阻断重连
    }
  }
  return raw;
}

/**
 * 在对局中开启在线托管。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function startManagedMode(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  const room = await roomRepository.startManagedMode(roomId, serviceId);
  const store = useRoomStore();
  store.setCurrentRoom(room);
  if (room?.gameCode) {
    try {
      await refreshRoomList(room.gameCode);
    } catch {
      // 列表刷新失败不阻断托管切换
    }
  }
  return room;
}

/**
 * 在对局中取消在线托管。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function stopManagedMode(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  const room = await roomRepository.stopManagedMode(roomId, serviceId);
  const store = useRoomStore();
  store.setCurrentRoom(room);
  if (room?.gameCode) {
    try {
      await refreshRoomList(room.gameCode);
    } catch {
      // 列表刷新失败不阻断托管切换
    }
  }
  return room;
}

/**
 * 房主在等待中的房间内添加一名 AI 玩家。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function addRoomAi(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  const room = await roomRepository.addRoomAi(roomId, serviceId);
  const store = useRoomStore();
  store.setCurrentRoom(room);
  if (room?.gameCode) {
    try {
      await refreshRoomList(room.gameCode);
    } catch {
      // 列表刷新失败不阻断添加 AI
    }
  }
  return room;
}

/**
 * 房主在等待中的房间内移除成员。
 * @param {string} roomId
 * @param {string} targetPlayerId
 * @returns {Promise<object>}
 */
export async function removeRoomMember(roomId, targetPlayerId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const normalizedTargetId = String(targetPlayerId || '').trim();
  if (!normalizedTargetId) {
    throw new Error('缺少 targetPlayerId');
  }
  const serviceId = requireServerUserId();
  const room = await roomRepository.removeRoomMember(roomId, serviceId, normalizedTargetId);
  const store = useRoomStore();
  store.setCurrentRoom(room);
  if (room?.gameCode) {
    try {
      await refreshRoomList(room.gameCode);
    } catch {
      // 列表刷新失败不阻断移除
    }
  }
  return room;
}

/**
 * 房主在等待中的房间内更新配置。
 * @param {string} roomId
 * @param {{ maxPlayers?: number; roomConfig?: object }} payload
 * @returns {Promise<object>}
 */
export async function updateRoomConfig(roomId, payload) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  const room = await roomRepository.updateRoomConfig(roomId, serviceId, payload || {});
  const store = useRoomStore();
  store.setCurrentRoom(room);
  if (room?.gameCode) {
    try {
      await refreshRoomList(room.gameCode);
    } catch {
      // 列表刷新失败不阻断配置更新
    }
  }
  return room;
}

/**
 * 当前用户离开房间。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function leaveRoom(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  const leaveResult = await roomRepository.leaveRoom(roomId, serviceId);
  const store = useRoomStore();
  const gameCode =
    leaveResult?.gameCode || store.currentRoom?.gameCode || store.activeGameCode;
  if (leaveResult?.dissolved) {
    store.clearCurrentRoom();
    resetRoomGameView();
  } else if (leaveResult?.room) {
    const currentPlayerId = getCurrentPlayerId();
    const stillInRoom = Array.isArray(leaveResult.room.members)
      ? leaveResult.room.members.some(
          (item) =>
            item?.playerId === currentPlayerId &&
            String(item?.managedMode || '').trim() !== 'shell'
        )
      : false;
    if (!stillInRoom && store.currentRoom?.roomId === roomId) {
      store.clearCurrentRoom();
      resetRoomGameView();
    } else if (stillInRoom && store.currentRoom?.roomId === roomId) {
      store.setCurrentRoom(leaveResult.room);
    }
  }
  if (gameCode) {
    try {
      await refreshRoomList(gameCode);
    } catch {
      // 列表刷新失败不阻断离开
    }
  }
  return leaveResult;
}

/**
 * 房主开始房间对局并刷新房间详情。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function startRoomGame(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const serviceId = requireServerUserId();
  strategyTurnGameViewService.setActiveRoom(roomId);
  const gameView = await roomRepository.startRoomGame(roomId, serviceId);
  strategyTurnGameViewService.acceptGameView(gameView);
  const room = await loadRoomDetail(roomId);
  const gameCode = room?.gameCode || useRoomStore().activeGameCode;
  if (gameCode) {
    try {
      await refreshRoomList(gameCode);
    } catch {
      // 列表刷新失败不阻断开局
    }
  }
  return { room, gameView };
}

/**
 * 查询房间对局 GameView 并写入展示管线。
 * @param {string} roomId
 * @returns {Promise<object>}
 */
export async function loadRoomGameView(roomId) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  strategyTurnGameViewService.setActiveRoom(roomId);
  const serviceId = requireServerUserId();
  const gameView = await roomRepository.fetchRoomGameView(roomId, serviceId);
  strategyTurnGameViewService.acceptGameView(gameView);
  return gameView;
}

/**
 * 提交房间对局操作并更新 GameView 展示管线。
 * @param {string} roomId
 * @param {{ actionId: string; baseVersion: number; clientSeq?: number }} body
 * @returns {Promise<object>}
 */
export async function applyRoomGameAction(roomId, body) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const actionId = String(body?.actionId || '').trim();
  if (!actionId) {
    throw new Error('缺少 actionId');
  }
  const serviceId = requireServerUserId();
  roomActionClientSeq += 1;
  const baseVersion = Number(body?.baseVersion);
  if (!Number.isFinite(baseVersion) || baseVersion < 0) {
    throw new Error('缺少 baseVersion');
  }
  const gameView = await roomRepository.applyRoomGameAction(roomId, serviceId, {
    actionId,
    baseVersion,
    clientSeq: body?.clientSeq != null ? Number(body.clientSeq) : roomActionClientSeq
  });
  strategyTurnGameViewService.acceptGameView(gameView);
  return gameView;
}

/**
 * 离开对局上下文时重置 GameView 本地状态。
 */
export function resetRoomGameView() {
  roomActionClientSeq = 0;
  strategyTurnGameViewService.resetGameViewState();
}

/**
 * 加载可邀请的在线用户（排除已在房间内的成员与当前用户）。
 * @param {string} roomId
 * @returns {Promise<object[]>}
 */
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

/**
 * 订阅房间实时通道（GameView / 房间元信息 / 邀请）。
 * @param {string} roomId
 * @returns {() => void}
 */
export function bindRoomRealtime(roomId) {
  return strategyTurnRealtimeService.subscribeRoomChannel(roomId);
}

/**
 * 取消房间实时订阅。
 * @param {string} roomId
 */
export function unbindRoomRealtime(roomId) {
  strategyTurnRealtimeService.unsubscribeRoomChannel(roomId);
}

/**
 * 绑定对局房间探活 pong 响应。
 * @param {string} roomId
 * @param {string} gameCode
 * @param {() => boolean} isActive
 * @returns {() => void}
 */
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

/**
 * 通过 WebSocket 向目标用户发送房间邀请。
 * @param {string} roomId
 * @param {{ serviceId: string; nickname: string }} target
 */
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
  const inviterPlayerId = requireServerUserId();
  const inviterNickname =
    (room.members || []).find((item) => item.playerId === inviterPlayerId)?.nickname ||
    inviterPlayerId;
  const sent = realtimeService.send(REALTIME_MESSAGE_TYPES.ROOM_INVITE, {
    targetServiceId,
    roomId: room.roomId,
    roomName: room.roomName,
    gameCode: room.gameCode,
    inviterNickname
  });
  if (!sent) {
    throw new Error('实时通道未连接，无法发送邀请');
  }
  const nickname = String(target?.nickname || '').trim() || '玩家';
  toastService.push(`已向 ${nickname} 发送邀请`, 'info');
}
