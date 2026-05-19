/**
 * 仅用于界面展示，禁止写入缓存或上传。
 * @param {number} timestamp Unix 毫秒
 * @returns {string}
 */
export function formatDisplayTime(timestamp) {
  if (timestamp == null || !Number.isFinite(timestamp)) {
    return '—';
  }
  return new Date(timestamp).toLocaleString();
}
