/**
 * 返回防抖后的函数。
 * @template {(...args: unknown[]) => unknown} T
 * @param {T} fn
 * @param {number} waitMs
 * @returns {(...args: Parameters<T>) => void}
 */
export function debounce(fn, waitMs = 300) {
  let timer = null;
  return (...args) => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = null;
      fn(...args);
    }, waitMs);
  };
}
