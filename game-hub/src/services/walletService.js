import * as walletRepository from '../repositories/walletRepository.js';
import { persistAllLocal } from '../repositories/localPersistRepository.js';
import { computeWalletBalanceAfter } from '../mappers/walletMapper.js';
import { useWalletStore } from '../stores/walletStore.js';
import { useUserStore } from '../stores/userStore.js';
import * as localRepo from '../repositories/localRepository.js';
import * as syncRepository from '../repositories/syncRepository.js';
import { nowMs } from '../utils/timeService.js';

/**
 * 积分增加流水。
 * @param {number} amount
 * @param {string} reason
 * @param {Record<string, unknown>} [payload]
 * @param {string} [gameCode]
 */
export function ledgerGain(amount, reason, payload = {}, gameCode = 'minesweeper') {
  if (!amount) {
    return;
  }
  const t = nowMs();
  const userStore = useUserStore();
  walletRepository.pushWalletLedger(
    {
      userId: userStore.auth.currentUserId,
      deviceId: localRepo.getDeviceId(),
      gameCode,
      type: 'gain',
      reason,
      amount,
      createdAt: t,
      updatedAt: t,
      syncStatus: 'pending',
      payload
    },
    (e) => syncRepository.appendPendingEvent(e)
  );
}

/**
 * 积分扣减流水。
 * @param {number} amount
 * @param {string} reason
 * @param {Record<string, unknown>} [payload]
 * @param {string} [gameCode]
 */
export function ledgerCost(amount, reason, payload = {}, gameCode = 'minesweeper') {
  if (!amount) {
    return;
  }
  const t = nowMs();
  const userStore = useUserStore();
  walletRepository.pushWalletLedger(
    {
      userId: userStore.auth.currentUserId,
      deviceId: localRepo.getDeviceId(),
      gameCode,
      type: 'cost',
      reason,
      amount,
      createdAt: t,
      updatedAt: t,
      syncStatus: 'pending',
      payload
    },
    (e) => syncRepository.appendPendingEvent(e)
  );
}

/**
 * 刷新远端钱包流水（模态打开时）。
 * @param {string} serverUserId
 */
export async function refreshRemote(serverUserId) {
  await walletRepository.refreshWallet(serverUserId);
}

/**
 * 流水展示用余额。
 * @param {object} row
 * @returns {number}
 */
export function balanceAfterLedgerRow(row) {
  const uid = useUserStore().auth.currentUserId;
  const list = useWalletStore().listForUser(uid);
  return computeWalletBalanceAfter(list, row.createdAt || 0);
}

export function persistLocal() {
  persistAllLocal();
}
