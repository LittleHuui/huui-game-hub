import { mapPurchaseRecord, mapLocalPurchaseToPayload } from '../mappers/purchaseMapper.js';
import { mapRemoteWalletToLocal } from '../mappers/walletMapper.js';
import { mapRemoteInventoryItemToLocalProps } from '../mappers/inventoryMapper.js';
import { pageItems } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { remoteRepository } from './remoteRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';

const PAGE = { pageNum: 1, pageSize: 20 };

/**
 * @param {object} rec
 * @param {(event: object) => void} [onPending]
 */
export function pushPurchaseRecord(rec, onPending) {
  const userStore = useUserStore();
  const historyStore = useHistoryStore();
  const uid = rec.userId || userStore.auth.currentUserId;
  ensureUserBucket(historyStore.purchaseRecordsByUser, uid);
  historyStore.purchaseRecordsByUser[uid].push(rec);
  if (rec.syncStatus !== 'synced' && resolveServerUserId() && onPending) {
    onPending({
      clientId: rec.clientId,
      eventType: 'prop_purchase',
      createdAt: rec.createdAt,
      updatedAt: rec.updatedAt,
      payload: mapLocalPurchaseToPayload(rec)
    });
  }
  persistAllLocal();
}

/**
 * 应用远端购买结果。
 * @param {object} result
 */
export function applyPurchaseResult(result) {
  const userStore = useUserStore();
  const historyStore = useHistoryStore();
  const uid = resolveServerUserId() || userStore.auth.currentUserId;
  if (result.wallet) {
    const scores = mapRemoteWalletToLocal(result.wallet);
    userStore.patchUserScores(uid, scores.score, scores.totalScore);
  }
  if (result.inventoryItem) {
    const patch = mapRemoteInventoryItemToLocalProps(result.inventoryItem);
    const u = userStore.users.find((x) => x.userId === uid);
    if (u) {
      userStore.patchUserProps(uid, { ...u.props, ...patch });
    }
  }
  if (result.purchaseRecord) {
    ensureUserBucket(historyStore.purchaseRecordsByUser, uid);
    historyStore.purchaseRecordsByUser[uid].push(mapPurchaseRecord(result.purchaseRecord));
  }
  persistAllLocal();
}

/**
 * @param {string} userId
 */
export async function refreshPurchases(userId) {
  const page = await remoteRepository.getPurchases(userId, PAGE);
  const historyStore = useHistoryStore();
  historyStore.purchaseRecordsByUser[userId] = pageItems(page).map(mapPurchaseRecord);
  persistAllLocal();
}

/**
 * 远端购买道具。
 * @param {object} payload
 * @returns {Promise<object>}
 */
export async function purchaseRemote(payload) {
  const result = await remoteRepository.purchaseProp(payload);
  applyPurchaseResult(result);
  return result;
}
