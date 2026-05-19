import { nowMs } from '../utils/timeService.js';

/**
 * @param {object} remote
 * @returns {object}
 */
export function mapPurchaseRecord(remote) {
  return {
    clientId: remote.clientId || '',
    serverId: remote.serverId || null,
    userId: remote.userId || '',
    deviceId: remote.deviceId || '',
    gameCode: remote.gameCode || '',
    propCode: remote.propCode || '',
    quantity: remote.quantity ?? 1,
    unitPrice: remote.unitPrice ?? 0,
    totalPrice: remote.totalPrice ?? 0,
    createdAt: remote.createdAt ?? nowMs(),
    updatedAt: remote.updatedAt ?? nowMs(),
    syncedAt: remote.syncedAt ?? null,
    syncStatus: 'synced',
    payload: {
      label: remote.propCode || '购买',
      cost: remote.totalPrice ?? 0
    }
  };
}

/**
 * @param {object} row
 * @returns {object}
 */
export function mapLocalPurchaseToPayload(row) {
  return {
    clientId: row.clientId,
    userId: row.userId,
    deviceId: row.deviceId,
    gameCode: row.gameCode,
    propCode: row.propCode || row.payload?.propCode || '',
    quantity: row.quantity ?? 1,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt
  };
}
