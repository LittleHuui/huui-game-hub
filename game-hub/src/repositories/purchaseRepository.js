import { mapPurchaseRecord, mapLocalPurchaseToPayload } from '../mappers/purchaseMapper.js';
import { pageItems } from '../mappers/sharedMapper.js';
import { useUserStore } from '../stores/userStore.js';
import { useHistoryStore } from '../stores/historyStore.js';
import { remoteRepository } from './remoteRepository.js';
import * as inventoryRepository from './inventoryRepository.js';
import { ensureUserBucket } from './helpers.js';
import { resolveServerUserId } from './userRepository.js';
import { persistAllLocal } from './localPersistRepository.js';

import { captureUserDataIdentity, mapRecordsToIdentity } from './userDataIdentity.js';
import { mergeRecordsByClientId } from './recordMerge.js';

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
 * 应用购买和库存事实；钱包由完整流水刷新重算，不能用余额摘要覆盖本地待同步流水。
 * @param {object} result
 * @param {{localUserId: string; serverUserId: string}} identity
 * @returns {void}
 */
export function applyPurchaseResult(result, identity) {
  const historyStore = useHistoryStore();
  const uid = identity.localUserId;
  if (result.inventoryItem) {
    inventoryRepository.applyPurchaseInventoryItem(uid, result.inventoryItem);
  }
  if (result.purchaseRecord) {
    ensureUserBucket(historyStore.purchaseRecordsByUser, uid);
    historyStore.purchaseRecordsByUser[uid] = mergeRecordsByClientId(
      historyStore.purchaseRecordsByUser[uid],
      mapRecordsToIdentity([result.purchaseRecord], mapPurchaseRecord, identity)
    );
  }
  persistAllLocal();
}

/**
 * @param {string} userId
 */
export async function refreshPurchases(userId) {
  const identity = captureUserDataIdentity(useUserStore(), userId);
  const page = await remoteRepository.getPurchases(userId, PAGE);
  const historyStore = useHistoryStore();
  const uid = identity.localUserId;
  historyStore.purchaseRecordsByUser[uid] = mergeRecordsByClientId(
    historyStore.purchaseRecordsByUser[uid], mapRecordsToIdentity(pageItems(page), mapPurchaseRecord, identity)
  );
  persistAllLocal();
}

/**
 * 远端购买道具。
 * @param {object} payload
 * @returns {Promise<object>}
 */
export async function purchaseRemote(payload) {
  const identity = captureUserDataIdentity(useUserStore(), payload.userId);
  const result = await remoteRepository.purchaseProp(payload);
  applyPurchaseResult(result, identity);
  return result;
}
