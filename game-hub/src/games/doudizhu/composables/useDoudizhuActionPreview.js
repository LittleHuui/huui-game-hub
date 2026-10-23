import { computed, onUnmounted, ref, watch } from 'vue';
import { ComposedActionAdapter } from '../../../services/action-interaction/composedActionAdapter.js';
import {
  buildSelectionSignature,
  createPreviewRequestController
} from '../../../services/action-interaction/previewRequestUtils.js';
import * as roomGameService from '../../../services/roomGameService.js';

/** @typedef {'IDLE' | 'LOADING' | 'VALID' | 'INVALID' | 'INCOMPLETE'} PreviewStatus */

const PREVIEW_DEBOUNCE_MS = 100;

/**
 * 管理斗地主出牌 Preview 状态与请求。
 * @param {object} input
 * @param {import('vue').Ref<string>} input.roomIdRef
 * @param {import('vue').Ref<number>} input.gameViewVersionRef
 * @param {import('vue').Ref<string[]>} input.selectedCardIdsRef
 * @param {import('vue').ComputedRef<boolean>} input.previewEnabledRef
 * @returns {{
 *   previewStatus: import('vue').Ref<PreviewStatus>;
 *   previewSummary: import('vue').Ref<object>;
 *   previewReason: import('vue').Ref<string>;
 *   playActionEnabled: import('vue').ComputedRef<boolean>;
 *   previewMessage: import('vue').ComputedRef<string>;
 *   invalidatePreview: () => void;
 *   resetPreview: () => void;
 * }}
 */
export function useDoudizhuActionPreview(input) {
  const {
    roomIdRef,
    gameViewVersionRef,
    selectedCardIdsRef,
    previewEnabledRef
  } = input;

  /** @type {import('vue').Ref<PreviewStatus>} */
  const previewStatus = ref('IDLE');
  const previewSummary = ref({});
  const previewReason = ref('');
  const previewController = createPreviewRequestController();
  /** @type {AbortController|null} */
  let requestAbortController = null;
  /** @type {ReturnType<typeof setTimeout>|null} */
  let debounceTimer = null;

  const playActionEnabled = computed(() => previewStatus.value === 'VALID');

  const previewMessage = computed(() => {
    if (previewStatus.value === 'LOADING') {
      return '校验中…';
    }
    if (previewStatus.value === 'VALID') {
      const summary = previewSummary.value;
      const text = summary?.text || summary?.comboText || summary?.combo?.text;
      return text ? String(text) : '可出牌';
    }
    if (previewStatus.value === 'INCOMPLETE') {
      return previewReason.value || '请选择更多牌';
    }
    if (previewStatus.value === 'INVALID') {
      return previewReason.value || '不可出牌';
    }
    return '';
  });

  /**
   * 重置预览状态为空闲。
   */
  function resetPreview() {
    previewStatus.value = 'IDLE';
    previewSummary.value = {};
    previewReason.value = '';
  }

  /**
   * 废弃请求代次并取消未完成预览与防抖任务。
   * @returns {void}
   */
  function cancelPendingPreview() {
    previewController.invalidate();
    requestAbortController?.abort();
    requestAbortController = null;
    if (debounceTimer != null) {
      clearTimeout(debounceTimer);
      debounceTimer = null;
    }
  }

  /**
   * 取消未完成工作并重置预览展示。
   * @returns {void}
   */
  function invalidatePreview() {
    cancelPendingPreview();
    resetPreview();
  }

  /**
   * 发起 preview 请求。
   * @returns {Promise<void>}
   */
  async function requestPreview() {
    const roomId = String(roomIdRef.value || '').trim();
    const cardInstanceIds = (selectedCardIdsRef.value || [])
      .map((id) => String(id || '').trim())
      .filter(Boolean);
    const selectionSignature = buildSelectionSignature(cardInstanceIds);
    const baseVersion = Number(gameViewVersionRef.value) || 0;

    if (!roomId || !previewEnabledRef.value || !cardInstanceIds.length) {
      resetPreview();
      return;
    }

    const requestId = previewController.nextRequestId(roomId, baseVersion, selectionSignature);
    const abortController = new AbortController();
    requestAbortController?.abort();
    requestAbortController = abortController;
    previewStatus.value = 'LOADING';
    previewReason.value = '';

    try {
      const submission = ComposedActionAdapter.buildSubmission('PLAY_CARDS', {
        cardInstanceIds
      });
      const raw = await roomGameService.previewRoomGameAction(roomId, {
        baseVersion,
        submission,
        signal: abortController.signal
      });
      if (!previewController.isCurrent(requestId, roomId, baseVersion, selectionSignature)) {
        return;
      }
      const parsed = ComposedActionAdapter.parsePreviewResponse(raw);
      previewStatus.value = parsed.status;
      previewSummary.value = parsed.summary;
      previewReason.value = parsed.reason || '';
    } catch (err) {
      if (!previewController.isCurrent(requestId, roomId, baseVersion, selectionSignature)) {
        return;
      }
      previewStatus.value = 'INVALID';
      previewReason.value = err?.message || '预览失败';
      previewSummary.value = {};
    } finally {
      if (requestAbortController === abortController) {
        requestAbortController = null;
      }
    }
  }

  /**
   * 防抖调度 preview。
   */
  function schedulePreview() {
    if (debounceTimer != null) {
      clearTimeout(debounceTimer);
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null;
      void requestPreview();
    }, PREVIEW_DEBOUNCE_MS);
  }

  /**
   * 选牌、开关或版本变化时立即失效旧 Preview，再防抖发起新请求。
   */
  function handlePreviewInputsChanged() {
    cancelPendingPreview();

    const enabled = Boolean(previewEnabledRef.value);
    const selectedIds = selectedCardIdsRef.value || [];
    if (!enabled || !Array.isArray(selectedIds) || !selectedIds.length) {
      resetPreview();
      return;
    }

    previewStatus.value = 'LOADING';
    previewSummary.value = {};
    previewReason.value = '';
    schedulePreview();
  }

  watch(
    [selectedCardIdsRef, previewEnabledRef, gameViewVersionRef, roomIdRef],
    () => {
      handlePreviewInputsChanged();
    },
    { deep: true }
  );

  onUnmounted(cancelPendingPreview);

  return {
    previewStatus,
    previewSummary,
    previewReason,
    playActionEnabled,
    previewMessage,
    invalidatePreview,
    resetPreview,
    dispose: cancelPendingPreview
  };
}
