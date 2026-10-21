import * as roomRepository from '../repositories/roomRepository.js';
import { useRoomStore } from '../stores/roomStore.js';
import { assertRoomRemoteAvailable, getRoomMembershipScope } from './roomAccessService.js';
import * as strategyTurnRealtimeService from './strategyTurnRealtimeService.js';

let listRequestGeneration = 0;
let detailRequestGeneration = 0;
let activeRoomRequest = null;

/**
 * 废止成员命令开始前的查询，避免旧读取在命令执行期间回写。
 * @returns {void} 取消网络请求，保留最后一次查询事实。
 */
export function cancelActiveRoomQuery() {
  activeRoomRequest?.abort();
  activeRoomRequest = null;
  useRoomStore().setActiveRoomQueryStatus('idle');
}

/**
 * 按当前访问上下文隔离共享快照；同一身份的页面切换不清空归属。
 * @returns {string} 当前查询上下文。
 */
export function synchronizeActiveRoomScope() {
  const store = useRoomStore();
  const scope = getRoomMembershipScope();
  if (store.activeRoomScope !== scope) {
    cancelActiveRoomQuery();
    store.setActiveRoomScope(scope);
  }
  return scope;
}

strategyTurnRealtimeService.setRoomListRefreshHandler((gameCode) => {
  void refreshRoomList(gameCode).catch(() => {});
});

export function applyRoomRuleContext(ruleDefinition) {
  const store = useRoomStore();
  const payload = ruleDefinition && typeof ruleDefinition === 'object' ? ruleDefinition : {};
  store.setRoomRuleContext({
    roomRule: payload.roomRule || null,
    roomConfigSchema: payload.roomConfigSchema || null
  });
}

/**
 * 刷新指定游戏的房间列表，身份或数据模式变化后不接受旧响应。
 * @param {string} gameCode 当前列表游戏。
 * @param {{signal?: AbortSignal}} [options] 页面生命周期。
 * @returns {Promise<object[]>} 查询结果，只有当前请求可写列表快照。
 */
export async function refreshRoomList(gameCode, options = {}) {
  assertRoomRemoteAvailable();
  if (!gameCode) {
    throw new Error('缺少 gameCode');
  }
  const store = useRoomStore();
  const scope = getRoomMembershipScope();
  const generation = ++listRequestGeneration;
  const isCurrent = () => generation === listRequestGeneration && !options.signal?.aborted && store.activeGameCode === gameCode && getRoomMembershipScope() === scope;
  store.setActiveGameCode(gameCode);
  store.setRoomsLoading(true);
  store.setRoomsError('');
  try {
    const rooms = await roomRepository.fetchRoomList(gameCode);
    if (isCurrent()) store.setRooms(rooms);
    return rooms;
  } catch (err) {
    if (isCurrent()) {
      store.setRooms([]);
      store.setRoomsError(err?.message || '加载房间列表失败');
    }
    throw err;
  } finally {
    if (generation === listRequestGeneration) store.setRoomsLoading(false);
  }
}

/**
 * 查询并保存跨游戏成员归属；最新查询失败保留已知快照，过期查询不写回。
 * @param {{signal?: AbortSignal}} [options] 页面查询上下文。
 * @returns {Promise<object|null>} 权威查询结果；取消或失败抛出，不被解释为无房间。
 */
export async function loadMyActiveRoom(options = {}) {
  const scope = synchronizeActiveRoomScope();
  assertRoomRemoteAvailable();
  const store = useRoomStore();
  cancelActiveRoomQuery();
  const controller = new AbortController();
  activeRoomRequest = controller;
  store.setActiveRoomQueryStatus('loading');
  const cancel = () => controller.abort();
  if (options.signal?.aborted) cancel();
  else options.signal?.addEventListener('abort', cancel, { once: true });
  const isCurrent = () => activeRoomRequest === controller && !controller.signal.aborted && getRoomMembershipScope() === scope;
  try {
    if (!isCurrent()) throw new globalThis.DOMException('成员查询已取消', 'AbortError');
    const room = await roomRepository.fetchMyActiveRoom({ signal: controller.signal });
    if (!isCurrent()) throw new globalThis.DOMException('成员查询已取消', 'AbortError');
    store.setActiveRoom(room);
    return room;
  } catch (err) {
    if (!isCurrent()) throw new globalThis.DOMException('成员查询已取消', 'AbortError');
    store.setActiveRoomError(err?.message || '查询当前房间失败，请刷新重试');
    throw err;
  } finally {
    options.signal?.removeEventListener('abort', cancel);
    if (activeRoomRequest === controller) {
      activeRoomRequest = null;
      if (store.activeRoomQueryStatus === 'loading') store.setActiveRoomQueryStatus('idle');
    }
  }
}

export async function loadMyManagedShell(gameCode) {
  assertRoomRemoteAvailable();
  if (!gameCode) {
    throw new Error('缺少 gameCode');
  }
  return roomRepository.fetchMyManagedShell(gameCode);
}

export async function loadRoomDetail(roomId, options = {}) {
  assertRoomRemoteAvailable();
  if (!roomId) {
    throw new Error('缺少 roomId');
  }
  const store = useRoomStore();
  const generation = ++detailRequestGeneration;
  const isCurrent = () => generation === detailRequestGeneration && !options.signal?.aborted;
  store.setCurrentRoomLoading(true);
  store.setCurrentRoomError('');
  try {
    const room = await roomRepository.fetchRoom(roomId, options);
    if (!room) {
      throw new Error('房间不存在');
    }
    if (isCurrent()) {
      const current = store.currentRoom;
      if (!current || current.roomId !== roomId || Number(room.roomVersion || 0) >= Number(current.roomVersion || 0)) {
        store.setCurrentRoom(room);
      }
    }
    return isCurrent() && store.currentRoom?.roomId === roomId ? store.currentRoom : room;
  } catch (err) {
    if (isCurrent() && err?.name !== 'AbortError') {
      store.setCurrentRoomError(err?.message || '加载房间失败');
    }
    throw err;
  } finally {
    if (generation === detailRequestGeneration) store.setCurrentRoomLoading(false);
  }
}
