<template>
  <div>
    <RoomListPage
      :title="pageTitle"
      :subtitle="pageSubtitle"
      :game-code="gameCode"
      :rooms="rooms"
      :room-config-schema="roomConfigSchema"
      :loading="loading || roomsLoading"
      :disabled="onlineBlocked || loading"
      :error-message="roomListErrorMessage"
      @refresh="onRefreshRooms"
      @create="openCreateDialog"
      @select-room="onSelectListRoom"
    />

    <CreateRoomDialog
      :visible="createDialogVisible"
      :room-config-schema="roomConfigSchema"
      :submitting="createSubmitting"
      :error-message="createError"
      @close="closeCreateDialog"
      @submit="onCreateRoom"
    />

    <RoomDetailDialog
      :visible="listDetailVisible"
      scene="list"
      :room="selectedListRoom"
      :room-config-schema="roomConfigSchema"
      :primary-action-text="selectedRoomPrimaryAction.text"
      :primary-action-disabled="selectedRoomPrimaryAction.disabled || listDetailLoading"
      :primary-action-loading="listDetailJoining || listDetailLoading"
      :primary-action-loading-text="listDetailLoading ? '加载中…' : '处理中…'"
      @close="closeListDetailDialog"
      @primary-action="onListDetailPrimaryAction"
    />

    <RoomResumePlayingDialog
      :visible="activePlayingConfirmVisible"
      :submitting="activePlayingConfirmSubmitting"
      :error-message="activePlayingConfirmError"
      @confirm="onConfirmActivePlaying"
      @cancel="onDeclineActivePlaying"
    />

    <RoomResumePlayingDialog
      :visible="listResumeConfirmVisible"
      title="回到对局"
      message="该房间对局进行中，是否回到对局？"
      confirm-text="回到对局"
      cancel-text="取消"
      :submitting="listResumeConfirmSubmitting"
      :error-message="listResumeConfirmError"
      @confirm="onConfirmListResumePlaying"
      @cancel="onCancelListResumePlaying"
    />

    <RoomResumePlayingDialog
      :visible="managedShellConfirmVisible"
      title="恢复对局"
      message="检测到你有可恢复的对局，是否回到原座位？"
      confirm-text="恢复并进入"
      cancel-text="暂不处理"
      :submitting="managedShellConfirmSubmitting"
      :error-message="managedShellConfirmError"
      @confirm="onConfirmManagedShellResume"
      @cancel="onCancelManagedShellResume"
    />

    <RoomResumePlayingDialog
      :visible="switchRoomConfirmVisible"
      title="切换房间"
      message="你已在其他房间中，加入新房间将退出当前房间，是否继续？"
      confirm-text="继续"
      cancel-text="取消"
      :submitting="switchRoomConfirmSubmitting"
      :error-message="switchRoomConfirmError"
      @confirm="onConfirmSwitchRoom"
      @cancel="onCancelSwitchRoom"
    />

    <RoomResumePlayingDialog
      :visible="managedShellSwitchConfirmVisible"
      title="恢复对局"
      message="你已在其他房间中，恢复原对局将退出当前房间，是否继续？"
      confirm-text="继续恢复"
      cancel-text="取消"
      :submitting="managedShellSwitchConfirmSubmitting"
      :error-message="managedShellSwitchConfirmError"
      @confirm="onConfirmManagedShellSwitch"
      @cancel="onCancelManagedShellSwitch"
    />
  </div>
</template>

