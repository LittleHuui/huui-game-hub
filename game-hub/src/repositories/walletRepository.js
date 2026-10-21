import { createClientId } from '../utils/idService.js';
import { nowMs } from '../utils/timeService.js';
import { mapWalletLedger, mapRemoteWalletToLocal, mapLocalWalletLedgerToPayload } from '../mappers/walletMapper.js';
import { pageItems } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useWalletStore } from '../stores/walletStore.js';
import { remoteRepository } from './remoteRepository.js';
import * as localRepo from './localRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';
import { requireGameCode } from '../utils/requireGameCode.js';

import { captureUserDataIdentity, mapRecordsToIdentity } from './userDataIdentity.js';
import { mergeRecordsByClientId } from './recordMerge.js';

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
    } else if (e.type === 'refund') {
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
    gameCode: requireGameCode(partial.gameCode, 'pushWalletLedger'),
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
  const identity = captureUserDataIdentity(useUserStore(), currentUserId);
  const walletStore = useWalletStore();
  const uid = identity.localUserId;
  const mapped = mapRecordsToIdentity(walletLedgers, mapWalletLedger, identity);
  walletStore.walletLedgersByUser[uid] = mergeRecordsByClientId(walletStore.listForUser(uid), mapped);
  if (Array.isArray(walletLedgers)) recomputeFromLedgers(uid);
  else if (wallet) {
    const scores = mapRemoteWalletToLocal(wallet);
    useUserStore().patchUserScores(uid, scores.score, scores.totalScore);
  }
}

/** 读取有界分页，确认完整后才合并事实；首屏缓存单独用于展示。 */
export async function refreshWallet(userId) {
  const identity = captureUserDataIdentity(useUserStore(), userId);
  const firstPage = await remoteRepository.getWalletLedgers(userId, PAGE);
  const total = Number(firstPage?.total);
  if (!Number.isInteger(total) || total < 0) throw new Error('钱包流水分页总数无效');
  const pageCount = Math.max(1, Math.ceil(total / PAGE.pageSize));
  const pages = [firstPage];
  for (let pageNum = 2; pageNum <= pageCount; pageNum += 1) {
    pages.push(await remoteRepository.getWalletLedgers(userId, { ...PAGE, pageNum }));
  }
  const remoteRows = [];
  for (let index = 0; index < pages.length; index += 1) {
    const page = pages[index];
    const expectedCount = Math.min(PAGE.pageSize, total - index * PAGE.pageSize);
    if (Number(page?.total) !== total || !Array.isArray(page?.items) || page.items.length !== expectedCount) {
      throw new Error('钱包流水在读取期间发生变化，请重试');
    }
    remoteRows.push(...page.items);
  }
  const mapped = mapRecordsToIdentity(remoteRows, mapWalletLedger, identity);
  const keys = new Set(mapped.map((row) => row.clientId || row.serverId).filter(Boolean));
  if (mapped.length !== total || keys.size !== total) throw new Error('钱包流水分页不完整，请重试');
  const store = useWalletStore();
  const uid = identity.localUserId;
  store.walletLedgersByUser[uid] = mergeRecordsByClientId(store.listForUser(uid), mapped);
  store.setDisplayPage(uid, mapRecordsToIdentity(pageItems(firstPage), mapWalletLedger, identity));
  recomputeFromLedgers(uid);
  persistAllLocal();
}
