const PROP_LOCAL_KEYS = {
  hint_card: 'hintCard',
  revive_card: 'reviveCard',
  match3_shuffle: 'match3Shuffle',
  match3_bomb: 'match3Bomb'
};

/**
 * @param {object[]} inventory
 * @returns {{ hintCard: number; reviveCard: number; match3Shuffle?: number; match3Bomb?: number }}
 */
export function mapRemoteInventoryToLocalProps(inventory) {
  const props = { hintCard: 0, reviveCard: 0 };
  if (!Array.isArray(inventory)) {
    return props;
  }
  for (const row of inventory) {
    const key = PROP_LOCAL_KEYS[row.propCode];
    if (key) {
      props[key] = Number(row.quantity) || 0;
    }
  }
  return props;
}

/**
 * 购买结果中的单条背包项 → 本地 props 补丁。
 * @param {object} inventoryItem
 * @returns {{ hintCard?: number; reviveCard?: number }}
 */
export function mapRemoteInventoryItemToLocalProps(inventoryItem) {
  if (!inventoryItem || !inventoryItem.propCode) {
    return {};
  }
  const qty = Number(inventoryItem.quantity) || 0;
  const key = PROP_LOCAL_KEYS[inventoryItem.propCode];
  if (key === 'hintCard') {
    return { hintCard: qty };
  }
  if (key === 'reviveCard') {
    return { reviveCard: qty };
  }
  return {};
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
