import { computed, ref } from 'vue';
import * as roomAccessService from '../services/roomAccessService.js';
import * as roomQueryService from '../services/roomQueryService.js';
import * as roomService from '../services/roomService.js';
import { resolveOnlineRoomMode } from '../services/onlineRoomService.js';
import { useRoomActiveRecovery } from './useRoomActiveRecovery.js';

/**
 * 组合大厅弹窗与房间命令；活跃房间恢复独立管理并受页面上下文取消约束。
 * @param {object} input 页面状态、上下文及导航回调。
 * @returns {object} 弹窗状态和用户操作入口。
 */
export function useRoomLobbyDialogs({ gameCode, onlineBlocked, context, loading, loadError, navigateToRoom, navigateToPlay }) {
  const createDialogVisible = ref(false);
  const createSubmitting = ref(false);
  const createError = ref('');
  const listDetailVisible = ref(false);
  const listDetailLoading = ref(false);
  const listDetailJoining = ref(false);
  /** @type {import('vue').Ref<object|null>} */
  const selectedListRoom = ref(null);
  const {
    activeRoom, activeRoomError, activeRoomReturning, activeRoomLeaving,
    activeRoomLeaveVisible, activeRoomLeaveError, activeRoomLeaveMessage,
    refreshActiveRoom, onReturnActiveRoom, resetActiveRoom,
    onRequestLeaveActiveRoom, onCancelLeaveActiveRoom, onConfirmLeaveActiveRoom
  } = useRoomActiveRecovery({ gameCode, context, onlineBlocked, isBusy: () => listBusy.value, navigateToRoom, navigateToPlay });

  const activePlayingConfirmVisible = ref(false);
  const activePlayingConfirmSubmitting = ref(false);
  const activePlayingConfirmError = ref('');

  const listResumeConfirmVisible = ref(false);
  const listResumeConfirmSubmitting = ref(false);
  const listResumeConfirmError = ref('');
  /** @type {import('vue').Ref<string>} */
  const listResumeRoomId = ref('');

  const managedShellConfirmVisible = ref(false);
  const managedShellConfirmSubmitting = ref(false);
  const managedShellConfirmError = ref('');
  /** @type {import('vue').Ref<object|null>} */
  const managedShellRoom = ref(null);
  const switchRoomConfirmVisible = ref(false);
  const switchRoomConfirmSubmitting = ref(false);
  const switchRoomConfirmError = ref('');
  /** @type {import('vue').Ref<string>} */
  const pendingJoinRoomId = ref('');
  /** @type {import('vue').Ref<object|null>} */
  const pendingLeaveActiveRoom = ref(null);
  const managedShellSwitchConfirmVisible = ref(false);
  const managedShellSwitchConfirmSubmitting = ref(false);
  const managedShellSwitchConfirmError = ref('');
  /** @type {import('vue').Ref<string>} */
  const pendingManagedShellRoomId = ref('');
  /** @type {import('vue').Ref<object|null>} */
  const pendingManagedShellActiveRoom = ref(null);

  const currentPlayerId = computed(() => roomAccessService.getCurrentPlayerId());

  /**
   * @param {object|null|undefined} room
   * @returns {boolean}
   */
  function isUserInRoom(room) {
    const playerId = currentPlayerId.value;
    if (!playerId || !room?.members) {
      return false;
    }
    return room.members.some((item) => {
      const samePlayer = String(item?.playerId || '').trim() === playerId;
      return samePlayer && String(item?.managedMode || '').trim() !== 'shell';
    });
  }

  const selectedRoomIsMember = computed(() => isUserInRoom(selectedListRoom.value));
  const selectedRoomIsManagedShell = computed(() => {
    const playerId = currentPlayerId.value;
    const room = selectedListRoom.value;
    if (!playerId || !room?.members) {
      return false;
    }
    return room.members.some((item) => {
      const samePlayer = String(item?.playerId || '').trim() === playerId;
      return samePlayer && String(item?.managedMode || '').trim() === 'shell';
    });
  });

  const selectedRoomStatus = computed(() => String(selectedListRoom.value?.status || '').trim());

  const selectedRoomPrimaryAction = computed(() => {
    const room = selectedListRoom.value;
    if (!room || listDetailLoading.value) {
      return { text: '加入房间', disabled: true };
    }
    const status = selectedRoomStatus.value;
    if (selectedRoomIsMember.value) {
      if (status === 'waiting') {
        return { text: '进入房间', disabled: false };
      }
      if (status === 'playing') {
        return { text: '回到对局', disabled: false };
      }
      return { text: '进入房间', disabled: true };
    }
    if (selectedRoomIsManagedShell.value) {
      return { text: '恢复对局', disabled: status !== 'playing' };
    }
    if (status === 'playing') {
      return { text: '', disabled: true };
    }
    const memberCount = Number(room.memberCount) || 0;
    const maxPlayers = Number(room.maxPlayers) || 0;
    const canJoin = status === 'waiting' && maxPlayers > 0 && memberCount < maxPlayers;
    return { text: '加入房间', disabled: !canJoin };
  });

  const listBusy = computed(() => loading.value || activeRoomReturning.value || activeRoomLeaving.value || createSubmitting.value || listDetailLoading.value || listDetailJoining.value || activePlayingConfirmSubmitting.value || listResumeConfirmSubmitting.value || managedShellConfirmSubmitting.value || switchRoomConfirmSubmitting.value || managedShellSwitchConfirmSubmitting.value);
  /**
   * 取消活跃房间查询并复位大厅弹窗；不发送退出房间命令。
   * @returns {void}
   */
  function resetDialogs() {
    createDialogVisible.value = false;
    createSubmitting.value = false;
    createError.value = '';
    listDetailVisible.value = false;
    listDetailLoading.value = false;
    listDetailJoining.value = false;
    selectedListRoom.value = null;
    resetActiveRoom();
    activePlayingConfirmVisible.value = false;
    activePlayingConfirmSubmitting.value = false;
    activePlayingConfirmError.value = '';
    listResumeConfirmVisible.value = false;
    listResumeConfirmSubmitting.value = false;
    listResumeConfirmError.value = '';
    listResumeRoomId.value = '';
    managedShellConfirmVisible.value = false;
    managedShellConfirmSubmitting.value = false;
    managedShellConfirmError.value = '';
    managedShellRoom.value = null;
    switchRoomConfirmVisible.value = false;
    switchRoomConfirmSubmitting.value = false;
    switchRoomConfirmError.value = '';
    pendingJoinRoomId.value = '';
    pendingLeaveActiveRoom.value = null;
    managedShellSwitchConfirmVisible.value = false;
    managedShellSwitchConfirmSubmitting.value = false;
    managedShellSwitchConfirmError.value = '';
    pendingManagedShellRoomId.value = '';
    pendingManagedShellActiveRoom.value = null;
  }
  async function onSelectListRoom(room) {
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const roomId = String(room?.roomId || '').trim();
    if (!roomId || onlineBlocked.value || listBusy.value) {
      return;
    }
    selectedListRoom.value = null;
    listDetailVisible.value = true;
    listDetailLoading.value = true;
    loadError.value = '';
    try {
      const detail = await roomQueryService.loadRoomDetail(roomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      selectedListRoom.value = detail;
    } catch (err) {
      if (!operation.isCurrent()) return;
      loadError.value = err?.message || '加载房间详情失败';
      listDetailVisible.value = false;
    } finally {
      if (operation.isCurrent()) listDetailLoading.value = false;
    }
  }

  function closeListDetailDialog() {
    if (listDetailJoining.value || listDetailLoading.value) {
      return;
    }
    listDetailVisible.value = false;
    selectedListRoom.value = null;
  }

  /**
   * 按详情能力进入房间或查询权威归属后加入；失败查询不会当作空闲成员。
   * @returns {Promise<void>} 只在当前页面上下文执行后续确认与导航。
   */
  async function onListDetailPrimaryAction() {
    const operation = context.capture();
    if (!operation.isCurrent() || listBusy.value) return;
    const room = selectedListRoom.value;
    const roomId = String(room?.roomId || '').trim();
    const action = selectedRoomPrimaryAction.value;
    if (!roomId || action.disabled) {
      return;
    }

    if (selectedRoomIsMember.value) {
      if (selectedRoomStatus.value === 'waiting') {
        listDetailVisible.value = false;
        selectedListRoom.value = null;
        await navigateToRoom(roomId);
        return;
      }
      if (selectedRoomStatus.value === 'playing') {
        listResumeRoomId.value = roomId;
        listResumeConfirmVisible.value = true;
        listResumeConfirmError.value = '';
        return;
      }
      return;
    }
    if (selectedRoomIsManagedShell.value) {
      managedShellRoom.value = room;
      managedShellConfirmVisible.value = true;
      managedShellConfirmError.value = '';
      return;
    }

    listDetailJoining.value = true;
    loadError.value = '';
    try {
      const currentActiveRoom = await roomQueryService.loadMyActiveRoom({ signal: operation.signal });
      if (!operation.isCurrent()) return;
      if (currentActiveRoom && currentActiveRoom.roomId !== roomId) {
        pendingJoinRoomId.value = roomId;
        pendingLeaveActiveRoom.value = currentActiveRoom;
        switchRoomConfirmVisible.value = true;
        switchRoomConfirmError.value = '';
        return;
      }
      if (currentActiveRoom && currentActiveRoom.roomId === roomId) {
        if (String(currentActiveRoom.status || '').trim() === 'playing') {
          listResumeRoomId.value = roomId;
          listResumeConfirmVisible.value = true;
          listResumeConfirmError.value = '';
          return;
        }
        listDetailVisible.value = false;
        selectedListRoom.value = null;
        await navigateToRoom(roomId);
        return;
      }
      const joinedRoom = await roomService.joinRoom(roomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      listDetailVisible.value = false;
      selectedListRoom.value = null;
      await navigateToRoom(joinedRoom.roomId);
    } catch (err) {
      if (!operation.isCurrent()) return;
      if (err?.name !== 'AbortError') loadError.value = err?.message || '加入房间失败';
    } finally {
      if (operation.isCurrent()) listDetailJoining.value = false;
    }
  }

  /**
   * 进入已确认活跃对局，导航使用该房间的游戏编码。
   * @returns {Promise<void>}
   */
  async function onConfirmActivePlaying() {
    if (listBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const roomId = String(activeRoom.value?.roomId || '').trim();
    if (!roomId) {
      activePlayingConfirmVisible.value = false;
      return;
    }
    activePlayingConfirmSubmitting.value = true;
    activePlayingConfirmError.value = '';
    try {
      activePlayingConfirmVisible.value = false;
      await navigateToPlay(roomId, activeRoom.value.gameCode || '');
    } catch (err) {
      if (!operation.isCurrent()) return;
      activePlayingConfirmError.value = err?.message || '进入对局失败';
      activePlayingConfirmVisible.value = true;
    } finally {
      if (operation.isCurrent()) activePlayingConfirmSubmitting.value = false;
    }
  }

  /**
   * 明确点击退出入口后打开通用确认；关闭恢复提醒不调用此入口。
   * @returns {void} 此步骤不发送成员命令。
   */
  function onDeclineActivePlaying() {
    if (listBusy.value) return;
    onRequestLeaveActiveRoom();
    activePlayingConfirmVisible.value = false;
  }

  /**
   * 关闭自动恢复提醒，不改变成员归属，也不触发退出确认。
   * @returns {void}
   */
  function onDismissActivePlaying() {
    if (activePlayingConfirmSubmitting.value) return;
    activePlayingConfirmVisible.value = false;
    activePlayingConfirmError.value = '';
  }

  async function onConfirmListResumePlaying() {
    if (listBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const roomId = listResumeRoomId.value;
    if (!roomId) {
      return;
    }
    listResumeConfirmSubmitting.value = true;
    listResumeConfirmError.value = '';
    try {
      listResumeConfirmVisible.value = false;
      listDetailVisible.value = false;
      selectedListRoom.value = null;
      await navigateToPlay(roomId);
    } catch (err) {
      if (!operation.isCurrent()) return;
      listResumeConfirmError.value = err?.message || '进入对局失败';
      listResumeConfirmVisible.value = true;
    } finally {
      if (operation.isCurrent()) listResumeConfirmSubmitting.value = false;
    }
  }

  function onCancelListResumePlaying() {
    if (listResumeConfirmSubmitting.value) {
      return;
    }
    listResumeConfirmVisible.value = false;
    listResumeRoomId.value = '';
    listResumeConfirmError.value = '';
  }

  /**
   * 查询共享成员归属后恢复席位，有其他房间时交给切换确认。
   * @returns {Promise<void>} 所有后续操作受页面上下文约束。
   */
  async function onConfirmManagedShellResume() {
    if (listBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const roomId = String(managedShellRoom.value?.roomId || '').trim();
    if (!roomId) {
      managedShellConfirmVisible.value = false;
      return;
    }
    managedShellConfirmSubmitting.value = true;
    managedShellConfirmError.value = '';
    try {
      const currentActiveRoom = await roomQueryService.loadMyActiveRoom({ signal: operation.signal });
      if (!operation.isCurrent()) return;
      if (!currentActiveRoom) {
        const room = await roomService.rejoinManagedRoom(roomId, { signal: operation.signal });
        if (!operation.isCurrent()) return;
        managedShellConfirmVisible.value = false;
        managedShellRoom.value = null;
        await navigateToPlay(room.roomId);
        return;
      }
      if (String(currentActiveRoom.roomId || '').trim() === roomId) {
        managedShellConfirmVisible.value = false;
        managedShellRoom.value = null;
        await navigateToPlay(roomId);
        return;
      }
      pendingManagedShellRoomId.value = roomId;
      pendingManagedShellActiveRoom.value = currentActiveRoom;
      managedShellConfirmVisible.value = false;
      managedShellSwitchConfirmVisible.value = true;
      managedShellSwitchConfirmError.value = '';
    } catch (err) {
      if (!operation.isCurrent()) return;
      if (err?.name !== 'AbortError') managedShellConfirmError.value = err?.message || '恢复对局失败';
    } finally {
      if (operation.isCurrent()) managedShellConfirmSubmitting.value = false;
    }
  }

  async function onConfirmSwitchRoom() {
    if (listBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const targetRoomId = String(pendingJoinRoomId.value || '').trim();
    const activeRoomId = String(pendingLeaveActiveRoom.value?.roomId || '').trim();
    if (!targetRoomId || !activeRoomId) {
      switchRoomConfirmVisible.value = false;
      return;
    }
    switchRoomConfirmSubmitting.value = true;
    switchRoomConfirmError.value = '';
    try {
      await roomService.leaveRoom(activeRoomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      const joinedRoom = await roomService.joinRoom(targetRoomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      switchRoomConfirmVisible.value = false;
      pendingJoinRoomId.value = '';
      pendingLeaveActiveRoom.value = null;
      listDetailVisible.value = false;
      selectedListRoom.value = null;
      await navigateToRoom(joinedRoom.roomId);
    } catch (err) {
      if (!operation.isCurrent()) return;
      switchRoomConfirmError.value = err?.message || '切换房间失败';
    } finally {
      if (operation.isCurrent()) switchRoomConfirmSubmitting.value = false;
    }
  }

  function onCancelSwitchRoom() {
    if (switchRoomConfirmSubmitting.value) {
      return;
    }
    switchRoomConfirmVisible.value = false;
    switchRoomConfirmError.value = '';
    pendingJoinRoomId.value = '';
    pendingLeaveActiveRoom.value = null;
  }

  async function onConfirmManagedShellSwitch() {
    if (listBusy.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    const managedRoomId = String(pendingManagedShellRoomId.value || '').trim();
    const activeRoomId = String(pendingManagedShellActiveRoom.value?.roomId || '').trim();
    if (!managedRoomId || !activeRoomId) {
      managedShellSwitchConfirmVisible.value = false;
      return;
    }
    managedShellSwitchConfirmSubmitting.value = true;
    managedShellSwitchConfirmError.value = '';
    try {
      await roomService.leaveRoom(activeRoomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      const room = await roomService.rejoinManagedRoom(managedRoomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      managedShellSwitchConfirmVisible.value = false;
      pendingManagedShellRoomId.value = '';
      pendingManagedShellActiveRoom.value = null;
      managedShellConfirmVisible.value = false;
      managedShellRoom.value = null;
      await navigateToPlay(room.roomId);
    } catch (err) {
      if (!operation.isCurrent()) return;
      managedShellSwitchConfirmError.value = err?.message || '恢复对局失败';
    } finally {
      if (operation.isCurrent()) managedShellSwitchConfirmSubmitting.value = false;
    }
  }

  function onCancelManagedShellResume() {
    if (managedShellConfirmSubmitting.value) {
      return;
    }
    managedShellConfirmVisible.value = false;
    managedShellConfirmError.value = '';
  }

  function onCancelManagedShellSwitch() {
    if (managedShellSwitchConfirmSubmitting.value) {
      return;
    }
    managedShellSwitchConfirmVisible.value = false;
    managedShellSwitchConfirmError.value = '';
    pendingManagedShellRoomId.value = '';
    pendingManagedShellActiveRoom.value = null;
  }

  function openCreateDialog() {
    if (onlineBlocked.value || listBusy.value) return;
    createError.value = '';
    createDialogVisible.value = true;
  }

  function closeCreateDialog() {
    if (createSubmitting.value) {
      return;
    }
    createDialogVisible.value = false;
    createError.value = '';
  }

  /**
   * 创建房间；成员归属对账由通用服务完成，页面只展示原命令结果。
   * @param {object} payload 用户填写的名称与房间配置。
   * @returns {Promise<void>} 成功后导航，失败保留表单和错误，不自动退出旧房间。
   */
  async function onCreateRoom(payload) {
    if (createSubmitting.value || onlineBlocked.value) return;
    const operation = context.capture();
    if (!operation.isCurrent()) return;
    if (!gameCode.value) {
      createError.value = '缺少 gameCode';
      return;
    }
    createSubmitting.value = true;
    createError.value = '';
    try {
      const room = await roomService.createRoom({
        gameCode: gameCode.value,
        mode: resolveOnlineRoomMode(gameCode.value),
        roomName: payload?.roomName,
        roomConfig: payload?.roomConfig
      }, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      createDialogVisible.value = false;
      await navigateToRoom(room.roomId);
    } catch (err) {
      if (!operation.isCurrent()) return;
      createError.value = err?.message || '创建房间失败';
    } finally {
      if (operation.isCurrent()) createSubmitting.value = false;
    }
  }
  return {
    createDialogVisible,
    createSubmitting,
    createError,
    listDetailVisible,
    listDetailLoading,
    listDetailJoining,
    selectedListRoom,
    activeRoom,
    activeRoomError,
    activeRoomLeaving,
    activeRoomLeaveVisible,
    activeRoomLeaveError,
    activeRoomLeaveMessage,
    onRequestLeaveActiveRoom,
    onCancelLeaveActiveRoom,
    onConfirmLeaveActiveRoom,
    currentPlayerId,
    refreshActiveRoom,
    onReturnActiveRoom,
    activePlayingConfirmVisible,
    activePlayingConfirmSubmitting,
    activePlayingConfirmError,
    listResumeConfirmVisible,
    listResumeConfirmSubmitting,
    listResumeConfirmError,
    managedShellConfirmVisible,
    managedShellConfirmSubmitting,
    managedShellConfirmError,
    managedShellRoom,
    switchRoomConfirmVisible,
    switchRoomConfirmSubmitting,
    switchRoomConfirmError,
    managedShellSwitchConfirmVisible,
    managedShellSwitchConfirmSubmitting,
    managedShellSwitchConfirmError,
    selectedRoomPrimaryAction,
    listBusy,
    resetDialogs,
    onSelectListRoom,
    closeListDetailDialog,
    onListDetailPrimaryAction,
    onConfirmActivePlaying,
    onDeclineActivePlaying,
    onDismissActivePlaying,
    onConfirmListResumePlaying,
    onCancelListResumePlaying,
    onConfirmManagedShellResume,
    onConfirmSwitchRoom,
    onCancelSwitchRoom,
    onConfirmManagedShellSwitch,
    onCancelManagedShellResume,
    onCancelManagedShellSwitch,
    openCreateDialog,
    closeCreateDialog,
    onCreateRoom
  };
}
