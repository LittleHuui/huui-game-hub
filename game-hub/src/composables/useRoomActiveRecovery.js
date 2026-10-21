import { computed, ref, watch } from 'vue';
import { useRoomStore } from '../stores/roomStore.js';
import { getRoomMembershipScope } from '../services/roomAccessService.js';
import * as roomQueryService from '../services/roomQueryService.js';
import * as roomService from '../services/roomService.js';

/**
 * 展示共享成员归属快照，管理返回与显式退出确认；服务层拥有查询及命令对账。
 * @param {object} input 页面上下文、忙态判断及按房间游戏导航的回调。
 * @returns {object} 活跃房间、错误、忙态与刷新、返回和重置操作。
 */
export function useRoomActiveRecovery({ gameCode, context, onlineBlocked, isBusy, navigateToRoom, navigateToPlay }) {
  const roomStore = useRoomStore();
  const entryError = ref('');
  const scope = computed(() => getRoomMembershipScope());
  const activeRoom = computed(() => roomStore.activeRoomScope === scope.value ? roomStore.activeRoom : null);
  const activeRoomError = computed(() => entryError.value || (roomStore.activeRoomScope === scope.value ? roomStore.activeRoomError : ''));
  watch(scope, () => roomQueryService.synchronizeActiveRoomScope(), { immediate: true, flush: 'sync' });
  const activeRoomReturning = ref(false);
  const activeRoomLeaving = ref(false);
  const activeRoomLeaveVisible = ref(false);
  const activeRoomLeaveError = ref('');
  const roomToLeave = ref(null);
  const activeRoomLeaveMessage = computed(() => {
    const name = roomToLeave.value?.roomName || roomToLeave.value?.roomId || '当前房间';
    return `确认退出「${name}」？正在进行的对局将按房间托管规则处理。`;
  });
  /**
   * 复位当前页面的确认和反馈；不清空其他页面可复用的共享归属快照。
   * @returns {void}
   */
  function resetActiveRoom() {
    entryError.value = '';
    activeRoomReturning.value = false;
    activeRoomLeaving.value = false;
    activeRoomLeaveVisible.value = false;
    activeRoomLeaveError.value = '';
    roomToLeave.value = null;
  }

  /**
   * 刷新成员查询快照；查询错误由服务单独展示，不把失败解释为已退出。
   * @returns {Promise<object|null>} 当前房间；无房间、失败或已取消时返回空。
   */
  async function refreshActiveRoom() {
    const operation = context.capture();
    if (!operation.isCurrent() || onlineBlocked.value) return null;
    entryError.value = '';
    try {
      return await roomQueryService.loadMyActiveRoom({ signal: operation.signal });
    } catch {
      return null;
    }
  }

  /**
   * 重查实际成员房间并导航；未知状态或游戏显式报错，不自动退出或切换成员资格。
   * @returns {Promise<void>}
   */
  async function onReturnActiveRoom() {
    const operation = context.capture();
    if (!operation.isCurrent() || onlineBlocked.value || isBusy()) return;
    activeRoomReturning.value = true;
    try {
      entryError.value = '';
      const room = await roomQueryService.loadMyActiveRoom({ signal: operation.signal });
      if (!operation.isCurrent()) return;
      if (!room) {
        entryError.value = '你已不在该房间中，可以刷新列表或创建房间';
        return;
      }
      if (room.status === 'playing') {
        await navigateToPlay(room.roomId, room.gameCode || '');
      } else if (room.status === 'waiting') {
        await navigateToRoom(room.roomId, room.gameCode || '');
      } else {
        throw new Error('当前房间状态不可进入，请刷新后重试');
      }
    } catch (err) {
      if (operation.isCurrent() && err?.name !== 'AbortError') entryError.value = err?.message || '返回房间失败';
    } finally {
      if (operation.isCurrent()) activeRoomReturning.value = false;
    }
  }

  /**
   * 为用户当前选中的实际房间打开退出确认，不发送成员命令。
   * @returns {void}
   */
  function onRequestLeaveActiveRoom() {
    if (!context.capture().isCurrent() || onlineBlocked.value || isBusy() || !activeRoom.value?.roomId) return;
    roomToLeave.value = { ...activeRoom.value };
    entryError.value = '';
    activeRoomLeaveError.value = '';
    activeRoomLeaveVisible.value = true;
  }

  /**
   * 取消退出确认，保持服务端房间成员资格。
   * @returns {void}
   */
  function onCancelLeaveActiveRoom() {
    if (activeRoomLeaving.value) return;
    activeRoomLeaveVisible.value = false;
    activeRoomLeaveError.value = '';
    roomToLeave.value = null;
  }

  /**
   * 确认后按固定房间 ID 调用通用退出；成员事实和命令后的查询由服务统一维护。
   * @returns {Promise<void>} 保持原退出语义；响应失败仍重查事实，不伪造退出成功。
   */
  async function onConfirmLeaveActiveRoom() {
    const operation = context.capture();
    const roomId = roomToLeave.value?.roomId;
    if (!operation.isCurrent() || onlineBlocked.value || isBusy() || !activeRoomLeaveVisible.value || !roomId) return;
    activeRoomLeaving.value = true;
    activeRoomLeaveError.value = '';
    try {
      await roomService.leaveRoom(roomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      activeRoomLeaveVisible.value = false;
      roomToLeave.value = null;
      await roomQueryService.refreshRoomList(gameCode.value, { signal: operation.signal }).catch(() => {});
    } catch (err) {
      if (!operation.isCurrent()) return;
      const message = err?.message || '退出房间失败';
      activeRoomLeaveError.value = message;
      if (roomStore.activeRoomQueryStatus === 'ready' && activeRoom.value?.roomId !== roomId) {
        activeRoomLeaveVisible.value = false;
        roomToLeave.value = null;
        entryError.value = `${message}；已重新查询当前房间状态`;
      }
    } finally {
      if (operation.isCurrent()) activeRoomLeaving.value = false;
    }
  }

  return {
    activeRoom, activeRoomError, activeRoomReturning, activeRoomLeaving,
    activeRoomLeaveVisible, activeRoomLeaveError, activeRoomLeaveMessage,
    refreshActiveRoom, onReturnActiveRoom, resetActiveRoom,
    onRequestLeaveActiveRoom, onCancelLeaveActiveRoom, onConfirmLeaveActiveRoom
  };
}
