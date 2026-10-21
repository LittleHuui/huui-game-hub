import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useRoomStore } from '../stores/roomStore.js';
import * as roomAccessService from '../services/roomAccessService.js';
import * as roomQueryService from '../services/roomQueryService.js';
import * as roomGameService from '../services/roomGameService.js';
import * as roomRealtimeService from '../services/roomRealtimeService.js';
import * as roomService from '../services/roomService.js';
import * as gameViewService from '../services/strategyTurnGameViewService.js';
import { canFetchRemote } from '../services/remoteGate.js';
import { useAsyncContext } from './useAsyncContext.js';

/**
 * 管理策略回合页面的房间加载、重连、切换和卸载。
 * @param {object} input
 * @param {string} input.defaultGameCode
 * @param {string} input.defaultRoomLabel
 * @param {(roomId: string, options?: object) => Promise<object>} input.loadGameView
 * @returns {object}
 */
export function useStrategyTurnRoomLifecycle(input) {
  const route = useRoute();
  const router = useRouter();
  const roomStore = useRoomStore();
  const { currentRoom: storedRoom } = storeToRefs(roomStore);
  const context = useAsyncContext();
  const loading = ref(false);
  const loadError = ref('');
  const gameViewLoadError = ref('');
  const shellRejoinOffered = ref(false);
  const rejoinBusy = ref(false);
  const activeRoomId = computed(() => String(route.params.roomId || '').trim());
  const currentRoom = computed(() => storedRoom.value?.roomId === activeRoomId.value ? storedRoom.value : null);
  const activeGameCode = computed(
    () => String(route.params.gameCode || '').trim() || input.defaultGameCode
  );
  const onlineBlocked = computed(() => !canFetchRemote());
  const playRoomLabel = computed(
    () => String(currentRoom.value?.roomName || '').trim() || input.defaultRoomLabel
  );
  /** @type {AbortController|null} */
  let loadController = null;
  /** @type {(() => void)|null} */
  let releaseRealtime = null;
  /** @type {(() => void)|null} */
  let releasePresence = null;
  let generation = 0;
  let disposed = false;

  /**
   * 判断当前用户是否仍是有效房间成员。
   * @param {object|null|undefined} room
   * @param {boolean} shell
   * @returns {boolean}
   */
  function hasMembership(room, shell = false) {
    const playerId = roomAccessService.getCurrentPlayerId();
    return Boolean(playerId && room?.members?.some((member) => {
      const samePlayer = String(member?.playerId || '').trim() === playerId;
      const isShell = String(member?.managedMode || '').trim() === 'shell';
      return samePlayer && isShell === shell;
    }));
  }

  const isRoomMember = computed(() => hasMembership(currentRoom.value));

  /**
   * 建立页面可显示 GameView 的状态。
   * @param {import('vue').Ref<boolean>} isGameOverRef
   * @param {import('vue').Ref<boolean>} terminalDismissedRef
   * @returns {import('vue').ComputedRef<boolean>}
   */
  function createCanShowGameView(isGameOverRef, terminalDismissedRef) {
    return computed(() => {
      if (onlineBlocked.value || loading.value || !currentRoom.value || !isRoomMember.value) {
        return false;
      }
      return String(currentRoom.value.status || '').trim() === 'playing' ||
        (isGameOverRef.value && !terminalDismissedRef.value);
    });
  }

  /**
   * 释放当前房间的实时绑定。
   * @returns {void}
   */
  function releaseBindings() {
    releaseRealtime?.();
    releasePresence?.();
    releaseRealtime = null;
    releasePresence = null;
  }

  /**
   * 返回等待页或大厅。
   * @returns {Promise<void>}
   */
  async function backToRoomOrLobby() {
    const roomId = activeRoomId.value;
    const params = { gameCode: activeGameCode.value };
    if (roomId) {
      await router.replace({ name: 'online-room-waiting', params: { ...params, roomId } });
    } else {
      await router.replace({ name: 'online-room-list', params });
    }
  }

  /**
   * 清理 GameView 并返回大厅。
   * @returns {Promise<void>}
   */
  async function navigateToLobby() {
    roomGameService.resetRoomGameView();
    await router.push({
      name: 'online-room-list',
      params: { gameCode: activeGameCode.value }
    });
  }

  /**
   * 加载房间和权威 GameView，旧房间响应不会回写新房间。
   * @returns {Promise<void>}
   */
  async function load() {
    const roomId = activeRoomId.value;
    if (!roomId || onlineBlocked.value || disposed) return;
    const localGeneration = ++generation;
    loadController?.abort();
    loadController = new AbortController();
    const controller = loadController;
    loading.value = true;
    loadError.value = '';
    gameViewLoadError.value = '';
    try {
      await roomQueryService.loadRoomDetail(roomId, { signal: controller.signal });
      if (disposed || controller.signal.aborted || localGeneration !== generation) return;
      if (!currentRoom.value) {
        loadError.value = '房间不存在或已被删除';
        await backToRoomOrLobby();
        return;
      }
      if (!isRoomMember.value) {
        if (hasMembership(currentRoom.value, true)) {
          shellRejoinOffered.value = true;
          return;
        }
        loadError.value = '你尚未加入该房间';
        await backToRoomOrLobby();
        return;
      }
      shellRejoinOffered.value = false;
      if (String(currentRoom.value.status || '').trim() !== 'playing') {
        await backToRoomOrLobby();
        return;
      }
      gameViewService.setActiveRoom(roomId);
      if (!gameViewService.getCurrentGameViewVersion()) {
        await input.loadGameView(roomId, { signal: controller.signal });
      }
    } catch (error) {
      if (!controller.signal.aborted && localGeneration === generation) {
        loadError.value = error?.message || '加载房间失败';
      }
    } finally {
      if (localGeneration === generation) loading.value = false;
      if (loadController === controller) loadController = null;
    }
  }

  /**
   * 重新加入 shell 托管房间。
   * @returns {Promise<void>}
   */
  async function rejoin() {
    const roomId = activeRoomId.value;
    const operation = context.capture();
    if (!roomId || rejoinBusy.value || onlineBlocked.value || !operation.isCurrent()) return;
    rejoinBusy.value = true;
    try {
      await roomService.rejoinManagedRoom(roomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      shellRejoinOffered.value = false;
      gameViewService.setActiveRoom(roomId);
      await input.loadGameView(roomId, { signal: operation.signal });
    } catch (error) {
      if (operation.isCurrent()) loadError.value = error?.message || '重新加入失败';
    } finally {
      if (operation.isCurrent()) rejoinBusy.value = false;
    }
  }

  /**
   * 离开房间并保留 shell 托管。
   * @returns {Promise<void>}
   */
  async function exitWithShell() {
    const roomId = activeRoomId.value;
    const operation = context.capture();
    if (onlineBlocked.value || !operation.isCurrent()) return;
    if (!roomId) return navigateToLobby();
    try {
      await roomService.leaveRoom(roomId, { signal: operation.signal });
      if (!operation.isCurrent()) return;
      await navigateToLobby();
    } catch (error) {
      if (operation.isCurrent()) loadError.value = error?.message || '退出房间失败';
    }
  }

  /**
   * 切换实时绑定并加载当前路由房间。
   * @returns {Promise<void>}
   */
  async function reset() {
    const operation = context.reset();
    generation += 1;
    loadController?.abort();
    loadController = null;
    releaseBindings();
    roomGameService.resetRoomGameView();
    loading.value = false;
    rejoinBusy.value = false;
    shellRejoinOffered.value = false;
    loadError.value = '';
    gameViewLoadError.value = '';
    const roomId = activeRoomId.value;
    if (!roomId || disposed || onlineBlocked.value) return;
    releaseRealtime = roomRealtimeService.bindRoomRealtime(roomId);
    releasePresence = roomRealtimeService.bindRoomPresencePong(
      roomId,
      activeGameCode.value,
      operation.isCurrent
    );
    await load();
  }

  /**
   * 释放请求、重连绑定和 GameView。
   * @returns {void}
   */
  function dispose() {
    if (disposed) return;
    disposed = true;
    context.reset();
    generation += 1;
    loadController?.abort();
    loadController = null;
    releaseBindings();
    roomGameService.resetRoomGameView();
  }

  onMounted(reset);
  watch([activeRoomId, activeGameCode, onlineBlocked], () => { void reset(); }, { flush: 'sync' });
  onUnmounted(dispose);

  return {
    loading,
    loadError,
    gameViewLoadError,
    shellRejoinOffered,
    rejoinBusy,
    activeRoomId,
    activeGameCode,
    onlineBlocked,
    currentRoom,
    isRoomMember,
    playRoomLabel,
    createCanShowGameView,
    load,
    rejoin,
    exitWithShell,
    backToRoomOrLobby,
    navigateToLobby,
    reset,
    dispose
  };
}
