/**
 * 校验 gameCode 非空。
 * @param {unknown} gameCode
 * @param {string} [context]
 * @returns {string}
 */
export function requireGameCode(gameCode, context) {
  const code = gameCode != null ? String(gameCode).trim() : '';
  if (!code) {
    const suffix = context ? `（${context}）` : '';
    throw new Error(`缺少 gameCode${suffix}`);
  }
  return code;
}
