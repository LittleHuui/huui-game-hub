/**
 * 生成客户端唯一 ID。
 * @param {string} prefix
 * @returns {string}
 */
export function createClientId(prefix) {
  const uuid = globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID()
    : `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}_${uuid}`;
}