<script setup>
import { computed, onActivated, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import RoomListPage from '../components/game-hub/room/RoomListPage.vue';
import RoomDetailDialog from '../components/game-hub/room/RoomDetailDialog.vue';
import CreateRoomDialog from '../components/game-hub/room/CreateRoomDialog.vue';
import RoomResumePlayingDialog from '../components/game-hub/room/RoomResumePlayingDialog.vue';
import { usePlatformStore } from '../stores/platformStore.js';
import * as roomService from '../services/roomService.js';
import { canFetchRemote } from '../services/remoteGate.js';
import { useRoomStore } from '../stores/roomStore.js';
import { loadOnlineRuleDefinition, resolveOnlineRoomMode } from '../services/onlineRoomService.js';

const route = useRoute();
const router = useRouter();
const platform = usePlatformStore();
const roomStore = useRoomStore();
const { rooms, roomsLoading, roomsError, roomConfigSchema } = storeToRefs(roomStore);

const loading = ref(false);
const loadError = ref('');
const createDialogVisible = ref(false);
const createSubmitting = ref(false);
const createError = ref('');
const listDetailVisible = ref(false);
const listDetailLoading = ref(false);
const listDetailJoining = ref(false);
/** @type {import('vue').Ref<object|null>} */
const selectedListRoom = ref(null);
/** @type {import('vue').Ref<object|null>} */
const activeRoom = ref(null);

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

/** @type {(() => void)|null} */
let releaseRoomRealtime = null;

const onlineBlocked = computed(() => !canFetchRemote());
const gameCode = computed(() => String(route.params.gameCode || '').trim());
const pageTitle = computed(() => '房间列表');
const pageSubtitle = computed(() => '');
const roomListErrorMessage = computed(() => {
  if (onlineBlocked.value) {
    return '当前为本地模式，在线房间不可用。';
  }
  if (loadError.value) {
    return loadError.value;
  }
  return roomsError.value;
});

const currentPlayerId = computed(() => roomService.getCurrentPlayerId());

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

/**
 * @param {string} roomId
 */
async function navigateToRoom(roomId) {
  const normalized = String(roomId || '').trim();
  if (!normalized || !gameCode.value) {
    return;
  }
  await router.push({
    name: 'online-room-waiting',
    params: { gameCode: gameCode.value, roomId: normalized }
  });
}

/**
 * @param {string} roomId
 */
async function navigateToPlay(roomId) {
  const normalized = String(roomId || '').trim();
  if (!normalized || !gameCode.value) {
    return;
  }
  await router.push({
    name: 'online-play-entry',
    params: { gameCode: gameCode.value, roomId: normalized }
  });
}

/**
 * @param {object} room
 */
async function onSelectListRoom(room) {
  const roomId = String(room?.roomId || '').trim();
  if (!roomId) {
    return;
  }
  selectedListRoom.value = null;
  listDetailVisible.value = true;
  listDetailLoading.value = true;
  loadError.value = '';
  try {
    const detail = await roomService.loadRoomDetail(roomId);
    selectedListRoom.value = detail;
  } catch (err) {
    loadError.value = err?.message || '加载房间详情失败';
    listDetailVisible.value = false;
  } finally {
    listDetailLoading.value = false;
  }
}

function closeListDetailDialog() {
  if (listDetailJoining.value || listDetailLoading.value) {
    return;
  }
  listDetailVisible.value = false;
  selectedListRoom.value = null;
}

async function onListDetailPrimaryAction() {
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
    const currentActiveRoom = await roomService.loadMyActiveRoom();
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
    const joinedRoom = await roomService.joinRoom(roomId);
    listDetailVisible.value = false;
    selectedListRoom.value = null;
    await navigateToRoom(joinedRoom.roomId);
  } catch (err) {
    loadError.value = err?.message || '加入房间失败';
  } finally {
    listDetailJoining.value = false;
  }
}

async function onConfirmActivePlaying() {
  const roomId = String(activeRoom.value?.roomId || '').trim();
  if (!roomId) {
    activePlayingConfirmVisible.value = false;
    return;
  }
  activePlayingConfirmSubmitting.value = true;
  activePlayingConfirmError.value = '';
  try {
    activePlayingConfirmVisible.value = false;
    await navigateToPlay(roomId);
  } catch (err) {
    activePlayingConfirmError.value = err?.message || '进入对局失败';
    activePlayingConfirmVisible.value = true;
  } finally {
    activePlayingConfirmSubmitting.value = false;
  }
}

async function onDeclineActivePlaying() {
  const roomId = String(activeRoom.value?.roomId || '').trim();
  if (!roomId) {
    activePlayingConfirmVisible.value = false;
    activeRoom.value = null;
    return;
  }
  activePlayingConfirmSubmitting.value = true;
  activePlayingConfirmError.value = '';
  try {
    await roomService.leaveRoom(roomId);
    activeRoom.value = null;
    activePlayingConfirmVisible.value = false;
    await roomService.refreshRoomList(gameCode.value);
  } catch (err) {
    activePlayingConfirmError.value = err?.message || '退出房间失败';
  } finally {
    activePlayingConfirmSubmitting.value = false;
  }
}

