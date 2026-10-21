/**
 * 从调用方快照捕获已有本地/服务端映射，供异步结果选择原目标桶。
 * @param {{users: object[]; auth: {currentUserId: string}}} store
 * @param {string} [serverUserId]
 * @returns {{localUserId: string; serverUserId: string}}
 */
export function captureUserDataIdentity(store, serverUserId) {
  const current = store.users.find((user) => user.userId === store.auth.currentUserId);
  const matches = (user) => user.userId === serverUserId || user.serverId === serverUserId;
  const user = serverUserId
    ? (current && matches(current) ? current : store.users.find(matches))
    : current;
  if (!user) throw new Error('用户数据目标不存在');
  return { localUserId: user.userId, serverUserId: user.serverId || user.userId };
}

/**
 * 核对当前快照仍对应发起请求时的身份。
 * @param {{users: object[]; auth: {currentUserId: string}}} store
 * @param {{localUserId: string; serverUserId: string}} identity
 * @returns {boolean}
 */
export function isCurrentUserDataIdentity(store, identity) {
  const user = store.users.find((entry) => entry.userId === identity.localUserId);
  return store.auth.currentUserId === identity.localUserId &&
    (user?.serverId || user?.userId) === identity.serverUserId;
}

/**
 * 只映射属于请求原身份的记录，不在此处读取或写入响应式状态。
 * @param {object[]} records
 * @param {(record: object) => object} mapper
 * @param {{localUserId: string; serverUserId: string}} identity
 * @returns {object[]}
 */
export function mapRecordsToIdentity(records, mapper, identity) {
  return (Array.isArray(records) ? records : [])
    .filter((row) => !row.userId || row.userId === identity.serverUserId || row.userId === identity.localUserId)
    .map((row) => ({ ...mapper(row), userId: identity.localUserId }));
}
