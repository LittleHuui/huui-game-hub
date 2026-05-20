/**
 * 历史记录排序用时间戳：优先 updatedAt，否则 createdAt。
 * @param {object} row
 * @returns {number}
 */
export function historyRecordTimestamp(row) {
  const updated = row?.updatedAt;
  const created = row?.createdAt;
  if (typeof updated === 'number' && updated > 0) {
    return updated;
  }
  if (typeof created === 'number' && created > 0) {
    return created;
  }
  return 0;
}

/**
 * 按时间倒序排序（不按 gameCode 分组）。
 * @param {object[]} rows
 * @returns {object[]}
 */
export function sortHistoryRecordsDesc(rows) {
  return [...rows].sort((a, b) => historyRecordTimestamp(b) - historyRecordTimestamp(a));
}

/**
 * 取最近 N 条历史（时间倒序）。
 * @param {object[]} rows
 * @param {number} [limit=50]
 * @returns {object[]}
 */
export function recentHistoryRecords(rows, limit = 50) {
  return sortHistoryRecordsDesc(rows).slice(0, limit);
}
