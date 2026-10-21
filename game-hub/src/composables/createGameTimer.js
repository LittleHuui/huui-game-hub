/**
 * Cancellable interval timer with an injectable scheduler for deterministic tests.
 * @param {{ onTick: () => void; intervalMs?: number; scheduler?: Pick<typeof globalThis, 'setInterval'|'clearInterval'> }} options
 */
export function createGameTimer({ onTick, intervalMs = 1000, scheduler = globalThis }) {
  let timerId = null;

  function start() {
    if (timerId != null) {
      return;
    }
    timerId = scheduler.setInterval(onTick, intervalMs);
  }

  function stop() {
    if (timerId == null) {
      return;
    }
    scheduler.clearInterval(timerId);
    timerId = null;
  }

  return {
    start,
    stop,
    reset: stop,
    isRunning: () => timerId != null
  };
}
