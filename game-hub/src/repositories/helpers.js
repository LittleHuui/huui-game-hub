/**
 * @param {Record<string, unknown[]>} map
 * @param {string} userId
 */
export function ensureUserBucket(map, userId) {
  if (!map[userId]) {
    map[userId] = [];
  }
}
