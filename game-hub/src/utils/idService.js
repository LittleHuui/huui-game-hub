/**
 * 生成客户端唯一 ID。
 * @param {string} prefix
 * @returns {string}
 */
let fallbackSequence = 0;

export function createClientId(prefix) {
  fallbackSequence += 1;
  const uuid = globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `fallback_${fallbackSequence}_${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}_${uuid}`;
}
