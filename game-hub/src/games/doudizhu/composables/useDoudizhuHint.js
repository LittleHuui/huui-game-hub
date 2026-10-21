import { onUnmounted, ref, watch } from 'vue';
import { ComposedActionAdapter } from '../../../services/action-interaction/composedActionAdapter.js';
import * as roomGameService from '../../../services/roomGameService.js';

const PLAY_CARDS_ACTION_TYPE = 'PLAY_CARDS';

/**
 * 管理斗地主提示（Suggestions）循环。
 * @param {object} input
 * @param {import('vue').Ref<string>} input.roomIdRef
 * @param {import('vue').Ref<number>} input.gameViewVersionRef
 * @param {import('vue').Ref<string>} [input.currentPlayerIdRef]
 * @param {import('vue').Ref<string>} [input.viewerPlayerIdRef]
 * @param {import('vue').ComputedRef<boolean>} input.hintEnabledRef
 * @param {(cardInstanceIds: string[]) => void} input.applySelection
 * @returns {{
 *   hintCursor: import('vue').Ref<string|null>;
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
    applySelection
  } = input;
  /** @type {import('vue').Ref<string|null>} */
  const hintCursor = ref(null);
  /** @type {boolean} */
  let disposed = false;
  /** @type {boolean} */
  let requestInFlight = false;
  /** @type {AbortController|null} */
  let requestAbortController = null;
  /** @type {{ roomId: string; baseVersion: number; cursor: string|null }|null} */
  let boundRequest = null;

  /**
   * 清空提示游标。
   */
  function clearHintCursor() {
    requestAbortController?.abort();
    requestAbortController = null;
    requestInFlight = false;
    hintCursor.value = null;
    boundRequest = null;
  }

  /**
   * 版本、房间或当前玩家变化时重置游标。
   */
  function resetHintOnContextChange() {
    clearHintCursor();
  }

  /**
   * 请求下一条提示并写入选牌（写入选牌后由 Preview composable 校验）。
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
    const cursor = hintCursor.value;
    const requestContext = {
      roomId,
      baseVersion,
      cursor: cursor != null ? String(cursor) : null
    };

    requestInFlight = true;
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

      if (
        disposed ||
        !boundRequest ||
        boundRequest.roomId !== requestContext.roomId ||
        boundRequest.baseVersion !== requestContext.baseVersion ||
        boundRequest.cursor !== requestContext.cursor
      ) {
        return;
      }

      const parsed = ComposedActionAdapter.parseSuggestionsResponse(raw);
      const candidate = parsed.items[0];
      if (!candidate) {
        clearHintCursor();
        return;
      }

      const cardInstanceIds = ComposedActionAdapter.extractCardInstanceIdsFromSuggestion(candidate);
      if (cardInstanceIds.length) {
        applySelection(cardInstanceIds);
      }

      hintCursor.value = parsed.nextCursor;
      boundRequest = null;
    } catch {
      // 提示失败时保持当前游标
    } finally {
      if (requestAbortController === abortController) {
        requestAbortController = null;
        requestInFlight = false;
      }
    }
  }

  watch(gameViewVersionRef, resetHintOnContextChange);
  watch(roomIdRef, resetHintOnContextChange);

  if (currentPlayerIdRef) {
    watch(currentPlayerIdRef, resetHintOnContextChange);
  }
  if (viewerPlayerIdRef) {
    watch(viewerPlayerIdRef, resetHintOnContextChange);
  }

  function dispose() {
    disposed = true;
    clearHintCursor();
  }

  onUnmounted(dispose);

  return {
    hintCursor,
    requestHint,
    clearHintCursor,
    reset: clearHintCursor,
    dispose
  };
}