async function onConfirmListResumePlaying() {
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
    listResumeConfirmError.value = err?.message || '进入对局失败';
    listResumeConfirmVisible.value = true;
  } finally {
    listResumeConfirmSubmitting.value = false;
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

async function onConfirmManagedShellResume() {
  const roomId = String(managedShellRoom.value?.roomId || '').trim();
  if (!roomId) {
    managedShellConfirmVisible.value = false;
    return;
  }
  managedShellConfirmSubmitting.value = true;
  managedShellConfirmError.value = '';
  try {
    const currentActiveRoom = await roomService.loadMyActiveRoom();
    if (!currentActiveRoom) {
      const room = await roomService.rejoinManagedRoom(roomId);
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
    managedShellConfirmError.value = err?.message || '恢复对局失败';
  } finally {
    managedShellConfirmSubmitting.value = false;
  }
}

async function onConfirmSwitchRoom() {
  const targetRoomId = String(pendingJoinRoomId.value || '').trim();
  const activeRoomId = String(pendingLeaveActiveRoom.value?.roomId || '').trim();
  if (!targetRoomId || !activeRoomId) {
    switchRoomConfirmVisible.value = false;
    return;
  }
  switchRoomConfirmSubmitting.value = true;
  switchRoomConfirmError.value = '';
  try {
    await roomService.leaveRoom(activeRoomId);
    const joinedRoom = await roomService.joinRoom(targetRoomId);
    switchRoomConfirmVisible.value = false;
    pendingJoinRoomId.value = '';
    pendingLeaveActiveRoom.value = null;
    listDetailVisible.value = false;
    selectedListRoom.value = null;
    await navigateToRoom(joinedRoom.roomId);
  } catch (err) {
    switchRoomConfirmError.value = err?.message || '切换房间失败';
  } finally {
    switchRoomConfirmSubmitting.value = false;
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
  const managedRoomId = String(pendingManagedShellRoomId.value || '').trim();
  const activeRoomId = String(pendingManagedShellActiveRoom.value?.roomId || '').trim();
  if (!managedRoomId || !activeRoomId) {
    managedShellSwitchConfirmVisible.value = false;
    return;
  }
  managedShellSwitchConfirmSubmitting.value = true;
  managedShellSwitchConfirmError.value = '';
  try {
    await roomService.leaveRoom(activeRoomId);
    const room = await roomService.rejoinManagedRoom(managedRoomId);
    managedShellSwitchConfirmVisible.value = false;
    pendingManagedShellRoomId.value = '';
    pendingManagedShellActiveRoom.value = null;
    managedShellConfirmVisible.value = false;
    managedShellRoom.value = null;
    await navigateToPlay(room.roomId);
  } catch (err) {
    managedShellSwitchConfirmError.value = err?.message || '恢复对局失败';
  } finally {
    managedShellSwitchConfirmSubmitting.value = false;
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

async function initPage() {
  if (!gameCode.value) {
    loadError.value = '缺少 gameCode';
    return;
  }
  platform.setCurrentGame(gameCode.value);
  if (onlineBlocked.value) {
    return;
  }
  loading.value = true;
  loadError.value = '';
  try {
    await loadOnlineRuleDefinition(gameCode.value);
    await roomService.refreshRoomList(gameCode.value);
    activeRoom.value = await roomService.loadMyActiveRoom();
    if (
      activeRoom.value?.status === 'playing' &&
      String(activeRoom.value?.gameCode || '').trim() === gameCode.value
    ) {
      activePlayingConfirmVisible.value = true;
      activePlayingConfirmError.value = '';
    }
    managedShellRoom.value = await roomService.loadMyManagedShell(gameCode.value);
    if (managedShellRoom.value?.roomId) {
      managedShellConfirmVisible.value = true;
      managedShellConfirmError.value = '';
    }
    releaseRoomRealtime = roomService.bindRoomRealtime(`__lobby__:${gameCode.value}`);
  } catch (err) {
    loadError.value = err?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function onRefreshRooms() {
  if (onlineBlocked.value || !gameCode.value) {
    return;
  }
  try {
    await roomService.refreshRoomList(gameCode.value);
  } catch {
    // 错误信息已由 service 写入 store
  }
}

function openCreateDialog() {
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
 * @param {{ roomName?: string; roomConfig?: object }} payload
 */
async function onCreateRoom(payload) {
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
    });
    createDialogVisible.value = false;
    await navigateToRoom(room.roomId);
  } catch (err) {
    createError.value = err?.message || '创建房间失败';
  } finally {
    createSubmitting.value = false;
  }
}

onMounted(() => {
  initPage();
});

onActivated(() => {
  if (onlineBlocked.value || !gameCode.value) {
    return;
  }
  void roomService.refreshRoomList(gameCode.value);
});

watch(
  () => route.params.gameCode,
  async (next, prev) => {
    if (String(next || '').trim() === String(prev || '').trim()) {
      return;
    }
    if (releaseRoomRealtime) {
      releaseRoomRealtime();
      releaseRoomRealtime = null;
    }
    activePlayingConfirmVisible.value = false;
    activeRoom.value = null;
    managedShellConfirmVisible.value = false;
    managedShellRoom.value = null;
    await initPage();
  }
);

onUnmounted(() => {
  if (releaseRoomRealtime) {
    releaseRoomRealtime();
    releaseRoomRealtime = null;
  }
});
</script>
