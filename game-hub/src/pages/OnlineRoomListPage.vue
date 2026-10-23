<template>
  <div>
    <RoomListPage
      :title="pageTitle"
      :rooms="rooms"
      :room-config-schema="roomConfigSchema"
      :loading="loading || roomsLoading"
      :disabled="onlineBlocked || listBusy"
      :error-message="roomListErrorMessage"
      @refresh="onRefreshRooms"
      @create="openCreateDialog"
      @select-room="onSelectListRoom"
    >
      <RoomActiveNotice
        :room="activeRoom"
        :game-name="activeRoomGameName"
        :disabled="onlineBlocked || listBusy"
        :error-message="activeRoomError"
        @return="onReturnActiveRoom"
        @leave="onRequestLeaveActiveRoom"
      />
    </RoomListPage>

    <CreateRoomDialog
      :visible="createDialogVisible"
      :room-config-schema="roomConfigSchema"
      :submitting="createSubmitting"
      :error-message="createError"
      @close="closeCreateDialog"
      @submit="onCreateRoom"
    >
      <template #error-action>
        <RoomActiveNotice
          v-if="createError"
          :room="activeRoom"
          :game-name="activeRoomGameName"
          :disabled="onlineBlocked || listBusy"
          :error-message="activeRoomError"
          @return="onReturnActiveRoom"
          @leave="onRequestLeaveActiveRoom"
        />
      </template>
    </CreateRoomDialog>

    <RoomResumePlayingDialog
      :visible="activeRoomLeaveVisible"
      title="退出房间"
      :message="activeRoomLeaveMessage"
      confirm-text="退出房间"
      cancel-text="取消"
      :submitting="activeRoomLeaving"
      :error-message="activeRoomLeaveError"
      @confirm="onConfirmLeaveActiveRoom"
      @secondary-action="onCancelLeaveActiveRoom"
      @dismiss="onCancelLeaveActiveRoom"
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
      @secondary-action="onDeclineActivePlaying"
      @dismiss="onDismissActivePlaying"
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
      @secondary-action="onCancelListResumePlaying"
      @dismiss="onCancelListResumePlaying"
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
      @secondary-action="onCancelManagedShellResume"
      @dismiss="onCancelManagedShellResume"
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
      @secondary-action="onCancelSwitchRoom"
      @dismiss="onCancelSwitchRoom"
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
      @secondary-action="onCancelManagedShellSwitch"
      @dismiss="onCancelManagedShellSwitch"
    />
  </div>
</template>

<script setup>
import { useRoomLobbyDialogs } from '../composables/useRoomLobbyDialogs.js';
import { computed, onActivated, ref, watch } from 'vue';
import { useAsyncContext } from '../composables/useAsyncContext.js';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import RoomListPage from '../components/game-hub/room/RoomListPage.vue';
import RoomDetailDialog from '../components/game-hub/room/RoomDetailDialog.vue';
import CreateRoomDialog from '../components/game-hub/room/CreateRoomDialog.vue';
import RoomResumePlayingDialog from '../components/game-hub/room/RoomResumePlayingDialog.vue';
import RoomActiveNotice from '../components/game-hub/room/RoomActiveNotice.vue';
import { usePlatformStore } from '../stores/platformStore.js';
import * as roomQueryService from '../services/roomQueryService.js';
import * as roomRealtimeService from '../services/roomRealtimeService.js';
import { canFetchRemote } from '../services/remoteGate.js';
import { useRoomStore } from '../stores/roomStore.js';
import { loadOnlineRuleDefinition } from '../services/onlineRoomService.js';
import { resolveGamePlayRoute } from '../games/gameModuleRegistry.js';
import { resolveGameDisplayName } from '../services/gameCatalogService.js';
import { getRoomMembershipScope } from '../services/roomAccessService.js';

const context = useAsyncContext();
const route = useRoute();
const router = useRouter();
const platform = usePlatformStore();
const roomStore = useRoomStore();
const { rooms, roomsLoading, roomsError, roomConfigSchema } = storeToRefs(roomStore);

const loading = ref(false);
const loadError = ref('');
const onlineBlocked = computed(() => !canFetchRemote());
const gameCode = computed(() => String(route.params.gameCode || '').trim());
const pageTitle = computed(() => '房间列表');
const roomListErrorMessage = computed(() => {
  if (onlineBlocked.value) {
    return '当前为本地模式，在线房间不可用。';
  }
  if (loadError.value) {
    return loadError.value;
  }
  return roomsError.value;
});

