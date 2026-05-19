/**
 * 分页响应取 items。
 * @param {unknown} pageOrList
 * @returns {object[]}
 */
export function pageItems(pageOrList) {
  if (Array.isArray(pageOrList)) {
    return pageOrList;
  }
  if (pageOrList && Array.isArray(pageOrList.items)) {
    return pageOrList.items;
  }
  return [];
}

/**
 * @param {object[]} list
 * @param {string} [userIdKey]
 * @returns {Record<string, object[]>}
 */
export function groupByUserId(list, userIdKey = 'userId') {
  const map = {};
  if (!Array.isArray(list)) {
    return map;
  }
  for (const row of list) {
    const uid = row[userIdKey];
    if (!uid) {
      continue;
    }
    if (!map[uid]) {
      map[uid] = [];
    }
    map[uid].push(row);
  }
  return map;
}
