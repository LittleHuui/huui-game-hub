<template>
  <RoomWaitingPage
    v-if="ready && room"
    :room="room"
    :current-player-id="currentPlayerId"
    :room-rule="roomRule"
    :actions-disabled="actionBusy"
    @detail="onOpenDetail"
    @leave="onLeaveRoom"
    @invite="onInvite"
    @start="onStartGame"
    @add-ai="onAddAi"
    @settings="settingsVisible = true"
    @remove-member="onRemoveMemberRequest"
  />
  <div v-else class="room-hub-page room-hub-page--waiting">
    <p class="empty-text">{{ statusText }}</p>
  </div>

  <RoomDetailDialog
    :visible="detailVisible"
    scene="waiting"
    :room="room"
    :room-config-schema="roomConfigSchema"
    @close="detailVisible = false"
  />

  <RoomConfigSettingsDialog
    :visible="settingsVisible"
    :room="room"
    :room-rule="roomRule"
    :room-config-schema="roomConfigSchema"
    :submitting="settingsSubmitting"
    @close="settingsVisible = false"
    @submit="onRoomSettingsSubmit"
  />

  <AppModal
    :visible="removeMemberConfirmVisible"
    title="移除成员"
    @close="onCancelRemoveMember"
  >
    <div class="room-hub-form">
      <p class="muted-small">{{ removeMemberConfirmMessage }}</p>
      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="actionBusy"
          @click="onConfirmRemoveMember"
        >
          {{ actionBusy ? '处理中…' : '确认移除' }}
        </button>
      </div>
    </div>
  </AppModal>

  <AppModal
    :visible="aiRemoveConfirmVisible"
    title="保存房间设置"
    @close="onCancelAiRemoveConfirm"
  >
    <div class="room-hub-form">
      <p class="muted-small">保存后将移除 {{ pendingAiRemoveCount }} 名 AI，是否继续？</p>
      <div class="room-hub-form__actions">
        <button
          type="button"
          class="game-action-btn game-action-btn--primary game-action-btn--sm"
          :disabled="settingsSubmitting"
          @click="onConfirmAiRemoveAndSave"
        >
          {{ settingsSubmitting ? '保存中…' : '确认保存' }}
        </button>
      </div>
    </div>
  </AppModal>

  <RoomInviteDialog
    :visible="inviteDialogVisible"
    :users="inviteUsers"
    :loading="inviteLoading"
    :submitting="inviteSubmitting"
    :error-message="inviteError"
    @close="inviteDialogVisible = false"
    @refresh="loadInviteUsers"
    @invite="onInviteUser"
  />
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import AppModal from '../components/AppModal.vue';
import RoomWaitingPage from '../components/game-hub/room/RoomWaitingPage.vue';
import RoomDetailDialog from '../components/game-hub/room/RoomDetailDialog.vue';
import RoomInviteDialog from '../components/game-hub/room/RoomInviteDialog.vue';
import RoomConfigSettingsDialog from '../components/game-hub/room/RoomConfigSettingsDialog.vue';
import { usePlatformStore } from '../stores/platformStore.js';
import { useRoomStore } from '../stores/roomStore.js';
import * as roomService from '../services/roomService.js';
import { loadOnlineRuleDefinition } from '../services/onlineRoomService.js';
import { canFetchRemote } from '../services/remoteGate.js';
import { estimateAiRemovalOnMaxPlayersChange } from '../utils/roomConfigFormUtils.js';
import * as toastService from '../services/toastService.js';
import '../components/game-hub/room/roomHub.css';

const route = useRoute();
const router = useRouter();
const platform = usePlatformStore();
const roomStore = useRoomStore();
const { currentRoom, roomRule, roomConfigSchema } = storeToRefs(roomStore);

const onlineBlocked = computed(() => !canFetchRemote());
const gameCode = computed(() => String(route.params.gameCode || '').trim());
const roomId = computed(() => String(route.params.roomId || '').trim());
const ready = ref(false);
const loading = ref(false);
const actionBusy = ref(false);
const errorMessage = ref('');

const detailVisible = ref(false);
const settingsVisible = ref(false);
const settingsSubmitting = ref(false);
const inviteDialogVisible = ref(false);
const inviteUsers = ref([]);
const inviteLoading = ref(false);
const inviteSubmitting = ref(false);
const inviteError = ref('');

const removeMemberConfirmVisible = ref(false);
const removeMemberTargetId = ref('');
const removeMemberConfirmMessage = ref('确认移除该玩家？');

