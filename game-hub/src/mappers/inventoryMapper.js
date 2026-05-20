/**
 * 远端背包列表 → 按 gameCode 分组的 propCode 数量。
 * @param {object[]} inventory
 * @returns {Record<string, Record<string, number>>}
 */
export function mapRemoteInventoryToBagByGame(inventory) {
  /** @type {Record<string, Record<string, number>>} */
  const byGame = {};
  if (!Array.isArray(inventory)) {
    return byGame;
  }
  for (const row of inventory) {
    const gameCode = row.gameCode;
    const propCode = row.propCode;
    if (!gameCode || !propCode) {
      continue;
    }
    if (!byGame[gameCode]) {
      byGame[gameCode] = {};
    }
    byGame[gameCode][propCode] = Math.max(0, Number(row.quantity) || 0);
  }
  return byGame;
}

/**
 * 单游戏背包列表 → propCode 数量。
 * @param {object[]} inventory
 * @returns {Record<string, number>}
 */
export function mapRemoteInventoryListToQuantities(inventory) {
  /** @type {Record<string, number>} */
  const map = {};
  if (!Array.isArray(inventory)) {
    return map;
  }
  for (const row of inventory) {
    if (!row?.propCode) {
      continue;
    }
    map[row.propCode] = Math.max(0, Number(row.quantity) || 0);
  }
  return map;
}

/**
 * @param {object} remote
 * @returns {object}
 */
export function mapPropUsageRecord(remote) {
  return {
    clientId: remote.clientId || '',
    serverId: remote.serverId || null,
    userId: remote.userId || '',
    deviceId: remote.deviceId || '',
    gameCode: remote.gameCode || '',
    propCode: remote.propCode || '',
    quantity: remote.quantity ?? 1,
    reason: remote.useReason || 'use',
    createdAt: remote.createdAt ?? Date.now(),
    updatedAt: remote.updatedAt ?? Date.now(),
    syncedAt: remote.syncedAt ?? null,
    syncStatus: 'synced',
    payload: remote.payload || { label: remote.useReason || remote.propCode }
  };
}

/**
 * @param {import('../stores/inventoryStore.js').InventoryLedger} row
 * @returns {object}
 */
export function mapLocalInventoryLedgerToPayload(row) {
  return {
    clientId: row.clientId,
    userId: row.userId,
    deviceId: row.deviceId,
    gameCode: row.gameCode,
    propCode: row.propCode,
    quantity: row.amount,
    useReason: row.reason,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    payload: row.payload || {}
  };
}
