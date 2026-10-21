import * as roomRepository from '../repositories/roomRepository.js';
import { useRoomStore } from '../stores/roomStore.js';
import { requireServerUserId, getCurrentPlayerId, assertRoomRemoteAvailable, getRoomMembershipScope } from './roomAccessService.js';
import { refreshRoomList, loadMyActiveRoom, cancelActiveRoomQuery, synchronizeActiveRoomScope } from './roomQueryService.js';
import { resetRoomGameView } from './roomGameService.js';

/**
 * 执行成员命令并对账归属，覆盖提交后响应失败；对账失败不改写命令结果。
 * @param {Function} mutation 接收上下文有效性判断的成员命令及本地展示更新。
 * @param {{signal?: AbortSignal}} options 调用者生命周期。
 * @returns {Promise<object>} 原命令结果；原命令异常保持原样抛出。
 */
async function executeMembershipMutation(mutation, options) {
  const scope = synchronizeActiveRoomScope();
  const isCurrent = () => !options.signal?.aborted && getRoomMembershipScope() === scope;
  if (!isCurrent()) throw new globalThis.DOMException('房间操作已取消', 'AbortError');
  cancelActiveRoomQuery();
  try {
    return await mutation(isCurrent);
  } finally {
    if (isCurrent()) {
      try {
        await loadMyActiveRoom(options);
      } catch {
        // 查询错误已单独写入归属快照；不能把已完成命令报告为失败。
      }
    }
  }
}

async function applyRoomMutation(room, options) {
  if (options.signal?.aborted) return room;
  const store = useRoomStore();
  const current = store.currentRoom;
  if (!current || current.roomId !== room.roomId || Number(room.roomVersion || 0) >= Number(current.roomVersion || 0)) store.setCurrentRoom(room);
  const gameCode = String(room?.gameCode || '').trim();
  if (!gameCode) {
    return room;
  }
  try {
    await refreshRoomList(gameCode, options);
  } catch {
    // 房间命令已成功，列表在下一次实时推送或手动刷新时同步。
  }
  return room;
}

/**
 * 创建房间并同步成员归属；页面取消后不接收本地展示更新。
 * @param {object} options 房间创建参数。
 * @param {{signal?: AbortSignal}} [requestOptions] 页面生命周期。
 * @returns {Promise<object>} 已创建房间，后续归属查询失败不撤销创建结果。
 */
export async function createRoom(options, requestOptions = {}) {
  assertRoomRemoteAvailable();
  const { gameCode, mode, roomName, roomConfig, expireSeconds } = options || {};
  if (!gameCode) {
    throw new Error('缺少 gameCode');
  }
  if (!mode) {
    throw new Error('缺少 mode');
  }
  requireServerUserId();
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
  return executeMembershipMutation(async (isCurrent) => {
    const room = await roomRepository.createRoom(payload);
    if (!isCurrent()) return room;
    const store = useRoomStore();
    store.setCurrentRoom(room);
    if (store.activeGameCode === gameCode) {
      void refreshRoomList(gameCode, requestOptions).catch(() => {});
    }
    return room;
  }, requestOptions);
}

/**
 * 加入房间并重查当前成员归属，包括并发占用冲突和提交后响应失败。
 * @param {string} roomId 目标房间。
 * @param {{signal?: AbortSignal}} [options] 页面生命周期。
 * @returns {Promise<object>} 原加入结果。
 */
export async function joinRoom(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  return executeMembershipMutation(async (isCurrent) => {
    const raw = await roomRepository.joinRoom(roomId);
    if (!isCurrent()) return raw;
    return applyRoomMutation(raw, options);
  }, options);
}

/**
 * 恢复托管席位并同步跨游戏成员归属，不根据客户端快照释放其他房间。
 * @param {string} roomId 待恢复房间。
 * @param {{signal?: AbortSignal}} [options] 页面生命周期。
 * @returns {Promise<object>} 原恢复结果。
 */
export async function rejoinManagedRoom(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  return executeMembershipMutation(async (isCurrent) => {
    const raw = await roomRepository.rejoinManagedRoom(roomId);
    if (!isCurrent()) return raw;
    return applyRoomMutation(raw, options);
  }, options);
}

export async function startManagedMode(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const room = await roomRepository.startManagedMode(roomId);
  return applyRoomMutation(room, options);
}

export async function stopManagedMode(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const room = await roomRepository.stopManagedMode(roomId);
  return applyRoomMutation(room, options);
}

export async function addRoomAi(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const room = await roomRepository.addRoomAi(roomId);
  return applyRoomMutation(room, options);
}

export async function removeRoomMember(roomId, targetPlayerId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const normalizedTargetId = String(targetPlayerId || '').trim();
  if (!normalizedTargetId) {
    throw new Error('缺少 targetPlayerId');
  }
  const room = await roomRepository.removeRoomMember(roomId, normalizedTargetId);
  return applyRoomMutation(room, options);
}

export async function updateRoomConfig(roomId, payload, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const room = await roomRepository.updateRoomConfig(roomId, payload || {});
  return applyRoomMutation(room, options);
}

/**
 * 执行已由调用方确认的退出，按响应更新详情，并始终重查实际成员归属。
 * @param {string} roomId 用户确认退出的房间。
 * @param {{signal?: AbortSignal}} [options] 页面生命周期。
 * @returns {Promise<object>} 原退出结果；失败不清空归属快照。
 */
export async function leaveRoom(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  return executeMembershipMutation(async (isCurrent) => {
    const leaveResult = await roomRepository.leaveRoom(roomId);
    if (!isCurrent()) return leaveResult;
    if (!leaveResult || leaveResult.roomId !== roomId) {
      throw new Error('退出结果与目标房间不一致，请刷新重试');
    }
    const store = useRoomStore();
    const gameCode =
      leaveResult?.gameCode || store.currentRoom?.gameCode || store.activeGameCode;
    if (leaveResult?.dissolved && store.currentRoom?.roomId === roomId) {
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
        await refreshRoomList(gameCode, options);
      } catch {
        // 列表刷新失败不阻断离开
      }
    }
    return leaveResult;
  }, options);
}
