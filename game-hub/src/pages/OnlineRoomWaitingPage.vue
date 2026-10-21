<template>
  <div v-if="shellRejoinOffered" class="room-hub-page room-hub-page--waiting">
    <p class="empty-text">你已退出对局，席位由托管保留。</p>
    <div class="room-hub-form__actions">
      <button
        type="button"
        class="game-action-btn game-action-btn--primary game-action-btn--sm"
        :disabled="rejoinBusy"
        @click="onRejoinManagedRoom"
      >
        {{ rejoinBusy ? '处理中…' : '重新加入' }}
      </button>
      <button
        type="button"
        class="game-action-btn game-action-btn--ghost game-action-btn--sm"
        @click="onBackToLobbyFromShell"
      >
        返回大厅
      </button>
    </div>
    <p v-if="errorMessage" class="empty-text">{{ errorMessage }}</p>
  </div>

  <RoomWaitingPage
    v-else-if="ready && room"
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
import { useRoomWaitingCommands } from '../composables/useRoomWaitingCommands.js';
import { useRoomWaitingDialogs } from '../composables/useRoomWaitingDialogs.js';
import { computed, ref, watch } from 'vue';
import { useAsyncContext } from '../composables/useAsyncContext.js';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import AppModal from '../components/AppModal.vue';
import RoomWaitingPage from '../components/game-hub/room/RoomWaitingPage.vue';
import RoomDetailDialog from '../components/game-hub/room/RoomDetailDialog.vue';
import RoomInviteDialog from '../components/game-hub/room/RoomInviteDialog.vue';
import RoomConfigSettingsDialog from '../components/game-hub/room/RoomConfigSettingsDialog.vue';
import { usePlatformStore } from '../stores/platformStore.js';
import { useRoomStore } from '../stores/roomStore.js';
import * as roomAccessService from '../services/roomAccessService.js';
import * as roomQueryService from '../services/roomQueryService.js';
import * as roomRealtimeService from '../services/roomRealtimeService.js';
import { loadOnlineRuleDefinition } from '../services/onlineRoomService.js';
import { canFetchRemote } from '../services/remoteGate.js';
import { resolveGamePlayRoute } from '../games/gameModuleRegistry.js';
import '../components/game-hub/room/roomHub.css';

const context = useAsyncContext();
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
const shellRejoinOffered = ref(false);
const rejoinBusy = ref(false);

const room = computed(() => currentRoom.value?.roomId === roomId.value ? currentRoom.value : null);
const currentPlayerId = computed(() => roomAccessService.getCurrentPlayerId());

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

/**
 * @param {object|null|undefined} value
 */
function isUserShellInRoom(value) {
  const playerId = currentPlayerId.value;
  if (!playerId || !value?.members) {
    return false;
  }
  return value.members.some((item) => {
    const samePlayer = String(item?.playerId || '').trim() === playerId;
    return samePlayer && String(item?.managedMode || '').trim() === 'shell';
  });
}

const isShellMember = computed(() => isUserShellInRoom(room.value));

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
  const playRoute = resolveGamePlayRoute(gameCode.value, roomId.value);
  if (!playRoute) {
    throw new Error('当前游戏不支持在线对战');
  }
  await router.push(playRoute);
}

async function ensureRoomContext() {
  const operation = context.capture();
  if (!operation.isCurrent()) return;
  const id = roomId.value;
  if (!id || !gameCode.value || onlineBlocked.value) {
    errorMessage.value = id ? '房间不可用' : '房间 ID 无效';
    await navigateLobby();
    if (!operation.isCurrent()) return;
    return;
  }
  loading.value = true;
  errorMessage.value = '';
  try {
    await loadOnlineRuleDefinition(gameCode.value, { signal: operation.signal });
    if (!operation.isCurrent()) return;
    await roomQueryService.loadRoomDetail(id, { signal: operation.signal });
    if (!operation.isCurrent()) return;
    if (!room.value) {
      errorMessage.value = '房间不存在或已被删除';
      await navigateLobby();
      if (!operation.isCurrent()) return;
      return;
    }
    if (!isRoomMember.value) {
      if (isUserShellInRoom(room.value)) {
        shellRejoinOffered.value = true;
        return;
      }
      errorMessage.value = '你尚未加入该房间';
      await navigateLobby();
      if (!operation.isCurrent()) return;
      return;
    }
    shellRejoinOffered.value = false;
    ready.value = true;
  } catch (err) {
    if (!operation.isCurrent()) return;
    errorMessage.value = err?.message || '加载房间失败';
    await navigateLobby();
    if (!operation.isCurrent()) return;
  } finally {
    if (operation.isCurrent()) loading.value = false;
  }
}

/**
 * @param {string} targetPlayerId
 */

/**
 * @param {{ error?: string; maxPlayers?: number; roomConfig?: object }} payload
 */

/**
 * @param {{ maxPlayers?: number; roomConfig?: object }} payload
 */

const {
  onRejoinManagedRoom,
  onBackToLobbyFromShell,
  onLeaveRoom,
  onAddAi,
  onStartGame
} = useRoomWaitingCommands({ roomId, room, isRoomMember, context, actionBusy, rejoinBusy, errorMessage, shellRejoinOffered, ready, navigateLobby, navigatePlayRoom });

const {
  detailVisible,
  settingsVisible,
  settingsSubmitting,
  inviteDialogVisible,
  inviteUsers,
  inviteLoading,
  inviteSubmitting,
  inviteError,
  removeMemberConfirmVisible,
  removeMemberConfirmMessage,
  aiRemoveConfirmVisible,
  pendingAiRemoveCount,
  resetDialogs,
  onOpenDetail,
  onRemoveMemberRequest,
  onCancelRemoveMember,
  onConfirmRemoveMember,
  onRoomSettingsSubmit,
  onCancelAiRemoveConfirm,
  onConfirmAiRemoveAndSave,
  loadInviteUsers,
  onInvite,
  onInviteUser
} = useRoomWaitingDialogs({ roomId, room, isRoomMember, context, actionBusy, errorMessage });

watch([gameCode, roomId, onlineBlocked], () => {
  const operation = context.reset();
  ready.value = false;
  loading.value = false;
  actionBusy.value = false;
  rejoinBusy.value = false;
  shellRejoinOffered.value = false;
  resetDialogs();
  if (!gameCode.value || onlineBlocked.value) return;
  platform.setCurrentGame(gameCode.value);
  if (roomId.value) operation.own(roomRealtimeService.bindRoomRealtime(roomId.value));
  void ensureRoomContext();
}, { immediate: true });

watch(
  () => room.value?.status,
  (status) => {
    const normalized = String(status || '').trim();
    if (!roomId.value || shellRejoinOffered.value || isShellMember.value) {
      return;
    }
    if (normalized === 'playing') {
      void navigatePlayRoom();
    }
  }
);

</script>