const aiRemoveConfirmVisible = ref(false);
const pendingSettingsPayload = ref(null);
const pendingAiRemoveCount = ref(0);

/** @type {(() => void)|null} */
let releaseRoomRealtime = null;

const room = computed(() => currentRoom.value);
const currentPlayerId = computed(() => roomService.getCurrentPlayerId());

const statusText = computed(() => {
  if (onlineBlocked.value) {
    return '当前为本地模式，在线房间不可用。';
  }
  if (loading.value) {
    return '正在加载房间信息...';
  }
  if (errorMessage.value) {
    return errorMessage.value;
  }
  return '正在进入房间...';
});

/**
 * @param {object|null|undefined} value
 */
function isUserInRoom(value) {
  const playerId = currentPlayerId.value;
  if (!playerId || !value?.members) {
    return false;
  }
  return value.members.some((item) => {
    const samePlayer = String(item?.playerId || '').trim() === playerId;
    const isShell = String(item?.managedMode || '').trim() === 'shell';
    return samePlayer && !isShell;
  });
}

const isRoomMember = computed(() => isUserInRoom(room.value));

async function navigateLobby() {
  if (!gameCode.value) {
    return;
  }
  await router.push({ name: 'online-room-list', params: { gameCode: gameCode.value } });
}

async function navigatePlayRoom() {
  if (!gameCode.value || !roomId.value) {
    return;
  }
  await router.push({
    name: 'online-play-entry',
    params: { gameCode: gameCode.value, roomId: roomId.value }
  });
}

