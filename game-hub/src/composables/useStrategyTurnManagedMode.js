import * as roomService from '../services/roomService.js';
import { computed, watch } from 'vue';
import { canFetchRemote } from '../services/remoteGate.js';
import { useAsyncContext } from './useAsyncContext.js';

/**
 * 复用策略回合页面的托管命令与请求状态更新。
 * @param {object} input
 * @param {import('vue').Ref<string>} input.roomIdRef
 * @param {import('vue').Ref<boolean>} input.managedActiveRef
 * @param {import('vue').Ref<boolean>} input.busyRef
 * @param {import('vue').Ref<string>} input.errorRef
 * @param {boolean} [input.clearErrorOnRequest=true] 是否在请求开始时清空旧错误。
 * @returns {{ start: () => Promise<void>; stop: () => Promise<void> }}
 */
export function useStrategyTurnManagedMode(input) {
  const context = useAsyncContext();
  const onlineAvailable = computed(canFetchRemote);
  watch([input.roomIdRef, onlineAvailable], () => {
    context.reset();
    input.busyRef.value = false;
  }, { flush: 'sync' });
  /**
   * 提交目标托管状态；保留页面既有的错误显示策略。
   * @param {boolean} enabled
   * @returns {Promise<void>}
   */
  async function changeManagedMode(enabled) {
    const roomId = input.roomIdRef.value;
    const operation = context.capture();
    if (!roomId || input.busyRef.value || !onlineAvailable.value || !operation.isCurrent() || Boolean(input.managedActiveRef.value) === enabled) {
      return;
    }
    input.busyRef.value = true;
    if (input.clearErrorOnRequest !== false) {
      input.errorRef.value = '';
    }
    try {
      if (enabled) {
        await roomService.startManagedMode(roomId, { signal: operation.signal });
      } else {
        await roomService.stopManagedMode(roomId, { signal: operation.signal });
      }
    } catch (err) {
      if (operation.isCurrent()) input.errorRef.value = err?.message || (enabled ? '开启托管失败' : '取消托管失败');
    } finally {
      if (operation.isCurrent()) input.busyRef.value = false;
    }
  }

  /**
   * 开启当前房间托管。
   * @returns {Promise<void>}
   */
  function start() {
    return changeManagedMode(true);
  }

  /**
   * 取消当前房间托管。
   * @returns {Promise<void>}
   */
  function stop() {
    return changeManagedMode(false);
  }

  return { start, stop };
}
