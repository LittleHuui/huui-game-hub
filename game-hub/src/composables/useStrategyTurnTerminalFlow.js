import { computed, onUnmounted, ref, watch } from 'vue';

const FINAL_SETTLEMENT_STATUSES = new Set(['COMPLETED', 'FAILED']);

/**
 * 管理策略回合游戏的通用终局展示、结算等待和单次导航。
 * @param {object} input
 * @param {import('vue').Ref<boolean>} input.isGameOverRef
 * @param {import('vue').Ref<number>} input.versionRef
 * @param {import('vue').Ref<boolean>} input.playbackBusyRef
 * @param {import('vue').Ref<object|null>} [input.terminalMetadataRef]
 * @param {import('vue').Ref<object|null>} [input.roomRef]
 * @param {import('vue').Ref<string>} [input.roomIdRef]
 * @param {(destination: string) => Promise<void>|void} input.navigate
 * @param {() => void} input.resetGameView
 * @param {number} [input.navigationDelayMs]
 * @param {boolean} [input.autoNavigateOnRoomFinalize]
 * @returns {object}
 */
export function useStrategyTurnTerminalFlow(input) {
  const visible = ref(false);
  const dismissed = ref(false);
  const hasNavigated = ref(false);
  const settlementStatus = computed(() =>
    String(input.terminalMetadataRef?.value?.settlementStatus || '').trim()
  );
  const canDismiss = computed(() =>
    !settlementStatus.value || FINAL_SETTLEMENT_STATUSES.has(settlementStatus.value)
  );
  /** @type {Promise<void>|null} */
  let navigationPromise = null;
  /** @type {ReturnType<typeof setTimeout>|null} */
  let navigationTimer = null;
  let finishNavigationWait = null;
  let disposed = false;

  /**
   * 在终局动画播放完成后展示结算。
   * @returns {boolean}
   */
  function showIfReady() {
    if (!input.isGameOverRef.value) {
      visible.value = false;
      return false;
    }
    if (
      dismissed.value ||
      !input.versionRef.value ||
      input.playbackBusyRef.value
    ) {
      return false;
    }
    visible.value = true;
    return true;
  }

  /**
   * 保证 Finalize、关闭弹窗和房间状态变化只触发一次导航。
   * @param {string} destination
   * @returns {Promise<void>}
   */
  function navigateOnce(destination) {
    if (hasNavigated.value || disposed) return navigationPromise || Promise.resolve();
    hasNavigated.value = true;
    visible.value = false;
    dismissed.value = true;
    input.resetGameView();
    const pendingNavigation = new Promise((resolve) => {
      finishNavigationWait = resolve;
      const run = () => {
        navigationTimer = null;
        finishNavigationWait = null;
        return Promise.resolve(input.navigate(destination))
          .catch(() => undefined)
          .finally(resolve);
      };
      const delay = Number(input.navigationDelayMs) || 0;
      if (delay > 0) navigationTimer = setTimeout(run, delay);
      else run();
    }).finally(() => {
      if (navigationPromise === pendingNavigation) navigationPromise = null;
    });
    navigationPromise = pendingNavigation;
    return pendingNavigation;
  }

  /**
   * 关闭可关闭的终局弹窗并返回等待页。
   * @returns {Promise<void>}
   */
  function close() {
    if (!canDismiss.value) return Promise.resolve();
    return navigateOnce('waiting');
  }

  /**
   * 重置终局流程。
   * @returns {void}
   */
  function reset() {
    if (navigationTimer != null) clearTimeout(navigationTimer);
    navigationTimer = null;
    finishNavigationWait?.();
    finishNavigationWait = null;
    navigationPromise = null;
    visible.value = false;
    dismissed.value = false;
    hasNavigated.value = false;
  }

  /**
   * 取消延迟导航并停止观察结果写回。
   * @returns {void}
   */
  function dispose() {
    disposed = true;
    if (navigationTimer != null) clearTimeout(navigationTimer);
    navigationTimer = null;
    finishNavigationWait?.();
    finishNavigationWait = null;
  }

  watch(
    [input.isGameOverRef, input.versionRef, input.playbackBusyRef, settlementStatus],
    showIfReady,
    { immediate: true }
  );
  if (input.roomRef && input.autoNavigateOnRoomFinalize) {
    watch(
      [input.roomRef, settlementStatus],
      ([room]) => {
        if (!input.isGameOverRef.value) return;
        if (!room) {
          void navigateOnce('lobby');
        } else if (String(room.status || '').trim() !== 'playing' && canDismiss.value) {
          void navigateOnce('waiting');
        }
      },
      { deep: true }
    );
  }

  if (input.roomIdRef) watch(input.roomIdRef, reset, { flush: 'sync' });
  onUnmounted(dispose);
  return {
    visible,
    dismissed,
    hasNavigated,
    settlementStatus,
    canDismiss,
    showIfReady,
    navigateOnce,
    close,
    reset,
    dispose
  };
}
