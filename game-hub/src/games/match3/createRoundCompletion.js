/**
 * 一局一次只接受一个棋盘动作；结束请求等待已接受动作，并保留唯一结算 Promise。
 * 结算失败不自动重放落盘；重开/卸载结束旧等待，旧异步响应须用 isCurrent 守卫。
 * @param {{settle: Function; onEndingChanged: Function}} options
 * @returns {{run: Function; finish: Function; reset: Function; readonly generation: number}}
 */
export function createRoundCompletion({ settle, onEndingChanged }) {
  let generation = 0;
  let controller = new AbortController();
  let action = null;
  let completion = null;

  /** 作废上一局并结束其动作和结算等待。 @returns {void} */
  function reset() {
    generation++;
    controller.abort();
    controller = new AbortController();
    action = null;
    completion = null;
    onEndingChanged(false);
  }

  /**
   * 将对局取消与异步任务一起等待，且始终消费旧任务的 rejection。
   * @param {Promise<unknown>} task
   * @param {AbortSignal} signal
   * @returns {Promise<unknown>}
   */
  function untilReset(task, signal) {
    return new Promise((resolve, reject) => {
      const cancel = () => resolve(null);
      signal.addEventListener('abort', cancel, { once: true });
      task.then((value) => {
        signal.removeEventListener('abort', cancel);
        resolve(value);
      }, (error) => {
        signal.removeEventListener('abort', cancel);
        reject(error);
      });
      if (signal.aborted) cancel();
    });
  }

  /**
   * 同步接纳并启动动作，避免倒计时在入场微任务前锁掉已接受输入。
   * @param {Function} actionHandler
   * @returns {Promise<unknown>}
   */
  function run(actionHandler) {
    if (action || completion) return Promise.resolve(null);
    let resolveAction;
    let rejectAction;
    const task = new Promise((resolve, reject) => {
      resolveAction = resolve;
      rejectAction = reject;
    });
    const operation = untilReset(task, controller.signal);
    action = operation;
    try {
      Promise.resolve(actionHandler()).then(resolveAction, rejectAction);
    } catch (error) {
      rejectAction(error);
    }
    return operation.finally(() => {
      if (action === operation) action = null;
    });
  }

  /**
   * 接受一次结束意图；动作最终产生的 deadBoard 也进入同一结算载荷。
   * @param {boolean} [deadBoard]
   * @returns {Promise<unknown>}
   */
  function finish(deadBoard = false) {
    if (completion) return completion;
    const currentGeneration = generation;
    const isCurrent = () => generation === currentGeneration;
    const pendingAction = action;
    const task = Promise.resolve(pendingAction).then((result) => {
      if (!isCurrent() || result?.aborted) return null;
      return settle(deadBoard || Boolean(result?.deadBoard), isCurrent);
    });
    const operation = untilReset(task, controller.signal).finally(() => {
      if (isCurrent()) onEndingChanged(false);
    });
    completion = operation;
    onEndingChanged(true);
    return operation;
  }

  return { run, finish, reset, get generation() { return generation; } };
}