async function ensureRoomContext() {
  const id = roomId.value;
  if (!id || !gameCode.value || onlineBlocked.value) {
    errorMessage.value = id ? '房间不可用' : '房间 ID 无效';
    await navigateLobby();
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  try {
    await loadOnlineRuleDefinition(gameCode.value);
    await roomService.loadRoomDetail(id);
    if (!room.value) {
      errorMessage.value = '房间不存在或已被删除';
      await navigateLobby();
      return;
    }
    if (!isRoomMember.value) {
      errorMessage.value = '你尚未加入该房间';
      await navigateLobby();
      return;
    }
    ready.value = true;
  } catch (err) {
    errorMessage.value = err?.message || '加载房间失败';
    await navigateLobby();
  } finally {
    loading.value = false;
  }
}

function onOpenDetail() {
  detailVisible.value = true;
}

async function onLeaveRoom() {
  const id = roomId.value;
  if (!id) {
    await navigateLobby();
    return;
  }
  actionBusy.value = true;
  errorMessage.value = '';
  try {
    await roomService.leaveRoom(id);
    await navigateLobby();
  } catch (err) {
    errorMessage.value = err?.message || '离开房间失败';
  } finally {
    actionBusy.value = false;
  }
}

/**
 * @param {string} targetPlayerId
 */
function onRemoveMemberRequest(targetPlayerId) {
  const normalizedTargetId = String(targetPlayerId || '').trim();
  if (!normalizedTargetId || !isRoomMember.value) {
    return;
  }
  const members = Array.isArray(room.value?.members) ? room.value.members : [];
  const target = members.find((item) => String(item?.playerId || '').trim() === normalizedTargetId);
  removeMemberTargetId.value = normalizedTargetId;
  removeMemberConfirmMessage.value = target?.isAi ? '确认移除该 AI？' : '确认移除该玩家？';
  removeMemberConfirmVisible.value = true;
}

function onCancelRemoveMember() {
  removeMemberConfirmVisible.value = false;
  removeMemberTargetId.value = '';
}

async function onConfirmRemoveMember() {
  const id = roomId.value;
  const normalizedTargetId = removeMemberTargetId.value;
  if (!id || !normalizedTargetId) {
    onCancelRemoveMember();
    return;
  }
  actionBusy.value = true;
  errorMessage.value = '';
  try {
    await roomService.removeRoomMember(id, normalizedTargetId);
    await roomService.loadRoomDetail(id);
    onCancelRemoveMember();
  } catch (err) {
    toastService.push(err?.message || '移除玩家失败', 'error');
  } finally {
    actionBusy.value = false;
  }
}

/**
 * @param {{ error?: string; maxPlayers?: number; roomConfig?: object }} payload
 */
async function onRoomSettingsSubmit(payload) {
  if (payload?.error) {
    toastService.push(payload.error, 'warning');
    return;
  }
  const id = roomId.value;
  if (!id || !isRoomMember.value || !payload) {
    return;
  }
  const aiRemoveCount = estimateAiRemovalOnMaxPlayersChange(room.value, payload.maxPlayers);
  if (aiRemoveCount > 0) {
    pendingSettingsPayload.value = payload;
    pendingAiRemoveCount.value = aiRemoveCount;
    aiRemoveConfirmVisible.value = true;
    return;
  }
  await saveRoomSettings(payload);
}

function onCancelAiRemoveConfirm() {
  aiRemoveConfirmVisible.value = false;
  pendingSettingsPayload.value = null;
  pendingAiRemoveCount.value = 0;
}

async function onConfirmAiRemoveAndSave() {
  const payload = pendingSettingsPayload.value;
  if (!payload) {
    onCancelAiRemoveConfirm();
    return;
  }
  await saveRoomSettings(payload);
  onCancelAiRemoveConfirm();
}

/**
 * @param {{ maxPlayers?: number; roomConfig?: object }} payload
 */
async function saveRoomSettings(payload) {
  const id = roomId.value;
  if (!id || !isRoomMember.value) {
    return;
  }
  settingsSubmitting.value = true;
  try {
    await roomService.updateRoomConfig(id, payload);
    await roomService.loadRoomDetail(id);
    settingsVisible.value = false;
  } catch (err) {
    toastService.push(err?.message || '保存房间设置失败', 'error');
  } finally {
    settingsSubmitting.value = false;
  }
}

async function onAddAi() {
  const id = roomId.value;
  if (!id || !isRoomMember.value) {
    return;
  }
  actionBusy.value = true;
  errorMessage.value = '';
  try {
    await roomService.addRoomAi(id);
    await roomService.loadRoomDetail(id);
  } catch (err) {
    errorMessage.value = err?.message || '添加 AI 失败';
  } finally {
    actionBusy.value = false;
  }
}

async function onStartGame() {
  const id = roomId.value;
  if (!id || !isRoomMember.value) {
    return;
  }
  actionBusy.value = true;
  errorMessage.value = '';
  try {
    await roomService.startRoomGame(id);
    await roomService.loadRoomDetail(id);
    const status = String(room.value?.status || '').trim();
    if (status === 'playing') {
      await navigatePlayRoom();
    }
  } catch (err) {
    errorMessage.value = err?.message || '开始游戏失败';
  } finally {
    actionBusy.value = false;
  }
}

async function loadInviteUsers() {
  const id = roomId.value;
  if (!id) {
    return;
  }
  inviteLoading.value = true;
  inviteError.value = '';
  try {
    inviteUsers.value = await roomService.loadInviteCandidates(id);
  } catch (err) {
    inviteUsers.value = [];
    inviteError.value = err?.message || '加载在线用户失败';
  } finally {
    inviteLoading.value = false;
  }
}

function onInvite() {
  if (!room.value || !isRoomMember.value) {
    return;
  }
  inviteError.value = '';
  inviteDialogVisible.value = true;
  void loadInviteUsers();
}

/**
 * @param {{ serviceId: string; nickname: string }} user
 */
async function onInviteUser(user) {
  const id = roomId.value;
  if (!id || !user?.serviceId) {
    return;
  }
  inviteSubmitting.value = true;
  try {
    roomService.sendRoomInvite(id, {
      serviceId: user.serviceId,
      nickname: user.nickname
    });
    inviteDialogVisible.value = false;
  } catch (err) {
    inviteError.value = err?.message || '邀请失败';
  } finally {
    inviteSubmitting.value = false;
  }
}

onMounted(async () => {
  if (!gameCode.value) {
    return;
  }
  platform.setCurrentGame(gameCode.value);
  if (onlineBlocked.value) {
    return;
  }
  const id = roomId.value;
  if (!id) {
    await navigateLobby();
    return;
  }
  if (releaseRoomRealtime) {
    releaseRoomRealtime();
    releaseRoomRealtime = null;
  }
  releaseRoomRealtime = roomService.bindRoomRealtime(id);
  await ensureRoomContext();
});

watch(
  () => room.value?.status,
  (status) => {
    const normalized = String(status || '').trim();
    if (!roomId.value) {
      return;
    }
    if (normalized === 'playing') {
      void navigatePlayRoom();
    }
  }
);

onUnmounted(() => {
  if (releaseRoomRealtime) {
    releaseRoomRealtime();
    releaseRoomRealtime = null;
  }
});
</script>
