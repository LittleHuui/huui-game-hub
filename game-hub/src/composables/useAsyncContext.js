import { onBeforeUnmount } from 'vue';

/** A page context owns its asynchronous work and cleanup functions. */
export function useAsyncContext() {
  let controller = new AbortController();
  let cleanups = [];
  let disposed = false;

  function capture() {
    const current = controller;
    return {
      signal: current.signal,
      isCurrent: () => !disposed && current === controller && !current.signal.aborted,
      own(cleanup) {
        if (disposed || current !== controller || current.signal.aborted) cleanup();
        else cleanups.push(cleanup);
      }
    };
  }

  function reset() {
    controller.abort();
    for (const cleanup of cleanups) cleanup();
    cleanups = [];
    controller = new AbortController();
    return capture();
  }

  onBeforeUnmount(() => {
    disposed = true;
    reset();
  });
  return { capture, reset };
}
