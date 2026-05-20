import { watch, onBeforeUnmount } from 'vue';
import { usePlatformStore } from '../stores/platformStore.js';

export const GAME_SWITCH_LOCK_DEFAULT_REASON =
  '当前对局进行中，请结束或重新开始后再切换游戏';

/**
 * 对局进行中同步平台层游戏切换锁（顶栏换游戏、换用户等共用）。
 * @param {import('vue').Ref<boolean>|import('vue').ComputedRef<boolean>} isInProgress
 * @param {string} [reason]
 */
export function useGameSwitchLock(isInProgress, reason = GAME_SWITCH_LOCK_DEFAULT_REASON) {
  const platform = usePlatformStore();

  watch(
    isInProgress,
    (locked) => {
      if (locked) {
        platform.lockGameSwitch(reason);
      } else {
        platform.unlockGameSwitch();
      }
    },
    { immediate: true }
  );

  onBeforeUnmount(() => {
    platform.unlockGameSwitch();
  });
}
