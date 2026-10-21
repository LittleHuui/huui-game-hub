import { computed, onUnmounted, ref, watch } from 'vue';
import { getAdapterForOffer } from '../services/action-interaction/actionInteractionAdapterRegistry.js';
import { findOfferByActionType } from '../services/action-interaction/actionOfferUtils.js';
import { createClientId } from '../utils/idService.js';
import { canFetchRemote } from '../services/remoteGate.js';

/**
 * 判断动作错误是否为版本冲突。
 * @param {unknown} error
 * @returns {boolean}
 */
function isVersionConflict(error) {
  const code = String(error?.code || error?.status || '').toUpperCase();
  const message = String(error?.message || '');
  return code === '409' || code.includes('CONFLICT') || /HTTP 409|版本冲突|并发冲突/i.test(message);
}

/**
 * 管理单次 Action Submission 的忙碌状态、requestId 和冲突恢复。
 * 冲突时只重新读取权威视图，绝不重复提交动作。
 * @param {object} input
 * @param {import('vue').Ref<string>} input.roomIdRef
 * @param {() => number} input.readVersion
 * @param {(roomId: string, body: object) => Promise<object>} input.submit
 * @param {(roomId: string, options?: object) => Promise<object>} input.reload
 * @param {import('vue').Ref<string>} [input.errorRef]
 * @returns {object}
 */
export function useStrategyTurnActionController(input) {
  const busy = ref(false);
  const status = ref('IDLE');
  const requestId = ref('');
  const disposed = ref(false);
  /** @type {AbortController|null} */
  let abortController = null;

  const onlineAvailable = computed(canFetchRemote);
  const canSubmit = computed(() => !busy.value && !disposed.value && onlineAvailable.value);

  /**
   * 提交已由 Adapter 构造的 submission。
   * @param {object} submission
   * @returns {Promise<object|null>}
   */
  async function submitSubmission(submission) {
    const roomId = String(input.roomIdRef.value || '').trim();
    const baseVersion = Number(input.readVersion()) || 0;
    if (!roomId || !baseVersion || !canSubmit.value) return null;

    busy.value = true;
    status.value = 'SUBMITTING';
    requestId.value = createClientId('room-action');
    if (input.errorRef) input.errorRef.value = '';
    abortController?.abort();
    abortController = new AbortController();
    const controller = abortController;
    try {
      const result = await input.submit(roomId, {
        submission,
        baseVersion,
        requestId: requestId.value,
        signal: controller.signal
      });
      if (controller.signal.aborted || abortController !== controller) return null;
      status.value = 'SUCCEEDED';
      return result;
    } catch (error) {
      if (disposed.value || controller.signal.aborted) return null;
      if (isVersionConflict(error)) {
        status.value = 'CONFLICTED';
        await input.reload(roomId, { signal: controller.signal });
        return null;
      }
      status.value = 'FAILED';
      if (input.errorRef) input.errorRef.value = error?.message || '操作失败';
      throw error;
    } finally {
      if (abortController === controller) {
        abortController = null;
        busy.value = false;
      }
    }
  }

  /**
   * 通过 Adapter Registry 从 Offer 构造并提交动作。
   * @param {object} offer
   * @param {unknown} selection
   * @returns {Promise<object|null>}
   */
  function submitOffer(offer, selection) {
    const adapter = getAdapterForOffer(offer);
    const submission = adapter.buildSubmission(offer.actionType, selection);
    return submitSubmission(submission);
  }

  /**
   * 按 actionType 查找 Offer，并由 Registry 对应的 Adapter 构造提交。
   * @param {object[]} offers
   * @param {string} actionType
   * @param {unknown} selection
   * @returns {Promise<object|null>}
   */
  function submitAction(offers, actionType, selection) {
    const offer = findOfferByActionType(offers, actionType);
    if (!offer) return Promise.resolve(null);
    return submitOffer(offer, selection);
  }

  /**
   * 取消当前请求并清空瞬时状态。
   * @returns {void}
   */
  function reset() {
    abortController?.abort();
    abortController = null;
    busy.value = false;
    status.value = 'IDLE';
    requestId.value = '';
  }

  /**
   * 释放控制器。
   * @returns {void}
   */
  function dispose() {
    if (disposed.value) return;
    disposed.value = true;
    reset();
  }

  watch([input.roomIdRef, onlineAvailable], reset, { flush: 'sync' });
  onUnmounted(dispose);
  return {
    busy,
    status,
    requestId,
    canSubmit,
    submitSubmission,
    submitOffer,
    submitAction,
    reset,
    dispose
  };
}
