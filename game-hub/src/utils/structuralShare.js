/**
 * 判断值是否是可递归比较的普通对象。
 * @param {unknown} value
 * @returns {boolean}
 */
function isPlainObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

/**
 * 复用与上一快照相同的分支。
 *
 * 接口快照按值传输，Vue 视图只需要对实际变化的数据触发更新。该工具不解释
 * 任何游戏字段，可用于所有需要稳定引用的展示快照。
 * @param {unknown} previous
 * @param {unknown} next
 * @returns {unknown}
 */
export function shareUnchangedStructure(previous, next) {
  if (Object.is(previous, next)) {
    return previous;
  }
  if (Array.isArray(previous) && Array.isArray(next)) {
    if (previous.length !== next.length) {
      return next;
    }
    let changed = false;
    const result = next.map((item, index) => {
      const value = shareUnchangedStructure(previous[index], item);
      changed ||= value !== previous[index];
      return value;
    });
    return changed ? result : previous;
  }
  if (isPlainObject(previous) && isPlainObject(next)) {
    const nextKeys = Object.keys(next);
    const previousKeys = Object.keys(previous);
    if (nextKeys.length !== previousKeys.length) {
      return next;
    }
    let changed = false;
    const result = {};
    for (const key of nextKeys) {
      if (!Object.prototype.hasOwnProperty.call(previous, key)) {
        return next;
      }
      const value = shareUnchangedStructure(previous[key], next[key]);
      changed ||= value !== previous[key];
      result[key] = value;
    }
    return changed ? result : previous;
  }
  return next;
}
