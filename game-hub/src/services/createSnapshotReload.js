/**
 * 合并同一上下文的快照恢复请求，并在取消时结束请求和退避等待。
 * apply 返回当前已接受版本；连续缺口只提高目标版本，不取消在途请求。
 * @param {{load: Function; apply: Function; readVersion: Function; onStart: Function; onReady: Function; onFailure: Function; backoffMs: number[]}} options
 * @returns {{request: Function; cancel: Function}}
 */
export function createSnapshotReload({ load, apply, readVersion, onStart, onReady, onFailure, backoffMs }) {
  let active = null;

  /** 结束当前请求及退避等待，旧响应不再调用 apply。 @returns {void} */
  function cancel() {
    const previous = active;
    active = null;
    previous?.controller.abort();
  }

  /**
   * 同一上下文合并目标版本；新上下文取消旧请求。
   * @param {string} key
   * @param {number} [minimumVersion]
   * @returns {Promise<object|null>}
   */
  function request(key, minimumVersion = 0) {
    if (active?.key === key) {
      active.minimumVersion = Math.max(active.minimumVersion, minimumVersion);
      return active.promise;
    }
    cancel();
    const controller = new AbortController();
    const operation = { key, minimumVersion, initialVersion: readVersion(), controller, promise: null };
    active = operation;
    operation.promise = Promise.resolve().then(() => run(operation));
    onStart();
    return operation.promise;
  }

  /**
   * 有限退避恢复；取消、后续推送追平以及低版本 HTTP 都有明确完成语义。
   * @param {object} operation
   * @returns {Promise<object|null>}
   */
  async function run(operation) {
    const { key, controller } = operation;
    const { signal } = controller;
    let timer = null;
    let finishCancellation;
    const cancellation = new Promise((resolve) => { finishCancellation = resolve; });
    const onAbort = () => finishCancellation(null);
    signal.addEventListener('abort', onAbort, { once: true });
    try {
      for (let attempt = 0; attempt < backoffMs.length; attempt++) {
        if (backoffMs[attempt] > 0) {
          await Promise.race([
            cancellation,
            new Promise((resolve) => { timer = setTimeout(resolve, backoffMs[attempt]); })
          ]);
          clearTimeout(timer);
          timer = null;
        }
        if (signal.aborted) return null;
        try {
          const view = await Promise.race([
            cancellation,
            Promise.resolve().then(() => signal.aborted ? null : load(key, { signal }))
          ]);
          if (signal.aborted) return null;
          const version = apply(view);
          if (signal.aborted) return null;
          if (version < operation.minimumVersion) {
            throw new Error('权威视图尚未追上最新版本');
          }
          active = null;
          onReady();
          return view;
        } catch (error) {
          if (signal.aborted) return null;
          if (readVersion() > operation.initialVersion && readVersion() >= operation.minimumVersion) {
            active = null;
            onReady();
            return null;
          }
          if (attempt === backoffMs.length - 1) {
            active = null;
            onFailure(error);
          }
        }
      }
      return null;
    } finally {
      clearTimeout(timer);
      signal.removeEventListener('abort', onAbort);
      if (active === operation) active = null;
    }
  }

  return { request, cancel };
}
