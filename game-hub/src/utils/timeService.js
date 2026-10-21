/**
 * 当前毫秒时间戳。
 * @returns {number}
 */
export function nowMs() {
  return Date.now();
}

/** 将秒数按 mm:ss 展示；各游戏共享同一格式语义。 */
export function formatDurationMmSs(totalSec) {
  const sec = Math.max(0, Math.floor(totalSec));
  const minutes = Math.floor(sec / 60);
  const seconds = sec % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

/**
 * 将 API/本地缓存中的时间值统一为毫秒整数。
 * @param {unknown} value
 * @param {number|null} [fallback]
 * @returns {number|null}
 */
export function toTimestampMs(value, fallback = null) {
  if (value == null || value === '') {
    return fallback;
  }
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return Math.round(numeric);
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? Math.round(parsed) : fallback;
}
