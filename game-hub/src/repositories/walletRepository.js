import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import { mapWalletLedger, mapRemoteWalletToLocal, mapLocalWalletLedgerToPayload } from '../mappers/walletMapper.js';
import { pageItems, groupByUserId } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useWalletStore } from '../stores/walletStore.js';
import { remoteRepository } from './remoteRepository.js';
import * as localRepo from './localRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';

const PAGE = { pageNum: 1, pageSize: 20 };

/**
 * 从流水重算用户积分。
 * @param {string} userId
 */
export function recomputeFromLedgers(userId) {
  const userStore = useUserStore();
  const walletStore = useWalletStore();
  const ledgers = walletStore.listForUser(userId);
  const sorted = [...ledgers].sort((a, b) => (a.createdAt || 0) - (b.createdAt || 0));
  let score = 0;
  let totalScore = 0;
  for (const e of sorted) {
    if (e.syncStatus === 'failed') {
      continue;
    }
    const amt = Math.abs(Number(e.amount) || 0);
    if (e.type === 'gain') {
      score += amt;
      totalScore += amt;
    } else if (e.type === 'cost') {
      score -= amt;
    }
  }
  userStore.patchUserScores(userId, score, totalScore);
}

/**
 * @param {Omit<import('../stores/walletStore.js').WalletLedger, 'syncedAt' | 'serverId'>} partial
 * @param {(event: object) => void} [onPending]
 */
export function pushWalletLedger(partial, onPending) {
  const userStore = useUserStore();
  const walletStore = useWalletStore();
  const uid = partial.userId || userStore.auth.currentUserId;
  ensureUserBucket(walletStore.walletLedgersByUser, uid);
  const row = {
    clientId: partial.clientId || createClientId('wl'),
    serverId: null,
    userId: uid,
    deviceId: partial.deviceId || localRepo.getDeviceId(),
    gameCode: partial.gameCode || 'minesweeper',
    type: partial.type,
    reason: partial.reason,
    amount: Math.abs(Number(partial.amount) || 0),
    createdAt: partial.createdAt ?? nowMs(),
    updatedAt: partial.updatedAt ?? nowMs(),
    syncedAt: null,
    syncStatus: partial.syncStatus || 'pending',
    payload: partial.payload || {}
  };
  walletStore.walletLedgersByUser[uid].push(row);
  recomputeFromLedgers(uid);
  if (row.syncStatus === 'pending' && resolveServerUserId() && onPending) {
    onPending({
      clientId: row.clientId,
      eventType: 'wallet_ledger',
      createdAt: row.createdAt,
      updatedAt: row.updatedAt,
      payload: mapLocalWalletLedgerToPayload(row)
    });
  }
  localRepo.writeWalletLedgers(walletStore.walletLedgersByUser);
  persistAllLocal();
}

/**
 * 应用云端钱包快照。
 * @param {object[]} walletLedgers
 * @param {object} [wallet]
 * @param {string} [currentUserId]
 */
export function applyCloudWallet(walletLedgers, wallet, currentUserId) {
  const walletStore = useWalletStore();
  const userStore = useUserStore();
  if (Array.isArray(walletLedgers) && walletLedgers.length) {
    const mapped = walletLedgers.map(mapWalletLedger);
    walletStore.replaceAll(groupByUserId(mapped));
  }
  const uid = currentUserId || userStore.auth.currentUserId;
  if (uid && wallet) {
    const scores = mapRemoteWalletToLocal(wallet);
    userStore.patchUserScores(uid, scores.score, scores.totalScore);
  }
}

/**
 * 远端刷新钱包。
 * @param {string} userId
 */
export async function refreshWallet(userId) {
  const wallet = await remoteRepository.getWallet(userId);
  const ledgersPage = await remoteRepository.getWalletLedgers(userId, PAGE);
  const userStore = useUserStore();
  const walletStore = useWalletStore();
  const scores = mapRemoteWalletToLocal(wallet);
  userStore.patchUserScores(userId, scores.score, scores.totalScore);
  walletStore.walletLedgersByUser[userId] = pageItems(ledgersPage).map(mapWalletLedger);
  persistAllLocal();
}
