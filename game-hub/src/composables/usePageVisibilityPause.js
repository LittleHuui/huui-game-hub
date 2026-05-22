import { onBeforeUnmount, onMounted } from 'vue';

/**
 * 浏览器标签页隐藏时触发暂停；标签页重新可见时不自动恢复。
 * 仅注册 visibilitychange 监听，具体暂停条件与计时由业务页通过回调实现。
 *
 * @param {object} options
 * @param {() => boolean} [options.shouldPause] 返回 true 时才调用 pause（默认始终暂停）
 * @param {() => void} options.pause 由业务页实现的暂停逻辑（如 pauseGame）
 * @returns {{ handleVisibilityChange: () => void }}
 */
export function usePageVisibilityPause(options) {
  const { shouldPause, pause } = options;

  function handleVisibilityChange() {
    if (!document.hidden) {
      return;
    }

    if (typeof shouldPause === 'function' && !shouldPause()) {
      return;
    }

    pause();
  }

  onMounted(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  });

  return {
    handleVisibilityChange
  };
}
