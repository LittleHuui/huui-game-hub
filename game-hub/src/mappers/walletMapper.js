import { nowMs } from '../utils/timeService.js';

/**
 * @param {object} wallet
 * @returns {{ score: number; totalScore: number }}
 */
export function mapRemoteWalletToLocal(wallet) {
  return {
    score: Number(wallet.balance) || 0,
    totalScore: Number(wallet.totalEarned) || 0
  };
}

/**
 * @param {object} remote
 * @returns {import('../stores/walletStore.js').WalletLedger}
 */
export function mapWalletLedger(remote) {
  const rawAmount = Number(remote.amount) || 0;
  const changeType = String(remote.changeType || '').toLowerCase();
  let type = 'gain';
  if (changeType === 'cost') {
    type = 'cost';
  } else if (changeType === 'refund') {
    type = 'refund';
  }
  return {
    clientId: remote.clientId || '',
    serverId: remote.serverId || null,
    userId: remote.userId || '',
    deviceId: remote.deviceId || '',
    gameCode: remote.gameCode || '',
    type,
    reason: remote.reason || '',
    amount: Math.abs(rawAmount),
    createdAt: remote.createdAt ?? nowMs(),
    updatedAt: remote.updatedAt ?? nowMs(),
    syncedAt: remote.syncedAt ?? remote.updatedAt ?? nowMs(),
    syncStatus: 'synced',
    payload: remote.payload || {}
  };
}

/**
 * @param {import('../stores/walletStore.js').WalletLedger} row
 * @returns {object}
 */
export function mapLocalWalletLedgerToPayload(row) {
  const changeType = row.type === 'cost' ? 'cost' : row.type === 'refund' ? 'refund' : 'gain';
  const amt = Math.abs(row.amount);
  return {
    clientId: row.clientId,
    userId: row.userId,
    deviceId: row.deviceId,
    gameCode: row.gameCode,
    changeType,
    reason: row.reason,
    amount: row.type === 'cost' ? -amt : amt,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    payload: row.payload || {}
  };
}

/**
 * 按流水计算截至某条记录后的余额。
 * @param {import('../stores/walletStore.js').WalletLedger[]} ledgers
 * @param {number} upToCreatedAt
 * @returns {number}
 */
export function computeWalletBalanceAfter(ledgers, upToCreatedAt) {
  const list = ledgers
    .filter((x) => (x.createdAt || 0) <= (upToCreatedAt || 0))
    .sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));
  let score = 0;
  for (const e of list) {
    if (e.syncStatus === 'failed') {
      continue;
    }
    const amt = Math.abs(e.amount || 0);
    if (e.type === 'gain' || e.type === 'refund') {
      score += amt;
    } else if (e.type === 'cost') {
      score -= amt;
    }
  }
  return score;
}
