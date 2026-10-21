import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';

const FINAL_SETTLEMENT_STATUSES = new Set(['COMPLETED', 'FAILED']);
const PENDING_LEAVE_MESSAGE = '平台积分仍在结算中。离开后结算会在后台继续，确定要离开本页面吗？';

/**
 * 管理斗地主终局弹窗、结算状态与单次导航。
 * @param {object} input
 * @param {import('vue').Ref<boolean>} input.gameViewIsGameOver
 * @param {import('vue').Ref<number>} input.gameViewVersion
 * @param {import('vue').Ref<boolean>} input.gameViewPlaybackBusy
 * @param {import('vue').Ref<object|null>} input.terminalMetadata
 * @param {import('vue').Ref<object|null>} input.currentRoom
 * @param {import('vue').Ref<string>} input.activeRoomId
 * @param {() => Promise<void>} input.navigateToWaiting
 * @param {() => Promise<void>|void} input.navigateToLobby
 * @param {() => void} input.resetGameView
 * @returns {object}
 */
export function useDoudizhuTerminalFlow(input) {
  const {
    gameViewIsGameOver,
    gameViewVersion,
    gameViewPlaybackBusy,
    terminalMetadata,
    currentRoom,
    activeRoomId,
    navigateToWaiting,
    navigateToLobby,
    resetGameView
  } = input;
  const settlementVisible = ref(false);
  const settlementDismissed = ref(false);
  const hasNavigated = ref(false);
  const observedRoom = ref(false);
  /** @type {Promise<void>|null} */
  let navigationPromise = null;

  const settlementStatus = computed(() =>
    String(terminalMetadata.value?.settlementStatus || '').trim()
  );
  const canDismissSettlement = computed(() =>
    FINAL_SETTLEMENT_STATUSES.has(settlementStatus.value)
  );
  const isSettlementPending = computed(() => settlementStatus.value === 'PENDING');

  /**
   * 在终局事件播放完成后打开同一个结算弹窗。
   * @returns {void}
   */
  function showSettlementIfReady() {
    if (
      settlementDismissed.value ||
      !gameViewIsGameOver.value ||
      !gameViewVersion.value ||
      gameViewPlaybackBusy.value
    ) {
      return;
    }
    settlementVisible.value = true;
  }

  /**
   * 执行一次终局导航，并在导航前清理 GameView。
   * @param {'waiting'|'lobby'} destination
   * @returns {Promise<void>}
   */
  function navigateOnce(destination) {
    if (hasNavigated.value) {
      return navigationPromise || Promise.resolve();
    }
    hasNavigated.value = true;
    settlementVisible.value = false;
    settlementDismissed.value = true;
    resetGameView();
    navigationPromise = Promise.resolve(
      destination === 'lobby' ? navigateToLobby() : navigateToWaiting()
    ).finally(() => {
      navigationPromise = null;
    });
    return navigationPromise;
  }

  /**
   * 处理结算弹窗关闭或返回房间。
   * @returns {Promise<void>}
   */
  async function onSettlementClose() {
    if (!canDismissSettlement.value) return;
    await navigateOnce('waiting');
  }

  /**
   * 重置当前终局流程状态。
   * @returns {void}
   */
  function resetTerminalFlow() {
    settlementVisible.value = false;
    settlementDismissed.value = false;
    hasNavigated.value = false;
    observedRoom.value = false;
    navigationPromise = null;
  }

  /**
   * 在浏览器整页离开时提示后台结算仍会继续。
   * @param {BeforeUnloadEvent} event
   * @returns {string|undefined}
   */
  function handleBeforeUnload(event) {
    if (!isSettlementPending.value || hasNavigated.value) return undefined;
    event.preventDefault();
    event.returnValue = PENDING_LEAVE_MESSAGE;
    return PENDING_LEAVE_MESSAGE;
  }

  watch(
    [gameViewIsGameOver, gameViewVersion, gameViewPlaybackBusy, settlementStatus],
    showSettlementIfReady,
    { immediate: true }
  );
  watch(activeRoomId, resetTerminalFlow, { flush: 'sync' });
  watch(
    [currentRoom, settlementStatus],
    ([room]) => {
      const expectedRoomId = String(activeRoomId.value || '').trim();
      const roomId = String(room?.roomId || '').trim();
      if (room && (!expectedRoomId || roomId === expectedRoomId)) {
        observedRoom.value = true;
        if (String(room.status || '').trim() !== 'playing' && canDismissSettlement.value) {
          void navigateOnce('waiting');
        }
        return;
      }
      if (observedRoom.value && !room) void navigateOnce('lobby');
    },
    { deep: true, immediate: true }
  );

  onBeforeRouteLeave(() => {
    if (!isSettlementPending.value || hasNavigated.value) return true;
    return window.confirm(PENDING_LEAVE_MESSAGE);
  });
  onMounted(() => window.addEventListener('beforeunload', handleBeforeUnload));

  /**
   * 释放浏览器离开监听。
   * @returns {void}
   */
  function dispose() {
    window.removeEventListener('beforeunload', handleBeforeUnload);
  }

  onUnmounted(dispose);

  return {
    settlementVisible,
    settlementDismissed,
    settlementStatus,
    canDismissSettlement,
    hasNavigated,
    onSettlementClose,
    resetTerminalFlow,
    reset: resetTerminalFlow,
    dispose
  };
}
