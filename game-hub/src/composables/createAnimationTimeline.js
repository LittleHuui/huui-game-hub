/**
 * 管理一次页面动画生命周期的延时与逐帧等待；取消时所有等待以 false 完成。
 * @returns {{wait: (ms: number) => Promise<boolean>; nextFrame: () => Promise<boolean>; cancel: () => void}}
 */
export function createAnimationTimeline() {
  const pending = new Set();
  let generation = 0;

  /**
   * 注册可取消等待。
   * @param {Function} schedule
   * @param {Function} unschedule
   * @returns {Promise<boolean>}
   */
  function waitFor(schedule, unschedule) {
    return new Promise((resolve) => {
      const finish = (completed) => {
        unschedule(handle);
        pending.delete(cancel);
        resolve(completed);
      };
      const cancel = () => finish(false);
      const handle = schedule(() => finish(true));
      pending.add(cancel);
    });
  }

  /** @param {number} ms @returns {Promise<boolean>} */
  function wait(ms) {
    return waitFor((callback) => setTimeout(callback, ms), clearTimeout);
  }

  /** 两帧后才能应用 CSS transition；取消后不再注册第二帧。 @returns {Promise<boolean>} */
  async function nextFrame() {
    const current = generation;
    if (!await waitFor(window.requestAnimationFrame.bind(window), window.cancelAnimationFrame.bind(window))) return false;
    if (current !== generation) return false;
    return waitFor(window.requestAnimationFrame.bind(window), window.cancelAnimationFrame.bind(window));
  }

  /** 结束全部延时与 RAF 等待。 @returns {void} */
  function cancel() {
    generation++;
    for (const finish of pending) finish();
  }

  return { wait, nextFrame, cancel };
}
