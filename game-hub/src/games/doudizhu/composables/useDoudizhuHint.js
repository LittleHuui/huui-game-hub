import { onUnmounted, ref, watch } from 'vue';
import { ComposedActionAdapter } from '../../../services/action-interaction/composedActionAdapter.js';
import * as roomGameService from '../../../services/roomGameService.js';
import { findFirstEnumeratedOption } from '../doudizhuActionOffersAdapter.js';

const PLAY_CARDS_ACTION_TYPE = 'PLAY_CARDS';

/**
 * 管理斗地主提示（Suggestions）循环。
 * @param {object} input
 * @param {import('vue').Ref<string>} input.roomIdRef
 * @param {import('vue').Ref<number>} input.gameViewVersionRef
 * @param {import('vue').Ref<string>} [input.currentPlayerIdRef]
 * @param {import('vue').Ref<string>} [input.viewerPlayerIdRef]
 * @param {import('vue').ComputedRef<boolean>} input.hintEnabledRef
 * @param {import('vue').Ref<object[]>} input.actionOffersRef
 * @param {(cardInstanceIds: string[]) => void} input.applySelection
 * @param {(action: { actionType: string; actionId: string }) => Promise<void>} input.submitPass
 * @returns {{
 *   hintCursor: import('vue').Ref<string|null>;
 *   hintMessage: import('vue').Ref<string>;
 *   requestHint: () => Promise<void>;
 *   clearHintCursor: () => void;
 * }}
 */
export function useDoudizhuHint(input) {
  const {
    roomIdRef,
    gameViewVersionRef,
    currentPlayerIdRef,
    viewerPlayerIdRef,
    hintEnabledRef,
    actionOffersRef,
    applySelection,
    submitPass
  } = input;
  /** @type {import('vue').Ref<string|null>} */
  const hintCursor = ref(null);
  const hintMessage = ref('');
  /** @type {boolean} */
  let disposed = false;
  /** @type {boolean} */
  let requestInFlight = false;
  /** @type {AbortController|null} */
  let requestAbortController = null;
  /** @type {{ roomId: string; baseVersion: number; currentPlayerId: string; viewerPlayerId: string }|null} */
  let boundRequest = null;

  /**
   * 清空提示游标。
   */
  function clearHintCursor() {
    requestAbortController?.abort();
    requestAbortController = null;
    requestInFlight = false;
    hintCursor.value = null;
    hintMessage.value = '';
    boundRequest = null;
  }

  /**
   * 核对请求所有权和当前权限，防止取消后同一上下文的旧回包被再次接纳。
   * @param {object} context
   * @param {AbortController} controller
   * @returns {boolean}
   */
  function isCurrentRequest(context, controller) {
    return !disposed &&
      !controller.signal.aborted &&
      boundRequest === context &&
      requestAbortController === controller &&
      hintEnabledRef.value &&
      String(roomIdRef.value || '').trim() === context.roomId &&
      Number(gameViewVersionRef.value) === context.baseVersion &&
      String(currentPlayerIdRef?.value || '') === context.currentPlayerId &&
      String(viewerPlayerIdRef?.value || '') === context.viewerPlayerId;
  }

  /**
   * 请求下一条提示；服务端确认无候选且仍允许不出时复用按钮动作提交。
   * @returns {Promise<void>}
   */
  async function requestHint() {
    if (!hintEnabledRef.value || disposed || requestInFlight) {
      return;
    }
    const roomId = String(roomIdRef.value || '').trim();
    if (!roomId) {
      return;
    }

    const baseVersion = Number(gameViewVersionRef.value) || 0;
    if (baseVersion <= 0) {
      return;
    }
    const cursor = hintCursor.value;
    const requestContext = {
      roomId,
      baseVersion,
      currentPlayerId: String(currentPlayerIdRef?.value || ''),
      viewerPlayerId: String(viewerPlayerIdRef?.value || '')
    };

    requestInFlight = true;
    hintMessage.value = '';
    boundRequest = requestContext;
    const abortController = new AbortController();
    requestAbortController?.abort();
    requestAbortController = abortController;

    try {
      const raw = await roomGameService.fetchRoomActionSuggestions(roomId, {
        baseVersion,
        actionType: PLAY_CARDS_ACTION_TYPE,
        cursor,
        limit: 1,
        signal: abortController.signal
      });

      if (!isCurrentRequest(requestContext, abortController)) {
        return;
      }
      if (!Array.isArray(raw?.items)) {
        hintMessage.value = '提示暂不可用，请重试';
        return;
      }

      const parsed = ComposedActionAdapter.parseSuggestionsResponse(raw);
      const candidate = parsed.items[0];
      if (!candidate) {
        hintCursor.value = null;
        // 候选可能被截断；只有服务端完整核验无合法牌，才允许沿按钮提交链不出。
        const passAction = raw.items.length === 0 && raw.nextCursor === null && raw.hasLegalAction === false
          ? findFirstEnumeratedOption(actionOffersRef.value, 'PASS')
          : null;
        if (passAction?.actionId && isCurrentRequest(requestContext, abortController)) {
          await submitPass(passAction);
        } else {
          hintMessage.value = '暂未找到提示，请手动选牌或稍后重试';
        }
        return;
      }

      const cardInstanceIds = ComposedActionAdapter.extractCardInstanceIdsFromSuggestion(candidate);
      if (cardInstanceIds.length) {
        applySelection(cardInstanceIds);
      }

      hintCursor.value = parsed.nextCursor;
    } catch {
      if (isCurrentRequest(requestContext, abortController)) {
        hintMessage.value = '提示获取失败，请重试';
      }
    } finally {
      if (requestAbortController === abortController) {
        requestAbortController = null;
        requestInFlight = false;
        boundRequest = null;
      }
    }
  }

  const stopContextWatch = watch(
    [gameViewVersionRef, roomIdRef, hintEnabledRef, currentPlayerIdRef, viewerPlayerIdRef].filter(Boolean),
    clearHintCursor,
    { flush: 'sync' }
  );

  /**
   * 释放提示请求及上下文观察。
   * @returns {void}
   */
  function dispose() {
    disposed = true;
    stopContextWatch();
    clearHintCursor();
  }

  onUnmounted(dispose);

  return {
    hintCursor,
    hintMessage,
    requestHint,
    clearHintCursor,
    reset: clearHintCursor,
    dispose
  };
}
