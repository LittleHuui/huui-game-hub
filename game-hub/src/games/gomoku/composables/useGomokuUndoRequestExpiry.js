import { computed, onUnmounted, ref, watch } from 'vue';

/**
 * 管理五子棋悔棋请求的本地到期展示与权威视图刷新。
 * @param {{ undoRequestRef: import('vue').Ref<object|null|undefined>; viewerIdRef: import('vue').Ref<string>; reload: (options: { signal?: AbortSignal }) => Promise<unknown> }} input
 * @returns {{ hasActiveIncomingUndoRequest: import('vue').ComputedRef<boolean>; reset: () => void }}
 */
export function useGomokuUndoRequestExpiry(input) {
  const expiredRequestId = ref('');
  let timerId = null;
  let refreshController = null;

  const undoRequest = computed(() => {
    const value = input.undoRequestRef.value;
    return value && typeof value === 'object' ? value : null;
  });
  const requestId = computed(() => String(undoRequest.value?.requestId || '').trim());
  const expiresAt = computed(() => Number(undoRequest.value?.expiresAt) || 0);
  const targetPlayerId = computed(() => String(undoRequest.value?.targetPlayerId || '').trim());
  const hasActiveIncomingUndoRequest = computed(() => {
    const currentRequestId = requestId.value;
    return Boolean(
      currentRequestId &&
      targetPlayerId.value === String(input.viewerIdRef.value || '').trim() &&
      expiresAt.value > Date.now() &&
      expiredRequestId.value !== currentRequestId
    );
  });

  /**
   * 取消当前到期计时与刷新请求，防止过期任务影响当前视图。
   * @returns {void}
   */
  function clearPendingWork() {
    if (timerId != null) {
      globalThis.clearTimeout(timerId);
      timerId = null;
    }
    if (refreshController) {
      refreshController.abort();
      refreshController = null;
    }
  }

  /**
   * 到期后隐藏对应请求并读取权威 GameView；刷新失败不恢复失效弹窗。
   * @param {string} expectedRequestId
   * @param {number} expectedExpiresAt
   * @returns {Promise<void>}
   */
  async function expireAndRefresh(expectedRequestId, expectedExpiresAt) {
    if (requestId.value !== expectedRequestId || expiresAt.value !== expectedExpiresAt) {
      return;
    }
    const remainingMs = expectedExpiresAt - Date.now();
    if (remainingMs > 0) {
      timerId = globalThis.setTimeout(
        () => void expireAndRefresh(expectedRequestId, expectedExpiresAt),
        remainingMs
      );
      return;
    }
    timerId = null;
    expiredRequestId.value = expectedRequestId;
    const controller = new AbortController();
    refreshController = controller;
    try {
      await input.reload({ signal: controller.signal });
    } catch (error) {
      if (error?.name !== 'AbortError') {
        // 到期后的展示已安全收敛，读取失败交由既有页面错误状态处理。
      }
    } finally {
      if (refreshController === controller) {
        refreshController = null;
      }
    }
  }

  /**
   * 按服务端 expiresAt 安排本地失效时钟。
   * @param {string} nextRequestId
   * @param {number} nextExpiresAt
   * @returns {void}
   */
  function scheduleExpiry(nextRequestId, nextExpiresAt) {
    clearPendingWork();
    if (!nextRequestId || nextExpiresAt <= 0) {
      expiredRequestId.value = '';
      return;
    }
    if (expiredRequestId.value !== nextRequestId) {
      expiredRequestId.value = '';
    }
    const remainingMs = nextExpiresAt - Date.now();
    if (remainingMs <= 0) {
      void expireAndRefresh(nextRequestId, nextExpiresAt);
      return;
    }
    timerId = globalThis.setTimeout(
      () => void expireAndRefresh(nextRequestId, nextExpiresAt),
      remainingMs
    );
  }

  watch(
    () => [requestId.value, expiresAt.value],
    ([nextRequestId, nextExpiresAt]) => scheduleExpiry(nextRequestId, nextExpiresAt),
    { immediate: true }
  );

  onUnmounted(clearPendingWork);

  return {
    hasActiveIncomingUndoRequest,
    reset: clearPendingWork
  };
}