/**
 * 按目标房间的游戏进入等待页；未知或不支持在线对战的游戏明确报错。
 * @param {string} roomId 房间标识。
 * @param {string} [targetGameCode] 房间实际游戏编码，当前大厅仅用于普通列表操作。
 * @returns {Promise<void>} 执行路由跳转，不改变房间成员资格。
 */
async function navigateToRoom(roomId, targetGameCode = gameCode.value) {
  const normalized = String(roomId || '').trim();
  const roomGameCode = String(targetGameCode || '').trim();
  if (!normalized || !resolveGamePlayRoute(roomGameCode, normalized)) {
    throw new Error('该房间所属游戏暂不支持在线进入');
  }
  await router.push({
    name: 'online-room-waiting',
    params: { gameCode: roomGameCode, roomId: normalized }
  });
}

/**
 * 按目标房间的游戏进入对战页，不把跨游戏房间送入当前游戏。
 * @param {string} roomId 房间标识。
 * @param {string} [targetGameCode] 房间实际游戏编码。
 * @returns {Promise<void>} 解析通用注册表后执行路由跳转。
 */
async function navigateToPlay(roomId, targetGameCode = gameCode.value) {
  const normalized = String(roomId || '').trim();
  const playRoute = resolveGamePlayRoute(String(targetGameCode || '').trim(), normalized);
  if (!playRoute) {
    throw new Error('该房间所属游戏暂不支持在线进入');
  }
  await router.push(playRoute);
}

const {
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
} = useRoomLobbyDialogs({ gameCode, onlineBlocked, context, loading, loadError, navigateToRoom, navigateToPlay });

const activeRoomGameName = computed(() => resolveGameDisplayName(activeRoom.value?.gameCode || ''));

/**
 * 初始化当前大厅；先独立查询活跃房间，避免列表或规则失败隐藏恢复入口。
 * @returns {Promise<void>} 更新展示并订阅大厅，过期页面不再写回。
 */
async function initPage() {
  const operation = context.capture();
  if (!operation.isCurrent()) return;
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
    await refreshActiveRoom();
    if (!operation.isCurrent()) return;
    await loadOnlineRuleDefinition(gameCode.value, { signal: operation.signal });
    if (!operation.isCurrent()) return;
    await roomQueryService.refreshRoomList(gameCode.value, { signal: operation.signal });
    if (!operation.isCurrent()) return;
    if (
      activeRoom.value?.status === 'playing' &&
      String(activeRoom.value?.gameCode || '').trim() === gameCode.value
    ) {
      activePlayingConfirmVisible.value = true;
      activePlayingConfirmError.value = '';
    }
    const loadedShellRoom = await roomQueryService.loadMyManagedShell(gameCode.value);
    if (!operation.isCurrent()) return;
    managedShellRoom.value = loadedShellRoom;
    if (managedShellRoom.value?.roomId) {
      managedShellConfirmVisible.value = true;
      managedShellConfirmError.value = '';
    }
    operation.own(roomRealtimeService.bindRoomRealtime(`__lobby__:${gameCode.value}`));
  } catch (err) {
    if (!operation.isCurrent()) return;
    loadError.value = err?.message || '加载失败';
  } finally {
    if (operation.isCurrent()) loading.value = false;
  }
}

/**
 * 同时刷新列表与跨游戏活跃房间；其中一条查询失败不阻止另一条完成。
 * @returns {Promise<void>} 各查询服务维护其错误展示，页面取消后不写回。
 */
async function onRefreshRooms() {
  const operation = context.capture();
  if (!operation.isCurrent()) return;
  if (onlineBlocked.value || !gameCode.value) {
    return;
  }
  try {
    await Promise.allSettled([
      roomQueryService.refreshRoomList(gameCode.value, { signal: operation.signal }),
      refreshActiveRoom()
    ]);
  } catch {
    // 错误信息已由 service 写入 store
  }
}

watch([gameCode, onlineBlocked, getRoomMembershipScope], () => {
  context.reset();
  resetDialogs();
  loading.value = false;
  void initPage();
}, { immediate: true, flush: 'sync' });

onActivated(() => { void onRefreshRooms(); });
</script>
